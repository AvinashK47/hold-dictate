# hold-dictate

System-wide hold-to-speak voice dictation for Linux (Wayland & X11), powered by local `whisper.cpp`.

Hold down a key, speak naturally, and release. The speech is transcribed locally with OpenAI's Whisper model and automatically typed into whatever window or input field currently has cursor focus — whether that's your terminal, browser URL bar, code editor, or AI chat prompt.

```
       [ Hold Key ]                        [ Release Key ]
             │                                    │
             ▼                                    ▼
┌─────────────────────────┐              ┌─────────────────────────┐
│  Record audio via       │              │  Transcribe with        │
│  PipeWire (16kHz WAV)   │ ───────────► │  whisper.cpp (small.en) │
└─────────────────────────┘              └─────────────────────────┘
                                                      │
                                                      ▼
                                         ┌─────────────────────────┐
                                         │  Inject text via        │
                                         │  ydotool & wl-clipboard │
                                         └─────────────────────────┘
```

---

## Features

- **Hold-to-Talk (Push-to-Talk):** Press and hold `Right Alt` (or any key you configure) to speak; release to transcribe and type.
- **Wayland Native:** Uses `ydotool` via `/dev/uinput` to emulate a virtual hardware keyboard, bypassing Wayland window isolation restrictions. Works seamlessly across KDE Plasma, GNOME, Hyprland, Sway, and X11.
- **100% Offline & Private:** Runs entirely on your machine using `whisper.cpp`. No audio leaves your computer.
- **Accurate & Developer-Friendly:** Defaults to the `small.en` model (~466 MB), which excels at technical vocabulary, coding syntax, punctuation, and capitalization.
- **Zero AUR or Untrusted Bloat:** Relies only on official Arch packages (`whisper-cpp`, `ydotool`, `python-evdev`, `wl-clipboard`, `pipewire`).
- **Sound & Notification Cues:** Audio chimes on key down and key up via `canberra-gtk-play`, with real-time desktop notifications.
- **Accidental Tap Protection:** Discards key presses shorter than 350 ms.
- **Dual Injection:** Types text directly into the focused field and simultaneously copies it to your clipboard (`wl-copy`) as a backup.

---

## Prerequisites

On **Arch Linux**, all required packages are in the official repositories:

```bash
sudo pacman -S --needed whisper-cpp ydotool python-evdev wl-clipboard pipewire
```

> [!NOTE]
> `ydotool` and `python-evdev` require access to `/dev/uinput` and `/dev/input/event*`. The installer sets up permanent udev rules and adds your user to the `input` group.

---

## Quick Start

### 1. Clone & Run the Installer

```bash
git clone https://github.com/AvinashK47/hold-dictate.git
cd hold-dictate
chmod +x install.sh
./install.sh
```

The installer will:
1. Verify and install missing packages.
2. Configure udev permissions for `/dev/uinput` and `/dev/input/event*`.
3. Add your user to the `input` group if needed.
4. Download the Whisper `small.en` model to `~/.local/share/whisper-models/`.
5. Install and enable the `ydotool` and `hold-dictate` user systemd services.

---

## Usage

1. Focus any text field (terminal prompt, browser tab, IDE, or chat box).
2. **Hold down `Right Alt`** and speak your prompt or instruction.
3. **Release `Right Alt`**. The transcribed text will appear at your cursor within 1–2 seconds.

### Viewing Live Logs

To see transcription logs and timing in real-time:

```bash
journalctl --user -u hold-dictate -f
```

---

## Configuration

### Changing the Trigger Key

The default trigger key is `KEY_RIGHTALT` (AltGr), which is easily reached with your right thumb and does not emit characters on its own.

To change it to another key (e.g. `KEY_RIGHTCTRL`, `KEY_CAPSLOCK`, `KEY_F8`):

1. Edit the service configuration:
   ```bash
   systemctl --user edit --full hold-dictate.service
   ```
2. Update the `ExecStart` line:
   ```ini
   ExecStart=%h/.local/bin/hold-dictate.py --key KEY_RIGHTCTRL
   ```
3. Reload and restart:
   ```bash
   systemctl --user daemon-reload && systemctl --user restart hold-dictate
   ```

### Changing the Whisper Model

To use a different model (e.g. `base.en` for faster response or `large-v3-turbo` for maximum accuracy):

1. Download the ggml model file from Hugging Face into `~/.local/share/whisper-models/`:
   ```bash
   curl -L -o ~/.local/share/whisper-models/ggml-base.en.bin \
     https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.en.bin
   ```
2. Update the service:
   ```ini
   ExecStart=%h/.local/bin/hold-dictate.py --model %h/.local/share/whisper-models/ggml-base.en.bin
   ```
3. Reload and restart:
   ```bash
   systemctl --user daemon-reload && systemctl --user restart hold-dictate
   ```

---

## Service Management

| Action | Command |
| :--- | :--- |
| **Check status** | `systemctl --user status hold-dictate` |
| **Restart service** | `systemctl --user restart hold-dictate` |
| **Stop service** | `systemctl --user stop hold-dictate` |
| **Disable autostart** | `systemctl --user disable hold-dictate` |

---

## Uninstall

To remove the daemon and service:

```bash
cd hold-dictate
chmod +x uninstall.sh
./uninstall.sh
```
