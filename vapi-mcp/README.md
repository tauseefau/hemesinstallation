# VAPI MCP Server — Hermes Plugin

An [MCP (Model Context Protocol)](https://modelcontextprotocol.io/) server that lets AI agents drive the
[Vapi](https://vapi.ai) voice-agent platform: discover assistants and phone numbers, create transient or
saved voice agents, and make/receive phone calls.

This directory is a **Hermes plugin**: place it in your Hermes `plugins/` directory (or install it via the
Hermes plugin manager) and the gateway auto-loads the 15 Vapi tools into your agent's toolset.

---

## What it gives you

* **15 tools** for the full Vapi lifecycle
  * Health check / connectivity (`vapi_health`)
  * Assistants (list, get, create, update, delete)
  * Phone numbers (list, get, create)
  * Calls (list, get, create, end)
  * Sessions (list, create)

## Quick start

### 1. Get your Vapi API key

1. Log in to the [Vapi Dashboard](https://vapi.ai/dashboard).
2. Copy your API key from **Settings → API Keys**.
3. Store it in Hermes Secrets Manager (recommended) or in a `.env` file.

**Via Bitwarden Secrets Manager (recommended):**
```bash
hermes secrets bitwarden add VAPI_API_KEY <your-key> --type env
hermes secrets bitwarden sync --apply
export VAPI_API_KEY=<your-key>   # or the my_env plugin resolves it
```

### 2. Install as a Hermes plugin

#### Option A — Clone the repo and link

```bash
# Clone this repo
git clone https://github.com/tauseefau/hemesinstallation.git ~/.hermes/plugins/vapi-mcp
cd ~/.hermes/plugins/vapi-mcp
# (requires a Python virtualenv with: mcp-server, httpx, starlette, uvicorn)
```

#### Option B — Install into the Hermes plugins dir

```bash
# Copy the plugin directory to Hermes plugins
cp -r vapi-mcp ~/.hermes/plugins/vapi-mcp
```

### 3. Restart the Hermes gateway

The gateway auto-discovers MCP plugins on startup. If the gateway is already running, restart it:

```bash
hermes restart
```

### 4. Use the tools

Once loaded, your agent has access to 15 Vapi tools:

| Tool | Description |
|------|-------------|
| `vapi_health` | Connectivity check |
| `vapi_list_assistants` / `vapi_get_assistant` | Assistant management |
| `vapi_create_assistant` / `vapi_update_assistant` / `vapi_delete_assistant` | Create, update, delete |
| `vapi_list_phone_numbers` / `vapi_get_phone_number` / `vapi_create_phone_number` | Phone number management |
| `vapi_list_calls` / `vapi_get_call` / `vapi_create_call` / `vapi_end_call` | Call management |
| `vapi_list_sessions` / `vapi_create_session` | Session management |

## Configuration

| Env var | Required | Description |
|---------|----------|-------------|
| `VAPI_API_KEY` | Yes | Your Vapi API key (from Vapi Dashboard) |
| `VAPI_BASE_URL` | No | Override the Vapi API base URL (default: `https://api.vapi.ai`) |

### Secrets management

Store `VAPI_API_KEY` in **Bitwarden Secrets Manager** and reference it via environment variable expansion
in `mcp.json`:

```json
"env": {
  "VAPI_API_KEY": "${VAPI_API_KEY}",
  "VAPI_BASE_URL": "${VAPI_BASE_URL:-https://api.vapi.ai}"
}
```

## Example: make a call with an assistant

```json
{
  "name": "mr harmes",
  "model": "gpt-4.1",
  "voice": {"version": 2, "voiceId": "Elliot", "provider": "vapi"},
  "firstMessage": "Hello, I am Mr Harmes.",
  "maxDurationSeconds": 300
}
```

## Development

```bash
pip install -r requirements.txt
python3 server.py --help
python3 server.py --stdio              # for MCP clients
python3 server.py --sse --port 8123    # for browser/SSE clients
python3 server.py --http --port 8123   # for streamable-HTTP clients
```

## License

MIT
