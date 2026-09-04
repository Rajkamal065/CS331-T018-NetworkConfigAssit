import os
import sys
import asyncio
import threading
from typing import Any, Dict, List, Optional
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = os.path.dirname(os.path.abspath(__file__))


class MCPClient:
    """
    Thread-safe client wrapper for connecting to server.py via stdio MCP transport.
    Manages background event loop to allow synchronous and non-blocking tool calls.
    """

    def __init__(self, server_script: str = "server.py", python_exec: str = sys.executable):
        self.server_script = (
            os.path.join(ROOT, server_script)
            if not os.path.isabs(server_script)
            else server_script
        )
        self.python_exec = python_exec
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._loop_thread: Optional[threading.Thread] = None
        self._session: Optional[ClientSession] = None
        self._cm_stdio = None
        self._cm_session = None
        self._connected = False

    def _start_background_loop(self, ready_event: threading.Event):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        ready_event.set()
        self._loop.run_forever()

    def connect(self) -> bool:
        if self._connected:
            return True

        ready_event = threading.Event()
        self._loop_thread = threading.Thread(
            target=self._start_background_loop,
            args=(ready_event,),
            daemon=True
        )
        self._loop_thread.start()
        ready_event.wait(timeout=5.0)

        future = asyncio.run_coroutine_threadsafe(
            self._async_connect(),
            self._loop
        )
        return future.result(timeout=15.0)

    async def _async_connect(self) -> bool:
        server_params = StdioServerParameters(
            command=self.python_exec,
            args=[self.server_script],
            env=dict(os.environ)
        )
        self._cm_stdio = stdio_client(server_params)
        read, write = await self._cm_stdio.__aenter__()
        self._cm_session = ClientSession(read, write)
        self._session = await self._cm_session.__aenter__()
        await self._session.initialize()
        self._connected = True
        return True

    def list_tools(self) -> List[Dict[str, Any]]:
        if not self._connected:
            self.connect()
        future = asyncio.run_coroutine_threadsafe(
            self._async_list_tools(),
            self._loop
        )
        return future.result(timeout=10.0)

    async def _async_list_tools(self) -> List[Dict[str, Any]]:
        response = await self._session.list_tools()
        result = []
        for tool in response.tools:
            schema = getattr(tool, "input_schema", None)
            if schema is None:
                schema = getattr(tool, "inputSchema", {})
            result.append({
                "name": tool.name,
                "description": tool.description,
                "inputSchema": schema
            })
        return result

    def call_tool(self, name: str, arguments: Optional[Dict[str, Any]] = None) -> str:
        if not self._connected:
            self.connect()
        if arguments is None:
            arguments = {}
        future = asyncio.run_coroutine_threadsafe(
            self._async_call_tool(name, arguments),
            self._loop
        )
        return future.result(timeout=30.0)

    async def _async_call_tool(self, name: str, arguments: Dict[str, Any]) -> str:
        result = await self._session.call_tool(name, arguments=arguments)
        texts = []
        if hasattr(result, "content") and result.content:
            for content_item in result.content:
                if hasattr(content_item, "text"):
                    texts.append(content_item.text)
                else:
                    texts.append(str(content_item))
        return "\n".join(texts) if texts else str(result)

    def close(self):
        if not self._connected or not self._loop:
            return
        future = asyncio.run_coroutine_threadsafe(
            self._async_close(),
            self._loop
        )
        try:
            future.result(timeout=5.0)
        except Exception:
            pass
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._connected = False

    async def _async_close(self):
        if self._cm_session:
            try:
                await self._cm_session.__aexit__(None, None, None)
            except Exception:
                pass
        if self._cm_stdio:
            try:
                await self._cm_stdio.__aexit__(None, None, None)
            except Exception:
                pass


_default_client: Optional[MCPClient] = None


def get_mcp_client() -> MCPClient:
    global _default_client
    if _default_client is None:
        _default_client = MCPClient()
        _default_client.connect()
    return _default_client
