#!/usr/bin/env python3
# EDI Agent - System Tray Node Monitor & Alert Agent
import sys
import json
import time
import fcntl
import socket
import ipaddress
import subprocess
import argparse
import concurrent.futures
from pathlib import Path
from datetime import datetime
from PySide6.QtWidgets import (
    QApplication, QSystemTrayIcon, QMenu, QDialog,
    QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QLabel, QLineEdit, QMessageBox
)
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QIcon, QColor, QPixmap, QFont, QPainter, QPen, QBrush

__version__ = "1.5.0"

BASE_DIR = Path(__file__).parent.resolve()
ASSETS_DIR = BASE_DIR / "assets"
LOGO_PATH = ASSETS_DIR / "app_logo.png"
MANUAL_PATH = BASE_DIR / "manual.py"
CONFIG_PATH = Path.home() / ".config" / "edi-alert-agent" / "nodes.json"
HISTORY_PATH = Path.home() / ".config" / "edi-alert-agent" / "history.json"
MAX_HISTORY_ENTRIES = 200

# The background tray daemon ticks every 30s (see MonitorApp.timer), which sets
# the effective minimum granularity for per-node check intervals below.
DEFAULT_CHECK_INTERVAL = 30
DEFAULT_FAILURE_THRESHOLD = 2

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

def load_history():
    if not HISTORY_PATH.exists():
        return []
    try:
        with open(HISTORY_PATH, "r") as f:
            fcntl.flock(f, fcntl.LOCK_SH)
            try:
                return json.load(f)
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)
    except Exception:
        return []

def save_history(events):
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(HISTORY_PATH, "w") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            json.dump(events, f, indent=2)
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)

def record_history_event(name, event, message):
    events = load_history()
    events.append({
        "timestamp": time.time(),
        "node": name,
        "event": event,
        "message": message
    })
    save_history(events[-MAX_HISTORY_ENTRIES:])

def is_valid_ip(ip):
    try:
        ipaddress.ip_address(ip)
        return True
    except ValueError:
        return False

def is_valid_port(port):
    return 1 <= port <= 65535

def is_valid_interval(seconds):
    return seconds >= 5

def is_valid_threshold(count):
    return count >= 1

def ping_nodes_concurrently(nodes):
    """Check all nodes in parallel so a 30-node fleet doesn't take 30 seconds to check."""
    results = {}
    if not nodes:
        return results
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(32, len(nodes))) as executor:
        future_to_name = {
            executor.submit(check_target, info["ip"], info.get("port")): name
            for name, info in nodes.items()
        }
        for future in concurrent.futures.as_completed(future_to_name):
            name = future_to_name[future]
            try:
                results[name] = future.result()
            except Exception:
                results[name] = (False, None)
    return results

def check_target(ip, port=None):
    """Returns (is_online, latency_ms). Uses a TCP port check if a port is given,
    otherwise falls back to an ICMP ping."""
    if port:
        return check_port(ip, port)
    return ping_node(ip)

