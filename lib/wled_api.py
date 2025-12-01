"""
WLED JSON API Client

Provides HTTP client for communicating with WLED devices
using the JSON API (recommended over HTTP API for full feature support).

API Documentation: https://kno.wled.ge/interfaces/json-api/
"""

import requests
import logging
import socket
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
    Uses synchronous requests for compatibility with PG3.
    """
    
    def __init__(self, host: str, port: int = 80, timeout: int = 5):
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
    
    def _request(self, method: str, endpoint: str, 
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
            if method == "GET":
                response = requests.get(url, timeout=self.timeout)
            elif method == "POST":
                response = requests.post(url, json=json_data, timeout=self.timeout)
            else:
                LOGGER.error(f"WLED {self.host}: Unknown method {method}")
                return None
            
            if response.status_code == 200:
                self._online = True
                self._last_error = None
                return response.json()
            else:
                self._last_error = f"HTTP {response.status_code}"
                LOGGER.warning(f"WLED {self.host}: HTTP {response.status_code} on {endpoint}")
                
        except requests.exceptions.Timeout:
            self._online = False
            self._last_error = "Timeout"
            LOGGER.warning(f"WLED {self.host}: Request timeout")
            
        except requests.exceptions.ConnectionError as e:
            self._online = False
            self._last_error = "Connection error"
            LOGGER.warning(f"WLED {self.host}: Connection error - {e}")
            
        except requests.exceptions.RequestException as e:
            self._online = False
            self._last_error = str(e)
            LOGGER.error(f"WLED {self.host}: Request error - {e}")
            
        except Exception as e:
            self._online = False
            self._last_error = str(e)
            LOGGER.error(f"WLED {self.host}: Unexpected error - {e}")
            
        return None
    
    def get_all(self) -> bool:
        """
        Fetch all data from device (state, info, effects, palettes).
        
        Returns:
            True if successful, False otherwise
        """
        data = self._request("GET", "/json")
        
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
    
    def get_state(self) -> Optional[WLEDState]:
        """
        Fetch current state from device.
        
        Returns:
            WLEDState or None on error
        """
        data = self._request("GET", "/json/state")
        
        if data:
            self._state = WLEDState.from_json(data)
            return self._state
        
        return None
    
    def get_info(self) -> Optional[WLEDInfo]:
        """
        Fetch device info.
        
        Returns:
            WLEDInfo or None on error
        """
        data = self._request("GET", "/json/info")
        
        if data:
            self._info = WLEDInfo.from_json(data)
            return self._info
        
        return None
    
    def set_state(self, **kwargs) -> bool:
        """
        Set device state.
        
        Args:
            on: Power state (True/False)
            bri: Brightness (0-255)
            transition: Transition time in 100ms units
            ps: Preset to load (-1 for none)
            seg: Segment settings (list of dicts)
            
        Returns:
            True if successful
        """
        data = self._request("POST", "/json/state", kwargs)
        
        if data:
            # Update cached state
            self._state = WLEDState.from_json(data)
            return True
        
        return False
    
    def set_power(self, on: bool) -> bool:
        """Turn device on or off"""
        LOGGER.info(f"WLED {self.host}: Setting power to {on}")
        return self.set_state(on=on)
    
    def set_brightness(self, brightness: int) -> bool:
        """Set brightness (0-255)"""
        brightness = max(0, min(255, brightness))
        LOGGER.info(f"WLED {self.host}: Setting brightness to {brightness}")
        return self.set_state(bri=brightness)
    
    def set_effect(self, effect_id: int, speed: Optional[int] = None, 
                   intensity: Optional[int] = None) -> bool:
        """Set effect on main segment"""
        seg_data = {"fx": effect_id}
        if speed is not None:
            seg_data["sx"] = max(0, min(255, speed))
        if intensity is not None:
            seg_data["ix"] = max(0, min(255, intensity))
        
        LOGGER.info(f"WLED {self.host}: Setting effect to {effect_id}")
        return self.set_state(seg=[seg_data])
    
    def set_palette(self, palette_id: int) -> bool:
        """Set palette on main segment"""
        LOGGER.info(f"WLED {self.host}: Setting palette to {palette_id}")
        return self.set_state(seg=[{"pal": palette_id}])
    
    def set_color(self, r: int, g: int, b: int, w: int = 0) -> bool:
        """Set primary color on main segment"""
        r = max(0, min(255, r))
        g = max(0, min(255, g))
        b = max(0, min(255, b))
        w = max(0, min(255, w))
        
        LOGGER.info(f"WLED {self.host}: Setting color to RGB({r},{g},{b})")
        return self.set_state(seg=[{"col": [[r, g, b, w]]}])
    
    def set_preset(self, preset_id: int) -> bool:
        """Load a preset"""
        LOGGER.info(f"WLED {self.host}: Loading preset {preset_id}")
        return self.set_state(ps=preset_id)
    
    def get_presets(self) -> Dict[int, str]:
        """
        Fetch presets from device.
        
        Returns:
            Dict mapping preset ID to preset name
        """
        try:
            response = requests.get(f"{self._base_url}/presets.json", timeout=self.timeout)
            if response.status_code == 200:
                data = response.json()
                presets = {}
                for key, value in data.items():
                    if isinstance(value, dict) and 'n' in value:
                        try:
                            preset_id = int(key)
                            presets[preset_id] = value['n']
                        except (ValueError, TypeError):
                            pass
                self._presets = presets
                LOGGER.info(f"WLED {self.host}: Found {len(presets)} presets")
                return presets
        except Exception as e:
            LOGGER.warning(f"WLED {self.host}: Failed to get presets - {e}")
        return {}
    
    def set_segment_state(self, segment_id: int, **kwargs) -> bool:
        """
        Set state for a specific segment.
        
        Args:
            segment_id: Segment ID (0-based)
            on: Segment power state
            bri: Segment brightness
            fx: Effect ID
            pal: Palette ID
            col: Colors [[r,g,b], ...]
        """
        seg_data = {"id": segment_id, **kwargs}
        return self.set_state(seg=[seg_data])


class WLEDDiscovery:
    """
    Discovery for WLED devices
    
    Uses HTTP probe to discover WLED devices on the local network.
    """
    
    def __init__(self):
        self._discovered: Dict[str, Dict[str, Any]] = {}
    
    def discover(self, timeout: float = 10.0) -> List[Dict[str, Any]]:
        """
        Discover WLED devices on the network using HTTP probing.
        
        Args:
            timeout: Discovery timeout in seconds
            
        Returns:
            List of discovered devices with ip, port, name, mac
        """
        devices = []
        
        # Get local IP to determine subnet
        local_ip = self._get_local_ip()
        if not local_ip:
            LOGGER.warning("Could not determine local IP for discovery")
            return devices
        
        # Generate IPs to probe (same /24 subnet)
        subnet_prefix = '.'.join(local_ip.split('.')[:3])
        ips_to_probe = [f"{subnet_prefix}.{i}" for i in range(1, 255)]
        
        LOGGER.info(f"Probing subnet {subnet_prefix}.0/24 for WLED devices...")
        
        # Probe each IP
        for ip in ips_to_probe:
            device = self._probe_ip(ip, timeout=1.0)
            if device:
                devices.append(device)
        
        LOGGER.info(f"Discovery found {len(devices)} WLED device(s)")
        return devices
    
    def _probe_ip(self, ip: str, timeout: float = 1.0) -> Optional[Dict[str, Any]]:
        """Probe a single IP for WLED device"""
        try:
            response = requests.get(f"http://{ip}/json/info", timeout=timeout)
            if response.status_code == 200:
                data = response.json()
                # Check if it's a WLED device
                if 'ver' in data and 'name' in data:
                    device = {
                        'ip': ip,
                        'port': 80,
                        'name': data.get('name', ip),
                        'mac': data.get('mac', '')
                    }
                    LOGGER.info(f"Discovered WLED: {device['name']} at {ip}")
                    return device
        except:
            pass  # Expected for non-WLED IPs
        return None
    
    def _get_local_ip(self) -> Optional[str]:
        """Get local IP address"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return None
    
    def discover_simple(self, timeout: float = 5.0) -> List[str]:
        """
        Simple discovery returning just IP addresses.
        
        Args:
            timeout: Discovery timeout in seconds
            
        Returns:
            List of IP addresses
        """
        devices = self.discover(timeout)
        return [d['ip'] for d in devices]


