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
    
    Status (Partially combined for cleaner UI):
        ST (Power): On/Off state
        GV0 (Brightness): 0-100%
        GV1 (Effect): Current effect ID
        GV2 (Palette): Current palette ID
        GV3 (Preset): Current preset ID
        GV4 (Red): Red component 0-255
        GV5 (Green): Green component 0-255
        GV6 (Blue): Blue component 0-255
        GV7 (Online): Connection status
        GV8 (Speed): Effect speed 0-100%
        GV9 (Intensity): Effect intensity 0-100%
        GV10 (Transition): Transition time in 100ms units
        GV11 (Live): Live/UDP override active
        GV12 (Nightlight): 0=off, 1-255=duration in minutes
        GV13 (Sync): 0=off, 1=send, 2=recv, 3=both
    """
    
    id = 'wled_device'
    
    # Node drivers (status values) - Sync and Nightlight combined, RGB/Speed kept separate for readability
    drivers = [
        {'driver': 'ST', 'value': 0, 'uom': 2},       # Power (On/Off)
        {'driver': 'GV0', 'value': 0, 'uom': 51},     # Brightness (%)
        {'driver': 'GV1', 'value': 0, 'uom': 25},     # Effect
        {'driver': 'GV2', 'value': 0, 'uom': 25},     # Palette
        {'driver': 'GV3', 'value': 0, 'uom': 25},     # Preset
        {'driver': 'GV4', 'value': 0, 'uom': 56},     # Red
        {'driver': 'GV5', 'value': 0, 'uom': 56},     # Green
        {'driver': 'GV6', 'value': 0, 'uom': 56},     # Blue
        {'driver': 'GV7', 'value': 0, 'uom': 2},      # Online
        {'driver': 'GV8', 'value': 50, 'uom': 51},    # Speed (%)
        {'driver': 'GV9', 'value': 50, 'uom': 51},    # Intensity (%)
        {'driver': 'GV10', 'value': 7, 'uom': 56},    # Transition (100ms units)
        {'driver': 'GV11', 'value': 0, 'uom': 2},     # Live override
        {'driver': 'GV12', 'value': 0, 'uom': 25},    # Nightlight (0=off, else duration) - uses NLS
        {'driver': 'GV13', 'value': 0, 'uom': 25},    # Sync (0=off, 1=send, 2=recv, 3=both)
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
                
                # Update color (separate RGB)
                color = state.primary_color
                if len(color) >= 3:
                    self.setDriver('GV4', color[0])  # Red
                    self.setDriver('GV5', color[1])  # Green
                    self.setDriver('GV6', color[2])  # Blue
                
                # Update speed and intensity (from main segment)
                speed_pct = 50
                intensity_pct = 50
                if state.segments and len(state.segments) > 0:
                    seg = state.segments[state.main_segment] if state.main_segment < len(state.segments) else state.segments[0]
                    speed_pct = int((seg.speed / 255) * 100)
                    intensity_pct = int((seg.intensity / 255) * 100)
                    self.setDriver('GV8', speed_pct)
                    self.setDriver('GV9', intensity_pct)
                
                # Update transition time
                self.setDriver('GV10', state.transition)
                
                # Update live override status
                self.setDriver('GV11', 1 if state.live else 0)
                
                # Update nightlight (combined: 0=off, else duration in minutes)
                if state.nightlight_on:
                    self.setDriver('GV12', state.nightlight_duration)
                else:
                    self.setDriver('GV12', 0)
                
                # Update sync (combined: 0=off, 1=send, 2=recv, 3=both)
                sync_val = 0
                if state.sync_send and state.sync_receive:
                    sync_val = 3  # Both
                elif state.sync_send:
                    sync_val = 1  # Send only
                elif state.sync_receive:
                    sync_val = 2  # Receive only
                self.setDriver('GV13', sync_val)
                
                LOGGER.debug(f"{self.name}: Power={state.on}, Brightness={brightness_pct}%, Effect={state.effect}, Speed={speed_pct}%")
            
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
        """Load a preset - updates all status values after loading"""
        import time
        preset_id = int(command.get('value', 1))
        LOGGER.info(f"Load Preset: {self.name} preset {preset_id}")
        
        if self._device:
            self._device.set_preset(preset_id)
            # Wait for WLED to apply the preset before reading status
            time.sleep(0.3)
            self.update_status(full_sync=True)  # Full sync to get all values
    
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
    
    def cmd_set_transition(self, command):
        """Set transition time (in 100ms units, 0-255)"""
        transition = int(command.get('value', 7))
        LOGGER.info(f"Set Transition: {self.name} to {transition} (= {transition * 100}ms)")
        
        if self._device:
            self._device.set_state(transition=transition)
            self.update_status()
    
    def cmd_set_live(self, command):
        """Enable/disable live override (external control like Hyperion)"""
        value = int(command.get('value', 0))
        live = value > 0
        LOGGER.info(f"Set Live Override: {self.name} to {live}")
        
        if self._device:
            # lor = live override (0 = off, 1 = until live off, 2 = until reboot)
            self._device.set_state(lor=1 if live else 0)
            self.update_status()
    
    def cmd_nightlight_on(self, command):
        """Set nightlight timer - gradually dims to off. 0 = disable timer."""
        duration = int(command.get('value', 60)) if command and 'value' in command else 60
        
        if duration == 0:
            # Treat 0 as "disable nightlight"
            LOGGER.info(f"Nightlight disabled: {self.name}")
            if self._device:
                self._device.set_state(nl={"on": False})
        else:
            LOGGER.info(f"Nightlight: {self.name} for {duration} minutes")
            if self._device:
                # Turn device ON if not already, then start nightlight timer
                # nl = nightlight settings (mode 1 = fade to tbri over dur minutes)
                self._device.set_state(on=True, nl={"on": True, "dur": duration, "mode": 1, "tbri": 0})
        
        self.update_status()
    
    def cmd_nightlight_off(self, command):
        """Disable nightlight mode"""
        LOGGER.info(f"Nightlight Off: {self.name}")
        
        if self._device:
            self._device.set_state(nl={"on": False})
            self.update_status()
    
    def cmd_sync_send(self, command):
        """Enable/disable UDP sync send"""
        value = int(command.get('value', 0))
        send = value > 0
        LOGGER.info(f"Set Sync Send: {self.name} to {send}")
        
        if self._device:
            self._device.set_state(udpn={"send": send})
            self.update_status()
    
    def cmd_sync_receive(self, command):
        """Enable/disable UDP sync receive"""
        value = int(command.get('value', 0))
        recv = value > 0
        LOGGER.info(f"Set Sync Receive: {self.name} to {recv}")
        
        if self._device:
            self._device.set_state(udpn={"recv": recv})
            self.update_status()
    
    def cmd_save_preset(self, command):
        """Save current state to a preset slot"""
        preset_id = int(command.get('value', 1))
        LOGGER.info(f"Save Preset: {self.name} to slot {preset_id}")
        
        if self._device:
            # psave = preset save (ID to save to)
            # The preset will be saved with current state
            self._device.set_state(psave=preset_id)
            self.update_status()
    
    def cmd_playlist_on(self, command):
        """Start a playlist"""
        playlist_id = int(command.get('value', 0)) if command and 'value' in command else 0
        LOGGER.info(f"Start Playlist: {self.name} playlist {playlist_id}")
        
        if self._device:
            self._device.set_state(pl=playlist_id)
            self.update_status()
    
    def cmd_playlist_off(self, command):
        """Stop playlist"""
        LOGGER.info(f"Stop Playlist: {self.name}")
        
        if self._device:
            self._device.set_state(pl=-1)
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
        'SAVE_PRESET': cmd_save_preset,
        'SET_COLOR': cmd_set_color,
        'SET_SPEED': cmd_set_speed,
        'SET_INTENSITY': cmd_set_intensity,
        'SET_TRANSITION': cmd_set_transition,
        'SET_LIVE': cmd_set_live,
        'NIGHTLIGHT_ON': cmd_nightlight_on,
        'NIGHTLIGHT_OFF': cmd_nightlight_off,
        'SYNC_SEND': cmd_sync_send,
        'SYNC_RECEIVE': cmd_sync_receive,
        'PLAYLIST_ON': cmd_playlist_on,
        'PLAYLIST_OFF': cmd_playlist_off,
        'QUERY': query,
    }