def check_port(ip, port, timeout=1):
    # Real TCP handshake to the service port, not just host reachability.
    start = time.monotonic()
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            latency_ms = round((time.monotonic() - start) * 1000, 1)
            return True, latency_ms
    except OSError:
        return False, None

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
def cli_add(name, ip, force=False, port=None, interval=None, threshold=None):
    if not is_valid_ip(ip):
        print(f"[!] '{ip}' is not a valid IP address.")
        return

    if port is not None and not is_valid_port(port):
        print(f"[!] '{port}' is not a valid port number (must be 1-65535).")
        return

    if interval is not None and not is_valid_interval(interval):
        print(f"[!] '{interval}' is not a valid interval (must be at least 5 seconds).")
        return

    if threshold is not None and not is_valid_threshold(threshold):
        print(f"[!] '{threshold}' is not a valid threshold (must be at least 1).")
        return

    cfg = load_config()
    if name in cfg["nodes"] and not force:
        print(f"[!] Node '{name}' already exists ({cfg['nodes'][name]['ip']}). "
              f"Use --force to overwrite, or 'edi-agent remove {name}' first.")
        return

    check_desc = f"TCP:{port}" if port else "ping"
    print(f"[?] Checking reachability for '{name}' ({ip}) via {check_desc}...", end=" ", flush=True)
    is_online, latency_ms = check_target(ip, port)
    status = "online" if is_online else "offline"

    cfg["nodes"][name] = {
        "ip": ip,
        "port": port,
        "check_interval": interval if interval is not None else DEFAULT_CHECK_INTERVAL,
        "failure_threshold": threshold if threshold is not None else DEFAULT_FAILURE_THRESHOLD,
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

def cli_edit(name, ip=None, port=None, clear_port=False, interval=None, threshold=None):
    cfg = load_config()
    if name not in cfg["nodes"]:
        print(f"[!] Node '{name}' not found.")
        return

    if ip is None and port is None and not clear_port and interval is None and threshold is None:
        print("[!] Nothing to update. Specify --ip, --port/--clear-port, --interval, and/or --threshold.")
        return
    if port is not None and clear_port:
        print("[!] Cannot use --port and --clear-port together.")
        return
    if ip is not None and not is_valid_ip(ip):
        print(f"[!] '{ip}' is not a valid IP address.")
        return
    if port is not None and not is_valid_port(port):
        print(f"[!] '{port}' is not a valid port number (must be 1-65535).")
        return
    if interval is not None and not is_valid_interval(interval):
        print(f"[!] '{interval}' is not a valid interval (must be at least 5 seconds).")
        return
    if threshold is not None and not is_valid_threshold(threshold):
        print(f"[!] '{threshold}' is not a valid threshold (must be at least 1).")
        return

    node = cfg["nodes"][name]
    if ip is not None:
        node["ip"] = ip
    if clear_port:
        node["port"] = None
    elif port is not None:
        node["port"] = port
    if interval is not None:
        node["check_interval"] = interval
    if threshold is not None:
        node["failure_threshold"] = threshold

    check_desc = f"TCP:{node['port']}" if node.get("port") else "ping"
    print(f"[?] Re-checking '{name}' ({node['ip']}) via {check_desc}...", end=" ", flush=True)
    is_online, latency_ms = check_target(node["ip"], node.get("port"))
    node["status"] = "online" if is_online else "offline"
    node["failures"] = 0 if is_online else 1
    node["last_checked"] = time.time()
    node["latency_ms"] = latency_ms
    save_config(cfg)

    status_str = "ONLINE" if is_online else "OFFLINE"
    print(f"Done!\n[+] Updated node: {name} ({node['ip']}) -> Status: {status_str}")

def format_latency(latency_ms):
    return f"{latency_ms:.0f} ms" if latency_ms is not None else "--"

def format_last_checked(timestamp):
    return datetime.fromtimestamp(timestamp).strftime("%H:%M:%S") if timestamp else "never"

def format_check_method(port):
    return f"TCP:{port}" if port else "ping"

def format_failures(failures, threshold):
    return f"{failures}/{threshold}"

def format_interval(seconds):
    return f"{seconds}s"

def format_history_timestamp(timestamp):
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S") if timestamp else "unknown"

def cli_list():
    cfg = load_config()
    if not cfg["nodes"]:
        print("No nodes currently monitored.")
        return
    print(f"\n{'NAME':<20} {'IP ADDRESS':<18} {'CHECK':<10} {'STATUS':<10} {'FAILS':<8} {'INTERVAL':<10} {'LATENCY':<10} {'LAST CHECKED'}")
    print("-" * 110)
    for name, data in cfg["nodes"].items():
        status = data.get('status', 'unknown').upper()
        failures = format_failures(data.get('failures', 0), data.get('failure_threshold', DEFAULT_FAILURE_THRESHOLD))
        check_method = format_check_method(data.get('port'))
        interval = format_interval(data.get('check_interval', DEFAULT_CHECK_INTERVAL))
        latency = format_latency(data.get('latency_ms'))
        last_checked = format_last_checked(data.get('last_checked'))
        print(f"{name:<20} {data['ip']:<18} {check_method:<10} {status:<10} {failures:<8} {interval:<10} {latency:<10} {last_checked}")
    print()

def cli_test():
    print("[*] Triggering test notification...")
    send_desktop_notification(
        f"EDI Agent (v{__version__}): Test",
        "This is a test notification from EDI Agent! Desktop alerts are working.",
        urgency="critical"
    )
    print("[+] Test notification sent to desktop.")

def cli_history(limit=20):
    events = load_history()
    if not events:
        print("No alert history yet.")
        return
    recent = list(reversed(events[-limit:]))
    print(f"\n{'TIME':<20} {'NODE':<20} {'EVENT':<10} MESSAGE")
    print("-" * 100)
    for e in recent:
        ts = format_history_timestamp(e.get("timestamp"))
        print(f"{ts:<20} {e.get('node', ''):<20} {e.get('event', '').upper():<10} {e.get('message', '')}")
    print()

# --- GUI / SYSTEM TRAY ---
class EditNodeDialog(QDialog):
    def __init__(self, name, node_info, parent=None):
        super().__init__(parent)
        self.name = name
        self.setWindowTitle(f"Edit Node: {name}")
        self.resize(380, 230)

        if LOGO_PATH.exists():
            self.setWindowIcon(QIcon(str(LOGO_PATH)))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        ip_row = QHBoxLayout()
        ip_row.addWidget(QLabel("IP Address:"))
        self.ip_input = QLineEdit(node_info.get("ip", ""))
        ip_row.addWidget(self.ip_input)
        layout.addLayout(ip_row)

        port_row = QHBoxLayout()
        port_row.addWidget(QLabel("Port (blank = ICMP ping):"))
        self.port_input = QLineEdit(str(node_info["port"]) if node_info.get("port") else "")
        self.port_input.setPlaceholderText("e.g. 5432, 32400, 8006")
        port_row.addWidget(self.port_input)
        layout.addLayout(port_row)

        interval_row = QHBoxLayout()
        interval_row.addWidget(QLabel("Check Interval (seconds):"))
        self.interval_input = QLineEdit(str(node_info.get("check_interval", DEFAULT_CHECK_INTERVAL)))
        interval_row.addWidget(self.interval_input)
        layout.addLayout(interval_row)

        threshold_row = QHBoxLayout()
        threshold_row.addWidget(QLabel("Alert Threshold (failures):"))
        self.threshold_input = QLineEdit(str(node_info.get("failure_threshold", DEFAULT_FAILURE_THRESHOLD)))
        threshold_row.addWidget(self.threshold_input)
        layout.addLayout(threshold_row)

        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color: #e74c3c;")
        self.error_label.setWordWrap(True)
        layout.addWidget(self.error_label)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        save_btn = QPushButton("Save")
        save_btn.setDefault(True)
        save_btn.clicked.connect(self.on_save)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(save_btn)
        layout.addLayout(btn_row)

    def on_save(self):
        ip = self.ip_input.text().strip()
        port_text = self.port_input.text().strip()
        interval_text = self.interval_input.text().strip()
        threshold_text = self.threshold_input.text().strip()

        if not is_valid_ip(ip):
            self.error_label.setText(f"'{ip}' is not a valid IP address.")
            return

        port = None
        clear_port = (port_text == "")
        if port_text:
            if not port_text.isdigit():
                self.error_label.setText("Port must be a number.")
                return
            port = int(port_text)
            if not is_valid_port(port):
                self.error_label.setText("Port must be between 1 and 65535.")
                return

        if not interval_text.isdigit():
            self.error_label.setText("Check interval must be a number.")
            return
        interval = int(interval_text)
        if not is_valid_interval(interval):
            self.error_label.setText("Check interval must be at least 5 seconds.")
            return

        if not threshold_text.isdigit():
            self.error_label.setText("Alert threshold must be a number.")
            return
        threshold = int(threshold_text)
        if not is_valid_threshold(threshold):
            self.error_label.setText("Alert threshold must be at least 1.")
            return

        cli_edit(self.name, ip=ip, port=port, clear_port=clear_port,
                  interval=interval, threshold=threshold)
        self.accept()

class HistoryDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"EDI Agent (v{__version__}) - Alert History")
        self.resize(680, 420)

        if LOGO_PATH.exists():
            self.setWindowIcon(QIcon(str(LOGO_PATH)))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        title_label = QLabel("Alert History")
        font = QFont()
        font.setPointSize(14)
        font.setBold(True)
        title_label.setFont(font)
        layout.addWidget(title_label)

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Time", "Node", "Event", "Message"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.table)

        btn_row = QHBoxLayout()
        self.clear_btn = QPushButton("Clear History")
        self.clear_btn.clicked.connect(self.clear_history)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(self.clear_btn)
        btn_row.addStretch()
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        self.reload_data()

    def reload_data(self):
        events = list(reversed(load_history()))
        self.table.setRowCount(len(events))
        for row, event in enumerate(events):
            time_item = QTableWidgetItem(format_history_timestamp(event.get("timestamp")))
            node_item = QTableWidgetItem(event.get("node", ""))
            kind_item = QTableWidgetItem(event.get("event", "").upper())
            message_item = QTableWidgetItem(event.get("message", ""))

            if event.get("event") == "offline":
                kind_item.setForeground(QColor("#e74c3c"))
            elif event.get("event") == "online":
                kind_item.setForeground(QColor("#2ecc71"))

            self.table.setItem(row, 0, time_item)
            self.table.setItem(row, 1, node_item)
            self.table.setItem(row, 2, kind_item)
            self.table.setItem(row, 3, message_item)

    def clear_history(self):
        reply = QMessageBox.question(
            self, "Clear History",
            "Delete all alert history? This cannot be undone.",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            save_history([])
            self.reload_data()

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
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels(
            ["Node Name", "IP Address", "Check", "Status", "Fails", "Interval", "Latency", "Last Checked"]
        )
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSortingEnabled(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.itemDoubleClicked.connect(self.open_edit_dialog)
        layout.addWidget(self.table)

        # --- ACTION BAR SECTION ---
        action_layout = QHBoxLayout()
        self.info_label = QLabel("Auto-checking every 30s • double-click a row to edit")
        self.edit_btn = QPushButton("Edit Selected")
        self.edit_btn.clicked.connect(self.open_edit_dialog_for_selection)
        self.history_btn = QPushButton("Alert History")
        self.history_btn.clicked.connect(self.open_history_dialog)
        self.refresh_btn = QPushButton("Refresh / Check Now")
        self.refresh_btn.clicked.connect(self.manual_refresh)

        action_layout.addWidget(self.info_label)
        action_layout.addStretch()
        action_layout.addWidget(self.edit_btn)
        action_layout.addWidget(self.history_btn)
        action_layout.addWidget(self.refresh_btn)

        layout.addLayout(action_layout)

        self.reload_data()

    def open_history_dialog(self):
        dialog = HistoryDialog(parent=self)
        dialog.exec()

    def open_edit_dialog_for_selection(self):
        row = self.table.currentRow()
        if row < 0:
            return
        self.open_edit_dialog(self.table.item(row, 0))

    def open_edit_dialog(self, item):
        row = item.row()
        name = self.table.item(row, 0).text()
        cfg = load_config()
        node = cfg["nodes"].get(name)
        if not node:
            return

        dialog = EditNodeDialog(name, node, parent=self)
        if dialog.exec():
            self.reload_data()
            if self.monitor_app:
                self.monitor_app.refresh_tray_icon(load_config())

    def manual_refresh(self):
        self.refresh_btn.setEnabled(False)
        self.refresh_btn.setText("Pinging Nodes...")
        QApplication.processEvents()
        
        if self.monitor_app:
            self.monitor_app.check_nodes(force=True)
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
            threshold = info.get("failure_threshold", DEFAULT_FAILURE_THRESHOLD)

            item_name = QTableWidgetItem(name)
            item_ip = QTableWidgetItem(info["ip"])
            item_check = QTableWidgetItem(format_check_method(info.get("port")))
            item_status = QTableWidgetItem(status)
            item_failures = QTableWidgetItem(format_failures(failures, threshold))
            item_interval = QTableWidgetItem(format_interval(info.get("check_interval", DEFAULT_CHECK_INTERVAL)))
            item_latency = QTableWidgetItem(format_latency(info.get("latency_ms")))
            item_last_checked = QTableWidgetItem(format_last_checked(info.get("last_checked")))

            item_check.setTextAlignment(Qt.AlignCenter)
            item_status.setTextAlignment(Qt.AlignCenter)
            item_failures.setTextAlignment(Qt.AlignCenter)
            item_interval.setTextAlignment(Qt.AlignCenter)
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
            self.table.setItem(row, 2, item_check)
            self.table.setItem(row, 3, item_status)
            self.table.setItem(row, 4, item_failures)
            self.table.setItem(row, 5, item_interval)
            self.table.setItem(row, 6, item_latency)
            self.table.setItem(row, 7, item_last_checked)
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

        self.history_action = self.menu.addAction("Alert History")
        self.history_action.triggered.connect(self.show_history)

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

    def check_nodes(self, force=False):
        cfg = load_config()
        if not cfg["nodes"]:
            self.refresh_tray_icon(cfg)
            return

        now = time.time()
        due_nodes = {
            name: info for name, info in cfg["nodes"].items()
            if force or now - info.get("last_checked", 0) >= info.get("check_interval", DEFAULT_CHECK_INTERVAL)
        }

        if due_nodes:
            results = ping_nodes_concurrently(due_nodes)
            for name, info in due_nodes.items():
                ip = info["ip"]
                is_online, latency_ms = results.get(name, (False, None))
                prev_status = info.get("status", "unknown")
                failures = info.get("failures", 0)
                threshold = info.get("failure_threshold", DEFAULT_FAILURE_THRESHOLD)

                info["last_checked"] = now
                info["latency_ms"] = latency_ms

                if not is_online:
                    failures += 1
                    info["failures"] = failures
                    if failures >= threshold and prev_status != "offline":
                        info["status"] = "offline"
                        message = f"ALERT: '{name}' ({ip}) is unreachable!"
                        self.tray.showMessage(
                            "EDI ALERT: Node Offline",
                            message,
                            QSystemTrayIcon.MessageIcon.Critical,
                            10000
                        )
                        record_history_event(name, "offline", message)
                else:
                    info["failures"] = 0
                    if prev_status != "online":
                        info["status"] = "online"
                        if prev_status == "offline":
                            message = f"Node '{name}' ({ip}) is back online."
                            self.tray.showMessage(
                                "EDI ALERT: Node Restored",
                                message,
                                QSystemTrayIcon.MessageIcon.Information,
                                5000
                            )
                            record_history_event(name, "online", message)

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

    def show_history(self):
        dialog = HistoryDialog()
        dialog.exec()

    def run(self):
        sys.exit(self.app.exec())

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=f"EDI Agent (v{__version__})")
    subparsers = parser.add_subparsers(dest="command")

    add_parser = subparsers.add_parser("add", help="Add a node to monitor")
    add_parser.add_argument("name", help="Node identifier (e.g. plex)")
    add_parser.add_argument("ip", help="IP address (e.g. 10.1.1.99)")
    add_parser.add_argument("--force", action="store_true", help="Overwrite an existing node with the same name")
    add_parser.add_argument("--port", type=int, default=None,
                             help="Check this TCP port instead of ICMP ping (e.g. 5432 for Postgres, 32400 for Plex)")
    add_parser.add_argument("--interval", type=int, default=None,
                             help=f"How often to check this node, in seconds (default {DEFAULT_CHECK_INTERVAL}, minimum 5)")
    add_parser.add_argument("--threshold", type=int, default=None,
                             help=f"Consecutive failures required before alerting (default {DEFAULT_FAILURE_THRESHOLD})")

    rem_parser = subparsers.add_parser("remove", help="Remove a monitored node")
    rem_parser.add_argument("name", help="Node identifier")

    edit_parser = subparsers.add_parser("edit", help="Edit an existing node's IP, port check, interval, or threshold")
    edit_parser.add_argument("name", help="Node identifier")
    edit_parser.add_argument("--ip", help="New IP address")
    edit_parser.add_argument("--port", type=int, help="Check this TCP port instead of ICMP ping")
    edit_parser.add_argument("--clear-port", action="store_true", help="Revert to ICMP ping (remove port check)")
    edit_parser.add_argument("--interval", type=int, help="How often to check this node, in seconds (minimum 5)")
    edit_parser.add_argument("--threshold", type=int, help="Consecutive failures required before alerting")

    subparsers.add_parser("list", help="List monitored nodes")
    subparsers.add_parser("test", help="Send a test notification")
    hist_parser = subparsers.add_parser("history", help="Show recent offline/recovery alert history")
    hist_parser.add_argument("--limit", type=int, default=20, help="Number of recent events to show (default 20)")
    subparsers.add_parser("help", help="Open manual window")
    subparsers.add_parser("gui", help="Run system tray monitor agent")

    args = parser.parse_args()

    if args.command == "add":
        cli_add(args.name, args.ip, force=args.force, port=args.port,
                interval=args.interval, threshold=args.threshold)
    elif args.command == "remove":
        cli_remove(args.name)
    elif args.command == "edit":
        cli_edit(args.name, ip=args.ip, port=args.port, clear_port=args.clear_port,
                  interval=args.interval, threshold=args.threshold)
    elif args.command == "list":
        cli_list()
    elif args.command == "test":
        cli_test()
    elif args.command == "history":
        cli_history(limit=args.limit)
    elif args.command == "help":
        open_manual_window()
    else:
        app = MonitorApp()
        app.run()