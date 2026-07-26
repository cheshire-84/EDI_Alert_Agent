<div align="center">
  <img src="assets/app_logo.png" alt="EDI Agent Logo" width="128" />
  <h1>EDI Agent (v1.5.0)</h1>
  <p>Lightweight LAN Node Monitoring Daemon for Fedora KDE Plasma</p>
</div>

**EDI Agent** is a lightweight, background LAN node monitoring daemon and desktop application built specifically for **Fedora KDE Plasma** (and Qt/systemd-based Linux desktops). 

It periodically monitors local infrastructure nodes (Proxmox, Plex, internal web applications, databases, etc.) using non-intrusive ICMP pings — or an optional TCP port check to verify a specific service is actually running, not just that the host is reachable — and delivers native desktop notification popups over DBus whenever a node drops offline or recovers.

---

## Key Features

* **Native KDE Plasma System Tray:** Integrates seamlessly near the desktop clock using PySide6 (Qt6) with custom branding, and a live green/red health badge on the icon itself.
* **Non-Intrusive Ping Strategy:** Concurrent ICMP checks every 30 seconds (the daemon's tick rate) with 1-second strict timeouts to prevent network bottlenecks.
* **Per-Node Check Interval & Alert Threshold:** Override the default 30s check interval or 2-strike alert threshold on any individual node — e.g. check a flaky IoT device every 5 minutes, or alert instantly on a critical database.
* **Optional Service-Level Port Checks:** Monitor a specific TCP port instead of ICMP (e.g. `5432` for PostgreSQL, `32400` for Plex, `8006` for Proxmox) to confirm the actual service is up, not just the host.
* **Configurable Failure Threshold:** Requires 2 consecutive failed checks (by default) before triggering a critical desktop popup, to prevent false alarms over Wi-Fi. Adjustable per node.
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
├── tests/
│   └── test_edi_agent.py  # pytest unit tests for CLI, config, and check logic
├── conftest.py          # Shared pytest fixtures (isolates tests from your real config)
├── edi_agent.py         # Core monitoring daemon & tray application logic
├── install.sh           # One-click automated setup & systemd service installer
├── uninstall.sh         # Removes the service, CLI wrapper, and venv
├── LICENSE              # Open-source MIT License
├── manual.py            # Interactive PySide6 Help & User Manual window
├── README.md            # Project documentation
├── requirements.txt     # Python dependency manifest (PySide6)
└── requirements-dev.txt # Adds pytest for running the test suite
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

*To remove EDI Agent later, run `./uninstall.sh` — it stops the service, removes the CLI wrapper and venv, and optionally clears your saved node list.*

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
| **Add Node** | `edi-agent add <name> <ip> [--port PORT] [--interval SEC] [--threshold N] [--force]` | Validates IP format and reachability immediately, then registers node. `--port` checks a TCP port instead of ICMP ping. `--interval` sets how often this node is checked (default 30s, minimum 5s). `--threshold` sets how many consecutive failures trigger an alert (default 2). Refuses to overwrite an existing node unless `--force` is passed. |
| **Remove Node** | `edi-agent remove <name>` | Unregisters node from the active registry. |
| **Edit Node** | `edi-agent edit <name> [--ip IP] [--port PORT] [--clear-port] [--interval SEC] [--threshold N]` | Updates a node's IP, port check, interval, and/or threshold in place and re-validates it immediately. `--clear-port` reverts the node back to ICMP ping. |
| **List Nodes** | `edi-agent list` | Displays a table of all tracked nodes, their check method (ping or TCP port), status, failures/threshold, check interval, latency, and when they were last checked. |
| **Test Alert** | `edi-agent test` | Triggers a test desktop popup notification over DBus. |
| **Alert History** | `edi-agent history [--limit N]` | Shows the most recent offline/recovery events (default 20), newest first. |
| **Open Help** | `edi-agent help` | Opens the interactive PySide6 manual window. |
| **Run GUI** | `edi-agent gui` | Launches background tray app directly (used by systemd). |

### CLI Examples

```bash
# Add new nodes with instant reachability check
edi-agent add gateway 10.1.1.1
edi-agent add pve-server 10.1.1.3
edi-agent add plex 10.1.1.99

# Add nodes with a service-level TCP port check instead of ICMP ping
edi-agent add plex 10.1.1.99 --port 32400       # Plex Media Server
edi-agent add edi-database 10.1.1.20 --port 5432  # PostgreSQL
edi-agent add pve-server 10.1.1.3 --port 8006   # Proxmox VE web UI

# Add nodes with a custom check interval or alert threshold
edi-agent add iot-sensor 10.1.1.200 --interval 300   # only check every 5 minutes
edi-agent add edi-database 10.1.1.20 --port 5432 --threshold 1  # alert on the first failure

# Edit a node in place (no need to remove + re-add)
edi-agent edit plex --ip 10.1.1.150       # host got a new IP
edi-agent edit gateway --port 22          # switch to a TCP port check
edi-agent edit gateway --clear-port       # revert back to ICMP ping
edi-agent edit iot-sensor --interval 600  # check even less often
edi-agent edit edi-database --threshold 3 # require 3 failures before alerting

# List monitored hosts
edi-agent list

# Send a test desktop notification
edi-agent test

# See the last 20 offline/recovery events
edi-agent history

# Open built-in interactive manual
edi-agent help
```

---

## Graphical Interface & System Tray

* **System Tray Dock:** Sits by the system clock with custom branding. The icon shows a **GREEN** badge when every node is online and a **RED** badge if any node is down, with a tooltip summarizing fleet health. Right-clicking the tray icon opens the context menu to launch the status window, open the manual, trigger a test notification, or quit the application.
* **Status Window:** Displays all registered hosts in a clean, sortable table (click any column header) with color-coded status badges (**GREEN** for `ONLINE`, **RED** for `OFFLINE`), the check method (ping or TCP port), failures/threshold, check interval, latency, and last-checked time per node.
* **Edit Node:** Double-click any row (or select it and click **Edit Selected**) to change a node's IP or check method without dropping to the terminal. Re-validates the node as soon as you save.
* **Alert History:** A dedicated window (via the tray menu or the **Alert History** button in the Status Window) listing every offline/recovery event with a timestamp, so you can see what happened even after the desktop popup is gone. Includes a **Clear History** option.
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
      "port": null,
      "check_interval": 30,
      "failure_threshold": 2,
      "status": "online",
      "failures": 0,
      "last_checked": 1753500000.0,
      "latency_ms": 1.8
    },
    "plex": {
      "ip": "10.1.1.99",
      "port": 32400,
      "check_interval": 30,
      "failure_threshold": 2,
      "status": "online",
      "failures": 0,
      "last_checked": 1753500000.0,
      "latency_ms": 4.2
    }
  }
}
```

> **Note:** `port` is `null` for nodes checked via ICMP ping, or a TCP port number for nodes checked via a service-level port test. `check_interval` (seconds) and `failure_threshold` (consecutive failures) default to 30 and 2 but can be overridden per node.

> **Note:** `last_checked` is a Unix timestamp; `latency_ms` is `null` while a node is offline.

> **Note:** The background service watches this file continuously. Adding or removing nodes via the CLI immediately updates the background daemon without requiring a service restart.

Offline/recovery alert history is stored separately at `~/.config/edi-alert-agent/history.json`, capped at the 200 most recent events.

---

## Diagnostics & Troubleshooting

* **`edi-agent: command not found`:** Ensure `~/.local/bin` is in your shell `$PATH`. Add `export PATH="$HOME/.local/bin:$PATH"` to your `~/.bashrc`.
* **Notifications Not Appearing:** Ensure `libnotify` is installed on your system (`sudo dnf install libnotify`) and test via `notify-send "Test" "Message"`.
* **Inspect Service Logs:** Run `journalctl --user -u edi-alert-agent.service -f` to view live execution logs and ping outputs.

---

## Development & Testing

Unit tests cover the CLI commands, config persistence, and reachability-check logic (mocked, so tests never touch the network or your real `nodes.json`):

```bash
source venv/bin/activate
pip install -r requirements-dev.txt
pytest
```

---

## License

This project is licensed under the **MIT License**. See the [LICENSE](LICENSE) file for details.