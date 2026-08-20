"""
===============================================================================
J.A.R.V.I.S. v4 - Acoustic Double-Clap Autonomous System Launcher
Listens continuously for a 👏 👏 double-clap acoustic signature, then launches:
  1. CMD -> ollama run llama3.1:8b
  2. PowerShell -> python main.py
===============================================================================
"""

import os
import sys
import time
import argparse
import subprocess
from pathlib import Path
import numpy as np

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

try:
    import sounddevice as sd
except ImportError:
    print("ERROR: 'sounddevice' package is required. Install via: pip install sounddevice numpy")
    sys.exit(1)

# === CONFIGURATION CONSTANTS ===
BASE_DIR = Path(__file__).resolve().parent
CLAP_THRESHOLD = 0.20          # Minimum peak amplitude threshold (0.0 to 1.0)
DOUBLE_CLAP_MIN_GAP = 0.12     # 120ms min gap (ignores reverb/echoes)
DOUBLE_CLAP_MAX_WINDOW = 0.75  # 750ms max gap between 👏 #1 and 👏 #2
COOLDOWN = 25.0                # 25 seconds cooldown after successful launch
SAMPLE_RATE = 44100            # Standard mic sampling rate
BLOCK_SIZE = 1024              # Processing frame size

# State variables
last_clap_time = 0.0
last_trigger_time = 0.0
is_starting = False


def print_banner():
    print(r"""
 ╔═══════════════════════════════════════════════════════════════════════════╗
 ║         J.A.R.V.I.S. v4  //  ACOUSTIC DOUBLE-CLAP WAKE LISTENER           ║
 ║                 Iron Man AI System Autonomous Launcher                    ║
 ╚═══════════════════════════════════════════════════════════════════════════╝
    """)
    print(" 🎤 Microphone listening for double-clap acoustic signature (👏 👏)...")
    print(f" ⚙️  Sensitivity Threshold: {CLAP_THRESHOLD} | Double-Clap Window: 120ms - 750ms")
    print(" 💡  Tip: Clap twice firmly near your laptop to wake JARVIS!\n")


def is_clap_acoustic_signature(audio_data: np.ndarray, sample_rate: int = SAMPLE_RATE) -> bool:
    """
    Acoustic spectral filtering to distinguish a hand clap from speech or low-frequency thuds.
    Hand claps exhibit:
      1. High crest factor (sharp transient attack time < 15ms)
      2. Concentrated high-frequency energy (2.0 kHz to 8.0 kHz)
    """
    audio_flat = audio_data.flatten()
    amplitude = np.max(np.abs(audio_flat))
    if amplitude < CLAP_THRESHOLD:
        return False

    rms = np.sqrt(np.mean(audio_flat ** 2))
    crest_factor = amplitude / (rms + 1e-6)

    # FFT Spectral Analysis
    fft_vals = np.abs(np.fft.rfft(audio_flat))
    freqs = np.fft.rfftfreq(len(audio_flat), 1.0 / sample_rate)

    low_freq_energy = np.sum(fft_vals[freqs < 600])
    high_freq_energy = np.sum(fft_vals[(freqs >= 2000) & (freqs <= 8000)])

    # Hand clap signature verification
    if crest_factor > 3.2 and (high_freq_energy > low_freq_energy * 0.6 or amplitude > 0.40):
        return True
    return False


def start_jarvis_system():
    """Triggers the automated dual-terminal launch of Ollama Core & PySide6 JARVIS UI."""
    global last_trigger_time, is_starting

    current_time = time.time()
    if current_time - last_trigger_time < COOLDOWN:
        print(" ⏳ Cooldown active... JARVIS is already initializing.")
        return

    last_trigger_time = current_time
    is_starting = True

    print("\n" + "=" * 70)
    print(" 👏 👏 DOUBLE CLAP DETECTED!")
    print(" 🚀 Launching J.A.R.V.I.S. v4 Autonomous System...")
    print("=" * 70 + "\n")

    # 1. Launch Ollama LLM Core in CMD
    print(" [1/2] Launching Ollama LLM Core in CMD...")
    cmd_command = 'cmd.exe /k "title J.A.R.V.I.S. Ollama Core && ollama run llama3.1:8b"'
    try:
        subprocess.Popen(cmd_command, shell=True, cwd=str(BASE_DIR))
        print("       ✓ CMD window launched: 'ollama run llama3.1:8b'")
    except Exception as e:
        print(f"       ❌ Failed to launch CMD: {e}")

    time.sleep(2.5)

    # 2. Launch PySide6 JARVIS UI in PowerShell
    print(" [2/2] Launching J.A.R.V.I.S. v4 GUI & Speech Engine in PowerShell...")
    ps_command = f'powershell.exe -NoExit -Command "Set-Location \'{BASE_DIR}\'; python main.py"'
    try:
        subprocess.Popen(ps_command, shell=True, cwd=str(BASE_DIR))
        print("       ✓ PowerShell window launched: 'python main.py'")
    except Exception as e:
        print(f"       ❌ Failed to launch PowerShell: {e}")

    print("\n 🤖 J.A.R.V.I.S. v4 is now ONLINE and ready for commands, Sir!\n")
    is_starting = False


