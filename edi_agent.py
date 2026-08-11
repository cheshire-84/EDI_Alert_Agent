#!/usr/bin/env python3
# 8-Bit Agent - System Tray Node Monitor & Alert Agent
import sys
import json
import time
import fcntl
import socket
import logging
import ipaddress
import threading
import subprocess
import argparse
import webbrowser
import urllib.request
import concurrent.futures
from pathlib import Path
from datetime import datetime
from logging.handlers import RotatingFileHandler
from PySide6.QtWidgets import (
    QApplication,
    QSystemTrayIcon,
    QMenu,
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QPushButton,
    QLabel,
    QLineEdit,
    QMessageBox,
    QFrame,
)
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QIcon, QColor, QPixmap, QFont, QPainter, QPen, QBrush

from style import DARK_GLASS_STYLE, LIGHT_GLASS_STYLE
import web_ui

__version__ = "1.9.0"
APP_NAME = "8-Bit Agent"
BASE_DIR = Path(__file__).parent.resolve()
ASSETS_DIR = BASE_DIR / "assets"
LOGO_PATH = ASSETS_DIR / "app_logo.png"
MANUAL_PATH = BASE_DIR / "manual.py"
CONFIG_PATH = Path.home() / ".config" / "edi-alert-agent" / "nodes.json"
HISTORY_PATH = Path.home() / ".config" / "edi-alert-agent" / "history.json"
SETTINGS_PATH = Path.home() / ".config" / "edi-alert-agent" / "settings.json"
LOG_PATH = Path.home() / ".local" / "state" / "edi-alert-agent" / "edi-agent.log"
MAX_HISTORY_ENTRIES = 200

DEFAULT_CHECK_INTERVAL = 30
DEFAULT_FAILURE_THRESHOLD = 2
DEFAULT_THEME = "dark"
DEFAULT_WEB_PORT = 7317

_logger = logging.getLogger("edi_agent")
_logger.setLevel(logging.INFO)


def get_logger():
    """Lazily (re)configures the module logger's file handler to point at the
    current LOG_PATH, so tests can retarget it via monkeypatch without any
    log output ever touching a real user's filesystem."""
    configured_path = getattr(get_logger, "_configured_path", None)
    if configured_path != LOG_PATH:
        for handler in list(_logger.handlers):
            _logger.removeHandler(handler)
            handler.close()
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(LOG_PATH, maxBytes=1_000_000, backupCount=3)
        handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        _logger.addHandler(handler)
        get_logger._configured_path = LOG_PATH
    return _logger


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
    except Exception as exc:
        get_logger().warning(f"load_config: failed to read {CONFIG_PATH}: {exc}")
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
    except Exception as exc:
        get_logger().warning(f"load_history: failed to read {HISTORY_PATH}: {exc}")
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
    events.append(
        {"timestamp": time.time(), "node": name, "event": event, "message": message}
    )
    save_history(events[-MAX_HISTORY_ENTRIES:])


def load_settings():
    if not SETTINGS_PATH.exists():
        return {"theme": DEFAULT_THEME}
    try:
        with open(SETTINGS_PATH, "r") as f:
            fcntl.flock(f, fcntl.LOCK_SH)
            try:
                settings = json.load(f)
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)
        settings.setdefault("theme", DEFAULT_THEME)
        return settings
    except Exception as exc:
        get_logger().warning(f"load_settings: failed to read {SETTINGS_PATH}: {exc}")
        return {"theme": DEFAULT_THEME}


def save_settings(settings):
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(SETTINGS_PATH, "w") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            json.dump(settings, f, indent=2)
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def get_theme_stylesheet(theme):
    return LIGHT_GLASS_STYLE if theme == "light" else DARK_GLASS_STYLE


def is_valid_webhook_url(url):
    return url.startswith("http://") or url.startswith("https://")


