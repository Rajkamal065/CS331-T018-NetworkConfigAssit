import tkinter as tk
from tkinter import scrolledtext
import threading
import io
import sys
import os

# ── Make sure project root is on path ──────────────────────────────────────────
ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import assistant

# ── Design Tokens (Antigravity Dark Zinc Theme) ─────────────────────────────
BG_DARK = "#09090b"        # App main background
PANEL_BG = "#141417"       # Sidebar & top header background
CARD_BG = "#1c1c21"        # Cards & message blocks background
BORDER_COLOR = "#27272a"   # Subtle borders
TEXT_PRIMARY = "#f4f4f5"   # Primary text
TEXT_MUTED = "#a1a1aa"     # Secondary text
ACCENT_INDIGO = "#6366f1"  # Indigo button accent
ACCENT_HOVER = "#4f46e5"   # Indigo hover
SUCCESS_GREEN = "#10b981"  # Success green
DANGER_RED = "#f43f5e"     # Policy rejection / Error red
WARNING_AMBER = "#f59e0b"  # Processing amber
CHIP_BG = "#27272a"        # Preset chip bg
CHIP_HOVER = "#3f3f46"     # Preset chip hover bg


class NetOpsAgentManager:
    """
    Antigravity-Style Agent Manager Desktop GUI for NetOps MCP Assistant.
    Interfaces exclusively with FastMCP server via stdio mcp_client.py transport.
    """

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("NetOps MCP Agent Manager")
        self.root.geometry("1080x720")
        self.root.minsize(880, 580)
        self.root.configure(bg=BG_DARK)

        self.tools_list = []
        self.mcp_connected = False

        self.build_ui()
        self.init_mcp_connection()

    def build_ui(self):
        # Main layout container
        self.main_container = tk.Frame(self.root, bg=BG_DARK)
        self.main_container.pack(fill="both", expand=True)

        # ── LEFT SIDEBAR (Width ~280px) ──────────────────────────────────────
        self.sidebar = tk.Frame(
            self.main_container,
            bg=PANEL_BG,
            width=280,
            highlightbackground=BORDER_COLOR,
            highlightthickness=1
        )
        self.sidebar.pack(side="left", fill="y", padx=0, pady=0)
        self.sidebar.pack_propagate(False)

        # Sidebar Header / Branding
        brand_frame = tk.Frame(self.sidebar, bg=PANEL_BG)
        brand_frame.pack(fill="x", padx=16, pady=(18, 12))

        tk.Label(
            brand_frame,
            text="[NETOPS] AGENT MANAGER",
            bg=PANEL_BG,
            fg=TEXT_PRIMARY,
            font=("Liberation Sans", 12, "bold")
        ).pack(anchor="w")

        tk.Label(
            brand_frame,
            text="FastMCP Standalone Control Center",
            bg=PANEL_BG,
            fg=TEXT_MUTED,
            font=("Liberation Sans", 8)
        ).pack(anchor="w", pady=(2, 0))

        # Divider
        tk.Frame(self.sidebar, bg=BORDER_COLOR, height=1).pack(fill="x", padx=16, pady=6)

        # MCP Server Connection Card
        self.server_card = tk.Frame(
            self.sidebar,
            bg=CARD_BG,
            highlightbackground=BORDER_COLOR,
            highlightthickness=1
        )
        self.server_card.pack(fill="x", padx=14, pady=8)

        server_header = tk.Frame(self.server_card, bg=CARD_BG)
        server_header.pack(fill="x", padx=12, pady=(10, 4))

        self.status_dot = tk.Label(
            server_header,
            text="●",
            bg=CARD_BG,
            fg=WARNING_AMBER,
            font=("Liberation Sans", 11)
        )
        self.status_dot.pack(side="left", padx=(0, 6))

        self.server_status_lbl = tk.Label(
            server_header,
            text="CONNECTING...",
            bg=CARD_BG,
            fg=TEXT_PRIMARY,
            font=("Liberation Sans", 9, "bold")
        )
        self.server_status_lbl.pack(side="left")

        self.server_detail_lbl = tk.Label(
            self.server_card,
            text="Transport: stdio | Server: server.py",
            bg=CARD_BG,
            fg=TEXT_MUTED,
            font=("Liberation Sans", 8)
        )
        self.server_detail_lbl.pack(anchor="w", padx=12, pady=(0, 10))

        # Registered Tools Section
        tools_lbl_frame = tk.Frame(self.sidebar, bg=PANEL_BG)
        tools_lbl_frame.pack(fill="x", padx=16, pady=(12, 4))

        tk.Label(
            tools_lbl_frame,
            text="DISCOVERED MCP TOOLS",
            bg=PANEL_BG,
            fg=TEXT_MUTED,
            font=("Liberation Sans", 8, "bold")
        ).pack(anchor="w")

        self.tools_container = tk.Frame(self.sidebar, bg=PANEL_BG)
        self.tools_container.pack(fill="x", padx=14, pady=4)

        # Default fallback tool badges
        self.render_tool_badges(["configure_firewall", "set_bandwidth_limit", "run_diagnostics", "list_firewall_rules"])

        # Policy Overview Card
        policy_card = tk.Frame(
            self.sidebar,
            bg=CARD_BG,
            highlightbackground=BORDER_COLOR,
            highlightthickness=1
        )
        policy_card.pack(fill="x", padx=14, pady=(12, 8))

        tk.Label(
            policy_card,
            text="SECURITY POLICY BOUNDARY",
            bg=CARD_BG,
            fg=ACCENT_INDIGO,
            font=("Liberation Sans", 8, "bold")
        ).pack(anchor="w", padx=12, pady=(8, 4))

        policy_text = (
            "• Protected Ports: 22, 53, 5000\n"
            "• Protected Ifaces: eth0, lo\n"
            "• Bandwidth Cap: 1 - 100 Mbps\n"
            "• Permitted Actions: ACCEPT, DROP, REJECT"
        )

        tk.Label(
            policy_card,
            text=policy_text,
            bg=CARD_BG,
            fg=TEXT_MUTED,
            justify="left",
            font=("Liberation Sans", 8)
        ).pack(anchor="w", padx=12, pady=(0, 8))

        # Quick Actions Header
        tk.Label(
            self.sidebar,
            text="QUICK ACTION CHIPS",
            bg=PANEL_BG,
            fg=TEXT_MUTED,
            font=("Liberation Sans", 8, "bold")
        ).pack(anchor="w", padx=16, pady=(12, 4))

        # Preset Quick Chips
        chips_frame = tk.Frame(self.sidebar, bg=PANEL_BG)
        chips_frame.pack(fill="x", padx=14, pady=4)

        presets = [
            ("[BLOCK] Port 8080", "block port 8080"),
            ("[ALLOW] Port 443", "allow port 443"),
            ("[PING] 127.0.0.1", "ping 127.0.0.1"),
            ("[LIST] Firewall Rules", "list firewall rules"),
            ("[TEST] Block Port 22", "block port 22"),  # Policy test
        ]

        for label, cmd in presets:
            btn = tk.Button(
                chips_frame,
                text=label,
                command=lambda c=cmd: self.trigger_quick_cmd(c),
                bg=CHIP_BG,
                fg=TEXT_PRIMARY,
                activebackground=CHIP_HOVER,
                activeforeground=TEXT_PRIMARY,
                relief="flat",
                borderwidth=0,
                anchor="w",
                font=("Liberation Sans", 8),
                padx=10,
                pady=5
            )
            btn.pack(fill="x", pady=2)

        # ── RIGHT MAIN WORKSPACE ──────────────────────────────────────────────
        self.workspace = tk.Frame(self.main_container, bg=BG_DARK)
        self.workspace.pack(side="right", fill="both", expand=True)

        # Top Header Bar
        self.header_bar = tk.Frame(
            self.workspace,
            bg=PANEL_BG,
            highlightbackground=BORDER_COLOR,
            highlightthickness=1
        )
        self.header_bar.pack(fill="x", padx=0, pady=0)

        tk.Label(
            self.header_bar,
            text="NETOPS AGENT EXECUTION FEED",
            bg=PANEL_BG,
            fg=TEXT_PRIMARY,
            font=("Liberation Sans", 11, "bold")
        ).pack(side="left", padx=20, pady=14)

        self.status_lbl = tk.Label(
            self.header_bar,
            text="STATUS: READY",
            bg=PANEL_BG,
            fg=SUCCESS_GREEN,
            font=("Liberation Sans", 9, "bold")
        )
        self.status_lbl.pack(side="right", padx=20)

        # Chat / Execution Activity Feed Scrollview
        feed_container = tk.Frame(self.workspace, bg=BG_DARK)
        feed_container.pack(fill="both", expand=True, padx=20, pady=12)

        self.chat = scrolledtext.ScrolledText(
            feed_container,
            wrap=tk.WORD,
            bg=PANEL_BG,
            fg=TEXT_PRIMARY,
            insertbackground=TEXT_PRIMARY,
            font=("DejaVu Sans Mono", 9.5),
            relief="flat",
            borderwidth=0,
            highlightbackground=BORDER_COLOR,
            highlightthickness=1
        )
        self.chat.pack(fill="both", expand=True, padx=0, pady=0)

        # Text Formatting Tags
        self.chat.tag_config("user_hdr", foreground="#818cf8", font=("Liberation Sans", 10, "bold"))
        self.chat.tag_config("agent_hdr", foreground=SUCCESS_GREEN, font=("Liberation Sans", 10, "bold"))
        self.chat.tag_config("step_info", foreground="#60a5fa")
        self.chat.tag_config("step_warn", foreground=WARNING_AMBER)
        self.chat.tag_config("step_pass", foreground=SUCCESS_GREEN)
        self.chat.tag_config("step_reject", foreground=DANGER_RED, font=("DejaVu Sans Mono", 9.5, "bold"))
        self.chat.tag_config("muted", foreground=TEXT_MUTED)

        # Welcome Text
        self.chat.insert(tk.END, "NETOPS MCP AGENT MANAGER\n", "agent_hdr")
        self.chat.insert(
            tk.END,
            "Connected to FastMCP stdio server via mcp_client.py.\n"
            "All commands undergo authoritative server-side security policy check before execution.\n\n",
            "muted"
        )
        self.chat.insert(
            tk.END,
            "Example Natural Language Prompts:\n"
            "  • block port 8080\n"
            "  • allow tcp port 443\n"
            "  • limit bandwidth to 10 Mbps on eth1\n"
            "  • ping 127.0.0.1\n"
            "  • list firewall rules\n"
            "  • block port 22  (Demonstrates policy rejection)\n\n",
            "muted"
        )

        # Bottom Input Area
        input_container = tk.Frame(self.workspace, bg=BG_DARK)
        input_container.pack(fill="x", padx=20, pady=(4, 16))

        input_wrapper = tk.Frame(
            input_container,
            bg=PANEL_BG,
            highlightbackground=BORDER_COLOR,
            highlightthickness=1
        )
        input_wrapper.pack(fill="x", expand=True)

        self.prompt_entry = tk.Entry(
            input_wrapper,
            bg=PANEL_BG,
            fg=TEXT_PRIMARY,
            insertbackground=TEXT_PRIMARY,
            relief="flat",
            font=("Liberation Sans", 11),
            borderwidth=0
        )
        self.prompt_entry.pack(side="left", fill="x", expand=True, ipady=12, padx=14)
        self.prompt_entry.bind("<Return>", lambda e: self.send_command())

        self.send_btn = tk.Button(
            input_wrapper,
            text="RUN AGENT >",
            command=self.send_command,
            bg=ACCENT_INDIGO,
            fg="white",
            activebackground=ACCENT_HOVER,
            activeforeground="white",
            relief="flat",
            borderwidth=0,
            font=("Liberation Sans", 9, "bold"),
            padx=16,
            pady=8
        )
        self.send_btn.pack(side="right", padx=6, pady=6)

        self.prompt_entry.focus_set()

    def render_tool_badges(self, tools: list):
        for widget in self.tools_container.winfo_children():
            widget.destroy()

        for tname in tools:
            badge = tk.Frame(
                self.tools_container,
                bg=CARD_BG,
                highlightbackground=BORDER_COLOR,
                highlightthickness=1
            )
            badge.pack(fill="x", pady=2)

            tk.Label(
                badge,
                text=f"[TOOL] {tname}",
                bg=CARD_BG,
                fg=TEXT_PRIMARY,
                font=("Liberation Sans", 8)
            ).pack(anchor="w", padx=8, pady=4)

    def init_mcp_connection(self):
        threading.Thread(target=self._connect_mcp_bg, daemon=True).start()

    def _connect_mcp_bg(self):
        try:
            from mcp_client import get_mcp_client
            client = get_mcp_client()
            tools = client.list_tools()
            self.tools_list = [t["name"] for t in tools]
            self.mcp_connected = True

            self.root.after(0, self._on_mcp_connected_ui)
        except Exception as e:
            self.root.after(0, lambda: self._on_mcp_error_ui(str(e)))

    def _on_mcp_connected_ui(self):
        self.status_dot.config(fg=SUCCESS_GREEN)
        self.server_status_lbl.config(text="MCP CONNECTED", fg=SUCCESS_GREEN)
        self.render_tool_badges(self.tools_list)
        self.status_lbl.config(text="STATUS: READY (MCP ACTIVE)", fg=SUCCESS_GREEN)

    def _on_mcp_error_ui(self, err_msg: str):
        self.status_dot.config(fg=DANGER_RED)
        self.server_status_lbl.config(text="DISCONNECTED", fg=DANGER_RED)
        self.status_lbl.config(text=f"STATUS: MCP ERROR ({err_msg})", fg=DANGER_RED)

    def trigger_quick_cmd(self, cmd_text: str):
        self.prompt_entry.delete(0, tk.END)
        self.prompt_entry.insert(0, cmd_text)
        self.send_command()

    def send_command(self):
        cmd = self.prompt_entry.get().strip()
        if not cmd:
            return

        self.prompt_entry.delete(0, tk.END)

        # User message UI entry
        self.chat.insert(tk.END, "\nUser Promoted Intent\n", "user_hdr")
        self.chat.insert(tk.END, f"  > {cmd}\n\n", "TEXT_PRIMARY")
        self.chat.see(tk.END)

        # Disable input while running
        self.send_btn.config(state=tk.DISABLED, bg=BORDER_COLOR)
        self.status_lbl.config(text="STATUS: AGENT EXECUTING...", fg=WARNING_AMBER)

        # Run non-blocking execution thread
        threading.Thread(target=self._execute_bg, args=(cmd,), daemon=True).start()

    def _execute_bg(self, message: str):
        buffer = io.StringIO()
        try:
            assistant.set_output(buffer)
            parsed = assistant.parse_command(message)
            intent = parsed["intent"]

            if intent == "unknown":
                output = "Command not recognized. Type 'help' for examples."
            elif intent == "firewall":
                assistant.handle_firewall(parsed["params"])
                output = buffer.getvalue()
            elif intent == "bandwidth":
                assistant.handle_bandwidth(parsed["params"])
                output = buffer.getvalue()
            elif intent == "diagnostics":
                assistant.handle_diagnostics(parsed["params"])
                output = buffer.getvalue()
            elif intent == "list_rules":
                assistant.handle_list_rules()
                output = buffer.getvalue()
            else:
                output = "Unknown operation."
        except Exception as e:
            output = f"Execution Error: {str(e)}"

        self.root.after(0, lambda: self.show_result(output))

    def show_result(self, output: str):
        self.chat.insert(tk.END, "Agent Activity & MCP Result\n", "agent_hdr")

        # Color-code output lines for rich feedback
        for line in output.splitlines():
            if "POLICY REJECT" in line or "POLICY REJECTED" in line:
                self.chat.insert(tk.END, line + "\n", "step_reject")
            elif "SUCCESS" in line or "Rule applied" in line or "PASS" in line:
                self.chat.insert(tk.END, line + "\n", "step_pass")
            elif "Intent identified" in line or "Invoking MCP tool" in line:
                self.chat.insert(tk.END, line + "\n", "step_info")
            elif "Checking policy" in line:
                self.chat.insert(tk.END, line + "\n", "step_warn")
            else:
                self.chat.insert(tk.END, line + "\n")

        self.chat.insert(tk.END, "\n")
        self.chat.see(tk.END)

        self.send_btn.config(state=tk.NORMAL, bg=ACCENT_INDIGO)
        self.status_lbl.config(text="STATUS: READY (MCP ACTIVE)", fg=SUCCESS_GREEN)
        self.prompt_entry.focus_set()


if __name__ == "__main__":
    root = tk.Tk()
    app = NetOpsAgentManager(root)
    root.mainloop()