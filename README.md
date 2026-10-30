# hermesinstallation

Hermes community plugins (MCP server plugins + hooks) for voice-agent and AI integration:

## Plugins

| Plugin | Description |
|--------|-------------|
| [elevenlabs-mcp](./elevenlabs-mcp) | ElevenLabs MCP server: voice discovery, voice management, text-to-speech. Hermes plugin for voice-agent integration. |
| [vapi-mcp](./vapi-mcp) | Vapi MCP server: voice-agent platform integration (reference plugin). |

## Skills

| Skill | Description |
|-------|-------------|
| [server-disk-cleanup](./skills/server-disk-cleanup) | Free disk space on a self-hosted server (local or remote over SSH): Docker image/build-cache prune, cache and journal cleanup, plus recurring every-2-days cron. |

## Docs

- [notion-mcp-setup.md](notion-mcp-setup.md) — reusable Notion MCP server setup for any Hermes Agent (token, sharing, install, config, verification, pitfalls).
- `Google setup` — Google Workspace notes.
- `Telegram Webhook Prompt` — Telegram webhook prompt/config.
- `docker-compose.yml` — container config.
- `vapi-mcp/` — Vapi MCP server plugin.
