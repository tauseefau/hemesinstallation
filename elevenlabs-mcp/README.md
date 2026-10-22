# ElevenLabs MCP Server — Hermes Plugin

An [MCP (Model Context Protocol)](https://modelcontextprotocol.io/) server that lets AI agents drive the
[ElevenLabs](https://elevenlabs.io) voice-agent platform: discover voices, manage the TTS voice library,
and generate text-to-speech audio.

This directory is a **Hermes plugin**: place it in your Hermes `plugins/` directory (or install it via the
Hermes plugin manager) and the gateway auto-loads the 8 ElevenLabs tools into your agent's toolset.

---

## What it gives you

* **8 tools** for the full ElevenLabs lifecycle
  * Health check / connectivity (`elevenlabs_health`)
  * Voices (list, get, create, delete)
  * Speech (generate TTS audio from text)
  * Models (list, get TTS models)

## Quick start

### 1. Get your ElevenLabs API key

1. Log in to the [ElevenLabs Dashboard](https://elevenlabs.io/app/settings/api-keys).
2. Copy your API key (starts with `el_`).
3. Store it in Hermes Secrets Manager (recommended) or in a `.env` file.

**Via Bitwarden Secrets Manager (recommended):**

```bash
hermes secrets bitwarden add ELEVENLABS_API_KEY <your-key> --type env
hermes secrets bitwarden sync --apply
export ELEVENLABS_API_KEY=<your-key>   # or the my_env plugin resolves it
```

### 2. Install as a Hermes plugin

#### Option A — Clone the repo and link

```bash
# Clone this repo (from the hermesinstallation parent)
git clone https://github.com/tauseefau/hemesinstallation.git ~/.hermes/plugins/elevenlabs-mcp
cd ~/.hermes/plugins/elevenlabs-mcp
# (requires a Python virtualenv with: mcp-server, httpx, starlette, uvicorn)
```

#### Option B — Install into the Hermes plugins dir

```bash
# Copy the plugin directory to Hermes plugins
cp -r elevenlabs-mcp ~/.hermes/plugins/elevenlabs-mcp
```

### 3. Install dependencies

```bash
cd ~/.hermes/plugins/elevenlabs-mcp
pip3 install --break-system-packages -r requirements.txt
```

### 4. Restart the Hermes gateway

```bash
hermes restart
```

The gateway auto-discovers MCP plugins on startup.

### 5. Use the tools

Once loaded, your agent has access to 8 ElevenLabs tools:

| Tool | Description |
|------|-------------|
| `elevenlabs_health` | Connectivity check |
| `elevenlabs_list_voices` / `elevenlabs_get_voice` | Voice management |
| `elevenlabs_create_voice` | Upload audio files or clone via webhook |
| `elevenlabs_delete_voice` | Delete a voice |
| `elevenlabs_generate_speech` | Generate TTS audio from text |
| `elevenlabs_list_models` / `elevenlabs_get_model` | TTS model management |

## Configuration

| Env var | Required | Description |
|---------|----------|-------------|
| `ELEVENLABS_API_KEY` | Yes | Your ElevenLabs API key (from ElevenLabs Dashboard, mirrored in Bitwarden Secrets Manager) |
| `ELEVENLABS_BASE_URL` | No | Override the ElevenLabs API base URL (default: `https://api.elevenlabs.io`) |

### Secrets management

Store `ELEVENLABS_API_KEY` in **Bitwarden Secrets Manager** and reference it via environment variable expansion
in `mcp.json`:

```json
"env": {
  "ELEVENLABS_API_KEY": "${ELEVENLABS_API_KEY}",
  "ELEVENLABS_BASE_URL": "${ELEVENLABS_BASE_URL:-https://api.elevenlabs.io}"
}
```

## Example: generate speech

```json
{
  "voice_id": "21nVXa6F8XsYtN71QqJr",
  "text": "Hello, this is ElevenLabs text to speech.",
  "model_id": "eleven_multilingual_v2",
  "output_format": "mp3_44100_128"
}
```

## Example: create a voice by cloning

```json
{
  "name": "My Clone",
  "files": ["https://example.com/clone.wav"],
  "webhook_url": "https://myapp.com/webhooks/elevenlabs"
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