def audio_callback(indata, frames, time_info, status):
    """Real-time sounddevice audio callback for processing incoming mic blocks."""
    global last_clap_time

    if status:
        return

    if is_clap_acoustic_signature(indata):
        current_time = time.time()
        time_since_last = current_time - last_clap_time

        # Check if this is the second clap within valid window (120ms to 750ms)
        if DOUBLE_CLAP_MIN_GAP <= time_since_last <= DOUBLE_CLAP_MAX_WINDOW:
            print(f"  👏 Second Clap! (Interval: {time_since_last:.2f}s)")
            start_jarvis_system()
            last_clap_time = 0.0
        else:
            print("  👏 First Clap detected...")
            last_clap_time = current_time


def install_windows_startup():
    """Registers wake_listener.py into Windows Startup folder for automatic boot listening."""
    startup_dir = Path(os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"))
    vbs_path = startup_dir / "JARVIS_DoubleClap_Listener.vbs"
    bat_path = BASE_DIR / "run_clap_listener.bat"

    python_exe = sys.executable

    # 1. Create batch launcher
    with open(bat_path, "w", encoding="utf-8") as f:
        f.write(f'@echo off\ncd /d "{BASE_DIR}"\n"{python_exe}" "{BASE_DIR / "wake_listener.py"}"\n')

    # 2. Create silent VBScript startup shortcut
    vbs_content = (
        'Set WshShell = CreateObject("WScript.Shell")\n'
        f'WshShell.Run chr(34) & "{bat_path}" & chr(34), 0, False\n'
    )
    with open(vbs_path, "w", encoding="utf-8") as f:
        f.write(vbs_content)

    print("\n" + "=" * 70)
    print(" ✓ SUCCESS: JARVIS Double-Clap Listener registered into Windows Startup!")
    print(f"   Startup VBScript: {vbs_path}")
    print(f"   Batch Script:    {bat_path}")
    print("   Your laptop will now automatically listen for 👏 👏 when turned on!")
    print("=" * 70 + "\n")


def uninstall_windows_startup():
    """Removes wake_listener.py from Windows Startup folder."""
    startup_dir = Path(os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"))
    vbs_path = startup_dir / "JARVIS_DoubleClap_Listener.vbs"
    bat_path = BASE_DIR / "run_clap_listener.bat"

    removed = False
    if vbs_path.exists():
        os.remove(vbs_path)
        removed = True
    if bat_path.exists():
        os.remove(bat_path)
        removed = True

    if removed:
        print(" ✓ Removed JARVIS Double-Clap Listener from Windows Startup.")
    else:
        print(" i Startup shortcut was not installed.")


def main():
    parser = argparse.ArgumentParser(description="J.A.R.V.I.S. v4 Double-Clap Listener")
    parser.add_argument("--install-startup", action="store_true", help="Register script to launch on Windows boot")
    parser.add_argument("--uninstall-startup", action="store_true", help="Remove script from Windows boot")
    parser.add_argument("--test-launch", action="store_true", help="Manually trigger launch sequence for testing")
    args = parser.parse_args()

    if args.install_startup:
        install_windows_startup()
        return

    if args.uninstall_startup:
        uninstall_windows_startup()
        return

    if args.test_launch:
        start_jarvis_system()
        return

    print_banner()

    try:
        with sd.InputStream(
            channels=1,
            samplerate=SAMPLE_RATE,
            blocksize=BLOCK_SIZE,
            callback=audio_callback
        ):
            while True:
                time.sleep(0.1)
    except KeyboardInterrupt:
        print("\n [!] Exiting Double-Clap Listener. Goodbye, Sir!")
    except Exception as e:
        print(f"\n [❌] Microphone Error: {e}")


if __name__ == "__main__":
    main()
