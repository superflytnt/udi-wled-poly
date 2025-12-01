"""
WLED JSON API Client

Provides async HTTP client for communicating with WLED devices
using the JSON API (recommended over HTTP API for full feature support).

API Documentation: https://kno.wled.ge/interfaces/json-api/
"""

import asyncio
import aiohttp
import logging
from typing import Optional, Dict, List, Any, Tuple
from dataclasses import dataclass, field

LOGGER = logging.getLogger(__name__)


@dataclass
class WLEDSegment:
    """Represents a WLED segment"""
    id: int
    start: int
    stop: int
    length: int
    on: bool = True
    brightness: int = 255
    effect: int = 0
    speed: int = 128
    intensity: int = 128
    palette: int = 0
    colors: List[List[int]] = field(default_factory=lambda: [[255, 255, 255]])
    
    @classmethod
    def from_json(cls, data: Dict[str, Any], seg_id: int) -> 'WLEDSegment':
        """Create segment from JSON API response"""
        return cls(
            id=seg_id,
            start=data.get('start', 0),
            stop=data.get('stop', 0),
            length=data.get('len', data.get('stop', 0) - data.get('start', 0)),
            on=data.get('on', True),
            brightness=data.get('bri', 255),
            effect=data.get('fx', 0),
            speed=data.get('sx', 128),
            intensity=data.get('ix', 128),
            palette=data.get('pal', 0),
            colors=data.get('col', [[255, 255, 255]])
        )


@dataclass
class WLEDState:
    """Represents the current state of a WLED device"""
    on: bool = False
    brightness: int = 0
    transition: int = 7
    preset: int = -1
    playlist: int = -1
    nightlight_on: bool = False
    nightlight_duration: int = 60
    nightlight_mode: int = 0
    nightlight_brightness: int = 0
    live: bool = False
    sync_send: bool = False
    sync_receive: bool = True
    main_segment: int = 0
    segments: List[WLEDSegment] = field(default_factory=list)
    
    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> 'WLEDState':
        """Create state from JSON API response"""
        segments = []
        for i, seg_data in enumerate(data.get('seg', [])):
            segments.append(WLEDSegment.from_json(seg_data, i))
        
        nl = data.get('nl', {})
        udpn = data.get('udpn', {})
        
        return cls(
            on=data.get('on', False),
            brightness=data.get('bri', 0),
            transition=data.get('transition', 7),
            preset=data.get('ps', -1),
            playlist=data.get('pl', -1),
            nightlight_on=nl.get('on', False),
            nightlight_duration=nl.get('dur', 60),
            nightlight_mode=nl.get('mode', 0),
            nightlight_brightness=nl.get('tbri', 0),
            live=data.get('lor', 0) > 0,
            sync_send=udpn.get('send', False),
            sync_receive=udpn.get('recv', True),
            main_segment=data.get('mainseg', 0),
            segments=segments
        )
    
    @property
    def primary_color(self) -> List[int]:
        """Get primary color from main segment"""
        if self.segments and len(self.segments) > self.main_segment:
            seg = self.segments[self.main_segment]
            if seg.colors and len(seg.colors) > 0:
                return seg.colors[0]
        return [255, 255, 255]
    
    @property
    def effect(self) -> int:
        """Get effect from main segment"""
        if self.segments and len(self.segments) > self.main_segment:
            return self.segments[self.main_segment].effect
        return 0
    
    @property
    def palette(self) -> int:
        """Get palette from main segment"""
        if self.segments and len(self.segments) > self.main_segment:
            return self.segments[self.main_segment].palette
        return 0


@dataclass
class WLEDInfo:
    """Represents WLED device information"""
    version: str = ""
    version_id: int = 0
    led_count: int = 0
    max_segments: int = 0
    name: str = ""
    udp_port: int = 21324
    live_support: bool = False
    live_mode: int = 0
    product: str = "WLED"
    brand: str = "wled"
    mac: str = ""
    ip: str = ""
    
    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> 'WLEDInfo':
        """Create info from JSON API response"""
        leds = data.get('leds', {})
        
        return cls(
            version=data.get('ver', ''),
            version_id=data.get('vid', 0),
            led_count=leds.get('count', 0),
            max_segments=leds.get('maxseg', 0),
            name=data.get('name', ''),
            udp_port=data.get('udpport', 21324),
            live_support=data.get('lm', False) if isinstance(data.get('lm'), bool) else bool(data.get('lm', 0)),
            live_mode=data.get('lip', 0) if isinstance(data.get('lip'), int) else 0,
            product=data.get('product', 'WLED'),
            brand=data.get('brand', 'wled'),
            mac=data.get('mac', ''),
            ip=data.get('ip', '')
        )


