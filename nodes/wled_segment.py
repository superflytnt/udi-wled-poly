"""
WLED Segment Node

Represents an individual LED segment on a WLED device.
Allows independent control of brightness, effect, and color per segment.
"""

import udi_interface
import asyncio
import logging
from typing import Optional, Any

LOGGER = udi_interface.LOGGER


class WLEDSegment(udi_interface.Node):
    """
    WLED Segment Node
    
    Provides control of a single segment on a WLED device.
    Each segment can have its own brightness, effect, palette, and color.
    
    Status:
        ST (Power): Segment on/off
        GV0 (Brightness): 0-100%
        GV1 (Effect): Current effect ID
        GV2 (Palette): Current palette ID
        GV3 (Red): Red component 0-255
        GV4 (Green): Green component 0-255
        GV5 (Blue): Blue component 0-255
        GV6 (Start): Start LED index
        GV7 (Stop): Stop LED index
    """
    
    id = 'wled_segment'
    
    # Node drivers (status values)
    drivers = [
        {'driver': 'ST', 'value': 0, 'uom': 2},      # Power (On/Off)
        {'driver': 'GV0', 'value': 0, 'uom': 51},    # Brightness (%)
        {'driver': 'GV1', 'value': 0, 'uom': 25},    # Effect
        {'driver': 'GV2', 'value': 0, 'uom': 25},    # Palette
        {'driver': 'GV3', 'value': 0, 'uom': 56},    # Red
        {'driver': 'GV4', 'value': 0, 'uom': 56},    # Green
        {'driver': 'GV5', 'value': 0, 'uom': 56},    # Blue
        {'driver': 'GV6', 'value': 0, 'uom': 56},    # Start LED
        {'driver': 'GV7', 'value': 0, 'uom': 56},    # Stop LED
    ]
    
    def __init__(self, polyglot, primary, address, name, segment_id: int, parent_device):
        """
        Initialize the WLED segment node.
        
        Args:
            polyglot: Polyglot interface
            primary: Primary node address (controller)
            address: Node address
            name: Segment name
            segment_id: Segment ID (0-based)
            parent_device: Parent WLEDDevice instance (API client)
        """
        super().__init__(polyglot, primary, address, name)
        
        self.poly = polyglot
        self.name = name
        self.primary = primary
        self.address = address
        
        # Segment info
        self._segment_id = segment_id
        self._parent_device = parent_device
        
        # Add node to polyglot
        polyglot.addNode(self)
    
    def _run_async(self, coro):
        """Run an async coroutine in sync context"""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.ensure_future(coro)
            else:
                loop.run_until_complete(coro)
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(coro)
            finally:
                loop.close()
    
    def update_from_state(self, segment_state):
        """
        Update node status from segment state.
        
        Args:
            segment_state: WLEDSegment state object
        """
        if not segment_state:
            return
        
        # Update power
        self.setDriver('ST', 1 if segment_state.on else 0)
        
        # Update brightness (convert 0-255 to 0-100%)
        brightness_pct = int((segment_state.brightness / 255) * 100)
        self.setDriver('GV0', brightness_pct)
        
        # Update effect
        self.setDriver('GV1', segment_state.effect)
        
        # Update palette
        self.setDriver('GV2', segment_state.palette)
        
        # Update color
        if segment_state.colors and len(segment_state.colors) > 0:
            color = segment_state.colors[0]
            if len(color) >= 3:
                self.setDriver('GV3', color[0])  # Red
                self.setDriver('GV4', color[1])  # Green
                self.setDriver('GV5', color[2])  # Blue
        
        # Update LED range
        self.setDriver('GV6', segment_state.start)
        self.setDriver('GV7', segment_state.stop)
    
    def query(self, command=None):
        """Query segment status"""
        LOGGER.info(f"Query segment: {self.name}")
        
        # Get state from parent device
        if self._parent_device and self._parent_device.state:
            segments = self._parent_device.state.segments
            if self._segment_id < len(segments):
                self.update_from_state(segments[self._segment_id])
        
        self.reportDrivers()
    
    def cmd_on(self, command=None):
        """Turn on the segment"""
        LOGGER.info(f"Turn On Segment: {self.name}")
        
        brightness = None
        if command and 'value' in command:
            brightness = int(command['value'])
        
        async def _on():
            if self._parent_device:
                if brightness is not None:
                    bri_val = int((brightness / 100) * 255)
                    await self._parent_device.set_segment(
                        self._segment_id, on=True, bri=bri_val
                    )
                else:
                    await self._parent_device.set_segment(
                        self._segment_id, on=True
                    )
        
        self._run_async(_on())
        self.setDriver('ST', 1)
    
    def cmd_off(self, command=None):
        """Turn off the segment"""
        LOGGER.info(f"Turn Off Segment: {self.name}")
        
        async def _off():
            if self._parent_device:
                await self._parent_device.set_segment(
                    self._segment_id, on=False
                )
        
        self._run_async(_off())
        self.setDriver('ST', 0)
    
    def cmd_set_brightness(self, command):
        """Set segment brightness"""
        brightness = int(command.get('value', 100))
        LOGGER.info(f"Set Segment Brightness: {self.name} to {brightness}%")
        
        async def _set_bri():
            if self._parent_device:
                bri_val = int((brightness / 100) * 255)
                await self._parent_device.set_segment(
                    self._segment_id, bri=bri_val
                )
        
        self._run_async(_set_bri())
        self.setDriver('GV0', brightness)
    
    def cmd_set_effect(self, command):
        """Set segment effect"""
        effect_id = int(command.get('value', 0))
        LOGGER.info(f"Set Segment Effect: {self.name} to {effect_id}")
        
        async def _set_effect():
            if self._parent_device:
                await self._parent_device.set_segment(
                    self._segment_id, fx=effect_id
                )
        
        self._run_async(_set_effect())
        self.setDriver('GV1', effect_id)
    
    def cmd_set_palette(self, command):
        """Set segment palette"""
        palette_id = int(command.get('value', 0))
        LOGGER.info(f"Set Segment Palette: {self.name} to {palette_id}")
        
        async def _set_palette():
            if self._parent_device:
                await self._parent_device.set_segment(
                    self._segment_id, pal=palette_id
                )
        
        self._run_async(_set_palette())
        self.setDriver('GV2', palette_id)
    
    def cmd_set_color(self, command):
        """Set segment RGB color"""
        r = int(command.get('R.uom56', command.get('R', 255)))
        g = int(command.get('G.uom56', command.get('G', 255)))
        b = int(command.get('B.uom56', command.get('B', 255)))
        
        LOGGER.info(f"Set Segment Color: {self.name} to RGB({r},{g},{b})")
        
        async def _set_color():
            if self._parent_device:
                await self._parent_device.set_segment(
                    self._segment_id, col=[[r, g, b]]
                )
        
        self._run_async(_set_color())
        self.setDriver('GV3', r)
        self.setDriver('GV4', g)
        self.setDriver('GV5', b)
    
    # Command handlers
    commands = {
        'DON': cmd_on,
        'DOF': cmd_off,
        'SET_BRI': cmd_set_brightness,
        'SET_EFFECT': cmd_set_effect,
        'SET_PALETTE': cmd_set_palette,
        'SET_COLOR': cmd_set_color,
        'QUERY': query,
    }

