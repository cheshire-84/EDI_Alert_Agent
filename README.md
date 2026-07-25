# EDI Alert Agent 📡

**EDI Alert Agent** is a lightweight, background LAN node monitor designed specifically for **Fedora KDE Plasma**. It periodically checks local infrastructure nodes (Proxmox, Plex, internal web applications, databases, etc.) via ICMP pings and triggers native desktop popup notifications when a host drops offline or recovers.

---

## 🚀 Features

* **Native KDE Integration:** Uses PySide6 (Qt6) for seamless panel system tray integration near the clock.
* **Non-Intrusive Monitoring:** Asynchronous ICMP checks every 30 seconds with 1-second strict timeouts to prevent network bottlenecks.
* **3-Strike Failure Protection:** Requires 2 consecutive failed pings before triggering a critical desktop popup to prevent false alarms over Wi-Fi.
* **Unified CLI & GUI:** Full control from any terminal (`edi-agent`) alongside a tray-docked GUI with real-time refresh capability.
* **Instant Reachability Validation:** Validates host reachability immediately when adding nodes via the CLI.
* **Systemd User Daemon:** Runs continuously in the background as an unprivileged user service that starts on boot.

---

## 📂 Project Structure

```text
EDI_Alert_Agent/
├── edi_agent.py        # Core application (CLI handlers + PySide6 GUI)
├── install.sh          # Automated deployment script for new machines
├── requirements.txt    # Python dependency manifest
├── .gitignore          # Excludes venv, cached files, and local IP configs
└── README.md           # Project documentation

```

---

## 🛠️ Deployment Instructions

### Prerequisites

* **OS:** Fedora 44 KDE Plasma (or any modern Systemd-based Linux distribution running Qt/KDE)
* **Python:** Python 3.10+
* **System Packages:** `iputils` (for `ping`), `libnotify` (for `notify-send`)

---

### Option A: Automated Installation (Recommended for Laptops)

1. **Clone or copy the repository to your system:**
```bash
git clone git@github.com:YOUR_USERNAME/EDI_Alert_Agent.git ~/Projects/EDI_Alert_Agent
cd ~/Projects/EDI_Alert_Agent

```


2. **Make `install.sh` executable and run it:**
```bash
chmod +x install.sh
./install.sh

```


3. **Verify service status:**
```bash
systemctl --user status edi-alert-agent.service

```



---

### Option B: Manual Installation (Step-by-Step)

If you prefer to configure the environment manually or need to debug installation steps:

1. **Navigate to the project directory:**
```bash
cd /path/to/EDI_Alert_Agent

```


2. **Create and activate a Python virtual environment:**
```bash
python3 -m venv venv
source venv/bin/activate

```


3. **Install dependencies:**
```bash
pip install --upgrade pip
pip install -r requirements.txt

```


4. **Create the global CLI binary wrapper:**
```bash
mkdir -p ~/.local/bin
cat << EOF > ~/.local/bin/edi-agent
#!/bin/bash
$(pwd)/venv/bin/python $(pwd)/edi_agent.py "\$@"
EOF
chmod +x ~/.local/bin/edi-agent

```


5. **Ensure `~/.local/bin` is in your system `$PATH`:**
Add this line to `~/.bashrc` or `~/.zshrc` if not already present:
```bash
export PATH="$HOME/.local/bin:$PATH"

```


6. **Configure the Systemd User Service:**
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

```


7. **Enable and start the daemon:**
```bash
systemctl --user daemon-reload
systemctl --user enable --now edi-alert-agent.service

```



---

## 📖 Complete Usage Guide

### CLI Commands

You can run `edi-agent` from any terminal prompt across your system.

| Command | Usage | Description |
| --- | --- | --- |
| **Add Node** | `edi-agent add <name> <ip>` | Performs immediate ping test and registers node. |
| **Remove Node** | `edi-agent remove <name>` | Unregisters node from monitoring registry. |
| **List Nodes** | `edi-agent list` | Outputs a clean table of monitored hosts and last status. |
| **Test Alert** | `edi-agent test` | Triggers a test desktop popup notification over DBus. |
| **Launch GUI** | `edi-agent gui` | Launches background tray app directly (used by systemd). |

#### CLI Examples

```bash
# Add nodes with immediate reachability check
edi-agent add proxmox 10.1.1.3
edi-agent add plex 10.1.1.99
edi-agent add gateway 10.1.1.1

# List all current hosts
edi-agent list

# Send a test desktop notification
edi-agent test

# Remove a node
edi-agent remove plex

```

---

### GUI / System Tray Features

* **System Tray Icon:** Located in the KDE Plasma panel near the clock.
* **Context Menu:** Right-click the icon to view status, launch the node status window, send a test alert, or quit the agent.
* **Status Window:** Click **Show Status Window** to see all tracked nodes, color-coded status badges (**GREEN** for `ONLINE`, **RED** for `OFFLINE`), and click **Refresh / Check Now** to re-ping all nodes on demand.

---

### Configuration File Location

The local database configuration file is stored in JSON format at:

```text
~/.config/edi-alert-agent/nodes.json

```

Example `nodes.json` structure:

```json
{
  "nodes": {
    "plex": {
      "ip": "10.1.1.99",
      "status": "online",
      "failures": 0
    },
    "pve-server": {
      "ip": "10.1.1.3",
      "status": "online",
      "failures": 0
    }
  }
}

```

> **Note:** The background service continuously reads from this JSON file. Adding or removing nodes via the CLI updates the daemon's monitoring targets dynamically without needing a service restart.

---

## 🔧 Troubleshooting & Diagnostics

### 1. `edi-agent: command not found`

* **Cause:** `~/.local/bin` is not in your environment `$PATH`.
* **Fix:** Run `echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc && source ~/.bashrc`.

### 2. Desktop Notifications Are Not Appearing

* **Cause:** The KDE Notification daemon or `libnotify` DBus interface is unreachable.
* **Fix 1:** Verify manual notifications work from terminal:
```bash
notify-send "Test" "Hello World"

```


* **Fix 2:** Ensure `libnotify` is installed on Fedora:
```bash
sudo dnf install libnotify

```



### 3. Service Fails to Start on Boot

* **Cause:** Systemd started the service before the graphical user session loaded.
* **Check Service Logs:**
```bash
journalctl --user -u edi-alert-agent.service -n 50 --no-pager

```


* **Restart the Service:**
```bash
systemctl --user restart edi-alert-agent.service

```



### 4. Nodes Show `OFFLINE` When They Are Online

* **Cause:** Host firewall dropping ICMP echo requests, or network routing issue.
* **Diagnostics:**
Run a direct ping test with a 1-second timeout:
```bash
ping -c 1 -W 1 <target-ip>

```


If this fails, check local subnets, VLAN tagging, or destination firewall settings (e.g., UFW/firewalld blocking ICMP).