def send_discord_webhook(message):
    """POSTs to the configured Discord webhook. Never raises - failures are
    logged and reported back as False so a broken webhook can't take down
    the daemon's own alerting."""
    url = load_settings().get("discord_webhook_url")
    if not url:
        return False
    try:
        payload = json.dumps({"content": message}).encode("utf-8")
        req = urllib.request.Request(
            url, data=payload, headers={"Content-Type": "application/json"}, method="POST"
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            if not (200 <= resp.status < 300):
                get_logger().warning(f"webhook: unexpected response status {resp.status}")
                return False
            return True
    except Exception as exc:
        get_logger().warning(f"webhook: failed to send: {exc}")
        return False


def send_discord_webhook_async(message):
    """Fire-and-forget wrapper for the GUI daemon: send_discord_webhook()
    itself blocks on a network call, and calling it directly from
    check_nodes() would freeze the Qt main thread exactly like the
    pre-v1.0.1 sequential-ping bug this project already fixed once."""
    threading.Thread(target=send_discord_webhook, args=(message,), daemon=True).start()


def cli_webhook_set(url):
    if not is_valid_webhook_url(url):
        print(f"[!] '{url}' doesn't look like a valid URL (must start with http:// or https://).")
        return False
    settings = load_settings()
    settings["discord_webhook_url"] = url
    save_settings(settings)
    print("[+] Discord webhook configured.")
    get_logger().info("webhook: configured")
    return True


def cli_webhook_clear():
    settings = load_settings()
    if not settings.get("discord_webhook_url"):
        print("[!] No webhook is currently configured.")
        return False
    settings["discord_webhook_url"] = None
    save_settings(settings)
    print("[-] Webhook removed.")
    get_logger().info("webhook: removed")
    return True


def cli_webhook_test():
    if not load_settings().get("discord_webhook_url"):
        print("[!] No webhook configured. Use 'edi-agent webhook set <url>' first.")
        return False
    print("[?] Sending test message to webhook...", end=" ", flush=True)
    ok = send_discord_webhook(f"{APP_NAME} (v{__version__}): Test message. Webhook alerts are working.")
    print("Done!" if ok else "Failed.")
    if not ok:
        print("[!] Could not reach the webhook URL. Check the URL and your network.")
    return ok


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
    results = {}
    if not nodes:
        return results
    with concurrent.futures.ThreadPoolExecutor(
        max_workers=min(32, len(nodes))
    ) as executor:
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
    if port:
        return check_port(ip, port)
    return ping_node(ip)


def check_port(ip, port, timeout=1):
    start = time.monotonic()
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            latency_ms = round((time.monotonic() - start) * 1000, 1)
            return True, latency_ms
    except OSError:
        return False, None


def ping_node(ip):
    start = time.monotonic()
    res = subprocess.run(
        ["ping", "-c", "1", "-W", "1", ip],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    is_online = res.returncode == 0
    latency_ms = round((time.monotonic() - start) * 1000, 1) if is_online else None
    return is_online, latency_ms


def send_desktop_notification(title, message, urgency="normal"):
    try:
        icon_arg = str(LOGO_PATH) if LOGO_PATH.exists() else "network-server"
        subprocess.run(
            ["notify-send", "-u", urgency, "-i", icon_arg, title, message], check=True
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
        base = QIcon.fromTheme(
            "network-server", QIcon.fromTheme("utilities-system-monitor")
        ).pixmap(64, 64)
    return base.scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation)


def build_badged_icon(base_pixmap, badge_color):
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
        return False
    if port is not None and not is_valid_port(port):
        print(f"[!] '{port}' is not a valid port number (must be 1-65535).")
        return False
    if interval is not None and not is_valid_interval(interval):
        print(f"[!] '{interval}' is not a valid interval (must be at least 5 seconds).")
        return False
    if threshold is not None and not is_valid_threshold(threshold):
        print(f"[!] '{threshold}' is not a valid threshold (must be at least 1).")
        return False
    cfg = load_config()
    if name in cfg["nodes"] and not force:
        print(
            f"[!] Node '{name}' already exists ({cfg['nodes'][name]['ip']}). "
            f"Use --force to overwrite, or 'edi-agent remove {name}' first."
        )
        return False
    check_desc = f"TCP:{port}" if port else "ping"
    print(
        f"[?] Checking reachability for '{name}' ({ip}) via {check_desc}...",
        end=" ",
        flush=True,
    )
    is_online, latency_ms = check_target(ip, port)
    status = "online" if is_online else "offline"
    cfg["nodes"][name] = {
        "ip": ip,
        "port": port,
        "check_interval": interval if interval is not None else DEFAULT_CHECK_INTERVAL,
        "failure_threshold": threshold
        if threshold is not None
        else DEFAULT_FAILURE_THRESHOLD,
        "status": status,
        "failures": 0 if is_online else 1,
        "last_checked": time.time(),
        "latency_ms": latency_ms,
    }
    save_config(cfg)
    status_str = "ONLINE" if is_online else "OFFLINE"
    print(f"Done!\n[+] Added node: {name} ({ip}) -> Status: {status_str}")
    get_logger().info(f"add: '{name}' ({ip}) added, status={status}")
    return True


def cli_remove(name):
    cfg = load_config()
    if name in cfg["nodes"]:
        del cfg["nodes"][name]
        save_config(cfg)
        print(f"[-] Removed node: {name}")
        get_logger().info(f"remove: '{name}' removed")
        return True
    print(f"[!] Node '{name}' not found.")
    return False


def cli_edit(name, ip=None, port=None, clear_port=False, interval=None, threshold=None):
    cfg = load_config()
    if name not in cfg["nodes"]:
        print(f"[!] Node '{name}' not found.")
        return False
    if (
        ip is None
        and port is None
        and not clear_port
        and interval is None
        and threshold is None
    ):
        print(
            "[!] Nothing to update. Specify --ip, --port/--clear-port, --interval, and/or --threshold."
        )
        return False
    if port is not None and clear_port:
        print("[!] Cannot use --port and --clear-port together.")
        return False
    if ip is not None and not is_valid_ip(ip):
        print(f"[!] '{ip}' is not a valid IP address.")
        return False
    if port is not None and not is_valid_port(port):
        print(f"[!] '{port}' is not a valid port number (must be 1-65535).")
        return False
    if interval is not None and not is_valid_interval(interval):
        print(f"[!] '{interval}' is not a valid interval (must be at least 5 seconds).")
        return False
    if threshold is not None and not is_valid_threshold(threshold):
        print(f"[!] '{threshold}' is not a valid threshold (must be at least 1).")
        return False
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
    print(
        f"[?] Re-checking '{name}' ({node['ip']}) via {check_desc}...",
        end=" ",
        flush=True,
    )
    is_online, latency_ms = check_target(node["ip"], node.get("port"))
    node["status"] = "online" if is_online else "offline"
    node["failures"] = 0 if is_online else 1
    node["last_checked"] = time.time()
    node["latency_ms"] = latency_ms
    save_config(cfg)
    status_str = "ONLINE" if is_online else "OFFLINE"
    print(f"Done!\n[+] Updated node: {name} ({node['ip']}) -> Status: {status_str}")
    get_logger().info(f"edit: '{name}' updated, status={status_str.lower()}")
    return True


def format_latency(latency_ms):
    return f"{latency_ms:.0f} ms" if latency_ms is not None else "--"


def format_last_checked(timestamp):
    return (
        datetime.fromtimestamp(timestamp).strftime("%H:%M:%S") if timestamp else "never"
    )


def format_check_method(port):
    return f"TCP:{port}" if port else "ping"


def format_failures(failures, threshold):
    return f"{failures}/{threshold}"


def format_interval(seconds):
    return f"{seconds}s"


def format_history_timestamp(timestamp):
    return (
        datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
        if timestamp
        else "unknown"
    )


def cli_list():
    cfg = load_config()
    if not cfg["nodes"]:
        print("No nodes currently monitored.")
        return
    print(
        f"\n{'NAME':<20} {'IP ADDRESS':<18} {'CHECK':<10} {'STATUS':<10} {'FAILS':<8} {'INTERVAL':<10} {'LATENCY':<10} {'LAST CHECKED'}"
    )
    print("-" * 110)
    for name, data in cfg["nodes"].items():
        status = data.get("status", "unknown").upper()
        failures = format_failures(
            data.get("failures", 0),
            data.get("failure_threshold", DEFAULT_FAILURE_THRESHOLD),
        )
        check_method = format_check_method(data.get("port"))
        interval = format_interval(data.get("check_interval", DEFAULT_CHECK_INTERVAL))
        latency = format_latency(data.get("latency_ms"))
        last_checked = format_last_checked(data.get("last_checked"))
        print(
            f"{name:<20} {data['ip']:<18} {check_method:<10} {status:<10} {failures:<8} {interval:<10} {latency:<10} {last_checked}"
        )
    print()


def cli_test():
    print("[*] Triggering test notification...")
    send_desktop_notification(
        f"{APP_NAME} (v{__version__}): Test",
        f"This is a test notification from {APP_NAME}! Desktop alerts are working.",
        urgency="critical",
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
        print(
            f"{ts:<20} {e.get('node', ''):<20} {e.get('event', '').upper():<10} {e.get('message', '')}"
        )
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
        self.port_input = QLineEdit(
            str(node_info["port"]) if node_info.get("port") else ""
        )
        self.port_input.setPlaceholderText("e.g. 5432, 32400, 8006")
        port_row.addWidget(self.port_input)
        layout.addLayout(port_row)

        interval_row = QHBoxLayout()
        interval_row.addWidget(QLabel("Check Interval (seconds):"))
        self.interval_input = QLineEdit(
            str(node_info.get("check_interval", DEFAULT_CHECK_INTERVAL))
        )
        interval_row.addWidget(self.interval_input)
        layout.addLayout(interval_row)

        threshold_row = QHBoxLayout()
        threshold_row.addWidget(QLabel("Alert Threshold (failures):"))
        self.threshold_input = QLineEdit(
            str(node_info.get("failure_threshold", DEFAULT_FAILURE_THRESHOLD))
        )
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
        clear_port = port_text == ""
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
        cli_edit(
            self.name,
            ip=ip,
            port=port,
            clear_port=clear_port,
            interval=interval,
            threshold=threshold,
        )
        self.accept()


class AddNodeDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Node")
        self.resize(380, 260)
        if LOGO_PATH.exists():
            self.setWindowIcon(QIcon(str(LOGO_PATH)))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("Node Name:"))
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g. plex")
        name_row.addWidget(self.name_input)
        layout.addLayout(name_row)

        ip_row = QHBoxLayout()
        ip_row.addWidget(QLabel("IP Address:"))
        self.ip_input = QLineEdit()
        self.ip_input.setPlaceholderText("e.g. 10.1.1.99")
        ip_row.addWidget(self.ip_input)
        layout.addLayout(ip_row)

        port_row = QHBoxLayout()
        port_row.addWidget(QLabel("Port (blank = ICMP ping):"))
        self.port_input = QLineEdit()
        self.port_input.setPlaceholderText("e.g. 5432, 32400, 8006")
        port_row.addWidget(self.port_input)
        layout.addLayout(port_row)

        interval_row = QHBoxLayout()
        interval_row.addWidget(QLabel("Check Interval (seconds):"))
        self.interval_input = QLineEdit(str(DEFAULT_CHECK_INTERVAL))
        interval_row.addWidget(self.interval_input)
        layout.addLayout(interval_row)

        threshold_row = QHBoxLayout()
        threshold_row.addWidget(QLabel("Alert Threshold (failures):"))
        self.threshold_input = QLineEdit(str(DEFAULT_FAILURE_THRESHOLD))
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
        save_btn = QPushButton("Add Node")
        save_btn.setObjectName("PrimaryButton")
        save_btn.setDefault(True)
        save_btn.clicked.connect(self.on_save)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(save_btn)
        layout.addLayout(btn_row)

    def on_save(self):
        name = self.name_input.text().strip()
        ip = self.ip_input.text().strip()
        port_text = self.port_input.text().strip()
        interval_text = self.interval_input.text().strip()
        threshold_text = self.threshold_input.text().strip()

        if not name:
            self.error_label.setText("Node name cannot be blank.")
            return
        if name in load_config()["nodes"]:
            self.error_label.setText(f"A node named '{name}' already exists.")
            return
        if not is_valid_ip(ip):
            self.error_label.setText(f"'{ip}' is not a valid IP address.")
            return

        port = None
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

        cli_add(name, ip, port=port, interval=interval, threshold=threshold)
        self.accept()


class WebhookDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Discord Webhook Alerts")
        self.resize(440, 180)
        if LOGO_PATH.exists():
            self.setWindowIcon(QIcon(str(LOGO_PATH)))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        info = QLabel(
            "Send the same offline/recovery alerts to a Discord channel via "
            "an incoming webhook, alongside the desktop popup."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        url_row = QHBoxLayout()
        url_row.addWidget(QLabel("Webhook URL:"))
        self.url_input = QLineEdit(load_settings().get("discord_webhook_url") or "")
        self.url_input.setPlaceholderText("https://discord.com/api/webhooks/...")
        url_row.addWidget(self.url_input)
        layout.addLayout(url_row)

        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        btn_row = QHBoxLayout()
        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self.on_clear)
        test_btn = QPushButton("Send Test")
        test_btn.clicked.connect(self.on_test)
        save_btn = QPushButton("Save")
        save_btn.setObjectName("PrimaryButton")
        save_btn.setDefault(True)
        save_btn.clicked.connect(self.on_save)
        btn_row.addWidget(clear_btn)
        btn_row.addStretch()
        btn_row.addWidget(test_btn)
        btn_row.addWidget(save_btn)
        layout.addLayout(btn_row)

    def on_save(self):
        url = self.url_input.text().strip()
        if not url:
            self.status_label.setText("Enter a webhook URL, or use Clear to remove it.")
            return
        if cli_webhook_set(url):
            self.status_label.setText("Saved.")
        else:
            self.status_label.setText("That doesn't look like a valid URL (must start with http:// or https://).")

    def on_clear(self):
        self.url_input.setText("")
        cli_webhook_clear()
        self.status_label.setText("Webhook removed.")

    def on_test(self):
        url = self.url_input.text().strip()
        if not url:
            self.status_label.setText("Enter a webhook URL first.")
            return
        cli_webhook_set(url)
        if cli_webhook_test():
            self.status_label.setText("Test message sent — check Discord.")
        else:
            self.status_label.setText("Failed to send. Check the URL and your network.")


class HistoryDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"{APP_NAME} (v{__version__}) - Alert History")
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
            time_item = QTableWidgetItem(
                format_history_timestamp(event.get("timestamp"))
            )
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
            self,
            "Clear History",
            "Delete all alert history? This cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            save_history([])
            self.reload_data()


class NodeManagerDialog(QDialog):
    def __init__(self, monitor_app=None):
        super().__init__()
        self.monitor_app = monitor_app
        self.setWindowTitle(f"{APP_NAME} (v{__version__}) - Dashboard")
        self.resize(980, 560)
        self.setMinimumSize(760, 440)

        if LOGO_PATH.exists():
            self.setWindowIcon(QIcon(str(LOGO_PATH)))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # --- HEADER SECTION ---
        header_layout = QHBoxLayout()
        header_layout.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        if LOGO_PATH.exists():
            logo_label = QLabel()
            pixmap = QPixmap(str(LOGO_PATH)).scaled(
                36, 36, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            logo_label.setPixmap(pixmap)
            header_layout.addWidget(logo_label)

        title_label = QLabel("Infrastructure Dashboard")
        font = QFont()
        font.setPointSize(16)
        font.setBold(True)
        title_label.setFont(font)
        header_layout.addWidget(title_label)

        header_layout.addStretch()

        self.help_btn = QPushButton("?")
        self.help_btn.setObjectName("IconButton")
        self.help_btn.setFixedSize(32, 32)
        self.help_btn.setToolTip("Open User Manual & Help")
        self.help_btn.clicked.connect(open_manual_window)
        header_layout.addWidget(self.help_btn)

        layout.addLayout(header_layout)

        # --- METRIC SUMMARY CARDS ROW ---
        metrics_layout = QHBoxLayout()
        metrics_layout.setSpacing(12)

        self.card_total = self.create_metric_card("Total Nodes", "0", "blue", "#3b82f6")
        self.card_online = self.create_metric_card("Online", "0", "green", "#2ecc71")
        self.card_offline = self.create_metric_card("Offline", "0", "red", "#e74c3c")
        self.card_latency = self.create_metric_card("Avg Latency", "--", "purple", "#8b5cf6")

        metrics_layout.addWidget(self.card_total)
        metrics_layout.addWidget(self.card_online)
        metrics_layout.addWidget(self.card_offline)
        metrics_layout.addWidget(self.card_latency)

        layout.addLayout(metrics_layout)

        # --- TABLE SECTION ---
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels(
            [
                "Node Name",
                "IP Address",
                "Check",
                "Status",
                "Fails",
                "Interval",
                "Latency",
                "Last Checked",
            ]
        )
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)      # Node Name
        header.setSectionResizeMode(1, QHeaderView.Stretch)      # IP Address
        for col in range(2, 8):
            header.setSectionResizeMode(col, QHeaderView.ResizeToContents)
        self.table.setSortingEnabled(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setShowGrid(False)
        self.table.verticalHeader().setVisible(False)
        self.table.itemDoubleClicked.connect(self.open_edit_dialog)
        layout.addWidget(self.table)

        # --- ACTION BAR SECTION ---
        action_layout = QHBoxLayout()
        self.info_label = QLabel("Auto-checking every 30s • Double-click to edit")
        self.info_label.setStyleSheet("color: #64748b; font-size: 11px;")

        self.add_btn = QPushButton("Add")
        self.add_btn.setToolTip("Add a new node")
        self.add_btn.clicked.connect(self.open_add_dialog)

        self.edit_btn = QPushButton("Edit")
        self.edit_btn.setToolTip("Edit the selected node")
        self.edit_btn.clicked.connect(self.open_edit_dialog_for_selection)

        self.delete_btn = QPushButton("Delete")
        self.delete_btn.setToolTip("Remove the selected node")
        self.delete_btn.clicked.connect(self.delete_selected)

        self.history_btn = QPushButton("History")
        self.history_btn.setToolTip("View alert history")
        self.history_btn.clicked.connect(self.open_history_dialog)

        self.refresh_btn = QPushButton("Refresh Now")
        self.refresh_btn.setObjectName("PrimaryButton")
        self.refresh_btn.clicked.connect(self.manual_refresh)

        action_layout.addWidget(self.info_label)
        action_layout.addStretch()
        action_layout.addWidget(self.add_btn)
        action_layout.addWidget(self.edit_btn)
        action_layout.addWidget(self.delete_btn)
        action_layout.addWidget(self.history_btn)
        action_layout.addWidget(self.refresh_btn)
        layout.addLayout(action_layout)

        self.reload_data()

    def create_metric_card(self, title, value, accent, accent_color):
        card = QFrame()
        card.setObjectName("MetricCard")
        card.setProperty("accent", accent)
        card.setFixedHeight(72)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 12, 16, 12)
        card_layout.setSpacing(4)

        title_lbl = QLabel(title)
        title_lbl.setObjectName("MetricTitle")

        val_lbl = QLabel(value)
        val_lbl.setObjectName(f"Val_{title.replace(' ', '')}")
        val_lbl.setStyleSheet(
            f"font-size: 22px; font-weight: 700; color: {accent_color}; background: transparent; border: none;"
        )

        card_layout.addWidget(title_lbl)
        card_layout.addWidget(val_lbl)
        return card

    def update_metrics(self, nodes):
        total = len(nodes)
        online = sum(1 for info in nodes.values() if info.get("status") == "online")
        offline = sum(1 for info in nodes.values() if info.get("status") == "offline")

        latencies = [
            info.get("latency_ms")
            for info in nodes.values()
            if info.get("latency_ms") is not None
        ]
        avg_lat = f"{sum(latencies) / len(latencies):.0f} ms" if latencies else "--"

        self.card_total.findChild(QLabel, "Val_TotalNodes").setText(str(total))
        self.card_online.findChild(QLabel, "Val_Online").setText(str(online))
        self.card_offline.findChild(QLabel, "Val_Offline").setText(str(offline))
        self.card_latency.findChild(QLabel, "Val_AvgLatency").setText(avg_lat)

    def open_history_dialog(self):
        dialog = HistoryDialog(parent=self)
        dialog.exec()

    def open_add_dialog(self):
        dialog = AddNodeDialog(parent=self)
        if dialog.exec():
            self.reload_data()
            if self.monitor_app:
                self.monitor_app.refresh_tray_icon(load_config())

    def open_edit_dialog_for_selection(self):
        row = self.table.currentRow()
        if row < 0:
            return
        self.open_edit_dialog(self.table.item(row, 0))

    def delete_selected(self):
        row = self.table.currentRow()
        if row < 0:
            return
        name = self.table.item(row, 0).text()
        reply = QMessageBox.question(
            self, "Delete Node",
            f"Remove '{name}' from monitoring? This cannot be undone.",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            cli_remove(name)
            self.reload_data()
            if self.monitor_app:
                self.monitor_app.refresh_tray_icon(load_config())

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
        self.refresh_btn.setText("Checking...")
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
        self.refresh_btn.setText("Refresh Now")
        self.refresh_btn.setEnabled(True)

    def reload_data(self):
        cfg = load_config()
        nodes = cfg.get("nodes", {})
        self.update_metrics(nodes)

        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(nodes))
        for row, (name, info) in enumerate(nodes.items()):
            status = info.get("status", "unknown").upper()
            failures = info.get("failures", 0)
            threshold = info.get("failure_threshold", DEFAULT_FAILURE_THRESHOLD)

            item_name = QTableWidgetItem(name)
            item_ip = QTableWidgetItem(info["ip"])
            item_check = QTableWidgetItem(format_check_method(info.get("port")))
            item_status = QTableWidgetItem(status)
            item_failures = QTableWidgetItem(format_failures(failures, threshold))
            item_interval = QTableWidgetItem(
                format_interval(info.get("check_interval", DEFAULT_CHECK_INTERVAL))
            )
            item_latency = QTableWidgetItem(format_latency(info.get("latency_ms")))
            item_last_checked = QTableWidgetItem(
                format_last_checked(info.get("last_checked"))
            )

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
                item_status.setForeground(QColor("#64748b"))

            if failures > 0:
                item_failures.setForeground(QColor("#f59e0b"))

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

        self.theme = load_settings().get("theme", DEFAULT_THEME)
        self.app.setStyleSheet(get_theme_stylesheet(self.theme))

        base_pixmap = load_base_tray_pixmap()
        self.icon_neutral = QIcon(base_pixmap)
        self.icon_online = build_badged_icon(base_pixmap, QColor("#2ecc71"))
        self.icon_offline = build_badged_icon(base_pixmap, QColor("#e74c3c"))

        self.tray = QSystemTrayIcon()
        self.tray.setIcon(self.icon_neutral)
        self.tray.setToolTip(f"{APP_NAME} (v{__version__})")
        self.tray.setVisible(True)

        self.menu = QMenu()
        self.status_action = self.menu.addAction(f"{APP_NAME} (v{__version__}): Active")
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
        self.webhook_action = self.menu.addAction("Discord Webhook...")
        self.webhook_action.triggered.connect(self.show_webhook_dialog)
        self.web_ui_action = self.menu.addAction("View Web UI")
        self.web_ui_action.triggered.connect(self.open_web_ui)
        self.theme_action = self.menu.addAction(self._theme_action_label())
        self.theme_action.triggered.connect(self.toggle_theme)
        self.quit_action = self.menu.addAction("Quit Agent")
        self.quit_action.triggered.connect(self.app.quit)
        self.tray.setContextMenu(self.menu)

        self.dialog = None
        self.next_check_timer = QTimer()
        self.next_check_timer.setSingleShot(True)
        self.next_check_timer.timeout.connect(self.check_nodes)
        self.next_check_timer.start(500)

        self.web_port = load_settings().get("web_ui_port", DEFAULT_WEB_PORT)
        threading.Thread(
            target=web_ui.run_web_server,
            kwargs={"port": self.web_port, "monitor_app": self},
            daemon=True,
        ).start()
        get_logger().info(f"{APP_NAME} v{__version__} daemon started (web UI on 127.0.0.1:{self.web_port})")

    def _theme_action_label(self):
        return "Switch to Light Theme" if self.theme == "dark" else "Switch to Dark Theme"

    def toggle_theme(self):
        self.theme = "light" if self.theme == "dark" else "dark"
        self.app.setStyleSheet(get_theme_stylesheet(self.theme))
        save_settings({**load_settings(), "theme": self.theme})
        self.theme_action.setText(self._theme_action_label())
        get_logger().info(f"theme switched to {self.theme}")

    def trigger_test_alert(self):
        self.tray.showMessage(
            f"{APP_NAME} (v{__version__}): Test",
            f"This is a test notification from {APP_NAME}!",
            QSystemTrayIcon.MessageIcon.Information,
            5000,
        )

    def check_nodes(self, force=False):
        cfg = load_config()
        if not cfg["nodes"]:
            self.refresh_tray_icon(cfg)
            self.schedule_next_check()
            return
        now = time.time()
        due_nodes = {
            name: info
            for name, info in cfg["nodes"].items()
            if force
            or now - info.get("last_checked", 0)
            >= info.get("check_interval", DEFAULT_CHECK_INTERVAL)
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
                            10000,
                        )
                        record_history_event(name, "offline", message)
                        get_logger().warning(f"'{name}' ({ip}) marked OFFLINE after {failures} failures")
                        send_discord_webhook_async(message)
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
                                5000,
                            )
                            record_history_event(name, "online", message)
                            get_logger().info(f"'{name}' ({ip}) back ONLINE")
                            send_discord_webhook_async(message)
            save_config(cfg)
        self.refresh_tray_icon(cfg)
        if self.dialog and self.dialog.isVisible():
            self.dialog.reload_data()
        self.schedule_next_check()

    def schedule_next_check(self):
        """Self-reschedules rather than relying on a fixed 30s QTimer, so a
        node with a shorter --interval is actually checked that often instead
        of being limited to the daemon's old fixed tick rate."""
        cfg = load_config()
        nodes = cfg.get("nodes", {})
        if not nodes:
            next_ms = DEFAULT_CHECK_INTERVAL * 1000
        else:
            now = time.time()
            remaining = [
                max(
                    0,
                    info.get("check_interval", DEFAULT_CHECK_INTERVAL)
                    - (now - info.get("last_checked", 0)),
                )
                for info in nodes.values()
            ]
            next_s = min(remaining)
            next_ms = max(1000, int(next_s * 1000))
        self.next_check_timer.stop()
        self.next_check_timer.start(next_ms)

    def refresh_tray_icon(self, cfg):
        nodes = cfg.get("nodes", {})
        if not nodes:
            self.tray.setIcon(self.icon_neutral)
            self.tray.setToolTip(f"{APP_NAME} (v{__version__}): No nodes monitored")
            return
        down = [name for name, info in nodes.items() if info.get("status") == "offline"]
        if down:
            self.tray.setIcon(self.icon_offline)
            self.tray.setToolTip(
                f"{APP_NAME} (v{__version__}): {len(down)} node(s) offline"
            )
        else:
            self.tray.setIcon(self.icon_online)
            self.tray.setToolTip(f"{APP_NAME} (v{__version__}): All nodes online")

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

    def show_webhook_dialog(self):
        dialog = WebhookDialog()
        dialog.exec()

    def open_web_ui(self):
        webbrowser.open(f"http://127.0.0.1:{self.web_port}")

    def run(self):
        sys.exit(self.app.exec())


