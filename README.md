# WLED Polyglot NodeServer

A Polyglot v3 (PG3) NodeServer for Universal Devices ISY that provides full control of WLED LED controllers.

## Features

- **Multi-device support** - Control multiple WLED devices from a single nodeserver
- **Automatic Discovery** - Find WLED devices on your network via mDNS
- **Manual Configuration** - Add devices by IP address
- **Full WLED Control**:
  - On/Off/Toggle
  - Brightness (0-255)
  - RGB Color control
  - Effect selection (100+ effects)
  - Palette selection (50+ palettes)
  - Preset management
  - Segment control
  - Sync settings

## Requirements

- Polyglot v3 (PG3) running on Polisy or eISY
- One or more WLED controllers on your network
- Python 3.9+

## Installation

### From PG3 Store (Recommended)
1. Open the PG3 dashboard
2. Navigate to NodeServer Store
3. Search for "WLED"
4. Click Install

### Manual Installation
1. Clone this repository to your PG3 nodeserver directory
2. Run `./install.sh` to install dependencies
3. Restart the nodeserver

## Configuration

### Adding Devices

**Automatic Discovery:**
1. Click "Discover" on the controller node
2. All WLED devices on your network will be detected and added

**Manual Addition:**
1. In the nodeserver configuration, add devices in the format:
   ```
   name1:192.168.1.100,name2:192.168.1.101
   ```

### Configuration Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `shortPoll` | Status update interval (seconds) | 30 |
| `longPoll` | Full device sync interval (seconds) | 120 |
| `devices` | Manual device list (name:ip pairs) | empty |

## Node Types

### Controller
The main controller node manages device discovery and configuration.

**Commands:**
- Discover - Scan network for WLED devices
- Query - Refresh all device status

### WLED Device
Each WLED controller appears as a device node.

**Status:**
- Power (On/Off)
- Brightness (0-100%)
- Effect (current effect name)
- Palette (current palette name)
- Preset (current preset number)
- Online (connection status)

**Commands:**
- On / Off / Toggle
- Set Brightness
- Set Effect
- Set Palette
- Set Color (RGB)
- Load Preset

### Segment (Optional)
Individual LED segments can be controlled separately.

**Status:**
- Power, Brightness, Effect, Color

**Commands:**
- On/Off, Set Brightness, Set Effect, Set Color

## WLED API

This nodeserver uses the WLED JSON API for full feature support:
- `GET /json` - Get current state
- `POST /json/state` - Set state
- `GET /json/info` - Device information
- `GET /json/effects` - Available effects
- `GET /json/palettes` - Available palettes

## Troubleshooting

### Device Not Responding
1. Verify WLED device is accessible at its IP address
2. Check that WLED firmware is up to date
3. Ensure no firewall is blocking port 80

### Discovery Not Finding Devices
1. Ensure WLED devices have mDNS enabled
2. Check that devices are on the same network/VLAN
3. Try manual IP configuration

## License

MIT License - See LICENSE file

## Credits

- WLED Project: https://kno.wled.ge/
- Universal Devices: https://www.universal-devices.com/
- Polyglot v3: https://github.com/UniversalDevicesInc-PG3

