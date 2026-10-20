# Hermes Installation

[Hermes Installation Related File ](README.md)

# VAPI MCP Server

An [MCP (Model Context Protocol)](https://modelcontextprotocol.io/) server that lets AI agents drive the
[Vapi](https://vapi.ai) voice-agent platform: discover assistants and phone numbers, create
transient voice agents, and make phone calls.

## What it gives you

* **15 tools** for the full Vapi lifecycle
  * Health check / connectivity
  * Assistants (list, get, create, update, delete)
  * Phone numbers (list, get, create)
  * Calls (list, get, create, end)
  * Sessions (list, create web SDK join tokens)
* **Two transports** — stdio (for Hermes / MCP clients) and SSE + streamable-HTTP (for browsers/remote clients)

## Quick start

### 1. Add the MCP server to Hermes

In your Hermes `config.yaml`:

```yaml
mcpServers:
  vapi:
    command: python
    args: ["/root/vapi-mcp/server.py", "--stdio"]
    env:
      VAPI_API_KEY: <your-vapi-api-key>
```

### 2. Get a Vapi API key

Add `VAPI_API_KEY` to your Bitwarden Secrets Manager (name: `VAPI_API_KEY`) and ensure
`secrets.bitwarden.enabled: true` in `config.yaml`. Hermes injects it automatically.

Alternatively set it in your shell:
```bash
export VAPI_API_KEY=<your-vapi-api-key>
```

### 3. Start the server

```bash
# stdio mode (default)
python -m vapi_mcp --stdio

# or HTTP + SSE mode
python -m vapi_mcp --sse --port 8123
```

## How to use it

Once connected, the AI agent sees 15 tools, e.g.:

```bash
# Make a call with a transient assistant
vapi_create_call name="Support call" first_message="Hi, how can I help today?"

# Make a call using a saved assistant
vapi_create_call assistant_id="<assistant-id>" name="Follow-up"

# End a live call
vapi_end_call call_id="<call-id>"

# Build a custom voice agent
vapi_create_assistant model="gpt-4.1" voice="jennifer-playht" first_message="Welcome!"

# Create a web SDK session (so a browser client can join a call)
vapi_create_session assistant_id="<assistant-id>"
```

## Project layout

```
vapi-mcp/
├── server.py        # The MCP server (stdio + SSE + streamable-HTTP)
├── requirements.txt # Python dependencies
├── README.md        # This file
└── .env.example     # Example env file (no secrets - copy to .env and fill in)
```

## Security

* `VAPI_API_KEY` is read from the environment only.
* Never commit `.env` or any config file containing a real key.
* See `.env.example` for the exact variables needed.
