<div align="center">
  <img src="assets/app_logo.png" alt="8-Bit Agent Logo" width="128" />
  <h1>8-Bit Agent (v1.9.0)</h1>
  <p>Lightweight LAN Node Monitoring Daemon for Fedora KDE Plasma</p>
</div>

**8-Bit Agent** (formerly EDI Agent) is a lightweight, background LAN node monitoring daemon and desktop application built specifically for **Fedora KDE Plasma** (and Qt/systemd-based Linux desktops). Full documentation, including an online copy of the manual, is at [8bitbunker.org](http://8bitbunker.org/apps/8bb-agent/latest/guide.html).

It periodically monitors local infrastructure nodes (Proxmox, Plex, internal web applications, databases, etc.) using non-intrusive ICMP pings — or an optional TCP port check to verify a specific service is actually running, not just that the host is reachable — and delivers native desktop notification popups over DBus whenever a node drops offline or recovers. Alerts can also be mirrored to a Discord channel via webhook, for when you're not sitting at this desktop, and a local web dashboard (bound to `127.0.0.1` only) lets you check and manage your nodes from a browser on the same machine.

> The CLI command (`edi-agent`), config directory (`~/.config/edi-alert-agent/`), and systemd unit name are all unchanged from the EDI Agent era, so existing installs keep working exactly as before — only the product's name and branding changed. See [FAQ](docs/FAQ.md) for common questions about other desktops, Windows, and Docker.

---

## Key Features

* **Native KDE Plasma System Tray:** Integrates seamlessly near the desktop clock using PySide6 (Qt6) with custom branding, and a live green/red health badge on the icon itself.
* **Non-Intrusive Ping Strategy:** Concurrent ICMP checks with 1-second strict timeouts to prevent network bottlenecks. The daemon reschedules itself dynamically around whichever node is due soonest, rather than polling on a fixed tick.
* **Per-Node Check Interval & Alert Threshold:** Override the default 30s check interval (minimum 5s, genuinely honored — not rounded up to a fixed daemon tick) or 2-strike alert threshold on any individual node — e.g. check a flaky IoT device every 5 minutes, or alert instantly on a critical database.
* **Dark / Light Theme:** Defaults to a dark glass theme; switch anytime from the tray menu. The choice is remembered across restarts.
* **Optional Service-Level Port Checks:** Monitor a specific TCP port instead of ICMP (e.g. `5432` for PostgreSQL, `32400` for Plex, `8006` for Proxmox) to confirm the actual service is up, not just the host.
* **Configurable Failure Threshold:** Requires 2 consecutive failed checks (by default) before triggering a critical desktop popup, to prevent false alarms over Wi-Fi. Adjustable per node.
* **Unified CLI & GUI:** Add, edit, and delete nodes from either the terminal (`edi-agent`) or the tray-docked GUI Dashboard — both operate on the same registry, so the two stay interchangeable.
* **Instant Reachability Validation:** Automatically tests host reachability immediately when adding new nodes via the CLI.
* **Built-In Interactive Manual:** Includes a standalone documentation GUI (`manual.py`) accessible via terminal command (`edi-agent help`) or the header **`?`** button in the UI.
* **Systemd User Service:** Runs silently in the background as an unprivileged user daemon that automatically starts on boot.
* **Rotating Application Log:** CLI actions, node status transitions, and any config/history read errors are logged to `~/.local/state/edi-alert-agent/edi-agent.log` (1MB × 3 backups), independent of `journalctl`.
* **Discord Webhook Alerts:** Mirror every offline/recovery alert to a Discord channel, in addition to the desktop popup — configure from the tray menu or `edi-agent webhook set <url>`. Sent on a background thread so a slow or unreachable webhook can never freeze the tray UI.
* **Local Web Dashboard:** A browser-based dashboard with the same add/edit/delete/refresh actions as the tray and CLI — delete confirmations, toast notifications, no terminal needed. Bound to `127.0.0.1` only (never your LAN) on an uncommon default port (`7317`); open it from the tray's **View Web UI** entry, or run it standalone with `edi-agent web` on a headless machine. It can't push live pop-up alerts like the tray — pair it with Discord webhooks for that.

---

## Project Structure

```text
EDI_Alert_Agent/
├── .github/
│   └── workflows/
│       └── tests.yml     # GitHub Actions CI: runs pytest on every push/PR
├── assets/
│   └── app_logo.png     # Application branding icon (Tray, Window Header, Notifications)
├── docs/
│   └── FAQ.md            # Answers to common questions (other desktops, Windows, Docker)
├── man/
│   ├── edi-agent.1              # Man page (view with `man man/edi-agent.1`)
│   └── edi-agent-packaging.7    # How this project is packaged (pyproject.toml, entry points)
├── tests/
│   ├── test_edi_agent.py  # pytest unit tests for CLI, config, GUI dialogs, and check logic
│   └── test_web_ui.py     # pytest unit tests for the local web dashboard's API routes
├── CLAUDE.md             # Project status, roadmap, and per-session change log
├── conftest.py          # Shared pytest fixtures (isolates tests from your real config)
├── edi_agent.py         # Core monitoring daemon, CLI, and tray/GUI application logic
├── web_ui.py             # Local web dashboard (Flask + waitress, bound to 127.0.0.1 only)
├── install.sh           # One-click automated setup & systemd service installer
├── uninstall.sh         # Removes the service, CLI wrapper, and venv
├── LICENSE              # Open-source MIT License
├── manual.py            # Interactive PySide6 Help & User Manual window
├── pyproject.toml        # Package metadata; `pip install -e .` gives you the `edi-agent` command
├── README.md            # Project documentation
├── requirements.txt     # Python dependency manifest (PySide6, Flask, waitress)
├── requirements-dev.txt # Adds pytest for running the test suite
└── style.py              # Qt dark-glass stylesheet shared by the GUI
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
| **Webhook** | `edi-agent webhook set <url>` \| `clear` \| `test` | Configures a Discord webhook to mirror offline/recovery alerts. `test` sends a message immediately to confirm it works. |
| **Web Dashboard** | `edi-agent web [--port PORT]` | Runs the local web dashboard standalone in the foreground, no tray/desktop session required. Bound to `127.0.0.1` only, default port `7317`. Also runs automatically alongside the tray daemon (`edi-agent gui`). |
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

# Mirror alerts to a Discord channel
edi-agent webhook set https://discord.com/api/webhooks/XXXXXXXXXXXX/XXXXXXXX
edi-agent webhook test
edi-agent webhook clear

# Run just the web dashboard, e.g. on a headless machine
edi-agent web
edi-agent web --port 9000

# Open built-in interactive manual
edi-agent help
```

---

## Graphical Interface & System Tray

* **System Tray Dock:** Sits by the system clock with custom branding. The icon shows a **GREEN** badge when every node is online and a **RED** badge if any node is down, with a tooltip summarizing fleet health. Right-clicking the tray icon opens the context menu to launch the Dashboard, open the manual, trigger a test notification, configure Discord alerts, open the web dashboard, switch the theme, or quit the application.
* **Dark / Light Theme:** Toggle from the tray menu at any time; the choice persists across restarts. Defaults to dark.
* **Infrastructure Dashboard:** The main GUI window. A summary row of metric cards (Total Nodes, Online, Offline, Avg Latency) sits above a sortable table (click any column header) of every registered host — check method (ping or TCP port), status, failures/threshold, check interval, latency, and last-checked time.
* **Add / Edit / Delete Nodes:** The GUI is no longer read-mostly — **Add**, **Edit**, and **Delete** buttons (plus double-click any row to edit) cover full node lifecycle management without touching a terminal. All three go through the same validated CLI functions under the hood, so GUI and CLI behavior stay identical.
* **Alert History:** A dedicated window (via the tray menu or the **History** button) listing every offline/recovery event with a timestamp, so you can see what happened even after the desktop popup is gone. Includes a **Clear History** option.
* **Discord Webhook Dialog:** From the tray menu, paste a Discord incoming webhook URL, save it, and send a test message — no terminal required. The same dialog can clear the webhook to go back to desktop-only alerts.
* **Web Dashboard:** Choose **View Web UI** from the tray menu to open a local web dashboard in your browser (`http://127.0.0.1:7317` by default) — the same Add/Edit/Delete/Refresh actions as the tray, with a delete confirmation and toast notifications. Bound to `127.0.0.1` only; nothing else on your LAN can reach it. It can't show a live pop-up the way the tray does since a browser tab isn't always open — that's what Discord webhooks are for.
* **Refresh Now:** Forces an on-demand check of every registered host, bypassing each node's own check interval.
* **Help (`?`) Button:** Click the circular **`?`** button in the top-right of the Dashboard to pop open the interactive user manual.

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

Offline/recovery alert history is stored separately at `~/.config/edi-alert-agent/history.json`, capped at the 200 most recent events. GUI theme, the Discord webhook URL, and an optional web dashboard port override live in `~/.config/edi-alert-agent/settings.json` — e.g. `{"theme": "dark", "discord_webhook_url": "https://discord.com/api/webhooks/...", "web_ui_port": 7317}`. To create a webhook URL: in Discord, go to a channel's **Settings → Integrations → Webhooks → New Webhook**, then copy its URL.

---

## Diagnostics & Troubleshooting

* **`edi-agent: command not found`:** Ensure `~/.local/bin` is in your shell `$PATH`. Add `export PATH="$HOME/.local/bin:$PATH"` to your `~/.bashrc`.
* **`man edi-agent` not found:** `install.sh` copies the man page to `~/.local/share/man/man1/`. Most modern `man-db` setups pick this up automatically; if not, add `export MANPATH="$HOME/.local/share/man:$MANPATH"` to your `~/.bashrc`.
* **Notifications Not Appearing:** Ensure `libnotify` is installed on your system (`sudo dnf install libnotify`) and test via `notify-send "Test" "Message"`.
* **Inspect Service Logs:** Run `journalctl --user -u edi-alert-agent.service -f` for systemd-level output, or check the application's own rotating log at `~/.local/state/edi-alert-agent/edi-agent.log` for CLI actions and node status transitions.
* **Discord Alerts Not Arriving:** Run `edi-agent webhook test` — it prints success/failure directly. Failures (bad URL, network issue, Discord returning a non-2xx status) are also logged to `edi-agent.log`. The webhook URL itself is never written to the log, only whether the send succeeded.
* **Web Dashboard Won't Load:** It's bound to `127.0.0.1` only — use `http://127.0.0.1:7317` or `http://localhost:7317`, not your machine's LAN IP; that's by design, not a bug. If port `7317` is already in use by something else, override it with `edi-agent web --port 9000` or a `web_ui_port` entry in `settings.json`.
* **Scripting against the CLI:** `edi-agent` exits `0` on success and `1` on any validation/operation failure (invalid IP, duplicate node, node not found, etc.), so `edi-agent add ... || echo "failed"` works as expected.

---

## Development & Testing

Unit tests cover the CLI commands, config persistence, GUI dialogs, and reachability-check logic (mocked, so tests never touch the network or your real `nodes.json`):

```bash
source venv/bin/activate
pip install -r requirements-dev.txt
pytest
```

A GitHub Actions workflow (`.github/workflows/tests.yml`) runs the same suite on every push and pull request.

---

## Installing as a Package

`install.sh` installs 8-Bit Agent as an editable Python package (`pip install -e .`) rather than a hand-rolled script wrapper, which is what actually creates the `edi-agent` command:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -e .
edi-agent list
```

See `man man/edi-agent-packaging.7` for what `pyproject.toml` is doing and why, if you're learning Python packaging alongside this project.

---

## Documentation

* **Man pages:** `man man/edi-agent.1` covers every CLI command and option; `man man/edi-agent-packaging.7` explains how the project is packaged. (Or `man -l <path>` from anywhere.)
* **In-app manual:** `edi-agent help`, or the **`?`** button in the Dashboard.
* **[FAQ](docs/FAQ.md):** Other desktop environments, Windows support, and Docker — the questions people actually ask.
* **Online guide:** [8bitbunker.org](http://8bitbunker.org/apps/8bb-agent/latest/guide.html) — a hosted copy of this manual.
* **`CLAUDE.md`:** Project status, known gaps, and the roadmap of planned improvements — the working notes for anyone (human or AI) picking up development.

---

## License

This project is licensed under the **MIT License**. See the [LICENSE](LICENSE) file for details.