# Setup Process — ElevenLabs MCP Server (Hermes Plugin)

Complete step-by-step setup for wiring ElevenLabs voice-agent integration into Hermes.
This mirrors the [Vapi MCP plugin](https://github.com/tauseefau/hemesinstallation/tree/main/vapi-mcp) pattern.

---

## 1. Prerequisites

- Hermes gateway running (`hermes status`)
- Python 3.10+ with `pip`
- An ElevenLabs API key (`el_...`) from the [ElevenLabs Dashboard](https://elevenlabs.io/app/settings/api-keys)
- (Recommended) Bitwarden Secrets Manager for the key

---

## 2. Store the API key in Bitwarden Secrets Manager

```bash
# Add the secret (name must match the env var in mcp.json)
hermes secrets bitwarden add ELEVENLABS_API_KEY <your-key> --type env

# Apply secrets at every start
hermes secrets bitwarden sync --apply

# Verify it is applied
echo $ELEVENLABS_API_KEY
```

> If you prefer not to use Secrets Manager, set the env var in `~/.hermes/.env` or export it in your shell
> before starting the gateway.

---

## 3. Clone / place the plugin

### Option A — Clone the plugin repo

```bash
git clone https://github.com/tauseefau/hemesinstallation.git ~/.hermes/plugins/elevenlabs-mcp
cd ~/.hermes/plugins/elevenlabs-mcp
```

### Option B — Copy an existing plugin directory

```bash
cp -r elevenlabs-mcp ~/.hermes/plugins/elevenlabs-mcp
```

The plugin directory **must** contain these files:

| File | Purpose |
|------|---------|
| `plugin.json` | Hermes plugin manifest (name, version, description, keywords) |
| `mcp.json` | MCP server configuration (command, args, env) |
| `server.py` | MCP server implementation |
| `requirements.txt` | Python dependencies |
| `.env.example` | Environment variable template |
| `.hermes-catalog.json` | Plugin catalog entry for `hermes plugins install` |
| `README.md` | Setup + usage documentation |

---

## 4. Install Python dependencies

```bash
cd ~/.hermes/plugins/elevenlabs-mcp
pip3 install --break-system-packages -r requirements.txt
```

If you use a virtualenv, activate it first and adjust `command` in `mcp.json` to the venv python:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

---

## 5. Enable the plugin

```bash
hermes plugins browse          # confirm the entry is listed
hermes plugins enable elevenlabs-mcp
hermes restart                 # gateway auto-discovers MCP plugins on startup
```

---

## 6. Verify the plugin is healthy

Ask your agent to list the tools:

```bash
hermes chat -q "List all your ElevenLabs tools"
```

Expected output (8 tools): `elevenlabs_health`, `elevenlabs_list_voices`, `elevenlabs_get_voice`,
`elevenlabs_create_voice`, `elevenlabs_delete_voice`, `elevenlabs_generate_speech`,
`elevenlabs_list_models`, `elevenlabs_get_model`.

You can also test directly:

```bash
cd ~/.hermes/plugins/elevenlabs-mcp
ELEVENLABS_API_KEY=$ELEVENLABS_API_KEY python3 server.py --stdio <<< '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
```

---

## 7. Use the tools

### Generate TTS speech

```json
{
  "voice_id": "21nVXa6F8XsYtN71QqJr",
  "text": "Hello, this is ElevenLabs speaking.",
  "model_id": "eleven_multilingual_v2",
  "output_format": "mp3_44100_128"
}
```

### List available voices

```json
{"name": "elevenlabs_list_voices", "arguments": {"limit": 20}}
```

### Create a voice (clone)

```json
{
  "name": "My Clone",
  "files": ["https://example.com/clone.wav"],
  "webhook_url": "https://myapp.com/webhooks/elevenlabs"
}
```

---

## 8. Troubleshooting

### Tools don't appear after restart

```bash
# Check gateway log for the MCP handshake
tail -f ~/.hermes/logs/gateway.log
```

### Python deps missing

The `command` in `mcp.json` resolves to the system `python3`, so install deps into that interpreter:

```bash
pip3 install --break-system-packages -r requirements.txt
```

### `ELEVENLABS_API_KEY` not set

The server exits with a clear error on startup. Add the key to Bitwarden Secrets Manager or export it:

```bash
export ELEVENLABS_API_KEY=<your-key>
```

### Schema validation fails

`hermes plugins validate ~/.hermes/plugins/elevenlabs-mcp --json`
- `ok: true` with zero warnings means the plugin is valid.
- Common failures: absolute paths in `args` (must be `./server.py`), unknown top-level fields in `plugin.json`
  (`category`, `requires_hermes` are rejected), non-relative `cwd` in `mcp.json`.

---

## 9. Repository layout

```
hemesinstallation/
├── elevenlabs-mcp/          # The Hermes plugin
│   ├── README.md
│   ├── plugin.json
│   ├── mcp.json
│   ├── server.py
│   ├── requirements.txt
│   ├── .env.example
│   ├── .hermes-catalog.json
│   ├── .gitignore
│   └── setup.md             # This file
└── vapi-mcp/                # Reference plugin (for comparison)
    └── ...
```

---

## 10. Roadmap — future voice agent integration

This server is the foundation for a full voice-agent setup. Planned extensions:

| Step | Tool / Feature | Status |
|------|---------------|--------|
| 1 | ElevenLabs MCP server (voices + speech) | Done |
| 2 | Ollama / local LLM | Planned |
| 3 | Webhook / session management | Planned |
| 4 | Voice agent orchestration | Planned |
| 5 | Real-time voice call (websockets) | Planned |

---

## 11. Diff — Vapi vs ElevenLabs

| | Vapi | ElevenLabs |
|---|---|---|
| API key env var | `VAPI_API_KEY` | `ELEVENLABS_API_KEY` |
| Base URL | `https://api.vapi.ai` | `https://api.elevenlabs.io` |
| Core resource | Assistants, Phone-Numbers, Calls | Voices, Speech |
| Transport | Web (websocket), Phone (carrier) | Text-to-speech |
| Key tools | `vapi_create_call`, `vapi_end_call` | `elevenlabs_generate_speech` |
