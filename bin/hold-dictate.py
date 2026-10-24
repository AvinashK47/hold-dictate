#!/usr/bin/env python3
"""
hold-dictate.py - Hold-to-speak voice dictation daemon for Linux / Wayland.
Powered by whisper.cpp, PipeWire, evdev, and ydotool.
"""

import os
import sys
import time
import signal
import subprocess
import selectors
import re
import argparse
import evdev
from evdev import ecodes

# Default Configuration
DEFAULT_KEY = "KEY_RIGHTALT"
DEFAULT_MODEL = os.path.expanduser("~/.local/share/whisper-models/ggml-small.en.bin")
AUDIO_FILE = "/tmp/hold_dictate_recording.wav"
MIN_DURATION = 0.35  # Ignore taps shorter than 350ms
THREADS = 8

# Silence / Hallucination filters
HALLUCINATIONS = {
    "you", "thank you", "thank you.", "thanks for watching", "thanks for watching.",
    "bye", "bye.", "subscribe", "subtitles by", "translated by", "(beep)", "[blank_audio]"
}


def play_sound(sound_name):
    """Play a lightweight desktop sound cue asynchronously."""
    try:
        subprocess.Popen(
            ["canberra-gtk-play", "-i", sound_name],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
    except Exception:
        pass


def show_notify(title, message, expire_ms=2000):
    """Show a desktop notification using notify-send."""
    try:
        subprocess.Popen([
            "notify-send",
            "-t", str(expire_ms),
            "-h", "string:x-canonical-private-synchronous:hold_dictate",
            title,
            message
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass


def get_ydotool_socket():
    """Find the active ydotool socket."""
    if "YDOTOOL_SOCKET" in os.environ:
        return os.environ["YDOTOOL_SOCKET"]
    uid = os.getuid()
    standard_socket = f"/run/user/{uid}/.ydotool_socket"
    if os.path.exists(standard_socket):
        return standard_socket
    return None


def clean_transcription(text):
    """Remove Whisper artifact tags, hallucinations, and extra whitespace."""
    if not text:
        return ""
    # Remove bracketed and parenthesized comments e.g. [BLANK_AUDIO] or (chuckles)
    text = re.sub(r"\[.*?\]", "", text)
    text = re.sub(r"\(.*?\)", "", text)
    text = " ".join(text.split()).strip()

    if text.lower() in HALLUCINATIONS:
        return ""
    return text


class HoldDictateDaemon:
    def __init__(self, key_name=DEFAULT_KEY, model_path=DEFAULT_MODEL):
        self.key_name = key_name
        self.key_code = getattr(ecodes, key_name, None)
        if self.key_code is None:
            print(f"[!] Error: Invalid evdev key name '{key_name}'", file=sys.stderr)
            sys.exit(1)

        self.model_path = model_path
        if not os.path.isfile(self.model_path):
            print(f"[!] Error: Whisper model not found at {self.model_path}", file=sys.stderr)
            sys.exit(1)

        self.is_recording = False
        self.start_time = 0
        self.rec_proc = None
        self.selector = selectors.DefaultSelector()
        self.registered_devices = {}
        self.ydotool_socket = get_ydotool_socket()

        print(f"[*] Initialized Hold-to-Dictate:")
        print(f"    - Target Key: {self.key_name} (code {self.key_code})")
        print(f"    - Model: {self.model_path}")
        print(f"    - ydotool socket: {self.ydotool_socket}")

    def update_devices(self):
        """Scan and register all input devices containing the target key."""
        current_paths = set(evdev.list_devices())
        registered_paths = set(self.registered_devices.keys())

        # Unregister disconnected devices
        for path in registered_paths - current_paths:
            dev = self.registered_devices.pop(path)
            try:
                self.selector.unregister(dev)
                dev.close()
            except Exception:
                pass
            print(f"[-] Unregistered disconnected device: {path}")

        # Register newly discovered devices
        for path in current_paths - registered_paths:
            try:
                dev = evdev.InputDevice(path)
                caps = dev.capabilities()
                if ecodes.EV_KEY in caps:
                    keys = caps[ecodes.EV_KEY]
                    if self.key_code in keys:
                        self.selector.register(dev, selectors.EVENT_READ)
                        self.registered_devices[path] = dev
                        print(f"[+] Listening on device: {dev.name} ({path})")
                    else:
                        dev.close()
                else:
                    dev.close()
            except Exception:
                pass

    def start_recording(self):
        """Called when key is pressed down."""
        if self.is_recording:
            return
        self.is_recording = True
        self.start_time = time.time()

        if os.path.exists(AUDIO_FILE):
            try:
                os.remove(AUDIO_FILE)
            except OSError:
                pass

        play_sound("Oxygen-Sys-App-Message")
        show_notify("🎙️ Listening...", "Hold key while speaking, release to send", 10000)
        print("\n[🎙️] Key DOWN: Recording audio...")

        self.rec_proc = subprocess.Popen(
            [
                "pw-record",
                "--rate", "16000",
                "--channels", "1",
                "--format", "s16",
                AUDIO_FILE
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

    def stop_recording_and_process(self):
        """Called when key is released."""
        if not self.is_recording:
            return
        self.is_recording = False
        duration = time.time() - self.start_time

        print(f"[⏹️] Key UP: Recording stopped ({duration:.2f}s).")

        # Stop PipeWire recording cleanly with SIGINT
        if self.rec_proc and self.rec_proc.poll() is None:
            self.rec_proc.send_signal(signal.SIGINT)
            try:
                self.rec_proc.wait(timeout=2.0)
            except subprocess.TimeoutExpired:
                self.rec_proc.kill()
        self.rec_proc = None

        if duration < MIN_DURATION:
            print("[i] Tap too short, ignoring.")
            show_notify("🎙️ Dictation", "Cancelled (tap was too brief)", 1000)
            return

        play_sound("Oxygen-Sys-App-Positive")
        show_notify("⏳ Transcribing...", f"Processing {duration:.1f}s of audio with small.en...", 5000)

        # Transcribe with whisper-cli
        whisper_cmd = [
            "whisper-cli",
            "-m", self.model_path,
            "-f", AUDIO_FILE,
            "-nt",       # No timestamps
            "-np",       # No progress/prints
            "-t", str(THREADS),
            "-fa"        # Flash attention
        ]

        t0 = time.time()
        try:
            res = subprocess.run(whisper_cmd, capture_output=True, text=True, timeout=20)
            raw_text = res.stdout
        except Exception as e:
            print(f"[!] Whisper execution failed: {e}")
            show_notify("⚠️ Dictation Error", str(e), 2000)
            return

        infer_time = time.time() - t0
        text = clean_transcription(raw_text)

        if text:
            print(f"[📝] Transcribed in {infer_time:.2f}s: \"{text}\"")

            # 1. Copy to clipboard
            try:
                subprocess.run(["wl-copy"], input=text.encode("utf-8"), check=True)
            except Exception as e:
                print(f"[!] wl-copy warning: {e}")

            # 2. Brief sleep so key release fully settles in compositor
            time.sleep(0.06)

            # 3. Type into focused input field via ydotool
            env = os.environ.copy()
            if self.ydotool_socket:
                env["YDOTOOL_SOCKET"] = self.ydotool_socket

            type_cmd = ["ydotool", "type", "--key-delay", "1", "--", text + " "]
            try:
                subprocess.run(type_cmd, env=env, check=True)
                print("[⌨️] Successfully typed text into active window.")
                show_notify("✅ Sent to Input", text, 2000)
            except Exception as e:
                print(f"[!] ydotool type error: {e}")
                show_notify("📋 Copied to Clipboard (Paste with Ctrl+V)", text, 3000)
        else:
            print("[i] No speech recognized or filtered as blank.")
            show_notify("🎙️ Dictation", "No speech detected", 1500)

    def run(self):
        print(f"\n[🚀] Hold-to-Dictate is active! Hold down [{self.key_name}] to speak.\n")
        last_device_scan = 0

        while True:
            now = time.time()
            if now - last_device_scan > 5.0:
                self.update_devices()
                last_device_scan = now

            events = self.selector.select(timeout=1.0)
            for key, _ in events:
                dev = key.fileobj
                try:
                    for ev in dev.read():
                        if ev.type == ecodes.EV_KEY and ev.code == self.key_code:
                            if ev.value == 1:       # Key Pressed Down
                                self.start_recording()
                            elif ev.value == 0:     # Key Released
                                self.stop_recording_and_process()
                            elif ev.value == 2:     # Key Held / Repeating
                                pass
                except (OSError, IOError):
                    # Device disconnected
                    self.update_devices()
                    break


def main():
    parser = argparse.ArgumentParser(description="Hold-to-speak voice dictation daemon")
    parser.add_argument(
        "--key",
        default=os.environ.get("DICTATE_KEY", DEFAULT_KEY),
        help=f"Evdev key name to hold (default: {DEFAULT_KEY}, e.g. KEY_RIGHTALT, KEY_RIGHTCTRL, KEY_CAPSLOCK, KEY_F8)"
    )
    parser.add_argument(
        "--model",
        default=os.environ.get("DICTATE_MODEL", DEFAULT_MODEL),
        help=f"Path to ggml model (default: {DEFAULT_MODEL})"
    )
    args = parser.parse_args()

    daemon = HoldDictateDaemon(key_name=args.key, model_path=args.model)
    try:
        daemon.run()
    except KeyboardInterrupt:
        print("\n[*] Exiting Hold-to-Dictate.")


if __name__ == "__main__":
    main()
