"""
demo/stop_demo.py — Cleanly terminate the demo listener service.

Usage:
  python demo/stop_demo.py
"""

import os
import sys
import signal

PID_FILE = os.path.join(os.path.dirname(__file__), "demo.pid")


def stop_demo():
    if not os.path.exists(PID_FILE):
        print("[-] No active demo PID file found. Service may not be running.")
        return

    try:
        with open(PID_FILE, "r") as f:
            pid = int(f.read().strip())

        print(f"[*] Terminating demo process (PID: {pid})...")
        if os.name == "nt":
            import subprocess
            subprocess.run(["taskkill", "/F", "/PID", str(pid)], check=False)
        else:
            os.kill(pid, signal.SIGTERM)

        print("[✔] Demo service terminated.")
    except Exception as e:
        print(f"[!] Error stopping process: {e}")
    finally:
        if os.path.exists(PID_FILE):
            os.remove(PID_FILE)


if __name__ == "__main__":
    stop_demo()