class WLEDDevice:
    """
    WLED Device API Client
    
    Handles all communication with a single WLED device via the JSON API.
    """
    
    def __init__(self, host: str, port: int = 80, timeout: int = 10):
        """
        Initialize WLED device client.
        
        Args:
            host: IP address or hostname of WLED device
            port: HTTP port (default 80)
            timeout: Request timeout in seconds
        """
        self.host = host
        self.port = port
        self.timeout = timeout
        self._base_url = f"http://{host}:{port}"
        self._session: Optional[aiohttp.ClientSession] = None
        
        # Cached data
        self._state: Optional[WLEDState] = None
        self._info: Optional[WLEDInfo] = None
        self._effects: List[str] = []
        self._palettes: List[str] = []
        self._presets: Dict[int, str] = {}
        
        # Connection status
        self._online = False
        self._last_error: Optional[str] = None
    
    @property
    def online(self) -> bool:
        """Check if device is online"""
        return self._online
    
    @property
    def state(self) -> Optional[WLEDState]:
        """Get cached state"""
        return self._state
    
    @property
    def info(self) -> Optional[WLEDInfo]:
        """Get cached info"""
        return self._info
    
    @property
    def effects(self) -> List[str]:
        """Get cached effects list"""
        return self._effects
    
    @property
    def palettes(self) -> List[str]:
        """Get cached palettes list"""
        return self._palettes
    
    @property
    def presets(self) -> Dict[int, str]:
        """Get cached presets"""
        return self._presets
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session"""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session
    
    async def close(self):
        """Close HTTP session"""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
    
    async def _request(self, method: str, endpoint: str, 
                       json_data: Optional[Dict] = None) -> Optional[Dict]:
        """
        Make HTTP request to WLED device.
        
        Args:
            method: HTTP method (GET, POST)
            endpoint: API endpoint (e.g., /json/state)
            json_data: JSON data for POST requests
            
        Returns:
            JSON response or None on error
        """
        url = f"{self._base_url}{endpoint}"
        
        try:
            session = await self._get_session()
            
            if method == "GET":
                async with session.get(url) as response:
                    if response.status == 200:
                        self._online = True
                        self._last_error = None
                        return await response.json()
                    else:
                        self._last_error = f"HTTP {response.status}"
                        LOGGER.warning(f"WLED {self.host}: HTTP {response.status} on {endpoint}")
                        
            elif method == "POST":
                async with session.post(url, json=json_data) as response:
                    if response.status == 200:
                        self._online = True
                        self._last_error = None
                        return await response.json()
                    else:
                        self._last_error = f"HTTP {response.status}"
                        LOGGER.warning(f"WLED {self.host}: HTTP {response.status} on {endpoint}")
                        
        except asyncio.TimeoutError:
            self._online = False
            self._last_error = "Timeout"
            LOGGER.warning(f"WLED {self.host}: Request timeout")
            
        except aiohttp.ClientError as e:
            self._online = False
            self._last_error = str(e)
            LOGGER.warning(f"WLED {self.host}: Connection error - {e}")
            
        except Exception as e:
            self._online = False
            self._last_error = str(e)
            LOGGER.error(f"WLED {self.host}: Unexpected error - {e}")
            
        return None
    
    async def get_all(self) -> bool:
        """
        Fetch all data from device (state, info, effects, palettes).
        
        Returns:
            True if successful, False otherwise
        """
        data = await self._request("GET", "/json")
        
        if data:
            # Parse state
            if 'state' in data:
                self._state = WLEDState.from_json(data['state'])
            
            # Parse info
            if 'info' in data:
                self._info = WLEDInfo.from_json(data['info'])
            
            # Parse effects
            if 'effects' in data:
                self._effects = [e for e in data['effects'] if e and e != '-']
            
            # Parse palettes
            if 'palettes' in data:
                self._palettes = [p for p in data['palettes'] if p and p != '-']
            
            return True
        
        return False
    
    async def get_state(self) -> Optional[WLEDState]:
        """Fetch current state from device"""
        data = await self._request("GET", "/json/state")
        
        if data:
            self._state = WLEDState.from_json(data)
            return self._state
        
        return None
    
    async def get_info(self) -> Optional[WLEDInfo]:
        """Fetch device info"""
        data = await self._request("GET", "/json/info")
        
        if data:
            self._info = WLEDInfo.from_json(data)
            return self._info
        
        return None
    
    async def get_effects(self) -> List[str]:
        """Fetch available effects"""
        data = await self._request("GET", "/json/eff")
        
        if data and isinstance(data, list):
            self._effects = [e for e in data if e and e != '-']
        
        return self._effects
    
    async def get_palettes(self) -> List[str]:
        """Fetch available palettes"""
        data = await self._request("GET", "/json/pal")
        
        if data and isinstance(data, list):
            self._palettes = [p for p in data if p and p != '-']
        
        return self._palettes
    
    async def get_presets(self) -> Dict[int, str]:
        """Fetch saved presets"""
        data = await self._request("GET", "/presets.json")
        
        if data:
            self._presets = {}
            for key, value in data.items():
                try:
                    preset_id = int(key)
                    if isinstance(value, dict) and 'n' in value:
                        self._presets[preset_id] = value['n']
                    elif isinstance(value, dict):
                        self._presets[preset_id] = f"Preset {preset_id}"
                except (ValueError, TypeError):
                    continue
        
        return self._presets
    
    async def set_state(self, **kwargs) -> bool:
        """
        Set device state.
        
        Supported kwargs:
            on: bool - Power state
            bri: int - Brightness (0-255)
            transition: int - Transition time (0-255, in 100ms units)
            ps: int - Load preset
            pl: int - Load playlist
            seg: list - Segment settings
            
        Returns:
            True if successful
        """
        data = await self._request("POST", "/json/state", kwargs)
        
        if data:
            self._state = WLEDState.from_json(data)
            return True
        
        return False
    
    # Convenience methods
    
    async def turn_on(self) -> bool:
        """Turn on the device"""
        return await self.set_state(on=True)
    
    async def turn_off(self) -> bool:
        """Turn off the device"""
        return await self.set_state(on=False)
    
    async def toggle(self) -> bool:
        """Toggle power state"""
        return await self.set_state(on="t")
    
    async def set_brightness(self, brightness: int) -> bool:
        """Set brightness (0-255)"""
        brightness = max(0, min(255, brightness))
        return await self.set_state(bri=brightness)
    
    async def set_color(self, r: int, g: int, b: int, segment: int = 0) -> bool:
        """Set RGB color for a segment"""
        r = max(0, min(255, r))
        g = max(0, min(255, g))
        b = max(0, min(255, b))
        
        return await self.set_state(seg=[{"id": segment, "col": [[r, g, b]]}])
    
    async def set_effect(self, effect_id: int, segment: int = 0) -> bool:
        """Set effect by ID"""
        return await self.set_state(seg=[{"id": segment, "fx": effect_id}])
    
    async def set_palette(self, palette_id: int, segment: int = 0) -> bool:
        """Set palette by ID"""
        return await self.set_state(seg=[{"id": segment, "pal": palette_id}])
    
    async def set_effect_speed(self, speed: int, segment: int = 0) -> bool:
        """Set effect speed (0-255)"""
        speed = max(0, min(255, speed))
        return await self.set_state(seg=[{"id": segment, "sx": speed}])
    
    async def set_effect_intensity(self, intensity: int, segment: int = 0) -> bool:
        """Set effect intensity (0-255)"""
        intensity = max(0, min(255, intensity))
        return await self.set_state(seg=[{"id": segment, "ix": intensity}])
    
    async def load_preset(self, preset_id: int) -> bool:
        """Load a preset by ID"""
        return await self.set_state(ps=preset_id)
    
    async def save_preset(self, preset_id: int, name: Optional[str] = None) -> bool:
        """Save current state to a preset"""
        data = {"psave": preset_id}
        if name:
            data["n"] = name
        return await self.set_state(**data)
    
    async def set_segment(self, segment_id: int, **kwargs) -> bool:
        """
        Set segment-specific settings.
        
        Supported kwargs:
            on: bool - Segment on/off
            bri: int - Segment brightness
            fx: int - Effect ID
            sx: int - Effect speed
            ix: int - Effect intensity
            pal: int - Palette ID
            col: list - Colors [[r,g,b], ...]
            start: int - Start LED
            stop: int - Stop LED
        """
        seg_data = {"id": segment_id, **kwargs}
        return await self.set_state(seg=[seg_data])


class WLEDDiscovery:
    """
    mDNS Discovery for WLED devices
    
    Uses zeroconf to discover WLED devices on the local network.
    """
    
    SERVICE_TYPE = "_wled._tcp.local."
    
    def __init__(self):
        self._discovered: Dict[str, Tuple[str, int, str]] = {}  # mac -> (ip, port, name)
        self._zeroconf = None
        self._browser = None
    
    async def discover(self, timeout: float = 5.0) -> List[Dict[str, Any]]:
        """
        Discover WLED devices on the network.
        
        Args:
            timeout: Discovery timeout in seconds
            
        Returns:
            List of discovered devices with ip, port, name, mac
        """
        try:
            from zeroconf import Zeroconf, ServiceBrowser
            from zeroconf.asyncio import AsyncZeroconf, AsyncServiceBrowser
        except ImportError:
            LOGGER.error("zeroconf library not installed")
            return []
        
        devices = []
        discovered_ips = set()
        
        class WLEDListener:
            def __init__(self, parent):
                self.parent = parent
            
            def add_service(self, zc, service_type, name):
                info = zc.get_service_info(service_type, name)
                if info:
                    ip = None
                    if info.addresses:
                        import socket
                        ip = socket.inet_ntoa(info.addresses[0])
                    
                    if ip and ip not in discovered_ips:
                        discovered_ips.add(ip)
                        device = {
                            'ip': ip,
                            'port': info.port or 80,
                            'name': info.server.rstrip('.') if info.server else name,
                            'mac': info.properties.get(b'mac', b'').decode('utf-8', errors='ignore')
                        }
                        devices.append(device)
                        LOGGER.info(f"Discovered WLED device: {device['name']} at {ip}")
            
            def remove_service(self, zc, service_type, name):
                pass
            
            def update_service(self, zc, service_type, name):
                pass
        
        try:
            zc = Zeroconf()
            listener = WLEDListener(self)
            browser = ServiceBrowser(zc, self.SERVICE_TYPE, listener)
            
            # Wait for discovery
            await asyncio.sleep(timeout)
            
            browser.cancel()
            zc.close()
            
        except Exception as e:
            LOGGER.error(f"mDNS discovery error: {e}")
        
        return devices
    
    async def discover_simple(self, timeout: float = 5.0) -> List[str]:
        """
        Simple discovery returning just IP addresses.
        
        Args:
            timeout: Discovery timeout in seconds
            
        Returns:
            List of IP addresses
        """
        devices = await self.discover(timeout)
        return [d['ip'] for d in devices]


class WLEDApi:
    """
    High-level WLED API manager for multiple devices.
    
    Manages connections to multiple WLED devices and provides
    unified access to all devices.
    """
    
    def __init__(self):
        self._devices: Dict[str, WLEDDevice] = {}
        self._discovery = WLEDDiscovery()
    
    @property
    def devices(self) -> Dict[str, WLEDDevice]:
        """Get all managed devices"""
        return self._devices
    
    def add_device(self, name: str, host: str, port: int = 80) -> WLEDDevice:
        """
        Add a WLED device to manage.
        
        Args:
            name: Friendly name for the device
            host: IP address or hostname
            port: HTTP port (default 80)
            
        Returns:
            WLEDDevice instance
        """
        device = WLEDDevice(host, port)
        self._devices[name] = device
        LOGGER.info(f"Added WLED device: {name} at {host}:{port}")
        return device
    
    def remove_device(self, name: str) -> bool:
        """Remove a device by name"""
        if name in self._devices:
            device = self._devices.pop(name)
            asyncio.create_task(device.close())
            LOGGER.info(f"Removed WLED device: {name}")
            return True
        return False
    
    def get_device(self, name: str) -> Optional[WLEDDevice]:
        """Get a device by name"""
        return self._devices.get(name)
    
    async def discover_devices(self, timeout: float = 5.0) -> List[Dict[str, Any]]:
        """
        Discover WLED devices on the network.
        
        Args:
            timeout: Discovery timeout in seconds
            
        Returns:
            List of discovered devices
        """
        return await self._discovery.discover(timeout)
    
    async def refresh_all(self) -> Dict[str, bool]:
        """
        Refresh state for all devices.
        
        Returns:
            Dict of device_name -> success status
        """
        results = {}
        
        for name, device in self._devices.items():
            try:
                results[name] = await device.get_all()
            except Exception as e:
                LOGGER.error(f"Failed to refresh {name}: {e}")
                results[name] = False
        
        return results
    
    async def close_all(self):
        """Close all device connections"""
        for device in self._devices.values():
            await device.close()
        self._devices.clear()

