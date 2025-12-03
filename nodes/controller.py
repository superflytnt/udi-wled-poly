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
    
    # Plugin version (major*100 + minor*10 + patch)
    VERSION = 153  # v1.5.3
    
    # Node drivers (status values)
    drivers = [
        {'driver': 'ST', 'value': 1, 'uom': 2},      # Status (On/Off)
        {'driver': 'GV0', 'value': 0, 'uom': 56},    # Device Count
        {'driver': 'GV2', 'value': 0, 'uom': 56},    # Online Count
        {'driver': 'GV3', 'value': 0, 'uom': 56},    # Devices On (powered on)
        {'driver': 'GV4', 'value': 0, 'uom': 56},    # Total LEDs
        {'driver': 'GV1', 'value': 150, 'uom': 25},  # Version (uses NLS)
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
        polyglot.subscribe(polyglot.DISCOVER, self.discover)  # Handle Discover button in PG3
        
        # Set ready flag
        polyglot.ready()
        polyglot.addNode(self)
    
    def start(self):
        """Start the controller node"""
        import datetime
        LOGGER.info(f"Starting WLED Controller: {self.name}")
        
        # Initialize WLED API
        from lib.wled_api import WLEDApi
        self._wled_api = WLEDApi()
        
        # Set online and version
        self.setDriver('ST', 1)
        self.setDriver('GV1', self.VERSION)
        
        # Load configuration and add configured devices
        self._load_config()
        
        # Auto-discover additional WLED devices on startup (this can take a while)
        LOGGER.info("Running auto-discovery for WLED devices...")
        self.discover()
        
        # Rebuild presets and effects with metadata after all devices are loaded
        if self._devices:
            LOGGER.info("Building preset and effect lists from devices...")
            self.rebuild_presets()  # This also calls _rebuild_effects_nls()
        
        # Show startup notice
        timestamp = datetime.datetime.now().strftime("%m/%d %H:%M")
        self.poly.Notices['startup'] = f"WLED Controller started ({timestamp}) - {len(self._devices)} device(s) configured"
        
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
        """Set configuration documentation - displays in PG3 Configuration tab"""
        html = '''
<h2>WLED Polyglot v3 NodeServer</h2>
<p style="color: #888;">Version 1.5.3</p>

<br>

<h3>Manual Configuration</h3>

<p>To manually add WLED devices, add a Custom Parameter below:</p>

<br>

<table border="1" cellpadding="10" style="border-collapse: collapse;">
  <tr><th align="left">Key</th><th align="left">Value</th></tr>
  <tr><td><b>devices</b></td><td>arcade:192.168.1.112,bar:192.168.1.185,kitchen:192.168.1.99</td></tr>
</table>

<br>

<p><i>Format: name1:ip1,name2:ip2,name3:ip3</i></p>

<br><br>

<h3>Auto-Discovery</h3>

<p>Click the <b>Discover</b> button above to automatically find WLED devices on your network.</p>

<br><br>

<hr>

<br>

<table cellpadding="5">
  <tr>
    <td><a href="https://github.com/superflytnt/udi-wled-poly" target="_blank">Source Code</a></td>
    <td style="color: #666;">—</td>
    <td>View and contribute on GitHub</td>
  </tr>
  <tr>
    <td><a href="https://github.com/superflytnt/udi-wled-poly#readme" target="_blank">Documentation</a></td>
    <td style="color: #666;">—</td>
    <td>Setup guide and command reference</td>
  </tr>
  <tr>
    <td><a href="https://github.com/superflytnt/udi-wled-poly/issues" target="_blank">Report Issue</a></td>
    <td style="color: #666;">—</td>
    <td>Bug reports and feature requests</td>
  </tr>
  <tr>
    <td><a href="https://kno.wled.ge/" target="_blank">WLED Docs</a></td>
    <td style="color: #666;">—</td>
    <td>Official WLED documentation</td>
  </tr>
</table>
'''
        self.poly.setCustomParamsDoc(html)
    
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
        
        # Update controller stats after polling all devices
        self.update_stats()
    
    def update_stats(self):
        """
        Update controller statistics from all devices.
        Called after polling and when device state changes.
        """
        online_count = 0
        devices_on = 0
        total_leds = 0
        
        for address, device_info in self._devices.items():
            node = device_info.get('node')
            if node and node._device:
                if node._device.online:
                    online_count += 1
                    if node._device.state and node._device.state.on:
                        devices_on += 1
                # Count LEDs from device info
                if node._device.info and node._device.info.led_count:
                    total_leds += node._device.info.led_count
        
        # Update controller stats
        self.setDriver('GV2', online_count)
        self.setDriver('GV3', devices_on)
        self.setDriver('GV4', total_leds)
    
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
        
        # Clear old discovery notice
        self.poly.Notices.clear()
        
        try:
            devices = self._wled_api.discover(timeout=10.0)
            
            if devices:
                LOGGER.info(f"Discovered {len(devices)} WLED device(s)")
                
                # Build list of discovered devices for notice
                device_names = []
                new_devices = 0
                
                for device in devices:
                    ip = device.get('ip')
                    name = device.get('name', '').replace('.local', '').replace('.', '_')
                    
                    if not name:
                        name = ip.replace('.', '_')
                    
                    LOGGER.info(f"Found WLED device: {name} at {ip}")
                    
                    # Check if this is a new device
                    address = name.lower().replace(' ', '_').replace('.', '_')
                    address = ''.join(c for c in address if c.isalnum() or c == '_')[:14]
                    
                    if address not in self._devices:
                        new_devices += 1
                    
                    device_names.append(f"{name} ({ip})")
                    self._add_wled_device(name, ip)
                
                # Show notice with results
                import datetime
                timestamp = datetime.datetime.now().strftime("%m/%d %H:%M")
                
                # Format device list nicely
                device_list = ', '.join(device_names)
                
                if new_devices > 0:
                    self.poly.Notices['discovery'] = f"Discovery complete ({timestamp}) - Found {len(devices)} device(s), {new_devices} new: {device_list}"
                else:
                    self.poly.Notices['discovery'] = f"Discovery complete ({timestamp}) - {len(devices)} device(s) already configured"
            else:
                LOGGER.info("No WLED devices found via discovery")
                LOGGER.info("Try adding devices manually via configuration")
                import datetime
                timestamp = datetime.datetime.now().strftime("%m/%d %H:%M")
                self.poly.Notices['discovery'] = f"Discovery complete ({timestamp}) - No WLED devices found. Add devices manually in Configuration."
                
        except Exception as e:
            LOGGER.error(f"Discovery failed: {e}")
            import datetime
            timestamp = datetime.datetime.now().strftime("%m/%d %H:%M")
            self.poly.Notices['discovery_error'] = f"Discovery failed ({timestamp}) - {e}"
    
    def rebuild_presets(self, command=None):
        """
        Fetch and log presets from all WLED devices.
        
        Each device has its own presets - this command logs them for reference.
        The ISY dropdown shows generic preset IDs (1-250) since each device
        has different preset names for the same ID.
        """
        LOGGER.info("Fetching presets from all WLED devices...")
        LOGGER.info("Note: Each device has unique presets. Check WLED web UI for preset names.")
        
        # Have each device fetch and log its own presets
        for address, device_info in self._devices.items():
            node = device_info.get('node')
            if node:
                try:
                    node._fetch_presets()
                    if node._available_presets:
                        LOGGER.info(f"Device {address} presets:")
                        for preset_id in sorted(node._available_presets.keys()):
                            LOGGER.info(f"  {preset_id}: {node._available_presets[preset_id]}")
                except Exception as e:
                    LOGGER.warning(f"Failed to get presets from {address}: {e}")
        
        # Also rebuild effects with metadata
        self._rebuild_effects_nls()
    
    def _rebuild_effects_nls(self):
        """
        Rebuild effects NLS with metadata (1D/2D, palette, volume, frequency).
        
        Fetches effect metadata from the first available device and updates
        the NLS file with effect types.
        """
        LOGGER.info("Rebuilding effects with metadata...")
        
        # Get metadata from first available device
        effect_metadata = None
        for address, device_info in self._devices.items():
            node = device_info.get('node')
            if node and hasattr(node, '_device') and node._device:
                try:
                    effect_metadata = node._device.get_effect_metadata()
                    if effect_metadata:
                        LOGGER.info(f"Got effect metadata from {address}")
                        break
                except Exception as e:
                    LOGGER.warning(f"Failed to get effect metadata from {address}: {e}")
        
        if not effect_metadata:
            LOGGER.warning("Could not get effect metadata from any device")
            return
        
        self._update_effect_nls(effect_metadata)
    
    def _update_effect_nls(self, effect_metadata: Dict[int, Dict]):
        """
        Update NLS file with effect names and metadata flags.
        
        Args:
            effect_metadata: Dict mapping effect ID to metadata dict
        """
        import os
        
        try:
            profile_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'profile', 'nls')
            nls_file = os.path.join(profile_dir, 'en_us.txt')
            
            # Read existing NLS content
            existing_lines = []
            if os.path.exists(nls_file):
                with open(nls_file, 'r') as f:
                    existing_lines = f.readlines()
            
            # Remove old effect entries (keep only non-EFFECT lines)
            filtered_lines = [line for line in existing_lines 
                             if not line.startswith('EFFECT-')]
            # Also remove the effect header
            filtered_lines = [line for line in filtered_lines 
                             if 'Effect Names' not in line and 'WLED effects' not in line]
            
            # Build new effect entries with metadata
            effect_lines = ["\n# Effect Names (WLED effects with type indicators)\n"]
            for effect_id in sorted(effect_metadata.keys()):
                meta = effect_metadata[effect_id]
                name = meta.get('name', f'Effect {effect_id}')
                
                # Build type indicators
                indicators = []
                if meta.get('is_2d'):
                    indicators.append('2D')
                else:
                    indicators.append('1D')
                
                if meta.get('uses_palette'):
                    indicators.append('Pal')
                
                if meta.get('volume'):
                    indicators.append('Vol')
                
                if meta.get('frequency'):
                    indicators.append('Freq')
                
                # Format: "ID: Name (1D, Pal)" or "ID: Name (2D, Vol, Freq)"
                if indicators:
                    indicator_str = ', '.join(indicators)
                    effect_lines.append(f"EFFECT-{effect_id} = {effect_id}: {name} ({indicator_str})\n")
                else:
                    effect_lines.append(f"EFFECT-{effect_id} = {effect_id}: {name}\n")
            
            # Write updated NLS file
            with open(nls_file, 'w') as f:
                f.writelines(filtered_lines)
                f.writelines(effect_lines)
            
            LOGGER.info(f"Updated NLS file with {len(effect_metadata)} effect names and metadata")
            
        except Exception as e:
            LOGGER.error(f"Failed to update effect NLS: {e}")
    
    
    def cmd_all_on(self, command=None):
        """Turn all WLED devices on, optionally with brightness level"""
        # Check for brightness parameter (from scene or DON with level)
        brightness = None
        if command and 'value' in command:
            brightness = int(command['value'])
            LOGGER.info(f"Turning ALL devices ON at {brightness}%")
        else:
            LOGGER.info("Turning ALL devices ON")
        
        for address, device_info in self._devices.items():
            node = device_info.get('node')
            if node and node._device:
                try:
                    node._device.set_power(True)
                    if brightness is not None:
                        bri_val = int((brightness / 100) * 255)
                        node._device.set_brightness(bri_val)
                except Exception as e:
                    LOGGER.error(f"Failed to turn on {address}: {e}")
        
        # Update all device statuses and controller stats
        self._poll_devices()
    
    def cmd_all_brighten(self, command=None):
        """Brighten all WLED devices by ~10%"""
        LOGGER.info("Brightening ALL devices")
        
        for address, device_info in self._devices.items():
            node = device_info.get('node')
            if node and node._device and node._device.state:
                try:
                    current = node._device.state.brightness
                    new_bri = min(255, current + 25)  # +10% roughly
                    node._device.set_brightness(new_bri)
                except Exception as e:
                    LOGGER.error(f"Failed to brighten {address}: {e}")
        
        # Update all device statuses
        self._poll_devices()
    
    def cmd_all_dim(self, command=None):
        """Dim all WLED devices by ~10%"""
        LOGGER.info("Dimming ALL devices")
        
        for address, device_info in self._devices.items():
            node = device_info.get('node')
            if node and node._device and node._device.state:
                try:
                    current = node._device.state.brightness
                    new_bri = max(0, current - 25)  # -10% roughly
                    node._device.set_brightness(new_bri)
                except Exception as e:
                    LOGGER.error(f"Failed to dim {address}: {e}")
        
        # Update all device statuses
        self._poll_devices()
    
    def cmd_all_off(self, command=None):
        """Turn all WLED devices off"""
        LOGGER.info("Turning ALL devices OFF")
        
        for address, device_info in self._devices.items():
            node = device_info.get('node')
            if node and node._device:
                try:
                    node._device.set_power(False)
                except Exception as e:
                    LOGGER.error(f"Failed to turn off {address}: {e}")
        
        # Update all device statuses and controller stats
        self._poll_devices()
    
    def cmd_set_all_brightness(self, command):
        """Set brightness on all WLED devices"""
        brightness = int(command.get('value', 100))
        LOGGER.info(f"Setting ALL devices brightness to {brightness}%")
        
        # Convert percentage to 0-255
        bri_val = int((brightness / 100) * 255)
        
        for address, device_info in self._devices.items():
            node = device_info.get('node')
            if node and node._device:
                try:
                    node._device.set_brightness(bri_val)
                except Exception as e:
                    LOGGER.error(f"Failed to set brightness on {address}: {e}")
        
        # Update all device statuses
        self._poll_devices()
    
    def cmd_set_all_effect(self, command):
        """Set effect on all WLED devices"""
        effect_id = int(command.get('value', 0))
        LOGGER.info(f"Setting ALL devices effect to {effect_id}")
        
        for address, device_info in self._devices.items():
            node = device_info.get('node')
            if node and node._device:
                try:
                    node._device.set_effect(effect_id)
                except Exception as e:
                    LOGGER.error(f"Failed to set effect on {address}: {e}")
        
        # Update all device statuses
        self._poll_devices()
    
    # Command handlers
    commands = {
        'DISCOVER': discover,
        'QUERY': query,
        'REBUILD_PRESETS': rebuild_presets,
        'ALL_ON': cmd_all_on,
        'ALL_OFF': cmd_all_off,
        'SET_ALL_BRI': cmd_set_all_brightness,
        'SET_ALL_EFFECT': cmd_set_all_effect,
        # Scene support: DON/DOF/DFON/DFOF/BRT/DIM for scene responder functionality
        'DON': cmd_all_on,
        'DOF': cmd_all_off,
        'DFON': cmd_all_on,
        'DFOF': cmd_all_off,
        'BRT': cmd_all_brighten,
        'DIM': cmd_all_dim,
    }

