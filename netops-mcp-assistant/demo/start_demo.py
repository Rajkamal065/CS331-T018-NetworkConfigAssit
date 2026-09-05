"""
demo/start_demo.py — Start lightweight TCP echo service on port 9999 for demo.

Usage:
  python demo/start_demo.py [--port 9999]
"""

import sys
import os
import socket
import select
import signal
import argparse

PID_FILE = os.path.join(os.path.dirname(__file__), "demo.pid")


def run_listener(host: str = "0.0.0.0", port: int = 9999):
    print(f"[*] Starting NetOps Demo TCP Service on {host}:{port}...")

    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        server_sock.bind((host, port))
        server_sock.listen(10)
    except Exception as e:
        print(f"[!] Could not bind to port {port}: {e}")
        sys.exit(1)

    # Save PID
    with open(PID_FILE, "w") as f:
        f.write(str(os.getpid()))

    print(f"[✔] Demo service active. Listening on TCP port {port} (PID: {os.getpid()})")
    print(f"[*] Press Ctrl+C or run 'python demo/stop_demo.py' to stop.")

    def handle_exit(signum, frame):
        print("\n[*] Stopping demo listener...")
        server_sock.close()
        if os.path.exists(PID_FILE):
            os.remove(PID_FILE)
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_exit)
    signal.signal(signal.SIGTERM, handle_exit)

    try:
        while True:
            rlist, _, _ = select.select([server_sock], [], [], 1.0)
            if rlist:
                client_sock, addr = server_sock.accept()
                print(f"[+] Received connection from {addr[0]}:{addr[1]}")
                try:
                    client_sock.sendall(b"NetOps Demo Service (Port 9999) - Connection Established.\n")
                except Exception:
                    pass
                finally:
                    client_sock.close()
    finally:
        server_sock.close()
        if os.path.exists(PID_FILE):
            os.remove(PID_FILE)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NetOps Demo Port Listener")
    parser.add_argument("--port", type=int, default=9999, help="Port to listen on (default: 9999)")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host interface (default: 0.0.0.0)")
    args = parser.parse_args()

    run_listener(args.host, args.port)
