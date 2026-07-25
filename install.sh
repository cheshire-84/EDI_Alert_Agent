#!/bin/bash
set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="$HOME/.local/bin"
SERVICE_DIR="$HOME/.config/systemd/user"

echo "[*] Setting up Python virtual environment..."
python3 -m venv "$PROJECT_DIR/venv"
"$PROJECT_DIR/venv/bin/pip" install --upgrade pip
"$PROJECT_DIR/venv/bin/pip" install -r "$PROJECT_DIR/requirements.txt"

echo "[*] Installing global CLI wrapper (~/.local/bin/edi-agent)..."
mkdir -p "$BIN_DIR"
cat << EOF > "$BIN_DIR/edi-agent"
#!/bin/bash
"$PROJECT_DIR/venv/bin/python" "$PROJECT_DIR/edi_agent.py" "\$@"
EOF
chmod +x "$BIN_DIR/edi-agent"

echo "[*] Configuring systemd user service..."
mkdir -p "$SERVICE_DIR"
cat << EOF > "$SERVICE_DIR/edi-alert-agent.service"
[Unit]
Description=EDI Alert Agent LAN Node Monitor
After=graphical-session.target network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=$PROJECT_DIR/venv/bin/python $PROJECT_DIR/edi_agent.py gui
Restart=on-failure
RestartSec=5s

[Install]
WantedBy=graphical-session.target
EOF

systemctl --user daemon-reload
systemctl --user enable --now edi-alert-agent.service

echo "[+] EDI Alert Agent successfully installed and active!"