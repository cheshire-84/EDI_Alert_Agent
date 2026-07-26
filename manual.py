#!/usr/bin/env python3
import sys
from pathlib import Path
from PySide6.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QHBoxLayout,
    QTextBrowser, QPushButton, QLabel
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap, QFont

BASE_DIR = Path(__file__).parent.resolve()
ASSETS_DIR = BASE_DIR / "assets"
LOGO_PATH = ASSETS_DIR / "app_logo.png"

MANUAL_HTML = """
<h2>EDI Agent (v1) - User Manual & Command Reference</h2>

<p><b>EDI Agent</b> is a background LAN node monitoring daemon and desktop tray application.</p>

<hr>

<h3>💻 Terminal CLI Commands</h3>
<p>Run these commands from any terminal prompt across your system:</p>

<ul>
  <li><b>Add a Monitored Node:</b><br>
      <code>edi-agent add &lt;name&gt; &lt;ip&gt;</code><br>
      <i>Example:</i> <code>edi-agent add plex 10.1.1.99</code><br>
      <i>Note:</i> Performs an immediate reachability check upon adding.</li>
      <br>
  <li><b>Remove a Monitored Node:</b><br>
      <code>edi-agent remove &lt;name&gt;</code><br>
      <i>Example:</i> <code>edi-agent remove plex</code></li>
      <br>
  <li><b>List All Monitored Nodes:</b><br>
      <code>edi-agent list</code><br>
      Outputs a table of registered nodes and their last known status.</li>
      <br>
  <li><b>Test Desktop Notifications:</b><br>
      <code>edi-agent test</code><br>
      Triggers a test desktop popup via DBus to verify system notifications.</li>
      <br>
  <li><b>Open Manual / Help:</b><br>
      <code>edi-agent help</code><br>
      Opens this interactive manual window.</li>
</ul>

<hr>

<h3>🖥️ Desktop UI & System Tray Features</h3>
<ul>
  <li><b>System Tray Icon:</b> Docks near the clock. Right-click to view the status, open this manual, send test alerts, or exit the agent.</li>
  <li><b>Status Window:</b> Displays tracked nodes with color-coded status badges (<b><font color="#2ecc71">ONLINE</font></b> / <b><font color="#e74c3c">OFFLINE</font></b>).</li>
  <li><b>Refresh / Check Now:</b> Pings all monitored nodes on demand.</li>
  <li><b>Help Button (<code>?</code>):</b> Click the <code>?</code> button at the top right of the status window to open this manual anytime.</li>
</ul>

<hr>

<h3>⚙️ Configuration File Location</h3>
<p>Target registry configuration is stored in JSON format at:</p>
<code>~/.config/edi-alert-agent/nodes.json</code>
<p><i>The background systemd daemon dynamically reloads changes made via CLI in real-time.</i></p>
"""

class ManualDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("EDI Agent (v1) - Help & Manual")
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

        title = QLabel("EDI Agent (v1) Help")
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