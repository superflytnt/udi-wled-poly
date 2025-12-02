# WLED Polyglot v3 NodeServer

[![Version](https://img.shields.io/badge/version-1.5.1-blue.svg)](https://github.com/superflytnt/udi-wled-poly)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

A Polyglot v3 (PG3) NodeServer for Universal Devices ISY/eISY that provides full control of WLED LED controllers.

## Features

### Device Management
- **Multi-device support** — Control unlimited WLED devices from a single nodeserver
- **Auto-Discovery** — Parallel network scan finds all WLED devices in seconds
- **Manual Configuration** — Add devices by name and IP address
- **Real-time Status** — See power, brightness, effect, palette, preset, and more
- **Controller Dashboard** — View online count, devices on, and total LED count

### WLED Control
| Feature | Description |
|---------|-------------|
| Power | On/Off/Toggle with optional brightness |
| Brightness | 0-100% dimming |
| Effects | 180+ effects with type indicators (1D/2D, Palette, Audio) |
| Palettes | 70+ color palettes |
| Presets | Load and save presets (names auto-populated from devices) |
| Color | RGB color control |
| Speed | Effect animation speed |
| Intensity | Effect intensity/size |
| Transition | Fade time between states |
| Nightlight | Auto-dim timer with preset durations (auto-turns on device) |
| Sync | UDP sync between WLED devices (send mode) |
| Live Override | Enable/disable external UDP control |

### Global Commands
| Command | Description |
|---------|-------------|
| All On | Turn on all WLED devices |
| All Off | Turn off all WLED devices |
| Set All Brightness | Set brightness for all devices |
| Set All Effect | Apply same effect to all devices |

### ISY Integration
- Full status display in ISY Admin Console and eisy-ui
- Works with ISY programs, scenes, and schedules
- Effect/Palette/Preset dropdowns show names, not just numbers
- Plugin version displayed on Controller node

## Requirements

- Polyglot v3 (PG3) running on Polisy or eISY
- One or more WLED controllers (v0.13+)
- WLED devices accessible on local network (port 80)

## Installation

### From Polyglot Store (Recommended)
1. In PG3, go to the NodeServer Store
2. Search for "WLED"
3. Click Install

### From GitHub (Developer Mode)
1. SSH to your eISY/Polisy
2. Clone repository:
   ```bash
   git clone https://github.com/superflytnt/udi-wled-poly /home/admin/WLED-Improved
   ```
3. In PG3, add as Local plugin pointing to `/home/admin/WLED-Improved`

## Configuration

### Auto-Discovery (Recommended)
1. Click the **Discover Devices** button in PG3
2. All WLED devices on your network will be found and added automatically

### Manual Configuration
Add a Custom Parameter in PG3 Configuration:

| Key | Value |
|-----|-------|
| `devices` | `arcade:192.168.1.112,bar:192.168.1.185,kitchen:192.168.1.99` |

Format: `name1:ip1,name2:ip2,name3:ip3`

## Node Commands

### Controller Node
| Command | Description |
|---------|-------------|
| Discover Devices | Scan network for WLED devices |
| Rebuild Presets | Refresh preset/effect names from all devices |
| All On | Turn on all devices |
| All Off | Turn off all devices |
| Set All Brightness | Set brightness for all devices (0-100%) |
| Set All Effect | Apply effect to all devices |
| Query | Update all device status |

### WLED Device Node
| Command | Description |
|---------|-------------|
| On | Turn on (optionally with brightness %) |
| Off | Turn off |
| Fast On/Off | Instant on/off (no transition) |
| Brighten/Dim | Increase/decrease brightness by 10% |
| Set Brightness | Set brightness 0-100% |
| Set Effect | Select from 180+ effects |
| Set Palette | Select from 70+ palettes |
| Set Color | Set RGB color |
| Load Preset | Load a saved preset |
| Save Preset | Save current state to a preset slot |
| Set Speed | Effect animation speed (0-100%) |
| Set Intensity | Effect intensity/size (0-100%) |
| Set Transition | Fade time in 100ms units (0-255) |
| Nightlight | Set auto-dim timer (Off, 15, 30, 45, 60, 90, 120 min) |
| Sync | UDP sync mode (Off, Send) |
| Live Override | Enable/disable external UDP control |
| Start/Stop Playlist | Control WLED playlists |
| Rebuild Presets | Refresh presets from this device |
| Query | Update device status |

## Status Values

### Controller Node
| Status | Description |
|--------|-------------|
| ST | Status (On/Off) |
| GV0 | Device Count |
| GV1 | Plugin Version |
| GV2 | Online Count |
| GV3 | Devices On |
| GV4 | Total LEDs |

### WLED Device Node
| Status | Description |
|--------|-------------|
| ST | Power (On/Off) |
| GV0 | Brightness (0-100%) |
| GV1 | Current Effect |
| GV2 | Current Palette |
| GV3 | Current Preset |
| GV4-GV6 | RGB Color values (Red, Green, Blue) |
| GV7 | Online status |
| GV8 | Speed (0-100%) |
| GV9 | Intensity (0-100%) |
| GV10 | Transition (100ms units) |
| GV11 | Live Override active |
| GV12 | Nightlight (Off or duration in minutes) |
| GV13 | Sync (Off or Send) |

## Troubleshooting

### Device Not Found During Discovery
- Ensure WLED device is powered on and connected to network
- Check that eISY/Polisy is on the same subnet as WLED devices
- Try adding device manually with IP address

### Commands Not Working
- Check WLED web interface is accessible at `http://<device-ip>`
- Verify WLED firmware is v0.13 or newer
- Check PG3 logs for error messages

### Effects/Presets Showing Numbers Only
- Click "Rebuild Presets" on the controller node
- Click "Load Profile" in PG3
- Restart ISY Admin Console

### Sync Receive Not Working
- This is a known limitation in WLED firmware (v0.15.2)
- The WLED JSON API does not save the receive setting
- Only Send mode is supported

## Version History

### v1.5.1 (2025-12-02)
- Auto-rebuild effect metadata on startup (survives git pulls)
- Fixed palette detection in effect metadata

### v1.5.0 (2025-12-02)
- Added global commands: All On, All Off, Set All Brightness, Set All Effect
- Added Controller stats: Online Count, Devices On, Total LEDs
- Controller stats update instantly when device power changes

### v1.4.9 (2025-12-02)
- Added Online Count and Devices On stats to Controller
- Moved Online status to prominent position on device nodes

### v1.4.8 (2025-12-02)
- Optimized discovery: mDNS primary + improved HTTP probe
- Added retry logic for missed devices
- Detailed discovery logging

### v1.4.7 (2025-12-02)
- Added per-device Rebuild Presets button
- Removed redundant Nightlight On/Off buttons

### v1.4.6 (2025-12-01)
- Combined Sync Send/Receive into single Sync command
- Simplified to Off/Send due to WLED API limitation

### v1.4.5 (2025-12-01)
- Added plugin version display to Controller node

### v1.4.4 (2025-12-01)
- Nightlight auto-turns on device when timer is set
- Renamed command to "Nightlight"

### v1.4.3 (2025-12-01)
- Added Nightlight dropdown with preset durations
- Setting to 0/Off turns nightlight off

### v1.4.2 (2025-12-01)
- Removed redundant Set NL Duration command

### v1.4.1 (2025-12-01)
- Fixed display issues with combined status cells
- Reverted RGB and Speed/Intensity to separate cells
- Fixed Nightlight and Sync display with correct UOMs

### v1.4.0 (2025-12-01)
- Attempted combined status cells (partially reverted)

### v1.3.0 (2025-12-01)
- Added Save Preset, Playlists, Nightlight, and Sync controls
- Preset loading updates all status values

### v1.2.0 (2025-12-01)
- Added Speed, Intensity, Transition, and Live Override controls

### v1.1.0 (2025-12-01)
- Added effect metadata (1D/2D, Palette, Volume, Frequency)
- Added parallel auto-discovery
- Improved configuration documentation

### v1.0.0 (2025-12-01)
- Initial release
- Basic WLED control (power, brightness, effects, palettes, presets, color)
- Auto-discovery and manual configuration

## Links

- **Source Code:** https://github.com/superflytnt/udi-wled-poly
- **Report Issues:** https://github.com/superflytnt/udi-wled-poly/issues
- **WLED Project:** https://kno.wled.ge/
- **Universal Devices:** https://www.universal-devices.com/
- **UDI Forum:** https://forum.universal-devices.com/

## License

MIT License — See [LICENSE](LICENSE) file

## Credits

- **WLED Project** — https://kno.wled.ge/
- **Universal Devices** — https://www.universal-devices.com/
- **udi-interface** — Python interface for Polyglot v3