class WLEDApi:
    """
    High-level WLED API manager for multiple devices.
    
    Provides device management and discovery capabilities.
    """
    
    def __init__(self):
        self._devices: Dict[str, WLEDDevice] = {}
        self._discovery = WLEDDiscovery()
    
    def add_device(self, host: str, port: int = 80) -> WLEDDevice:
        """
        Add a device to manage.
        
        Args:
            host: IP address or hostname
            port: HTTP port
            
        Returns:
            WLEDDevice instance
        """
        key = f"{host}:{port}"
        if key not in self._devices:
            self._devices[key] = WLEDDevice(host, port)
        return self._devices[key]
    
    def get_device(self, host: str, port: int = 80) -> Optional[WLEDDevice]:
        """Get device by host"""
        key = f"{host}:{port}"
        return self._devices.get(key)
    
    def remove_device(self, host: str, port: int = 80):
        """Remove a device"""
        key = f"{host}:{port}"
        if key in self._devices:
            del self._devices[key]
    
    def discover(self, timeout: float = 10.0) -> List[Dict[str, Any]]:
        """
        Discover WLED devices on the network.
        
        Returns:
            List of discovered devices
        """
        return self._discovery.discover(timeout)
    
    @property
    def devices(self) -> Dict[str, WLEDDevice]:
        """Get all managed devices"""
        return self._devices
