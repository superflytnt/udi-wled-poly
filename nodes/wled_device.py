"""
WLED Device Node

Represents a single WLED controller with full control capabilities
including brightness, effects, palettes, presets, and color.
"""

import udi_interface
import logging
from typing import Optional, Any

LOGGER = udi_interface.LOGGER


class WLEDDevice(udi_interface.Node):
    """
    WLED Device Node
    
    Provides full control of a single WLED device.
    
    Status:
        ST (Power): On/Off state
        GV0 (Brightness): 0-100%
        GV1 (Effect): Current effect ID
        GV2 (Palette): Current palette ID
        GV3 (Preset): Current preset ID
        GV4 (Red): Red component 0-255
        GV5 (Green): Green component 0-255
        GV6 (Blue): Blue component 0-255
        GV7 (Online): Connection status
    """
    
    id = 'wled_device'
    
    # Node drivers (status values)
    drivers = [
        {'driver': 'ST', 'value': 0, 'uom': 2},      # Power (On/Off)
        {'driver': 'GV0', 'value': 0, 'uom': 51},    # Brightness (%)
        {'driver': 'GV1', 'value': 0, 'uom': 25},    # Effect
        {'driver': 'GV2', 'value': 0, 'uom': 25},    # Palette
        {'driver': 'GV3', 'value': 0, 'uom': 25},    # Preset
        {'driver': 'GV4', 'value': 0, 'uom': 56},    # Red
        {'driver': 'GV5', 'value': 0, 'uom': 56},    # Green
        {'driver': 'GV6', 'value': 0, 'uom': 56},    # Blue
        {'driver': 'GV7', 'value': 0, 'uom': 2},     # Online
    ]
    
    def __init__(self, polyglot, primary, address, name, ip: str, port: int = 80, wled_api=None):
        """
        Initialize the WLED device node.
        
        Args:
            polyglot: Polyglot interface
            primary: Primary node address (controller)
            address: Node address
            name: Device name
            ip: Device IP address
            port: HTTP port (default 80)
            wled_api: Shared WLEDApi instance
        """
        super().__init__(polyglot, primary, address, name)
        
        self.poly = polyglot
        self.name = name
        self.primary = primary
        self.address = address
        
        # Device connection info
        self._ip = ip
        self._port = port
        
        # WLED API
        self._wled_api = wled_api
        self._device = None
        
        # Presets cache
        self._available_presets = {}
        
        # Initialize device connection
        self._init_device()
        
        # Add node to polyglot
        polyglot.addNode(self)
        
        # Initial status update and preset fetch
        self.update_status(full_sync=True)
        self._fetch_presets()
    
    def _init_device(self):
        """Initialize WLED device connection"""
        from lib.wled_api import WLEDDevice as WLEDApiDevice
        self._device = WLEDApiDevice(self._ip, self._port)
    
    def _fetch_presets(self):
        """Fetch available presets from device"""
        if self._device:
            try:
                presets = self._device.get_presets()
                if presets:
                    self._available_presets = presets
                    LOGGER.info(f"{self.name}: Loaded {len(presets)} presets")
            except Exception as e:
                LOGGER.warning(f"{self.name}: Failed to fetch presets - {e}")
    
    def update_status(self, full_sync: bool = False):
        """
        Update node status from device.
        
        Args:
            full_sync: If True, fetch all data including effects/palettes
        """
        if not self._device:
            LOGGER.warning(f"No device connection for {self.name}")
            return
        
        try:
            if full_sync:
                # Get all data
                success = self._device.get_all()
            else:
                # Just get state
                self._device.get_state()
                success = self._device.online
            
            # Update online status
            self.setDriver('GV7', 1 if self._device.online else 0)
            
            if self._device.online and self._device.state:
                state = self._device.state
                
                # Update power
                self.setDriver('ST', 1 if state.on else 0)
                
                # Update brightness (convert 0-255 to 0-100%)
                brightness_pct = int((state.brightness / 255) * 100)
                self.setDriver('GV0', brightness_pct)
                
                # Update effect
                self.setDriver('GV1', state.effect)
                
                # Update palette
                self.setDriver('GV2', state.palette)
                
                # Update preset
                preset = state.preset if state.preset >= 0 else 0
                self.setDriver('GV3', preset)
                
                # Update color
                color = state.primary_color
                if len(color) >= 3:
                    self.setDriver('GV4', color[0])  # Red
                    self.setDriver('GV5', color[1])  # Green
                    self.setDriver('GV6', color[2])  # Blue
                
                LOGGER.debug(f"{self.name}: Power={state.on}, Brightness={brightness_pct}%, Effect={state.effect}")
            
        except Exception as e:
            LOGGER.error(f"Failed to update status for {self.name}: {e}")
            self.setDriver('GV7', 0)  # Mark offline
    
    def query(self, command=None):
        """Query device status"""
        LOGGER.info(f"Query: {self.name}")
        self.update_status(full_sync=True)
        self.reportDrivers()
    
    def cmd_on(self, command=None):
        """Turn on the device"""
        LOGGER.info(f"Turn On: {self.name}")
        
        if self._device:
            # Check for brightness parameter
            brightness = None
            if command and 'value' in command:
                brightness = int(command['value'])
            
            self._device.set_power(True)
            if brightness is not None:
                # Convert percentage to 0-255
                bri_val = int((brightness / 100) * 255)
                self._device.set_brightness(bri_val)
            self.update_status()
    
    def cmd_off(self, command=None):
        """Turn off the device"""
        LOGGER.info(f"Turn Off: {self.name}")
        
        if self._device:
            self._device.set_power(False)
            self.update_status()
    
    def cmd_fast_on(self, command=None):
        """Fast on (instant, no transition)"""
        LOGGER.info(f"Fast On: {self.name}")
        
        if self._device:
            self._device.set_state(on=True, transition=0)
            self.update_status()
    
    def cmd_fast_off(self, command=None):
        """Fast off (instant, no transition)"""
        LOGGER.info(f"Fast Off: {self.name}")
        
        if self._device:
            self._device.set_state(on=False, transition=0)
            self.update_status()
    
    def cmd_brighten(self, command=None):
        """Brighten by 10%"""
        LOGGER.info(f"Brighten: {self.name}")
        
        if self._device and self._device.state:
            current = self._device.state.brightness
            new_bri = min(255, current + 25)  # +10% roughly
            self._device.set_brightness(new_bri)
            self.update_status()
    
    def cmd_dim(self, command=None):
        """Dim by 10%"""
        LOGGER.info(f"Dim: {self.name}")
        
        if self._device and self._device.state:
            current = self._device.state.brightness
            new_bri = max(0, current - 25)  # -10% roughly
            self._device.set_brightness(new_bri)
            self.update_status()
    
    def cmd_set_brightness(self, command):
        """Set brightness percentage"""
        brightness = int(command.get('value', 100))
        LOGGER.info(f"Set Brightness: {self.name} to {brightness}%")
        
        if self._device:
            # Convert percentage to 0-255
            bri_val = int((brightness / 100) * 255)
            self._device.set_brightness(bri_val)
            self.update_status()
    
    def cmd_set_effect(self, command):
        """Set effect by ID"""
        effect_id = int(command.get('value', 0))
        LOGGER.info(f"Set Effect: {self.name} to {effect_id}")
        
        if self._device:
            self._device.set_effect(effect_id)
            self.update_status()
    
    def cmd_set_palette(self, command):
        """Set palette by ID"""
        palette_id = int(command.get('value', 0))
        LOGGER.info(f"Set Palette: {self.name} to {palette_id}")
        
        if self._device:
            self._device.set_palette(palette_id)
            self.update_status()
    
    def cmd_set_preset(self, command):
        """Load a preset"""
        preset_id = int(command.get('value', 1))
        LOGGER.info(f"Load Preset: {self.name} preset {preset_id}")
        
        if self._device:
            self._device.set_preset(preset_id)
            self.update_status()
    
    def cmd_set_color(self, command):
        """Set RGB color"""
        r = int(command.get('R.uom56', command.get('R', 255)))
        g = int(command.get('G.uom56', command.get('G', 255)))
        b = int(command.get('B.uom56', command.get('B', 255)))
        
        LOGGER.info(f"Set Color: {self.name} to RGB({r},{g},{b})")
        
        if self._device:
            self._device.set_color(r, g, b)
            self.update_status()
    
    def cmd_set_speed(self, command):
        """Set effect speed"""
        speed = int(command.get('value', 128))
        LOGGER.info(f"Set Speed: {self.name} to {speed}%")
        
        if self._device:
            # Convert percentage to 0-255 and set via effect
            speed_val = int((speed / 100) * 255)
            if self._device.state:
                self._device.set_effect(self._device.state.effect, speed=speed_val)
            self.update_status()
    
    def cmd_set_intensity(self, command):
        """Set effect intensity"""
        intensity = int(command.get('value', 128))
        LOGGER.info(f"Set Intensity: {self.name} to {intensity}%")
        
        if self._device:
            # Convert percentage to 0-255 and set via effect
            intensity_val = int((intensity / 100) * 255)
            if self._device.state:
                self._device.set_effect(self._device.state.effect, intensity=intensity_val)
            self.update_status()
    
    # Command handlers
    commands = {
        'DON': cmd_on,
        'DOF': cmd_off,
        'DFON': cmd_fast_on,
        'DFOF': cmd_fast_off,
        'BRT': cmd_brighten,
        'DIM': cmd_dim,
        'SET_BRI': cmd_set_brightness,
        'SET_EFFECT': cmd_set_effect,
        'SET_PALETTE': cmd_set_palette,
        'SET_PRESET': cmd_set_preset,
        'SET_COLOR': cmd_set_color,
        'SET_SPEED': cmd_set_speed,
        'SET_INTENSITY': cmd_set_intensity,
        'QUERY': query,
    }
