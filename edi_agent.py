#!/usr/bin/env python3
# EDI Agent - System Tray Node Monitor & Alert Agent
import sys
import json
import time
import fcntl
import ipaddress
import subprocess
import argparse
import concurrent.futures
from pathlib import Path
from datetime import datetime
from PySide6.QtWidgets import (
    QApplication, QSystemTrayIcon, QMenu, QDialog,
    QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QLabel
)
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QIcon, QColor, QPixmap, QFont, QPainter, QPen, QBrush

__version__ = "1.0.4"

BASE_DIR = Path(__file__).parent.resolve()
ASSETS_DIR = BASE_DIR / "assets"
LOGO_PATH = ASSETS_DIR / "app_logo.png"
MANUAL_PATH = BASE_DIR / "manual.py"
CONFIG_PATH = Path.home() / ".config" / "edi-alert-agent" / "nodes.json"

def load_config():
    if not CONFIG_PATH.exists():
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        return {"nodes": {}}
    try:
        with open(CONFIG_PATH, "r") as f:
            fcntl.flock(f, fcntl.LOCK_SH)
            try:
                return json.load(f)
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)
    except Exception:
        return {"nodes": {}}

def save_config(cfg):
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            json.dump(cfg, f, indent=2)
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)

def is_valid_ip(ip):
    try:
        ipaddress.ip_address(ip)
        return True
    except ValueError:
        return False

def ping_nodes_concurrently(nodes):
    """Ping all nodes in parallel so a 30-node fleet doesn't take 30 seconds to check."""
    results = {}
    if not nodes:
        return results
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(32, len(nodes))) as executor:
        future_to_name = {
            executor.submit(ping_node, info["ip"]): name
            for name, info in nodes.items()
        }
        for future in concurrent.futures.as_completed(future_to_name):
            name = future_to_name[future]
            try:
                results[name] = future.result()
            except Exception:
                results[name] = (False, None)
    return results

def ping_node(ip):
    # Single ICMP ping with 1-second timeout on Linux. Returns (is_online, latency_ms).
    start = time.monotonic()
    res = subprocess.run(
        ["ping", "-c", "1", "-W", "1", ip],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    is_online = res.returncode == 0
    latency_ms = round((time.monotonic() - start) * 1000, 1) if is_online else None
    return is_online, latency_ms

def send_desktop_notification(title, message, urgency="normal"):
    try:
        icon_arg = str(LOGO_PATH) if LOGO_PATH.exists() else "network-server"
        subprocess.run(
            ["notify-send", "-u", urgency, "-i", icon_arg, title, message],
            check=True
        )
    except Exception:
        pass

def open_manual_window():
    if MANUAL_PATH.exists():
        subprocess.Popen([sys.executable, str(MANUAL_PATH)])

def load_base_tray_pixmap():
    if LOGO_PATH.exists():
        base = QPixmap(str(LOGO_PATH))
    else:
        base = QIcon.fromTheme("network-server", QIcon.fromTheme("utilities-system-monitor")).pixmap(64, 64)
    return base.scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation)