def build_arg_parser():
    parser = argparse.ArgumentParser(description=f"{APP_NAME} (v{__version__})")
    subparsers = parser.add_subparsers(dest="command")

    add_parser = subparsers.add_parser("add", help="Add a node to monitor")
    add_parser.add_argument("name", help="Node identifier (e.g. plex)")
    add_parser.add_argument("ip", help="IP address (e.g. 10.1.1.99)")
    add_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing node with the same name",
    )
    add_parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Check this TCP port instead of ICMP ping",
    )
    add_parser.add_argument(
        "--interval",
        type=int,
        default=None,
        help=f"Check interval in seconds (default {DEFAULT_CHECK_INTERVAL})",
    )
    add_parser.add_argument(
        "--threshold",
        type=int,
        default=None,
        help=f"Failure threshold (default {DEFAULT_FAILURE_THRESHOLD})",
    )

    rem_parser = subparsers.add_parser("remove", help="Remove a monitored node")
    rem_parser.add_argument("name", help="Node identifier")

    edit_parser = subparsers.add_parser("edit", help="Edit an existing node")
    edit_parser.add_argument("name", help="Node identifier")
    edit_parser.add_argument("--ip", help="New IP address")
    edit_parser.add_argument("--port", type=int, help="Check TCP port")
    edit_parser.add_argument(
        "--clear-port", action="store_true", help="Revert to ICMP ping"
    )
    edit_parser.add_argument("--interval", type=int, help="Check interval in seconds")
    edit_parser.add_argument("--threshold", type=int, help="Failure threshold")

    subparsers.add_parser("list", help="List monitored nodes")
    subparsers.add_parser("test", help="Send a test notification")

    hist_parser = subparsers.add_parser("history", help="Show alert history")
    hist_parser.add_argument(
        "--limit", type=int, default=20, help="Number of events to show"
    )

    webhook_parser = subparsers.add_parser(
        "webhook", help="Configure a Discord webhook for offline/recovery alerts"
    )
    webhook_sub = webhook_parser.add_subparsers(dest="webhook_action")
    webhook_set_parser = webhook_sub.add_parser("set", help="Set the webhook URL")
    webhook_set_parser.add_argument("url")
    webhook_sub.add_parser("clear", help="Remove the configured webhook")
    webhook_sub.add_parser("test", help="Send a test message to the configured webhook")

    web_cmd_parser = subparsers.add_parser(
        "web", help="Run the local web dashboard standalone (no tray icon required)"
    )
    web_cmd_parser.add_argument(
        "--port", type=int, default=None,
        help=f"Port to bind on 127.0.0.1 (default {DEFAULT_WEB_PORT})",
    )

    subparsers.add_parser("help", help="Open manual window")
    subparsers.add_parser("gui", help="Run system tray monitor agent")
    return parser


