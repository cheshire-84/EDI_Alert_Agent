#!/usr/bin/env python3
# 8-Bit Agent - System Tray Node Monitor & Alert Agent
import sys
from pathlib import Path
from PySide6.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QHBoxLayout,
    QTextBrowser, QPushButton, QLabel
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap, QFont

from edi_agent import __version__, APP_NAME, DEFAULT_WEB_PORT

BASE_DIR = Path(__file__).parent.resolve()
ASSETS_DIR = BASE_DIR / "assets"
LOGO_PATH = ASSETS_DIR / "app_logo.png"

MANUAL_HTML = f"""
<h2>{APP_NAME} (v{__version__}) - User Manual & Command Reference</h2>

<p><b>{APP_NAME}</b> (formerly EDI Agent) is a background LAN node monitoring
daemon and desktop tray application. Full documentation, including a copy of
this manual, is at
<a href="http://8bitbunker.org/apps/8bb-agent/latest/guide.html">8bitbunker.org</a>.</p>

<hr>

<h3>Terminal CLI Commands</h3>
<p>Run these commands from any terminal prompt across your system:</p>

<ul>
  <li><b>Add a Monitored Node:</b><br>
      <code>edi-agent add &lt;name&gt; &lt;ip&gt; [--port PORT] [--interval SEC] [--threshold N]</code><br>
      <i>Example:</i> <code>edi-agent add plex 10.1.1.99 --port 32400</code><br>
      <i>Note:</i> Performs an immediate reachability check upon adding. Rejects invalid IP addresses,
      and refuses to overwrite an existing node unless you add <code>--force</code>. Add
      <code>--port</code> to check a specific TCP service (e.g. <code>5432</code> for PostgreSQL,
      <code>32400</code> for Plex, <code>8006</code> for Proxmox) instead of a plain ICMP ping &mdash;
      this confirms the service itself is running, not just that the host is reachable. Use
      <code>--interval</code> to check this node on its own schedule (seconds, default 30, minimum 5)
      and <code>--threshold</code> to control how many consecutive failures trigger an alert (default 2).</li>
      <br>
  <li><b>Remove a Monitored Node:</b><br>
      <code>edi-agent remove &lt;name&gt;</code><br>
      <i>Example:</i> <code>edi-agent remove plex</code></li>
      <br>
  <li><b>Edit a Monitored Node:</b><br>
      <code>edi-agent edit &lt;name&gt; [--ip IP] [--port PORT] [--clear-port] [--interval SEC] [--threshold N]</code><br>
      <i>Example:</i> <code>edi-agent edit gateway --port 22</code><br>
      Updates a node's IP, check method, interval, and/or alert threshold in place and re-validates
      it immediately &mdash; no need to remove and re-add. <code>--clear-port</code> reverts a node
      back to ICMP ping.</li>
      <br>
  <li><b>List All Monitored Nodes:</b><br>
      <code>edi-agent list</code><br>
      Outputs a table of registered nodes, their check method (ping or TCP port), last known status,
      failures/threshold, check interval, latency, and last-checked time.</li>
      <br>
  <li><b>Test Desktop Notifications:</b><br>
      <code>edi-agent test</code><br>
      Triggers a test desktop popup via DBus to verify system notifications.</li>
      <br>
  <li><b>View Alert History:</b><br>
      <code>edi-agent history [--limit N]</code><br>
      Shows the most recent offline/recovery events (default 20), newest first.</li>
      <br>
  <li><b>Configure Discord Alerts:</b><br>
      <code>edi-agent webhook set &lt;url&gt;</code> / <code>clear</code> / <code>test</code><br>
      <i>Example:</i> <code>edi-agent webhook set https://discord.com/api/webhooks/...</code><br>
      Mirrors offline/recovery alerts to a Discord channel via an incoming webhook, in
      addition to the desktop popup. <code>test</code> sends a message immediately to confirm
      it works. The webhook URL is never printed back out or written to the log file.</li>
      <br>
  <li><b>Run the Web Dashboard Standalone:</b><br>
      <code>edi-agent web [--port PORT]</code><br>
      Runs just the local web dashboard in the foreground, with no tray icon or
      desktop session required &mdash; useful for a headless machine. Defaults to
      port {DEFAULT_WEB_PORT} on 127.0.0.1.</li>
      <br>
  <li><b>Open Manual / Help:</b><br>
      <code>edi-agent help</code><br>
      Opens this interactive manual window.</li>
</ul>

<hr>

<h3>Desktop UI & System Tray Features</h3>
<ul>
  <li><b>System Tray Icon:</b> Docks near the clock and shows a live health badge &mdash; <b><font color="#2ecc71">green</font></b> when every node is online, <b><font color="#e74c3c">red</font></b> if any node is down. Hover for a summary; right-click to view the Dashboard, open this manual, send test alerts, configure Discord alerts, switch the theme, or exit the agent.</li>
  <li><b>Discord Webhook Dialog:</b> Paste a Discord incoming webhook URL, save it, and send a test message &mdash; all from the tray menu, no terminal needed. Clearing the field and saving removes it again.</li>
  <li><b>Web Dashboard:</b> Choose <b>View Web UI</b> from the tray menu to open a local web dashboard in your browser (<code>http://127.0.0.1:{DEFAULT_WEB_PORT}</code> by default) &mdash; the same add/edit/delete/refresh actions as the tray, with delete confirmations and toast notifications, no terminal needed. Bound to 127.0.0.1 only; it is never reachable from other machines on your network. It cannot show live pop-up alerts the way the tray does, since your browser doesn't stay open &mdash; use a Discord webhook alongside it for that.</li>
  <li><b>Dark / Light Theme:</b> Toggle from the tray menu at any time. The choice is saved and restored on the next launch. Defaults to dark.</li>
  <li><b>Infrastructure Dashboard:</b> Metric cards (Total Nodes, Online, Offline, Avg Latency) summarize fleet health at a glance above a sortable table (click any column header) &mdash; check method (ping or TCP port), status, failures/threshold, check interval, latency, and last-checked time per node.</li>
  <li><b>Add Node:</b> Click <b>Add</b> to register a new node &mdash; name, IP, optional TCP port, check interval, and alert threshold &mdash; without touching the terminal.</li>
  <li><b>Edit Node:</b> Double-click a row (or select it and click <b>Edit</b>) to change its IP, check method, interval, or threshold. Saving re-validates the node immediately.</li>
  <li><b>Delete Node:</b> Select a row and click <b>Delete</b> to remove it from monitoring, after a confirmation prompt.</li>
  <li><b>Alert History:</b> Open via the tray menu or the <b>History</b> button to see every past offline/recovery event with a timestamp &mdash; even after the desktop popup is gone. Includes a <b>Clear History</b> option.</li>
  <li><b>Refresh Now:</b> Checks every monitored node on demand, bypassing each node's own check interval.</li>
  <li><b>Help Button (<code>?</code>):</b> Click the circular <code>?</code> button at the top right of the Dashboard to open this manual anytime.</li>
</ul>

<hr>

<h3>Configuration File Location</h3>
<p>Target registry configuration is stored in JSON format at:</p>
<code>~/.config/edi-alert-agent/nodes.json</code>
<p><i>The background systemd daemon dynamically reloads changes made via CLI in real-time.</i></p>

<hr>

<h3>Frequently Asked Questions</h3>
<p>See <code>docs/FAQ.md</code> in the repository, or
<a href="http://8bitbunker.org/apps/8bb-agent/latest/guide.html">the online guide</a>,
for answers to the most common questions &mdash; other desktop environments,
Windows support, and Docker.</p>
"""

class ManualDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} (v{__version__}) - Help & Manual")
        self.resize(600, 520)

        if LOGO_PATH.exists():
            self.setWindowIcon(QIcon(str(LOGO_PATH)))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)

        # Header Section
        header_layout = QHBoxLayout()
        if LOGO_PATH.exists():
            logo_label = QLabel()
            pixmap = QPixmap(str(LOGO_PATH)).scaled(36, 36, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            logo_label.setPixmap(pixmap)
            header_layout.addWidget(logo_label)

        title = QLabel(f"{APP_NAME} (v{__version__}) Help")
        font = QFont()
        font.setPointSize(14)
        font.setBold(True)
        title.setFont(font)
        header_layout.addWidget(title)
        header_layout.addStretch()
        layout.addLayout(header_layout)

        # Content Text Browser
        text_browser = QTextBrowser()
        text_browser.setHtml(MANUAL_HTML)
        layout.addWidget(text_browser)

        # Bottom Action Bar
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        close_btn = QPushButton("Close Manual")
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

def show_manual():
    app = QApplication.instance()
    is_standalone = False
    if not app:
        app = QApplication(sys.argv)
        is_standalone = True

    dialog = ManualDialog()
    dialog.exec()

    if is_standalone:
        sys.exit(0)

if __name__ == "__main__":
    show_manual()