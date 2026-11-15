# RideMate MCP server

Lets Claude use your RideMate account: *"I'm reaching Kazhakoottam around 6:15 on Monday,
find me someone going to Kulathoor"*.

It wraps the RideMate REST API and speaks the Model Context Protocol (MCP) over **stdio**:
the client starts `server.py` as a child process and they exchange JSON messages through
its stdin/stdout.

| | Name | What it does |
|---|---|---|
| Tool (read-only) | `list_places` | Stations and areas RideMate knows |
| Tool (read-only) | `find_co_travellers` | Rides to your destination or passing it, with host rating and your fare share |
| Tool | `post_trip` | Offer a ride as host |
| Tool | `request_to_join` | Ask a host for a seat |
| Tool (read-only) | `my_upcoming_rides` | Rides you host or asked to join |
| Resource | `ridemate://trips/upcoming` | The same as JSON, to attach as context |

Place arguments are names ("kulathoor", "technopark 1"), not ids; times are ISO 8601 with a
timezone (`2026-11-16T06:15:00+05:30`).

## Setup

The RideMate backend must be running (see the main README).

```bash
cd mcp-server
uv sync
```

Configuration is through environment variables: `RIDEMATE_API_URL` (default
`http://localhost:8000`), `RIDEMATE_EMAIL`, `RIDEMATE_PASSWORD`.

## Test it with MCP Inspector

```bash
npx @modelcontextprotocol/inspector -e RIDEMATE_EMAIL=you@example.com -e RIDEMATE_PASSWORD=yourpassword uv run server.py
```

It opens a browser page where you can list the tools, call them with your own arguments and
read the resource.

## Connect it to Claude Desktop

Edit Claude Desktop's config file (Settings > Developer > Edit Config), on Windows
`%APPDATA%\Claude\claude_desktop_config.json`, on macOS
`~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "ridemate": {
      "command": "uv",
      "args": ["run", "--directory", "C:\\path\\to\\Api_llm\\mcp-server", "server.py"],
      "env": {
        "RIDEMATE_API_URL": "http://localhost:8000",
        "RIDEMATE_EMAIL": "you@example.com",
        "RIDEMATE_PASSWORD": "yourpassword"
      }
    }
  }
}
```

Restart Claude Desktop. RideMate's tools appear in the tools menu, and Claude asks for your
approval before running one.

## Notes

- **Credentials**: the password sits in plain text in that config file. Use a RideMate
  account made for this, or (a natural next feature) add personal access tokens to the API
  so the config holds a revocable token instead of a password.
- **Errors**: problems the user should hear about are raised as `ToolError`, whose message
  reaches the model. Any other exception reaches the client only as a generic error, so
  internal details don't leak.
- **Never print to stdout** in `server.py`: stdout is the protocol channel. Log to stderr.
- Built on the MCP Python SDK 2.x (`MCPServer`, formerly `FastMCP` in 1.x).
