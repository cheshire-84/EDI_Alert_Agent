#!/usr/bin/env python3
import sys
import json
import subprocess
import argparse
from pathlib import Path
from PySide6.QtWidgets import (
    QApplication, QSystemTrayIcon, QMenu, QDialog,
    QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QLabel
)
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QIcon, QColor, QPixmap, QFont

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
            return json.load(f)
    except Exception:
        return {"nodes": {}}

def save_config(cfg):
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=2)

def ping_node(ip):
    # Single ICMP ping with 1-second timeout on Linux
    res = subprocess.run(
        ["ping", "-c", "1", "-W", "1", ip],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    return res.returncode == 0

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

# --- CLI COMMANDS ---
def cli_add(name, ip):
    print(f"[?] Checking reachability for '{name}' ({ip})...", end=" ", flush=True)
    is_online = ping_node(ip)
    status = "online" if is_online else "offline"
    
    cfg = load_config()
    cfg["nodes"][name] = {
        "ip": ip,
        "status": status,
        "failures": 0 if is_online else 1
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

def cli_list():
    cfg = load_config()
    if not cfg["nodes"]:
        print("No nodes currently monitored.")
        return
    print(f"\n{'NAME':<20} {'IP ADDRESS':<18} {'STATUS'}")
    print("-" * 50)
    for name, data in cfg["nodes"].items():
        print(f"{name:<20} {data['ip']:<18} {data.get('status', 'unknown').upper()}")
    print()

def cli_test():
    print("[*] Triggering test notification...")
    send_desktop_notification(
        "EDI Agent (v1): Test",
        "This is a test notification from EDI Agent! Desktop alerts are working.",
        urgency="critical"
    )
    print("[+] Test notification sent to desktop.")

# --- GUI / SYSTEM TRAY ---
class NodeManagerDialog(QDialog):
    def __init__(self, monitor_app=None):
        super().__init__()
        self.monitor_app = monitor_app
        self.setWindowTitle("EDI Agent (v1) - Monitored Nodes")
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
        
        title_label = QLabel("EDI Agent (v1)")
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
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Node Name", "IP Address", "Status"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
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
            for name, info in cfg["nodes"].items():
                is_online = ping_node(info["ip"])
                info["status"] = "online" if is_online else "offline"
            save_config(cfg)
            
        self.reload_data()
        self.refresh_btn.setText("Refresh / Check Now")
        self.refresh_btn.setEnabled(True)

    def reload_data(self):
        cfg = load_config()
        self.table.setRowCount(len(cfg["nodes"]))
        for row, (name, info) in enumerate(cfg["nodes"].items()):
            status = info.get("status", "unknown").upper()
            
            item_name = QTableWidgetItem(name)
            item_ip = QTableWidgetItem(info["ip"])
            item_status = QTableWidgetItem(status)
            
            item_status.setTextAlignment(Qt.AlignCenter)
            if status == "ONLINE":
                item_status.setForeground(QColor("#2ecc71"))
            elif status == "OFFLINE":
                item_status.setForeground(QColor("#e74c3c"))
            else:
                item_status.setForeground(QColor("#95a5a6"))
                
            self.table.setItem(row, 0, item_name)
            self.table.setItem(row, 1, item_ip)
            self.table.setItem(row, 2, item_status)

class MonitorApp:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)

        # Tray Icon
        self.tray = QSystemTrayIcon()
        if LOGO_PATH.exists():
            icon = QIcon(str(LOGO_PATH))
        else:
            icon = QIcon.fromTheme("network-server", QIcon.fromTheme("utilities-system-monitor"))
        
        self.tray.setIcon(icon)
        self.tray.setVisible(True)

        # Context Menu
        self.menu = QMenu()
        self.status_action = self.menu.addAction("EDI Agent (v1): Active")
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
            "EDI Agent (v1): Test",
            "This is a test notification from EDI Agent!",
            QSystemTrayIcon.MessageIcon.Information,
            5000
        )

    def check_nodes(self):
        cfg = load_config()
        updated = False

        for name, info in cfg["nodes"].items():
            ip = info["ip"]
            is_online = ping_node(ip)
            prev_status = info.get("status", "unknown")
            failures = info.get("failures", 0)

            if not is_online:
                failures += 1
                info["failures"] = failures
                if failures >= 2 and prev_status != "offline":
                    info["status"] = "offline"
                    updated = True
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
                    updated = True
                    if prev_status == "offline":
                        self.tray.showMessage(
                            "EDI ALERT: Node Restored",
                            f"Node '{name}' ({ip}) is back online.",
                            QSystemTrayIcon.MessageIcon.Information,
                            5000
                        )

        if updated:
            save_config(cfg)
            
        if self.dialog and self.dialog.isVisible():
            self.dialog.reload_data()

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
    parser = argparse.ArgumentParser(description="EDI Agent (v1)")
    subparsers = parser.add_subparsers(dest="command")

    add_parser = subparsers.add_parser("add", help="Add a node to monitor")
    add_parser.add_argument("name", help="Node identifier (e.g. plex)")
    add_parser.add_argument("ip", help="IP address (e.g. 10.1.1.99)")

    rem_parser = subparsers.add_parser("remove", help="Remove a monitored node")
    rem_parser.add_argument("name", help="Node identifier")

    subparsers.add_parser("list", help="List monitored nodes")
    subparsers.add_parser("test", help="Send a test notification")
    subparsers.add_parser("help", help="Open manual window")
    subparsers.add_parser("gui", help="Run system tray monitor agent")

    args = parser.parse_args()

    if args.command == "add":
        cli_add(args.name, args.ip)
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