def main():
    args = build_arg_parser().parse_args()

    if args.command == "add":
        success = cli_add(
            args.name,
            args.ip,
            force=args.force,
            port=args.port,
            interval=args.interval,
            threshold=args.threshold,
        )
    elif args.command == "remove":
        success = cli_remove(args.name)
    elif args.command == "edit":
        success = cli_edit(
            args.name,
            ip=args.ip,
            port=args.port,
            clear_port=args.clear_port,
            interval=args.interval,
            threshold=args.threshold,
        )
    elif args.command == "list":
        success = cli_list()
    elif args.command == "test":
        success = cli_test()
    elif args.command == "history":
        success = cli_history(limit=args.limit)
    elif args.command == "webhook":
        if args.webhook_action == "set":
            success = cli_webhook_set(args.url)
        elif args.webhook_action == "clear":
            success = cli_webhook_clear()
        elif args.webhook_action == "test":
            success = cli_webhook_test()
        else:
            print("[!] Specify a webhook action: set <url>, clear, or test.")
            success = False
    elif args.command == "help":
        success = open_manual_window()
    elif args.command == "web":
        port = args.port if args.port is not None else load_settings().get("web_ui_port", DEFAULT_WEB_PORT)
        print(f"[*] {APP_NAME} web dashboard running at http://127.0.0.1:{port} (Ctrl+C to stop)")
        web_ui.run_web_server(port=port)
        return
    else:
        app = MonitorApp()
        app.run()
        return

    if success is False:
        sys.exit(1)


if __name__ == "__main__":
    main()
