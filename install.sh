#!/bin/bash
set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="$HOME/.local/bin"
SERVICE_DIR="$HOME/.config/systemd/user"
MAN_DIR="$HOME/.local/share/man/man1"

echo "[*] Setting up Python virtual environment..."
python3 -m venv "$PROJECT_DIR/venv"
"$PROJECT_DIR/venv/bin/pip" install --upgrade pip

echo "[*] Installing EDI Agent as an editable package (pip install -e .)..."
"$PROJECT_DIR/venv/bin/pip" install -e "$PROJECT_DIR"

echo "[*] Linking global CLI command (~/.local/bin/edi-agent)..."
mkdir -p "$BIN_DIR"
ln -sf "$PROJECT_DIR/venv/bin/edi-agent" "$BIN_DIR/edi-agent"

echo "[*] Installing man page (man edi-agent)..."
mkdir -p "$MAN_DIR"
cp "$PROJECT_DIR/man/edi-agent.1" "$MAN_DIR/edi-agent.1"
command -v mandb >/dev/null 2>&1 && mandb -q "$HOME/.local/share/man" 2>/dev/null || true

echo "[*] Configuring systemd user service..."
mkdir -p "$SERVICE_DIR"
cat << EOF > "$SERVICE_DIR/edi-alert-agent.service"
[Unit]
Description=EDI Alert Agent LAN Node Monitor
After=graphical-session.target network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=$PROJECT_DIR/venv/bin/edi-agent gui
Restart=on-failure
RestartSec=5s

[Install]
WantedBy=graphical-session.target
EOF

systemctl --user daemon-reload
systemctl --user enable --now edi-alert-agent.service

echo "[+] EDI Alert Agent successfully installed and active!"
echo "    Run 'man edi-agent' for the full command reference (you may need to open a new shell)."
