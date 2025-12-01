"""
WLED Controller Node

Main controller node that manages device discovery, configuration,
and creates/removes WLED device nodes.
"""

import udi_interface
import logging
from typing import Optional, Dict, Any

LOGGER = udi_interface.LOGGER
Custom = udi_interface.Custom


class Controller(udi_interface.Node):
    """
    WLED Controller Node
    
    Manages multiple WLED devices from a single nodeserver.
    Handles device discovery (mDNS) and manual configuration.
    """
    
    id = 'controller'
    
    # Node drivers (status values)
    drivers = [
        {'driver': 'ST', 'value': 1, 'uom': 2},      # Status (On/Off)
        {'driver': 'GV0', 'value': 0, 'uom': 56},    # Device Count
    ]
    
    def __init__(self, polyglot, primary, address, name):
        """
        Initialize the controller node.
        
        Args:
            polyglot: Polyglot interface
            primary: Primary node address (self for controller)
            address: Node address
            name: Node name
        """
        super().__init__(polyglot, primary, address, name)
        
        self.poly = polyglot
        self.name = name
        self.primary = primary
        self.address = address
        
        # Managed devices
        self._devices: Dict[str, Any] = {}
        self._wled_api = None
        
        # Configuration
        self._config_done = False
        self._custom_params = Custom(polyglot, 'customparams')
        
        # Subscribe to events
        polyglot.subscribe(polyglot.START, self.start, address)
        polyglot.subscribe(polyglot.POLL, self.poll)
        polyglot.subscribe(polyglot.STOP, self.stop)
        polyglot.subscribe(polyglot.CUSTOMPARAMS, self.parameter_handler)
        polyglot.subscribe(polyglot.ADDNODEDONE, self.node_added)
        
        # Set ready flag
        polyglot.ready()
        polyglot.addNode(self)
    
    def start(self):
        """Start the controller node"""
        LOGGER.info(f"Starting WLED Controller: {self.name}")
        
        # Initialize WLED API
        from lib.wled_api import WLEDApi
        self._wled_api = WLEDApi()
        
        # Set online
        self.setDriver('ST', 1)
        
        # Load configuration and add configured devices
        self._load_config()
        
        # Auto-discover WLED devices on startup
        LOGGER.info("Running auto-discovery for WLED devices...")
        self.discover()
        
        # Rebuild presets from all devices
        if self._devices:
            LOGGER.info("Building preset list from devices...")
            self.rebuild_presets()
        
        LOGGER.info("WLED Controller started successfully")
    
    def _load_config(self):
        """Load configuration and add configured devices"""
        LOGGER.info("Loading WLED configuration...")
        
        # Get custom parameters
        params = self._custom_params
        
        # Look for 'devices' parameter
        # Format: "name1:192.168.1.100,name2:192.168.1.101"
        devices_str = params.get('devices', '')
        
        if devices_str:
            LOGGER.info(f"Found device configuration: {devices_str}")
            self._parse_devices(devices_str)
        else:
            LOGGER.info("No devices configured. Use Discover or add manually.")
            # Set help text for configuration
            self._set_config_docs()
        
        self._config_done = True
    
    def _set_config_docs(self):
        """Set configuration documentation"""
        config = {
            'devices': {
                'name': 'WLED Devices',
                'desc': 'List of WLED devices in format: name1:ip1,name2:ip2',
                'default': '',
                'isRequired': False
            }
        }
        self.poly.setCustomParamsDoc(config)
    
    def _parse_devices(self, devices_str: str):
        """
        Parse device configuration string and add devices.
        
        Args:
            devices_str: Comma-separated list of name:ip pairs
        """
        if not devices_str:
            return
        
        for device_entry in devices_str.split(','):
            device_entry = device_entry.strip()
            if not device_entry:
                continue
            
            if ':' in device_entry:
                parts = device_entry.split(':')
                name = parts[0].strip()
                ip = parts[1].strip()
                
                if name and ip:
                    self._add_wled_device(name, ip)
            else:
                # Just an IP address, use IP as name
                ip = device_entry.strip()
                name = ip.replace('.', '_')
                self._add_wled_device(name, ip)
    
    def _add_wled_device(self, name: str, ip: str, port: int = 80):
        """
        Add a WLED device node.
        
        Args:
            name: Device name
            ip: IP address
            port: HTTP port (default 80)
        """
        # Create node address from name (max 14 chars, lowercase, alphanumeric + _)
        address = name.lower().replace(' ', '_').replace('.', '_')
        address = ''.join(c for c in address if c.isalnum() or c == '_')[:14]
        
        # Check if already exists
        if address in self._devices:
            LOGGER.warning(f"Device {name} ({address}) already exists")
            return
        
        LOGGER.info(f"Adding WLED device: {name} at {ip}:{port} (address: {address})")
        
        try:
            # Import here to avoid circular imports
            from nodes.wled_device import WLEDDevice
            
            # Create the device node
            node = WLEDDevice(
                self.poly,
                self.address,
                address,
                name,
                ip,
                port,
                self._wled_api
            )
            
            self._devices[address] = {
                'name': name,
                'ip': ip,
                'port': port,
                'node': node
            }
            
            # Update device count
            self._update_device_count()
            
        except Exception as e:
            LOGGER.error(f"Failed to add device {name}: {e}")
    
    def _remove_wled_device(self, address: str):
        """
        Remove a WLED device node.
        
        Args:
            address: Node address
        """
        if address in self._devices:
            device = self._devices.pop(address)
            self.poly.delNode(address)
            LOGGER.info(f"Removed WLED device: {device['name']}")
            self._update_device_count()
    
    def _update_device_count(self):
        """Update device count status"""
        count = len(self._devices)
        self.setDriver('GV0', count)
        LOGGER.debug(f"Device count: {count}")
    
    def parameter_handler(self, params):
        """Handle configuration parameter changes"""
        LOGGER.info("Configuration parameters updated")
        
        # Update custom params
        self._custom_params.load(params)
        
        # Reload configuration if already started
        if self._config_done:
            self._load_config()
    
    def node_added(self, node):
        """Called when a node is added"""
        LOGGER.debug(f"Node added: {node.get('address')}")
    
    def poll(self, polltype):
        """
        Poll all devices for status updates.
        
        Args:
            polltype: 'shortPoll' or 'longPoll'
        """
        if polltype == 'shortPoll':
            LOGGER.debug("Short poll - updating device status")
            self._poll_devices()
        elif polltype == 'longPoll':
            LOGGER.debug("Long poll - full device sync")
            self._poll_devices(full_sync=True)
    
    def _poll_devices(self, full_sync: bool = False):
        """
        Poll all devices for status.
        
        Args:
            full_sync: If True, do a full sync including effects/palettes
        """
        for address, device_info in self._devices.items():
            node = device_info.get('node')
            if node:
                try:
                    node.update_status(full_sync=full_sync)
                except Exception as e:
                    LOGGER.error(f"Failed to poll device {address}: {e}")
    
    def stop(self):
        """Stop the controller node"""
        LOGGER.info("Stopping WLED Controller...")
        LOGGER.info("WLED Controller stopped")
    
    def query(self):
        """Query all devices"""
        LOGGER.info("Query all devices")
        self._poll_devices(full_sync=True)
        self.reportDrivers()
    
    def discover(self, command=None):
        """
        Discover WLED devices on the network.
        
        This scans the local network for WLED devices.
        """
        LOGGER.info("Starting WLED device discovery...")
        
        try:
            devices = self._wled_api.discover(timeout=10.0)
            
            if devices:
                LOGGER.info(f"Discovered {len(devices)} WLED device(s)")
                
                for device in devices:
                    ip = device.get('ip')
                    name = device.get('name', '').replace('.local', '').replace('.', '_')
                    
                    if not name:
                        name = ip.replace('.', '_')
                    
                    LOGGER.info(f"Found WLED device: {name} at {ip}")
                    self._add_wled_device(name, ip)
            else:
                LOGGER.info("No WLED devices found via mDNS discovery")
                LOGGER.info("Try adding devices manually via configuration")
                
        except Exception as e:
            LOGGER.error(f"Discovery failed: {e}")
    
    def rebuild_presets(self, command=None):
        """
        Rebuild presets from all WLED devices.
        
        Fetches presets from each device and updates the NLS file
        with preset names for better ISY display.
        """
        LOGGER.info("Rebuilding presets from all WLED devices...")
        
        all_presets = {}
        
        # Collect presets from all devices
        for address, device_info in self._devices.items():
            node = device_info.get('node')
            if node and hasattr(node, '_device') and node._device:
                try:
                    presets = node._device.get_presets()
                    if presets:
                        LOGGER.info(f"Device {address}: Found {len(presets)} presets")
                        # Merge presets (using highest ID as unique)
                        for preset_id, preset_name in presets.items():
                            if preset_id not in all_presets:
                                all_presets[preset_id] = preset_name
                except Exception as e:
                    LOGGER.warning(f"Failed to get presets from {address}: {e}")
        
        if all_presets:
            LOGGER.info(f"Total unique presets found: {len(all_presets)}")
            self._update_preset_nls(all_presets)
            
            # Store presets for each device node
            for address, device_info in self._devices.items():
                node = device_info.get('node')
                if node:
                    node._available_presets = all_presets
        else:
            LOGGER.warning("No presets found on any device")
    
    def _update_preset_nls(self, presets: Dict[int, str]):
        """
        Update NLS file with preset names.
        
        Args:
            presets: Dict mapping preset ID to preset name
        """
        import os
        
        try:
            # Get the profile directory
            profile_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'profile', 'nls')
            nls_file = os.path.join(profile_dir, 'en_us.txt')
            
            # Read existing NLS content
            existing_lines = []
            if os.path.exists(nls_file):
                with open(nls_file, 'r') as f:
                    existing_lines = f.readlines()
            
            # Remove old preset entries
            filtered_lines = [line for line in existing_lines if not line.startswith('PRESET_')]
            
            # Add new preset entries
            preset_lines = ["\n# WLED Presets (auto-generated)\n"]
            for preset_id in sorted(presets.keys()):
                preset_name = presets[preset_id]
                # Sanitize preset name for NLS
                safe_name = preset_name.replace('"', "'").replace('\n', ' ')
                preset_lines.append(f"PRESET_{preset_id} = {safe_name}\n")
            
            # Write updated NLS file
            with open(nls_file, 'w') as f:
                f.writelines(filtered_lines)
                f.writelines(preset_lines)
            
            LOGGER.info(f"Updated NLS file with {len(presets)} preset names")
            
            # Reload profile to apply changes
            LOGGER.info("Reloading profile to apply preset changes...")
            self.poly.updateProfile()
            
        except Exception as e:
            LOGGER.error(f"Failed to update preset NLS: {e}")
    
    # Command handlers
    commands = {
        'DISCOVER': discover,
        'QUERY': query,
        'REBUILD_PRESETS': rebuild_presets,
    }

