"""
app.py — Standalone Desktop AI Network Operations Assistant.

Technology Stack:
  HTML/CSS/JavaScript
          ↓
  pywebview desktop application window (or local web browser)
          ↓
  Python bridge (NetOpsBridge)
          ↓
  LLM client (Claude / Groq / OpenRouter / Ollama)
          ↓
  MCP client (mcp_client.py)
          ↓
  FastMCP server stdio transport (server.py)
          ↓
  Authoritative security/policy validation (policies.yaml)
          ↓
  Real Linux network operations (iptables, tc, ss)
          ↓
  Independent verification (DiagnosticVerifier)

Run:
  python app.py            # Opens native Desktop Window
  python app.py --web      # Opens in default Web Browser (Chrome/Edge/Firefox)
"""

import os
import sys
import json
import socket
import logging
import argparse
import threading
import webbrowser
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse
from dotenv import load_dotenv

# Ensure root directory is on sys.path
ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# Load environment configuration (.env)
load_dotenv(os.path.join(ROOT, ".env"))

from assistant import NetOpsBridge

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("NetOpsApp")


class NetOpsHTTPHandler(SimpleHTTPRequestHandler):
    """
    Lightweight embedded HTTP handler that serves the UI static files
    and provides REST endpoints (/api/status, /api/message, /api/tools)
    connected directly to the authoritative NetOpsBridge.
    """
    bridge: NetOpsBridge = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=os.path.join(ROOT, "ui"), **kwargs)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/status":
            self._send_json(self.bridge.get_status() if self.bridge else {})
        elif parsed.path == "/api/tools":
            self._send_json(self.bridge.list_tools() if self.bridge else [])
        else:
            super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/message":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")
            try:
                data = json.loads(body) if body else {}
            except Exception:
                data = {}
            message = data.get("message", "")
            response = self.bridge.send_message(message) if self.bridge else {"error": "Bridge offline"}
            self._send_json(response)
        else:
            self.send_error(404, "Not Found")

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def _send_json(self, data: dict):
        body = json.dumps(data).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        # Suppress routine static asset logs
        if "GET /api/" in format % args or "POST /api/" in format % args:
            super().log_message(format, *args)


def find_available_port(start_port=8000, max_attempts=50) -> int:
    """Find an available TCP port starting from start_port."""
    for port in range(start_port, start_port + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    return start_port


def start_http_server(bridge: NetOpsBridge, port: int, host: str = "127.0.0.1") -> ThreadingHTTPServer:
    """Start embedded HTTP server in a background daemon thread."""
    NetOpsHTTPHandler.bridge = bridge
    server = ThreadingHTTPServer((host, port), NetOpsHTTPHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def parse_args():
    parser = argparse.ArgumentParser(description="NetOps MCP AI Desktop Assistant")
    parser.add_argument("--web", "-w", action="store_true", help="Launch in default Web Browser instead of pywebview window")
    parser.add_argument("--host", type=str, default=os.getenv("NETOPS_HOST", "127.0.0.1"), help="HTTP host to bind (default: 127.0.0.1, use 0.0.0.0 for Docker)")
    parser.add_argument("--port", "-p", type=int, default=int(os.getenv("NETOPS_PORT", 8000)), help="Local HTTP server port (default: 8000)")
    parser.add_argument("--connect", type=str, default=None, help="Connect desktop window to existing backend URL (e.g. http://localhost:5000 from Docker)")
    parser.add_argument("--no-browser", action="store_true", help="Start server without auto-launching browser")
    parser.add_argument("--debug", action="store_true", help="Enable pywebview debug inspector")
    return parser.parse_args()


def main():
    args = parse_args()

    # Remote Docker backend connection mode:
    # Open the Docker backend URL in the system browser.
    # NOTE: We intentionally do NOT use pywebview here — pywebview intercepts
    # static file requests (app.js, styles.css) and serves them from the local
    # Windows disk instead of Docker, which causes Windows tools to run instead
    # of Linux tools. The real browser fetches everything from Docker correctly.
    if args.connect:
        app_url = args.connect.rstrip("/")
        logger.info(f"Opening Docker backend in system browser: {app_url}")
        print(f"\n=======================================================")
        print(f"  NetOps MCP Assistant — Docker Backend")
        print(f"  Connected to: {app_url}")
        print(f"  The app will open in your default browser.")
        print(f"  Press Ctrl+C here to disconnect.")
        print(f"=======================================================\n")
        webbrowser.open(app_url)
        try:
            while True:
                threading.Event().wait(1)
        except KeyboardInterrupt:
            logger.info("Disconnected from Docker backend.")
        return


    logger.info("Initializing NetOps MCP Assistant Subsystems...")

    # Instantiate the Python bridge (connects LLM + FastMCP server via stdio)
    bridge = NetOpsBridge()

    ui_path = os.path.join(ROOT, "ui", "index.html")
    if not os.path.isfile(ui_path):
        logger.error(f"UI file not found: {ui_path}")
        sys.exit(1)

    port = find_available_port(args.port)
    server = start_http_server(bridge, port, host=args.host)
    display_host = "127.0.0.1" if args.host == "0.0.0.0" else args.host
    app_url = f"http://{display_host}:{port}"
    logger.info(f"NetOps Web Server active at: {app_url} (bound to {args.host}:{port})")

    if args.web:
        logger.info(f"Opening in default web browser: {app_url}")
        if not args.no_browser:
            webbrowser.open(app_url)
        print(f"\n=======================================================")
        print(f"  NetOps AI Assistant is running!")
        print(f"  Access URL: {app_url}")
        print(f"  Press Ctrl+C to stop.")
        print(f"=======================================================\n")
        try:
            while True:
                threading.Event().wait(1)
        except KeyboardInterrupt:
            logger.info("Stopping NetOps Assistant...")
        finally:
            if bridge.mcp:
                bridge.mcp.close()
            server.shutdown()
        return

    # Attempt native desktop window via pywebview
    try:
        import webview
        has_webview = True
    except ImportError:
        has_webview = False

    if not has_webview:
        logger.warning("pywebview is not installed. Opening in default web browser instead...")
        webbrowser.open(app_url)
        try:
            while True:
                threading.Event().wait(1)
        except KeyboardInterrupt:
            pass
        finally:
            if bridge.mcp:
                bridge.mcp.close()
            server.shutdown()
        return

    logger.info(f"Opening native desktop window: {app_url}...")
    window = webview.create_window(
        title="NetOps MCP Assistant — AI Network Operations",
        url=app_url,
        js_api=bridge,
        width=1260,
        height=860,
        min_size=(960, 640),
        background_color="#080c14"
    )

    try:
        webview.start(debug=args.debug)
    except Exception as e:
        logger.warning(f"Native window encountered an issue: {e}")
        logger.info(f"Falling back to web browser: {app_url}")
        webbrowser.open(app_url)
        try:
            while True:
                threading.Event().wait(1)
        except KeyboardInterrupt:
            pass
    finally:
        logger.info("Application closed. Cleaning up MCP stdio connections...")
        if bridge.mcp:
            bridge.mcp.close()
        server.shutdown()


if __name__ == "__main__":
    main()