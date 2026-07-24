# simhub-mcp

MCP server that exposes live [SimHub](https://www.simhubdash.com/) telemetry and controls to
Claude, via the [SimHubPropertyServer](https://github.com/pre-martin/SimHubPropertyServer)
plugin's TCP protocol.

## Prerequisites

1. SimHub running on this PC.
2. The **Property Server** plugin (by pre-martin) installed and enabled in SimHub, under
   *Additional Plugins* -> *Property Server*. Default port is `18082`.

## Install

```powershell
cd simhub-mcp
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
```

## Register with Claude Code

```powershell
claude mcp add simhub -- "C:\Users\haari\ClaudeCode\simhub-mcp\.venv\Scripts\python.exe" -m simhub_mcp.server
```

Or add to `claude_desktop_config.json` / Claude Code MCP config manually:

```json
{
  "mcpServers": {
    "simhub": {
      "command": "C:\\Users\\haari\\ClaudeCode\\simhub-mcp\\.venv\\Scripts\\python.exe",
      "args": ["-m", "simhub_mcp.server"]
    }
  }
}
```

If the Property Server plugin uses a non-default host/port, set `SIMHUB_HOST` / `SIMHUB_PORT`
env vars on the server entry.

## Tools

- `list_properties(prefix="")` - catalog of `dcp.*` / `acc.*` properties (from the plugin's `help`).
- `get_property(name, timeout=2.0)` - current value of one property (subscribes on first use).
- `get_properties(names, timeout=2.0)` - batch version.
- `get_telemetry_snapshot()` - speed, rpm, gear, pedals, lap/timing, fuel, track/car, flags.
- `trigger_input(name, mode="press")` - fire a SimHub control mapping (`press` / `pressed` / `released`).
- `shakeit_bass_structure()` / `shakeit_motors_structure()` - list ShakeIt profiles + GUIDs, for
  use with `sib.<guid>.gain` / `sim.<guid>.gain` etc.

Property names follow the plugin's naming convention, e.g. `DataCorePlugin.GameData.SpeedKmh` ->
`dcp.gd.SpeedKmh`. "Generic" properties (anything not under `dcp.*` / `acc.*`) aren't listed by
`list_properties` but can still be read with `get_property` - find their exact name via SimHub's
own "Available properties" panel ("Copy name").

## Notes

- Values only update while a supported game/session is running; before that, properties read
  as `null`.
- The plugin pushes updates at 10 Hz max - not meant for hard real-time use.
- One TCP connection is kept open for the lifetime of the MCP server process; property
  subscriptions persist across tool calls within that process.
