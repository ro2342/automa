# LNXlink GUI

A **GNOME/GTK4 + libadwaita** control panel for the [LNXlink](https://github.com/bkbilly/lnxlink) MQTT agent — the Linux equivalent of HASS.Agent for Windows.

---

## Features

| Section | What it does |
|---|---|
| **Dashboard** | Shows `lnxlink.service` status (Running / Stopped / Failed) with Start / Stop / Restart buttons and a live service log. |
| **MQTT Config** | Edits broker host, port, credentials and discovery prefix directly in `config.yaml`. |
| **Sensors** | Toggles hardware/desktop sensor modules on or off via the `modules.exclude` list in the YAML. |
| **Commands** | Full CRUD interface for `custom_commands` — add Bash scripts that Home Assistant can trigger. |
| **System Tray** | Lives in the StatusNotifier tray; closing the window hides it rather than quitting. |

---

## Prerequisites

### Runtime
- **LNXlink** installed separately (e.g. via pip or your distro's package manager).
- A `lnxlink.service` systemd **user** unit (LNXlink creates this automatically on first run with `--service install`).
- GNOME desktop with Wayland or X11.

### Python dependencies (outside Flatpak)
```bash
# Fedora / RHEL
sudo dnf install python3-gobject gtk4 libadwaita python3-pip

# Debian / Ubuntu
sudo apt install python3-gi gir1.2-gtk-4.0 gir1.2-adw-1 python3-pip

# AppIndicator (optional, for system tray)
# Fedora:
sudo dnf install libayatana-appindicator-gtk3

pip install ruamel.yaml
```

---

## Running (Development / Without Flatpak)

```bash
git clone <this-repo>
cd lnxlink-gui
pip install ruamel.yaml
python3 main.py
```

---

## Building & Installing as Flatpak

### 1. Install build tools
```bash
flatpak install flathub org.gnome.Platform//46 org.gnome.Sdk//46
sudo dnf install flatpak-builder   # or apt install flatpak-builder
```

### 2. Fix source checksums
Before building, update the `sha256` fields in `io.github.lnxlink.automa.json`
for `ruamel.yaml`, `ruamel.yaml.clib`, and `libayatana-appindicator` by
downloading the tarballs and running `sha256sum` on them.

### 3. Build
```bash
flatpak-builder --user --install --force-clean build-dir io.github.lnxlink.automa.json
```

### 4. Run
```bash
flatpak run io.github.lnxlink.automa
```

---

## Flatpak Sandbox — How systemctl Access Works

The Flatpak sandbox normally prevents direct access to the host's systemd
session. This app escapes the sandbox using **two complementary mechanisms**:

### Option A — `flatpak-spawn --host` (used by default)
All `systemctl --user …` calls in `service_manager.py` are prefixed with
`flatpak-spawn --host` when the `FLATPAK_ID` environment variable is set.
This executes the command on the **host system** outside the sandbox.

**Required manifest permission:**
```json
"--talk-name=org.freedesktop.Flatpak"
```

### Option B — DBus `org.freedesktop.systemd1`
The systemd DBus API is exposed through the sandbox via:
```json
"--talk-name=org.freedesktop.systemd1"
```
This is a more targeted approach (included in the manifest as a fallback).

### Config file access
```json
"--filesystem=~/.config/lnxlink:rw"
```
Grants read/write access to the LNXlink config directory only —
following the principle of least privilege.

---

## File Structure

```
lnxlink-gui/
├── main.py                          # App entry point, window, tray
├── config_manager.py                # YAML read/write with ruamel.yaml
├── service_manager.py               # systemctl wrapper + Flatpak escape
├── pages/
│   ├── __init__.py
│   ├── dashboard.py                 # Service status & control
│   ├── mqtt_config.py               # MQTT broker settings form
│   ├── sensors.py                   # Sensor module toggles
│   └── commands.py                  # Custom commands CRUD
├── data/
│   ├── lnxlink-gui.sh               # Flatpak launcher script
│   ├── io.github.lnxlink.automa.desktop
│   ├── io.github.lnxlink.automa.metainfo.xml
│   └── icons/hicolor/scalable/apps/
│       └── io.github.lnxlink.automa.svg
└── io.github.lnxlink.automa.json      # Flatpak manifest
```

---

## License

GPL-3.0-or-later
