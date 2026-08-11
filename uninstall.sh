#!/bin/bash
set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="$HOME/.local/bin"
SERVICE_DIR="$HOME/.config/systemd/user"
SERVICE_FILE="$SERVICE_DIR/edi-alert-agent.service"
CONFIG_DIR="$HOME/.config/edi-alert-agent"
STATE_DIR="$HOME/.local/state/edi-alert-agent"
MAN_FILE="$HOME/.local/share/man/man1/edi-agent.1"

echo "[*] Stopping and disabling systemd user service..."
systemctl --user disable --now edi-alert-agent.service 2>/dev/null || true

echo "[*] Removing systemd service file..."
rm -f "$SERVICE_FILE"
systemctl --user daemon-reload

echo "[*] Removing global CLI command (~/.local/bin/edi-agent)..."
rm -f "$BIN_DIR/edi-agent"

echo "[*] Removing man page..."
rm -f "$MAN_FILE"

echo "[*] Removing Python virtual environment..."
rm -rf "$PROJECT_DIR/venv"

read -p "[?] Remove monitored node config, history, and settings at $CONFIG_DIR too? (y/N): " confirm
if [[ "$confirm" =~ ^[Yy]$ ]]; then
    rm -rf "$CONFIG_DIR"
    echo "[*] Removed node configuration."
else
    echo "[*] Keeping node configuration at $CONFIG_DIR."
fi

read -p "[?] Remove application log at $STATE_DIR too? (y/N): " confirm_log
if [[ "$confirm_log" =~ ^[Yy]$ ]]; then
    rm -rf "$STATE_DIR"
    echo "[*] Removed application log."
else
    echo "[*] Keeping application log at $STATE_DIR."
fi

echo "[+] EDI Alert Agent has been uninstalled."
echo "    (The project directory itself was left untouched: $PROJECT_DIR)"
