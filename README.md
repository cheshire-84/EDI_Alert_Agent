<div align="center">
  <img src="assets/app_logo.png" alt="EDI Agent Logo" width="128" />
  <h1>EDI Agent (v1.0.1)</h1>
  <p>Lightweight LAN Node Monitoring Daemon for Fedora KDE Plasma</p>
</div>

**EDI Agent** is a lightweight, background LAN node monitoring daemon and desktop application built specifically for **Fedora KDE Plasma** (and Qt/systemd-based Linux desktops). 

It periodically monitors local infrastructure nodes (Proxmox, Plex, internal web applications, databases, etc.) using non-intrusive ICMP pings and delivers native desktop notification popups over DBus whenever a node drops offline or recovers.

---

## Key Features

* **Native KDE Plasma System Tray:** Integrates seamlessly near the desktop clock using PySide6 (Qt6) with custom branding.
* **Non-Intrusive Ping Strategy:** Asynchronous ICMP checks every 30 seconds with 1-second strict timeouts to prevent network bottlenecks.
* **3-Strike Failure Protection:** Requires 2 consecutive failed pings before triggering a critical desktop popup to prevent false alarms over Wi-Fi.
* **Unified CLI & GUI:** Full control from any terminal (`edi-agent`) alongside a tray-docked GUI featuring real-time refresh capability.
* **Instant Reachability Validation:** Automatically tests host reachability immediately when adding new nodes via the CLI.
* **Built-In Interactive Manual:** Includes a standalone documentation GUI (`manual.py`) accessible via terminal command (`edi-agent help`) or the header **`?`** button in the UI.
* **Systemd User Service:** Runs silently in the background as an unprivileged user daemon that automatically starts on boot.

---

## Project Structure

```text
EDI_Alert_Agent/
├── assets/
│   └── app_logo.png     # Application branding icon (Tray, Window Header, Notifications)
├── edi_agent.py         # Core monitoring daemon & tray application logic
├── install.sh           # One-click automated setup & systemd service installer
├── LICENSE              # Open-source MIT License
├── manual.py            # Interactive PySide6 Help & User Manual window
├── README.md            # Project documentation
└── requirements.txt     # Python dependency manifest (PySide6)
```

---

## Quick Start / Installation

### Option A: One-Click Automated Setup (Recommended)

1. **Clone the repository:**
```bash
git clone git@github.com:cheshire-84/EDI_Alert_Agent.git ~/Projects/EDI_Alert_Agent
cd ~/Projects/EDI_Alert_Agent
```

2. **Run the installation script:**
```bash
chmod +x install.sh
./install.sh
```

*The installer automatically builds the Python virtual environment, installs dependencies, links `edi-agent` to `~/.local/bin`, and registers/enables the `edi-alert-agent.service` systemd user daemon.*

3. **Verify the background service:**
```bash
systemctl --user status edi-alert-agent.service
```

---

### Option B: Manual Setup

1. **Create and activate a virtual environment:**
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

2. **Create the global executable wrapper:**
```bash
mkdir -p ~/.local/bin
cat << EOF > ~/.local/bin/edi-agent
#!/bin/bash
$(pwd)/venv/bin/python $(pwd)/edi_agent.py "\$@"
EOF
chmod +x ~/.local/bin/edi-agent
```

3. **Register the Systemd User Service:**
```bash
mkdir -p ~/.config/systemd/user
cat << EOF > ~/.config/systemd/user/edi-alert-agent.service
[Unit]
Description=EDI Alert Agent LAN Node Monitor
After=graphical-session.target network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=$(pwd)/venv/bin/python $(pwd)/edi_agent.py gui
Restart=on-failure
RestartSec=5s

[Install]
WantedBy=graphical-session.target
EOF

systemctl --user daemon-reload
systemctl --user enable --now edi-alert-agent.service

```

---

## Command Line Interface (CLI)

Once installed, the `edi-agent` command can be called from any terminal prompt across your system:

| Command | Usage | Description |
| --- | --- | --- |
| **Add Node** | `edi-agent add <name> <ip> [--force]` | Validates IP format and reachability immediately, then registers node. Refuses to overwrite an existing node unless `--force` is passed. |
| **Remove Node** | `edi-agent remove <name>` | Unregisters node from the active registry. |
| **List Nodes** | `edi-agent list` | Displays a table of all tracked nodes and their status. |
| **Test Alert** | `edi-agent test` | Triggers a test desktop popup notification over DBus. |
| **Open Help** | `edi-agent help` | Opens the interactive PySide6 manual window. |
| **Run GUI** | `edi-agent gui` | Launches background tray app directly (used by systemd). |

### CLI Examples

```bash
# Add new nodes with instant reachability check
edi-agent add gateway 10.1.1.1
edi-agent add pve-server 10.1.1.3
edi-agent add plex 10.1.1.99

# List monitored hosts
edi-agent list

# Send a test desktop notification
edi-agent test

# Open built-in interactive manual
edi-agent help
```

---

## Graphical Interface & System Tray

* **System Tray Dock:** Sits by the system clock with custom branding. Right-clicking the tray icon opens the context menu to launch the status window, open the manual, trigger a test notification, or quit the application.
* **Status Window:** Displays all registered hosts in a clean table with color-coded status badges (**GREEN** for `ONLINE`, **RED** for `OFFLINE`).
* **Refresh / Check Now:** Forces an on-demand re-ping of all registered hosts.
* **Help (`?`) Button:** Click the **`?`** button in the top-right header of the status window to pop open the interactive user manual.

---

## Configuration Storage

The node registry is stored as a clean JSON file at:

```text
~/.config/edi-alert-agent/nodes.json
```

Example configuration:

```json
{
  "nodes": {
    "gateway": {
      "ip": "10.1.1.1",
      "status": "online",
      "failures": 0
    },
    "plex": {
      "ip": "10.1.1.99",
      "status": "online",
      "failures": 0
    }
  }
}
```

> **Note:** The background service watches this file continuously. Adding or removing nodes via the CLI immediately updates the background daemon without requiring a service restart.

---

## Diagnostics & Troubleshooting

* **`edi-agent: command not found`:** Ensure `~/.local/bin` is in your shell `$PATH`. Add `export PATH="$HOME/.local/bin:$PATH"` to your `~/.bashrc`.
* **Notifications Not Appearing:** Ensure `libnotify` is installed on your system (`sudo dnf install libnotify`) and test via `notify-send "Test" "Message"`.
* **Inspect Service Logs:** Run `journalctl --user -u edi-alert-agent.service -f` to view live execution logs and ping outputs.

---

## License

This project is licensed under the **MIT License**. See the [LICENSE](LICENSE) file for details.