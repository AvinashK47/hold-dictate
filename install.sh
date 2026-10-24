#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODEL_DIR="$HOME/.local/share/whisper-models"
MODEL_FILE="$MODEL_DIR/ggml-small.en.bin"
MODEL_URL="https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small.en.bin"

echo "========================================="
echo "   Hold-to-Dictate Installer (Linux)     "
echo "========================================="

# 1. Package Dependencies Check
if command -v pacman >/dev/null 2>&1; then
    echo "[*] Arch Linux detected. Verifying dependencies..."
    PKGS=("whisper-cpp" "ydotool" "python-evdev" "wl-clipboard" "pipewire")
    MISSING=()
    for pkg in "${PKGS[@]}"; do
        if ! pacman -Q "$pkg" >/dev/null 2>&1; then
            MISSING+=("$pkg")
        fi
    done

    if [ ${#MISSING[@]} -gt 0 ]; then
        echo "[*] Installing missing packages: ${MISSING[*]}"
        sudo pacman -S --needed --noconfirm "${MISSING[@]}"
    else
        echo "[✓] All Arch packages already installed."
    fi
else
    echo "[!] Non-Arch distro detected. Please ensure the following are installed:"
    echo "    - whisper-cpp (or whisper.cpp binary in PATH)"
    echo "    - ydotool & ydotoold"
    echo "    - python-evdev (python3 -m pip install evdev)"
    echo "    - wl-clipboard (wl-copy)"
    echo "    - pipewire (pw-record)"
fi

# 2. Add user to input group if not already a member
if ! id -nG "$USER" | grep -qw "input"; then
    echo "[*] Adding $USER to 'input' group for hardware key listener..."
    sudo usermod -aG input "$USER"
    echo "[!] Note: You may need to log out and log back in once for group changes to take full effect."
else
    echo "[✓] User $USER is already in the 'input' group."
fi

# 3. Install udev rule for persistent uinput / input permissions
if [ ! -f /etc/udev/rules.d/99-input.rules ]; then
    echo "[*] Installing udev rules to /etc/udev/rules.d/99-input.rules..."
    sudo cp "$SCRIPT_DIR/udev/99-input.rules" /etc/udev/rules.d/99-input.rules
    sudo udevadm control --reload-rules && sudo udevadm trigger
    echo "[✓] udev rules applied."
else
    echo "[✓] udev rules already exist."
fi

# Grant immediate ACL permissions to current session if needed
sudo setfacl -m "u:$USER:rw" /dev/input/event* /dev/uinput 2>/dev/null || true

# 4. Download Whisper Model (small.en)
mkdir -p "$MODEL_DIR"
if [ ! -f "$MODEL_FILE" ]; then
    echo "[*] Downloading Whisper small.en model (~466 MB)..."
    curl -L --progress-bar -o "$MODEL_FILE" "$MODEL_URL"
    echo "[✓] Model downloaded successfully to $MODEL_FILE"
else
    echo "[✓] Whisper model already present at $MODEL_FILE"
fi

# 5. Install Daemon Binary
mkdir -p "$HOME/.local/bin"
echo "[*] Installing daemon to $HOME/.local/bin/hold-dictate.py..."
cp "$SCRIPT_DIR/bin/hold-dictate.py" "$HOME/.local/bin/hold-dictate.py"
chmod +x "$HOME/.local/bin/hold-dictate.py"

# 6. Install and enable systemd user services
mkdir -p "$HOME/.config/systemd/user"
echo "[*] Installing systemd service..."
cp "$SCRIPT_DIR/systemd/hold-dictate.service" "$HOME/.config/systemd/user/hold-dictate.service"

systemctl --user daemon-reload

# Enable & start ydotool
if systemctl --user list-unit-files | grep -q "ydotool.service"; then
    systemctl --user enable --now ydotool
    echo "[✓] ydotool service enabled and active."
fi

# Enable & start hold-dictate
systemctl --user enable --now hold-dictate
echo "[✓] hold-dictate service enabled and active."

echo ""
echo "========================================="
echo "   🎉 Installation Complete!             "
echo "========================================="
echo "How to use:"
echo "  1. Focus any text field (terminal, browser, IDE, chat bar)."
echo "  2. Hold down [Right Alt] and speak."
echo "  3. Release [Right Alt] to transcribe and type directly into the field!"
echo ""
echo "To monitor live logs:"
echo "  journalctl --user -u hold-dictate -f"
echo "========================================="