def build_badged_icon(base_pixmap, badge_color):
    """Overlay a colored health-status dot on the tray icon's corner."""
    pixmap = QPixmap(base_pixmap.size())
    pixmap.fill(Qt.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.drawPixmap(0, 0, base_pixmap)

    diameter = int(pixmap.width() * 0.4)
    x = pixmap.width() - diameter
    y = pixmap.height() - diameter
    painter.setPen(QPen(QColor("white"), 2))
    painter.setBrush(QBrush(badge_color))
    painter.drawEllipse(x, y, diameter, diameter)
    painter.end()

    return QIcon(pixmap)

# --- CLI COMMANDS ---
def cli_add(name, ip, force=False):
    if not is_valid_ip(ip):
        print(f"[!] '{ip}' is not a valid IP address.")
        return

    cfg = load_config()
    if name in cfg["nodes"] and not force:
        print(f"[!] Node '{name}' already exists ({cfg['nodes'][name]['ip']}). "
              f"Use --force to overwrite, or 'edi-agent remove {name}' first.")
        return

    print(f"[?] Checking reachability for '{name}' ({ip})...", end=" ", flush=True)
    is_online, latency_ms = ping_node(ip)
    status = "online" if is_online else "offline"

    cfg["nodes"][name] = {
        "ip": ip,
        "status": status,
        "failures": 0 if is_online else 1,
        "last_checked": time.time(),
        "latency_ms": latency_ms
    }
    save_config(cfg)

    status_str = "ONLINE" if is_online else "OFFLINE"
    print(f"Done!\n[+] Added node: {name} ({ip}) -> Status: {status_str}")

def cli_remove(name):
    cfg = load_config()
    if name in cfg["nodes"]:
        del cfg["nodes"][name]
        save_config(cfg)
        print(f"[-] Removed node: {name}")
    else:
        print(f"[!] Node '{name}' not found.")

def format_latency(latency_ms):
    return f"{latency_ms:.0f} ms" if latency_ms is not None else "--"

def format_last_checked(timestamp):
    return datetime.fromtimestamp(timestamp).strftime("%H:%M:%S") if timestamp else "never"

def cli_list():
    cfg = load_config()
    if not cfg["nodes"]:
        print("No nodes currently monitored.")
        return
    print(f"\n{'NAME':<20} {'IP ADDRESS':<18} {'STATUS':<10} {'FAILURES':<10} {'LATENCY':<10} {'LAST CHECKED'}")
    print("-" * 90)
    for name, data in cfg["nodes"].items():
        status = data.get('status', 'unknown').upper()
        failures = data.get('failures', 0)
        latency = format_latency(data.get('latency_ms'))
        last_checked = format_last_checked(data.get('last_checked'))
        print(f"{name:<20} {data['ip']:<18} {status:<10} {failures:<10} {latency:<10} {last_checked}")
    print()

def cli_test():
    print("[*] Triggering test notification...")
    send_desktop_notification(
        f"EDI Agent (v{__version__}): Test",
        "This is a test notification from EDI Agent! Desktop alerts are working.",
        urgency="critical"
    )
    print("[+] Test notification sent to desktop.")

# --- GUI / SYSTEM TRAY ---
class NodeManagerDialog(QDialog):
    def __init__(self, monitor_app=None):
        super().__init__()
        self.monitor_app = monitor_app
        self.setWindowTitle(f"EDI Agent (v{__version__}) - Monitored Nodes")
        self.resize(580, 400)
        
        if LOGO_PATH.exists():
            self.setWindowIcon(QIcon(str(LOGO_PATH)))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)
        
        # --- HEADER SECTION ---
        header_layout = QHBoxLayout()
        header_layout.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        
        if LOGO_PATH.exists():
            logo_label = QLabel()
            pixmap = QPixmap(str(LOGO_PATH)).scaled(42, 42, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            logo_label.setPixmap(pixmap)
            header_layout.addWidget(logo_label)
        
        title_label = QLabel(f"EDI Agent (v{__version__})")
        font = QFont()
        font.setPointSize(16)
        font.setBold(True)
        title_label.setFont(font)
        header_layout.addWidget(title_label)
        
        header_layout.addStretch()
        
        # '?' Help Button
        self.help_btn = QPushButton("?")
        self.help_btn.setFixedWidth(28)
        self.help_btn.setToolTip("Open User Manual & Help")
        self.help_btn.clicked.connect(open_manual_window)
        header_layout.addWidget(self.help_btn)
        
        layout.addLayout(header_layout)
        
        # --- TABLE SECTION ---
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(
            ["Node Name", "IP Address", "Status", "Failures", "Latency", "Last Checked"]
        )
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSortingEnabled(True)
        layout.addWidget(self.table)
        
        # --- ACTION BAR SECTION ---
        action_layout = QHBoxLayout()
        self.info_label = QLabel("Auto-checking every 30s")
        self.refresh_btn = QPushButton("Refresh / Check Now")
        self.refresh_btn.clicked.connect(self.manual_refresh)
        
        action_layout.addWidget(self.info_label)
        action_layout.addStretch()
        action_layout.addWidget(self.refresh_btn)
        
        layout.addLayout(action_layout)
        
        self.reload_data()

    def manual_refresh(self):
        self.refresh_btn.setEnabled(False)
        self.refresh_btn.setText("Pinging Nodes...")
        QApplication.processEvents()
        
        if self.monitor_app:
            self.monitor_app.check_nodes()
        else:
            cfg = load_config()
            results = ping_nodes_concurrently(cfg["nodes"])
            now = time.time()
            for name, info in cfg["nodes"].items():
                is_online, latency_ms = results.get(name, (False, None))
                info["status"] = "online" if is_online else "offline"
                info["last_checked"] = now
                info["latency_ms"] = latency_ms
            save_config(cfg)
            
        self.reload_data()
        self.refresh_btn.setText("Refresh / Check Now")
        self.refresh_btn.setEnabled(True)

    def reload_data(self):
        cfg = load_config()
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(cfg["nodes"]))
        for row, (name, info) in enumerate(cfg["nodes"].items()):
            status = info.get("status", "unknown").upper()
            failures = info.get("failures", 0)

            item_name = QTableWidgetItem(name)
            item_ip = QTableWidgetItem(info["ip"])
            item_status = QTableWidgetItem(status)
            item_failures = QTableWidgetItem()
            item_failures.setData(Qt.DisplayRole, failures)
            item_latency = QTableWidgetItem(format_latency(info.get("latency_ms")))
            item_last_checked = QTableWidgetItem(format_last_checked(info.get("last_checked")))

            item_status.setTextAlignment(Qt.AlignCenter)
            item_failures.setTextAlignment(Qt.AlignCenter)
            item_latency.setTextAlignment(Qt.AlignCenter)
            item_last_checked.setTextAlignment(Qt.AlignCenter)
            if status == "ONLINE":
                item_status.setForeground(QColor("#2ecc71"))
            elif status == "OFFLINE":
                item_status.setForeground(QColor("#e74c3c"))
            else:
                item_status.setForeground(QColor("#95a5a6"))
            if failures > 0:
                item_failures.setForeground(QColor("#e67e22"))

            self.table.setItem(row, 0, item_name)
            self.table.setItem(row, 1, item_ip)
            self.table.setItem(row, 2, item_status)
            self.table.setItem(row, 3, item_failures)
            self.table.setItem(row, 4, item_latency)
            self.table.setItem(row, 5, item_last_checked)
        self.table.setSortingEnabled(True)

