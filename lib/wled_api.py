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

try:
    import udi_interface
    LOGGER = udi_interface.LOGGER
except ImportError:
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
    
    def get_effect_metadata(self) -> Dict[int, Dict[str, Any]]:
        """
        Fetch effect metadata from device (fxdata).
        
        Returns:
            Dict mapping effect ID to metadata dict with keys:
            - is_2d: bool - True if 2D effect
            - uses_palette: bool - True if effect uses palette colors
            - volume: bool - True if volume reactive (audio)
            - frequency: bool - True if frequency reactive (audio)
        """
        metadata = {}
        try:
            # Get effect names
            effects_response = requests.get(f"{self._base_url}/json/effects", timeout=self.timeout)
            fxdata_response = requests.get(f"{self._base_url}/json/fxdata", timeout=self.timeout)
            
            if effects_response.status_code == 200 and fxdata_response.status_code == 200:
                effects = effects_response.json()
                fxdata = fxdata_response.json()
                
                for i, (name, data) in enumerate(zip(effects, fxdata)):
                    if not name or name == '-':
                        continue
                    
                    # Parse fxdata format: "params;colors;palette;flags;options"
                    # Flags can be: 0, 01, 1, 2, 01v, 1v, 2v, 01f, 1f, 2f, etc.
                    meta = {
                        'name': name,
                        'is_2d': False,
                        'uses_palette': False,
                        'volume': False,
                        'frequency': False
                    }
                    
                    if data:
                        parts = data.split(';')
                        if len(parts) >= 3:
                            # Third part is palette section - if not empty, uses palette
                            palette_part = parts[2].strip() if len(parts) > 2 else ''
                            meta['uses_palette'] = bool(palette_part and palette_part != '!')
                        
                        if len(parts) >= 4:
                            # Fourth part contains flags
                            flags = parts[3].strip()
                            # Remove any key=value options after the flags
                            if flags:
                                flag_part = flags.split(',')[0] if ',' in flags else flags
                                
                                # Check for 2D (flag contains '2')
                                meta['is_2d'] = '2' in flag_part
                                
                                # Check for volume reactive (ends with 'v')
                                meta['volume'] = 'v' in flag_part.lower()
                                
                                # Check for frequency reactive (ends with 'f')
                                meta['frequency'] = 'f' in flag_part.lower()
                    
                    metadata[i] = meta
                
                LOGGER.info(f"WLED {self.host}: Parsed metadata for {len(metadata)} effects")
                
        except Exception as e:
            LOGGER.warning(f"WLED {self.host}: Failed to get effect metadata - {e}")
        
        return metadata
    
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
    
    Uses mDNS (primary) + HTTP probing (fallback) to discover WLED devices.
    """
    
    def __init__(self):
        self._discovered: Dict[str, Dict[str, Any]] = {}
    
    def discover(self, timeout: float = 10.0) -> List[Dict[str, Any]]:
        """
        Discover WLED devices using mDNS first, then HTTP probe as fallback.
        
        Args:
            timeout: Total discovery timeout in seconds
            
        Returns:
            List of discovered devices with ip, port, name, mac
        """
        import time
        start_time = time.time()
        
        LOGGER.info("=" * 50)
        LOGGER.info("WLED Discovery started")
        LOGGER.info("=" * 50)
        
        all_devices = {}  # Use dict to dedupe by IP
        
        # Phase 1: mDNS discovery (fast, ~3s)
        mdns_start = time.time()
        LOGGER.info("Phase 1: mDNS discovery started...")
        
        try:
            mdns_devices = self._discover_mdns(timeout=3.0)
            mdns_elapsed = time.time() - mdns_start
            
            for device in mdns_devices:
                all_devices[device['ip']] = device
                LOGGER.info(f"  mDNS: Found \"{device['name']}\" ({device['ip']}) in {mdns_elapsed:.1f}s")
            
            LOGGER.info(f"Phase 1 complete: {len(mdns_devices)} device(s) via mDNS in {mdns_elapsed:.1f}s")
        except Exception as e:
            LOGGER.warning(f"Phase 1 mDNS failed: {e}")
            mdns_elapsed = time.time() - mdns_start
        
        # Phase 2: HTTP probe for any missed devices
        http_start = time.time()
        remaining_timeout = max(1.0, timeout - (time.time() - start_time))
        found_ips = set(all_devices.keys())
        
        LOGGER.info(f"Phase 2: HTTP probe started (excluding {len(found_ips)} already found)...")
        
        try:
            http_devices = self._discover_http(timeout=remaining_timeout, exclude_ips=found_ips)
            http_elapsed = time.time() - http_start
            
            new_count = 0
            for device in http_devices:
                if device['ip'] not in all_devices:
                    all_devices[device['ip']] = device
                    new_count += 1
                    LOGGER.info(f"  HTTP: Found \"{device['name']}\" ({device['ip']})")
            
            LOGGER.info(f"Phase 2 complete: {new_count} additional device(s) via HTTP in {http_elapsed:.1f}s")
        except Exception as e:
            LOGGER.warning(f"Phase 2 HTTP probe failed: {e}")
        
        # Summary
        total_elapsed = time.time() - start_time
        devices = list(all_devices.values())
        
        LOGGER.info("=" * 50)
        LOGGER.info(f"Discovery complete: {len(devices)} total device(s) in {total_elapsed:.1f}s")
        for d in devices:
            LOGGER.info(f"  - {d['name']} ({d['ip']})")
        LOGGER.info("=" * 50)
        
        return devices
    
    def _discover_mdns(self, timeout: float = 3.0) -> List[Dict[str, Any]]:
        """
        Discover WLED devices via mDNS (Zeroconf).
        WLED devices register as _wled._tcp.local
        
        Args:
            timeout: Discovery timeout in seconds
            
        Returns:
            List of discovered devices
        """
        import time
        import threading
        
        devices = []
        devices_lock = threading.Lock()
        
        try:
            from zeroconf import ServiceBrowser, Zeroconf, ServiceListener
            
            class WLEDListener(ServiceListener):
                def __init__(self):
                    self.start_time = time.time()
                
                def add_service(self, zc: Zeroconf, type_: str, name: str) -> None:
                    try:
                        info = zc.get_service_info(type_, name)
                        if info:
                            # Get IP address
                            if info.addresses:
                                ip = '.'.join(str(b) for b in info.addresses[0])
                            elif info.parsed_addresses():
                                ip = info.parsed_addresses()[0]
                            else:
                                return
                            
                            # Get device name (strip .local suffix)
                            device_name = name.replace('._wled._tcp.local.', '').replace('.local', '')
                            
                            device = {
                                'ip': ip,
                                'port': info.port or 80,
                                'name': device_name,
                                'mac': ''
                            }
                            
                            elapsed = time.time() - self.start_time
                            with devices_lock:
                                # Avoid duplicates
                                if not any(d['ip'] == ip for d in devices):
                                    devices.append(device)
                                    LOGGER.debug(f"mDNS found: {device_name} at {ip} ({elapsed:.2f}s)")
                    except Exception as e:
                        LOGGER.debug(f"mDNS service info error: {e}")
                
                def remove_service(self, zc: Zeroconf, type_: str, name: str) -> None:
                    pass
                
                def update_service(self, zc: Zeroconf, type_: str, name: str) -> None:
                    pass
            
            # Start mDNS browser
            zeroconf = Zeroconf()
            listener = WLEDListener()
            browser = ServiceBrowser(zeroconf, "_wled._tcp.local.", listener)
            
            # Wait for timeout
            time.sleep(timeout)
            
            # Cleanup
            browser.cancel()
            zeroconf.close()
            
        except ImportError:
            LOGGER.warning("zeroconf not installed - skipping mDNS discovery")
        except OSError as e:
            if e.errno == 48:  # Address already in use
                LOGGER.info("mDNS port 5353 in use by system - using HTTP probe only")
            else:
                LOGGER.warning(f"mDNS discovery error: {e}")
        except Exception as e:
            LOGGER.warning(f"mDNS discovery error: {e}")
        
        return devices
    
    def _discover_http(self, timeout: float = 7.0, exclude_ips: set = None) -> List[Dict[str, Any]]:
        """
        Discover WLED devices via HTTP probing with improved reliability.
        
        Args:
            timeout: Total discovery timeout in seconds
            exclude_ips: Set of IPs to skip (already found via mDNS)
            
        Returns:
            List of discovered devices
        """
        import concurrent.futures
        import threading
        import time
        
        devices = []
        devices_lock = threading.Lock()
        exclude_ips = exclude_ips or set()
        
        # Get local IP to determine subnet
        local_ip = self._get_local_ip()
        if not local_ip:
            LOGGER.warning("Could not determine local IP for HTTP probe")
            return devices
        
        # Generate IPs to probe (same /24 subnet), excluding already found
        subnet_prefix = '.'.join(local_ip.split('.')[:3])
        ips_to_probe = [f"{subnet_prefix}.{i}" for i in range(1, 255) 
                       if f"{subnet_prefix}.{i}" not in exclude_ips]
        
        LOGGER.debug(f"HTTP probe: scanning {len(ips_to_probe)} IPs on {subnet_prefix}.0/24")
        
        failed_ips = []  # Track failed IPs for retry
        failed_lock = threading.Lock()
        
        def probe_and_collect(ip: str, is_retry: bool = False):
            """Probe IP and add to results if WLED found"""
            device = self._probe_ip(ip, timeout=2.0)  # 2s timeout for reliability
            if device:
                with devices_lock:
                    if not any(d['ip'] == ip for d in devices):
                        devices.append(device)
                        if is_retry:
                            LOGGER.debug(f"HTTP retry found: {device['name']} at {ip}")
            elif not is_retry:
                # Track for retry
                with failed_lock:
                    failed_ips.append(ip)
        
        # First pass: probe all IPs with 30 workers (reduced from 50)
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=30) as executor:
                futures = [executor.submit(probe_and_collect, ip, False) for ip in ips_to_probe]
                concurrent.futures.wait(futures, timeout=timeout * 0.7)  # Use 70% of timeout for first pass
        except Exception as e:
            LOGGER.error(f"HTTP probe error: {e}")
        
        # Second pass: retry failed IPs (some may have been temporarily busy)
        if failed_ips and (timeout * 0.3) > 1.0:
            LOGGER.debug(f"HTTP probe: retrying {len(failed_ips)} failed IPs...")
            try:
                with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
                    futures = [executor.submit(probe_and_collect, ip, True) for ip in failed_ips]
                    concurrent.futures.wait(futures, timeout=timeout * 0.3)
            except Exception as e:
                LOGGER.debug(f"HTTP retry error: {e}")
        
        return devices
    
    def _probe_ip(self, ip: str, timeout: float = 1.0) -> Optional[Dict[str, Any]]:
        """Probe a single IP for WLED device"""
        try:
            response = requests.get(f"http://{ip}/json/info", timeout=timeout)
            if response.status_code == 200:
                data = response.json()
                # Check if it's a WLED device (has version and name)
                if 'ver' in data and 'name' in data:
                    device = {
                        'ip': ip,
                        'port': 80,
                        'name': data.get('name', ip),
                        'mac': data.get('mac', '')
                    }
                    return device
        except requests.exceptions.Timeout:
            pass  # Expected for non-responsive IPs
        except requests.exceptions.ConnectionError:
            pass  # Expected for non-listening IPs
        except Exception:
            pass  # Any other error, skip silently
        return None
    
    def _get_local_ip(self) -> Optional[str]:
        """Get local IP address"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception as e:
            LOGGER.error(f"Failed to get local IP: {e}")
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
