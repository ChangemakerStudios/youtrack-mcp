# YouTrack MCP

[![npm version](https://img.shields.io/npm/v/youtrack-mcp-tonyzorin)](https://www.npmjs.com/package/youtrack-mcp-tonyzorin)
[![npm downloads](https://img.shields.io/npm/dm/youtrack-mcp-tonyzorin)](https://www.npmjs.com/package/youtrack-mcp-tonyzorin)

Open-source MCP server for JetBrains YouTrack. You run it locally; it talks to YouTrack Cloud or Server over the REST API.

This package shipped in **April 2025**, before JetBrains added a Remote MCP to YouTrack 2025.3. It talks to the REST API, so it still works on Server that has not upgraded. New JetBrains MCP features (OAuth, time tracking, tags, drafts) live in the [official `/mcp` endpoint](https://www.jetbrains.com/help/youtrack/cloud/model-context-protocol-server.html) — use that on 2025.3+. Full comparison: [GitHub README](https://github.com/tonyzorin/youtrack-mcp#why-this-still-exists).

## Install

Requires Node.js 18+ and Python 3.14+.

```bash
npx -y youtrack-mcp-tonyzorin
```

Or install globally: `npm install -g youtrack-mcp-tonyzorin`.

## Claude Desktop / Cursor

```json
{
  "mcpServers": {
    "youtrack": {
      "command": "npx",
      "args": ["-y", "youtrack-mcp-tonyzorin"],
      "env": {
        "YOUTRACK_URL": "https://your-instance.youtrack.cloud",
        "YOUTRACK_API_TOKEN": "perm-xxx.your-token"
      }
    }
  }
}
```

Create a [permanent token](https://www.jetbrains.com/help/youtrack/cloud/manage-permanent-tokens.html) in YouTrack. Docker and extra registries: [GitHub README](https://github.com/tonyzorin/youtrack-mcp#quick-start).

## CLI

```
npx youtrack-mcp-tonyzorin              # stdio (default)
npx youtrack-mcp-tonyzorin --http --port 8000   # streamable HTTP
npx youtrack-mcp-tonyzorin --help
```

| Variable | Required | Description |
| --- | --- | --- |
| `YOUTRACK_URL` | yes | YouTrack base URL |
| `YOUTRACK_API_TOKEN` | yes | Permanent token |
| `YOUTRACK_VERIFY_SSL` | no | Default `true` |
| `ENABLED_TOOLS` / `DISABLED_TOOLS` | no | Tool allowlist / denylist |

## Support

- [GitHub README](https://github.com/tonyzorin/youtrack-mcp) — tools, examples, Docker
- [Issues](https://github.com/tonyzorin/youtrack-mcp/issues)
- Telegram: [t.me/tonyzorin](https://t.me/tonyzorin)

MIT © Anton Zorin
