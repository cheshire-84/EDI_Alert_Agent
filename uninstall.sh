#!/bin/bash
set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="$HOME/.local/bin"
SERVICE_DIR="$HOME/.config/systemd/user"
SERVICE_FILE="$SERVICE_DIR/edi-alert-agent.service"
CONFIG_DIR="$HOME/.config/edi-alert-agent"

echo "[*] Stopping and disabling systemd user service..."
systemctl --user disable --now edi-alert-agent.service 2>/dev/null || true

echo "[*] Removing systemd service file..."
rm -f "$SERVICE_FILE"
systemctl --user daemon-reload

echo "[*] Removing global CLI wrapper (~/.local/bin/edi-agent)..."
rm -f "$BIN_DIR/edi-agent"

echo "[*] Removing Python virtual environment..."
rm -rf "$PROJECT_DIR/venv"

read -p "[?] Remove monitored node config at $CONFIG_DIR too? (y/N): " confirm
if [[ "$confirm" =~ ^[Yy]$ ]]; then
    rm -rf "$CONFIG_DIR"
    echo "[*] Removed node configuration."
else
    echo "[*] Keeping node configuration at $CONFIG_DIR."
fi

echo "[+] EDI Alert Agent has been uninstalled."
echo "    (The project directory itself was left untouched: $PROJECT_DIR)"
