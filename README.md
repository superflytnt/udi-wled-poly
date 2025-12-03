# WLED Polyglot v3 NodeServer

[![Version](https://img.shields.io/badge/version-1.5.4-blue.svg)](https://github.com/superflytnt/udi-wled-poly)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![WLED](https://img.shields.io/badge/WLED-v0.13+-orange.svg)](https://kno.wled.ge/)

Control your WLED LED strips directly from your Universal Devices ISY or eISY. This Polyglot v3 NodeServer provides complete integration with WLED controllers, bringing all your addressable LEDs into your home automation system.

## Quick Start

1. **Install** the plugin from the PG3 NodeServer Store (search "WLED")
2. **Click "Discover Devices"** to automatically find all WLED controllers on your network
3. **Control your lights** from ISY Admin Console, eisy-ui, or ISY programs

That's it! Your WLED devices will appear as nodes you can control just like any other ISY device.

---

## What Can You Control?

| Feature | What It Does |
|---------|--------------|
| **Power** | Turn lights on/off, with optional brightness level |
| **Brightness** | Dim from 0-100% |
| **180+ Effects** | Rainbow, Fire, Chase, Twinkle, and many more |
| **70+ Palettes** | Color schemes for effects |
| **Presets** | Save and load your favorite configurations |
| **Colors** | Set specific RGB colors |
| **Speed & Intensity** | Fine-tune how effects look |
| **Nightlight** | Auto-dim timer (15 min to 2 hours) |
| **Sync** | Synchronize multiple WLED devices together |

### Global Controls (Controller Node)

Control all your WLED devices at once from the Controller node:
- **On / Off** — Turn all devices on or off (works in scenes!)
- **Brighten / Dim** — Adjust all devices by ~10%
- **All Brightness** — Set all devices to specific brightness
- **All Effect** — Apply the same effect to every device

The Controller works as a **scene responder** — add it to an ISY scene and On/Off/Brighten/Dim will control all WLED devices.

---

## Requirements

- **Polyglot v3** running on Polisy or eISY
- **WLED controllers** running firmware v0.13 or newer
- Devices must be on the same network as your Polisy/eISY

---

## Installation

### From the NodeServer Store (Recommended)

1. Open PG3 and go to **NodeServer Store**
2. Search for **"WLED"**
3. Click **Install**
4. After installation, click **Discover Devices**

### Manual Installation (Developers)

```bash
# SSH to your eISY/Polisy
ssh admin@your-eisy-ip

# Clone the repository
git clone https://github.com/superflytnt/udi-wled-poly /home/admin/wled-poly

# In PG3, add as Local plugin with path: /home/admin/wled-poly
```

---

## Configuration

### Automatic Discovery (Recommended)

Click **"Discover Devices"** on the WLED Controller node. The plugin will scan your network and automatically add all WLED devices it finds.

> **Tip:** If a device isn't found, make sure it's powered on and connected to your network. You can also try clicking Discover again — some devices may take a moment to respond.

### Manual Configuration

If auto-discovery doesn't find a device, you can add it manually:

1. Go to **Configuration** in PG3
2. Add a **Custom Parameter**:

| Key | Value |
|-----|-------|
| `devices` | `kitchen:192.168.1.100,bedroom:192.168.1.101` |

**Format:** `name:ip,name:ip,name:ip`

- **name** = What you want to call the device (no spaces)
- **ip** = The device's IP address

---

## Using the Plugin

### Controller Node

The main controller shows an overview of all your WLED devices:

| Status | Meaning |
|--------|---------|
| Devices | Total number of configured WLED devices |
| Online | How many devices are currently reachable |
| On | How many devices are currently turned on |
| Total LEDs | Combined LED count across all devices |
| Avg Brightness | Average brightness across all online devices (0-100%) |
| Effect | Last effect set via "All Effect" command |
| Version | Plugin version |

**Commands:**
- **On / Off** — Turn all devices on or off (scene-compatible)
- **Brighten / Dim** — Adjust all devices by ~10%
- **Discover** — Scan network for new WLED devices
- **Rebuild Presets** — Refresh effect names from devices
- **All Brightness** — Set brightness for all devices
- **All Effect** — Apply an effect to all devices

### Device Nodes

Each WLED device appears as its own node with full control:

| Status | Meaning |
|--------|---------|
| Power | On or Off |
| Online | Is the device reachable? |
| Brightness | Current brightness (0-100%) |
| Effect | Currently playing effect |
| Palette | Current color palette |
| Preset | Loaded preset (if any) |
| R / G / B | Current color values |
| Speed | Effect animation speed |
| Intensity | Effect intensity |
| Nightlight | Auto-dim timer status |
| Sync | UDP sync status |

**Commands:**
- **On / Off** — Basic power control
- **Set Brightness** — Adjust brightness
- **Set Effect** — Choose from 180+ effects
- **Set Palette** — Choose color palette for effects
- **Load Preset** — Load a saved configuration
- **Set Color** — Set RGB color values
- **Set Speed / Intensity** — Adjust effect parameters
- **Nightlight** — Set auto-dim timer (turns on device automatically)
- **Sync** — Enable UDP sync to other WLED devices
- **Rebuild Presets** — Refresh preset list from this device

---

## ISY Programs

You can use WLED devices in ISY programs just like any other device:

```
If
    Time is Sunset
Then
    Set 'WLED / Kitchen' On
    Set 'WLED / Kitchen' Set Effect Rainbow
    Set 'WLED / Kitchen' Set Brightness 75%
```

```
If
    'WLED / Kitchen' is On
Then
    Set 'Living Room Lamp' On
```

---

## Troubleshooting

### Devices Not Found During Discovery

- **Check power** — Is the WLED device powered on?
- **Check network** — Can you access the WLED web interface at `http://device-ip`?
- **Same subnet** — Your eISY/Polisy must be on the same network subnet
- **Try manual config** — Add the device manually using its IP address

### Effects/Presets Show Numbers Instead of Names

1. Click **"Rebuild Presets"** on the Controller node
2. In PG3, click **"Load Profile"**
3. Restart ISY Admin Console (or refresh eisy-ui)

### Commands Not Working

- Verify WLED firmware is **v0.13 or newer**
- Check the WLED web interface works at `http://device-ip`
- Check PG3 logs for error messages

---

## Technical Limitations

These are known platform or firmware limitations that affect how the plugin works.

### Device Discovery Uses Network Scanning (Not mDNS)

The standard way to discover WLED devices is via mDNS (Bonjour), but the eISY/Polisy system already uses the mDNS port (5353) for its own services. This plugin uses **direct IP scanning** instead, which scans the local subnet for devices responding to WLED API requests. Discovery may take 10-15 seconds but works reliably without port conflicts.

### Preset Names Are Generic (Not Device-Specific)

The UDI Polyglot platform uses a single shared NLS (National Language Support) file for all nodes of the same type. This means the preset dropdown shows the same labels for every WLED device—it's impossible to show device-specific preset names like "Party Mode" on one device and "Movie Lights" on another.

**Workaround:** Presets are shown as generic IDs (1, 2, 3...). Refer to each WLED device's web interface to see what each preset number means for that device.

### Sync "Receive" Mode Not Available

WLED firmware (tested on v0.15.2) has a bug where the JSON API doesn't properly save the "receive" sync setting. The API call succeeds but the setting doesn't persist. Only "Send" sync mode is supported through this plugin.

**Workaround:** Configure sync receive settings directly through the WLED web interface.

### Save Preset Not Supported

The WLED JSON API's `psave` command for saving presets doesn't work reliably across different firmware versions. The command was removed from this plugin to avoid confusion.

**Workaround:** Save presets directly through the WLED web interface.

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| **1.5.4** | 2025-12-03 | Controller status: Avg Brightness & Effect display, cleaned up redundant commands |
| **1.5.3** | 2025-12-03 | Scene support: Controller responds to On/Off/Brighten/Dim for use as scene responder |
| **1.5.2** | 2025-12-03 | Generic preset IDs (per-device presets), removed Save Preset, reordered status fields |
| **1.5.1** | 2025-12-02 | Effect metadata auto-rebuilds on startup |
| **1.5.0** | 2025-12-02 | Global commands (All On/Off, Set All), Controller stats |
| **1.4.x** | 2025-12-01 | Nightlight auto-on, combined Sync control, per-device rebuild |
| **1.3.0** | 2025-12-01 | Playlists, Nightlight, Sync controls |
| **1.2.0** | 2025-12-01 | Speed, Intensity, Transition, Live Override |
| **1.1.0** | 2025-12-01 | Effect metadata, parallel discovery |
| **1.0.0** | 2025-12-01 | Initial release |

---

## Links

| Resource | URL |
|----------|-----|
| **Source Code** | https://github.com/superflytnt/udi-wled-poly |
| **Report Issues** | https://github.com/superflytnt/udi-wled-poly/issues |
| **WLED Project** | https://kno.wled.ge/ |
| **Universal Devices** | https://www.universal-devices.com/ |
| **UDI Forum** | https://forum.universal-devices.com/ |

---

## License

MIT License — See [LICENSE](LICENSE) file

## Credits

- [WLED Project](https://kno.wled.ge/) — The amazing LED controller firmware
- [Universal Devices](https://www.universal-devices.com/) — ISY and Polyglot platform
- [udi-interface](https://pypi.org/project/udi-interface/) — Python interface for Polyglot v3