class MonitorApp:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)

        # Tray Icon
        base_pixmap = load_base_tray_pixmap()
        self.icon_neutral = QIcon(base_pixmap)
        self.icon_online = build_badged_icon(base_pixmap, QColor("#2ecc71"))
        self.icon_offline = build_badged_icon(base_pixmap, QColor("#e74c3c"))

        self.tray = QSystemTrayIcon()
        self.tray.setIcon(self.icon_neutral)
        self.tray.setToolTip(f"EDI Agent (v{__version__})")
        self.tray.setVisible(True)

        # Context Menu
        self.menu = QMenu()
        self.status_action = self.menu.addAction(f"EDI Agent (v{__version__}): Active")
        self.status_action.setEnabled(False)
        self.menu.addSeparator()

        self.manage_action = self.menu.addAction("Show Status Window")
        self.manage_action.triggered.connect(self.show_manager)

        self.help_action = self.menu.addAction("Help / Manual")
        self.help_action.triggered.connect(open_manual_window)

        self.test_action = self.menu.addAction("Send Test Alert")
        self.test_action.triggered.connect(self.trigger_test_alert)

        self.quit_action = self.menu.addAction("Quit Agent")
        self.quit_action.triggered.connect(self.app.quit)

        self.tray.setContextMenu(self.menu)

        # 30-Second Ping Loop
        self.timer = QTimer()
        self.timer.timeout.connect(self.check_nodes)
        self.timer.start(30000)

        # Immediate check on launch
        QTimer.singleShot(500, self.check_nodes)

        self.dialog = None

    def trigger_test_alert(self):
        self.tray.showMessage(
            f"EDI Agent (v{__version__}): Test",
            "This is a test notification from EDI Agent!",
            QSystemTrayIcon.MessageIcon.Information,
            5000
        )

    def check_nodes(self):
        cfg = load_config()
        if not cfg["nodes"]:
            self.refresh_tray_icon(cfg)
            return

        results = ping_nodes_concurrently(cfg["nodes"])
        now = time.time()
        for name, info in cfg["nodes"].items():
            ip = info["ip"]
            is_online, latency_ms = results.get(name, (False, None))
            prev_status = info.get("status", "unknown")
            failures = info.get("failures", 0)

            info["last_checked"] = now
            info["latency_ms"] = latency_ms

            if not is_online:
                failures += 1
                info["failures"] = failures
                if failures >= 2 and prev_status != "offline":
                    info["status"] = "offline"
                    self.tray.showMessage(
                        "EDI ALERT: Node Offline",
                        f"ALERT: '{name}' ({ip}) is unreachable!",
                        QSystemTrayIcon.MessageIcon.Critical,
                        10000
                    )
            else:
                info["failures"] = 0
                if prev_status != "online":
                    info["status"] = "online"
                    if prev_status == "offline":
                        self.tray.showMessage(
                            "EDI ALERT: Node Restored",
                            f"Node '{name}' ({ip}) is back online.",
                            QSystemTrayIcon.MessageIcon.Information,
                            5000
                        )

        save_config(cfg)
        self.refresh_tray_icon(cfg)

        if self.dialog and self.dialog.isVisible():
            self.dialog.reload_data()

    def refresh_tray_icon(self, cfg):
        nodes = cfg.get("nodes", {})
        if not nodes:
            self.tray.setIcon(self.icon_neutral)
            self.tray.setToolTip(f"EDI Agent (v{__version__}): No nodes monitored")
            return

        down = [name for name, info in nodes.items() if info.get("status") == "offline"]
        if down:
            self.tray.setIcon(self.icon_offline)
            self.tray.setToolTip(f"EDI Agent (v{__version__}): {len(down)} node(s) offline")
        else:
            self.tray.setIcon(self.icon_online)
            self.tray.setToolTip(f"EDI Agent (v{__version__}): All nodes online")

    def show_manager(self):
        if not self.dialog:
            self.dialog = NodeManagerDialog(monitor_app=self)
        else:
            self.dialog.reload_data()
        self.dialog.show()
        self.dialog.raise_()
        self.dialog.activateWindow()

    def run(self):
        sys.exit(self.app.exec())

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=f"EDI Agent (v{__version__})")
    subparsers = parser.add_subparsers(dest="command")

    add_parser = subparsers.add_parser("add", help="Add a node to monitor")
    add_parser.add_argument("name", help="Node identifier (e.g. plex)")
    add_parser.add_argument("ip", help="IP address (e.g. 10.1.1.99)")
    add_parser.add_argument("--force", action="store_true", help="Overwrite an existing node with the same name")

    rem_parser = subparsers.add_parser("remove", help="Remove a monitored node")
    rem_parser.add_argument("name", help="Node identifier")

    subparsers.add_parser("list", help="List monitored nodes")
    subparsers.add_parser("test", help="Send a test notification")
    subparsers.add_parser("help", help="Open manual window")
    subparsers.add_parser("gui", help="Run system tray monitor agent")

    args = parser.parse_args()

    if args.command == "add":
        cli_add(args.name, args.ip, force=args.force)
    elif args.command == "remove":
        cli_remove(args.name)
    elif args.command == "list":
        cli_list()
    elif args.command == "test":
        cli_test()
    elif args.command == "help":
        open_manual_window()
    else:
        app = MonitorApp()
        app.run()