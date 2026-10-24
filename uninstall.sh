#!/usr/bin/env bash
set -e

echo "Uninstalling Hold-to-Dictate..."

systemctl --user stop hold-dictate 2>/dev/null || true
systemctl --user disable hold-dictate 2>/dev/null || true

rm -f "$HOME/.config/systemd/user/hold-dictate.service"
systemctl --user daemon-reload

rm -f "$HOME/.local/bin/hold-dictate.py"

echo "Do you also want to remove downloaded Whisper models? [y/N]"
read -r resp
if [[ "$resp" =~ ^[Yy]$ ]]; then
    rm -rf "$HOME/.local/share/whisper-models"
    echo "Removed Whisper models."
fi

echo "Hold-to-Dictate uninstalled successfully."
