# WLED Polyglot v3 NodeServer

[![Version](https://img.shields.io/badge/version-1.2.0-blue.svg)](https://github.com/superflytnt/udi-wled-poly)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

A Polyglot v3 (PG3) NodeServer for Universal Devices ISY/eISY that provides full control of WLED LED controllers.

## Features

### Device Management
- **Multi-device support** — Control unlimited WLED devices from a single nodeserver
- **Auto-Discovery** — Parallel network scan finds all WLED devices in seconds
- **Manual Configuration** — Add devices by name and IP address
- **Real-time Status** — See power, brightness, effect, palette, and preset status

### WLED Control
| Feature | Description |
|---------|-------------|
| Power | On/Off/Toggle with optional brightness |
| Brightness | 0-100% dimming |
| Effects | 180+ effects with type indicators (1D/2D, Palette, Audio) |
| Palettes | 70+ color palettes |
| Presets | Load saved presets (names auto-populated from devices) |
| Color | RGB color control |
| Speed | Effect animation speed |
| Intensity | Effect intensity/size |

### ISY Integration
- Full status display in ISY Admin Console and eisy-ui
- Works with ISY programs, scenes, and schedules
- Effect/Palette/Preset dropdowns show names, not just numbers

## Requirements

- Polyglot v3 (PG3) running on Polisy or eISY
- One or more WLED controllers (v0.13+)
- WLED devices accessible on local network (port 80)

## Installation

### From Local (Developer Mode)
1. SSH to your eISY/Polisy
2. Clone repository:
   ```bash
   git clone https://github.com/superflytnt/udi-wled-poly /home/admin/WLED-Improved
   ```
3. In PG3, add as Local plugin pointing to `/home/admin/WLED-Improved`

### Manual Installation
1. Clone this repository to your PG3 nodeserver directory
2. Run `./install.sh` to install dependencies
3. Add as Local plugin in PG3

## Configuration

### Auto-Discovery (Recommended)
1. Click the **Discover** button in PG3
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
| Discover | Scan network for WLED devices |
| Rebuild Presets | Refresh preset/effect names from devices |
| Query | Update all device status |

### WLED Device Node
| Command | Description |
|---------|-------------|
| On | Turn on (optionally with brightness %) |
| Off | Turn off |
| Fast On/Off | Instant on/off (no transition) |
| Set Brightness | Set brightness 0-100% |
| Set Effect | Select from 180+ effects |
| Set Palette | Select from 70+ palettes |
| Set Color | Set RGB color |
| Load Preset | Load a saved preset |
| Set Speed | Effect animation speed (0-100%) |
| Set Intensity | Effect intensity/size (0-100%) |
| Set Transition | Fade time in 100ms units (0-255) |
| Live Override | Enable/disable external UDP control |

## Status Values

| Status | Description |
|--------|-------------|
| ST | Power (On/Off) |
| GV0 | Brightness (0-100%) |
| GV1 | Current Effect |
| GV2 | Current Palette |
| GV3 | Current Preset |
| GV4-GV6 | RGB Color values |
| GV7 | Online status |
| GV8 | Speed (0-100%) |
| GV9 | Intensity (0-100%) |
| GV10 | Transition (100ms units) |
| GV11 | Live Override active |

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

## Version History

### v1.2.0 (2025-12-01)
- Added Speed control (effect animation speed)
- Added Intensity control (effect size/intensity)
- Added Transition Time control (fade duration)
- Added Live Override control (enable/disable external UDP control)
- New status displays: Speed, Intensity, Transition, Live Override
- Real-time segment data display

### v1.1.0 (2025-12-01)
- Added effect metadata (1D/2D, Palette, Volume, Frequency indicators)
- Added parallel auto-discovery (scans network in ~5 seconds)
- Added Rebuild Presets command
- Improved notices with discovery results
- Better configuration documentation
- Fixed Discover button in PG3

### v1.0.0 (2025-12-01)
- Initial release
- Basic WLED control (power, brightness, effects, palettes, presets, color)
- Auto-discovery and manual configuration
- Multi-device support

## Links

- **Source Code:** https://github.com/superflytnt/udi-wled-poly
- **Report Issues:** https://github.com/superflytnt/udi-wled-poly/issues
- **WLED Project:** https://kno.wled.ge/
- **Universal Devices:** https://www.universal-devices.com/

## License

MIT License — See [LICENSE](LICENSE) file

## Credits

- **WLED Project** — https://kno.wled.ge/
- **Universal Devices** — https://www.universal-devices.com/
- **udi-interface** — Python interface for Polyglot v3
