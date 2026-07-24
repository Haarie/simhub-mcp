from __future__ import annotations

import os
from typing import Literal

from mcp.server.fastmcp import FastMCP

from .simhub_client import SimHubClient

HOST = os.environ.get("SIMHUB_HOST", "127.0.0.1")
PORT = int(os.environ.get("SIMHUB_PORT", "18082"))

mcp = FastMCP("simhub")
client = SimHubClient(host=HOST, port=PORT)

SNAPSHOT_PROPERTIES = [
    "dcp.GameRunning",
    "dcp.GameName",
    "dcp.gd.SpeedKmh",
    "dcp.gd.Rpms",
    "dcp.gd.Gear",
    "dcp.gd.Throttle",
    "dcp.gd.Brake",
    "dcp.gd.Clutch",
    "dcp.gd.CurrentLap",
    "dcp.gd.CurrentLapTime",
    "dcp.gd.LastLapTime",
    "dcp.gd.BestLapTime",
    "dcp.gd.Position",
    "dcp.gd.Fuel",
    "dcp.gd.FuelPercent",
    "dcp.gd.TrackName",
    "dcp.gd.CarModel",
    "dcp.gd.IsInPit",
    "dcp.gd.Flag_Yellow",
    "dcp.gd.Flag_Checkered",
]


@mcp.tool()
async def list_properties(prefix: str = "") -> str:
    """List SimHub properties known to the Property Server plugin (dcp.* and acc.* prefixes),
    optionally filtered to lines containing `prefix`. 'Generic' properties (no dcp/acc prefix)
    aren't enumerated by this command - find their names in SimHub's own 'Available properties'
    panel, then query them directly with get_property."""
    text = await client.help()
    if not prefix:
        return text
    lines = [line for line in text.splitlines() if prefix in line]
    return "\n".join(lines) if lines else f"No properties matching '{prefix}'."


@mcp.tool()
async def get_property(name: str, timeout: float = 2.0) -> dict:
    """Subscribe to (if needed) and return the current value of a single SimHub property,
    e.g. 'dcp.gd.SpeedKmh' or 'dcp.GameRunning'."""
    pv = await client.get(name, timeout=timeout)
    if pv is None:
        return {"name": name, "error": "no value received within timeout"}
    return {"name": pv.name, "type": pv.type, "value": pv.value}


@mcp.tool()
async def get_properties(names: list[str], timeout: float = 2.0) -> dict:
    """Subscribe to (if needed) and return current values for multiple SimHub properties at once."""
    result: dict = {}
    for name in names:
        pv = await client.get(name, timeout=timeout)
        result[name] = {"type": pv.type, "value": pv.value} if pv else {"error": "no value received"}
    return result


@mcp.tool()
async def get_telemetry_snapshot() -> dict:
    """Return a snapshot of common live telemetry (speed, rpm, gear, pedals, lap/timing, fuel,
    track/car, flags). Values are null if no game/session is currently running."""
    result: dict = {}
    for name in SNAPSHOT_PROPERTIES:
        pv = await client.get(name, timeout=1.5)
        result[name] = pv.value if pv else None
    return result


@mcp.tool()
async def trigger_input(name: str, mode: Literal["press", "pressed", "released"] = "press") -> str:
    """Trigger a SimHub control/input mapping by name (as configured in SimHub's Controls mapper).
    'press' sends a full press+release; 'pressed'/'released' send only that half, for controls
    that need to be held."""
    await client.trigger_input(name, mode)
    return f"Sent {mode} for input '{name}'."


@mcp.tool()
async def shakeit_bass_structure() -> str:
    """List all ShakeIt Bass profiles, effect groups and effects with their GUIDs, for use with
    sib.<guid>.gain / sib.<guid>.ismuted properties."""
    return await client.shakeit_structure("bass")


@mcp.tool()
async def shakeit_motors_structure() -> str:
    """List all ShakeIt Motors profiles, effect groups and effects with their GUIDs, for use with
    sim.<guid>.gain / sim.<guid>.ismuted properties."""
    return await client.shakeit_structure("motors")


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
