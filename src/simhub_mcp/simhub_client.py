from __future__ import annotations

import asyncio
from dataclasses import dataclass


@dataclass
class PropertyValue:
    name: str
    type: str
    value: str | None


class SimHubClient:
    """Async client for the SimHubPropertyServer plugin's line-based TCP protocol.

    Protocol reference: https://github.com/pre-martin/SimHubPropertyServer
    Connect, then send commands like `subscribe <name>` / `trigger-input <name>` / `help`.
    The server pushes `Property <name> <type> <value|(null)>` lines whenever a
    subscribed property changes, interleaved with any command output.
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 18082):
        self.host = host
        self.port = port
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._read_task: asyncio.Task | None = None
        self._cache: dict[str, PropertyValue] = {}
        self._subscribed: set[str] = set()
        self._line_queue: asyncio.Queue[str] = asyncio.Queue()
        self._connect_lock = asyncio.Lock()

    async def connect(self) -> None:
        if self._writer is not None:
            return
        async with self._connect_lock:
            if self._writer is not None:
                return
            self._reader, self._writer = await asyncio.open_connection(self.host, self.port)
            await self._reader.readline()  # banner: "SimHub Property Server v..."
            self._read_task = asyncio.create_task(self._read_loop())

    async def _read_loop(self) -> None:
        assert self._reader is not None
        while True:
            line = await self._reader.readline()
            if not line:
                break
            text = line.decode(errors="replace").rstrip("\r\n")
            if text.startswith("Property "):
                self._handle_property_line(text)
            await self._line_queue.put(text)

    def _handle_property_line(self, text: str) -> None:
        # Format: Property <name> <type> <value-or-(null)>
        parts = text.split(" ", 3)
        if len(parts) < 4:
            return
        _, name, ptype, raw_value = parts
        value = None if raw_value == "(null)" else raw_value
        self._cache[name] = PropertyValue(name=name, type=ptype, value=value)

    async def _send(self, command: str) -> None:
        assert self._writer is not None
        self._writer.write((command + "\n").encode())
        await self._writer.drain()

    async def _drain_lines(self, idle_timeout: float = 0.5, max_wait: float = 3.0) -> list[str]:
        """Collect queued lines until the queue has been idle for idle_timeout seconds.

        The protocol has no explicit end-of-response marker, so multi-line replies
        (like `help`) are terminated by a quiet period instead.
        """
        lines: list[str] = []
        loop = asyncio.get_event_loop()
        deadline = loop.time() + max_wait
        while True:
            remaining = deadline - loop.time()
            if remaining <= 0:
                break
            try:
                line = await asyncio.wait_for(self._line_queue.get(), timeout=min(idle_timeout, remaining))
            except asyncio.TimeoutError:
                break
            lines.append(line)
        return lines

    async def subscribe(self, name: str) -> None:
        await self.connect()
        if name not in self._subscribed:
            self._subscribed.add(name)
            await self._send(f"subscribe {name}")
            await asyncio.sleep(0.2)  # let the initial value push arrive

    async def unsubscribe(self, name: str) -> None:
        if name in self._subscribed:
            self._subscribed.discard(name)
            await self._send(f"unsubscribe {name}")

    async def get(self, name: str, timeout: float = 2.0) -> PropertyValue | None:
        await self.subscribe(name)
        loop = asyncio.get_event_loop()
        deadline = loop.time() + timeout
        while name not in self._cache and loop.time() < deadline:
            await asyncio.sleep(0.05)
        return self._cache.get(name)

    async def help(self) -> str:
        await self.connect()
        await self._send("help")
        lines = await self._drain_lines()
        return "\n".join(line for line in lines if not line.startswith("Property "))

    async def trigger_input(self, name: str, mode: str = "press") -> None:
        await self.connect()
        command_map = {
            "press": "trigger-input",
            "pressed": "trigger-input-pressed",
            "released": "trigger-input-released",
        }
        cmd = command_map.get(mode, "trigger-input")
        await self._send(f"{cmd} {name}")

    async def shakeit_structure(self, kind: str = "bass") -> str:
        await self.connect()
        cmd = "shakeit-bass-structure" if kind == "bass" else "shakeit-motors-structure"
        await self._send(cmd)
        lines = await self._drain_lines()
        return "\n".join(line for line in lines if not line.startswith("Property "))

    async def close(self) -> None:
        if self._writer is not None:
            try:
                await self._send("disconnect")
            except Exception:
                pass
            self._writer.close()
        if self._read_task is not None:
            self._read_task.cancel()
