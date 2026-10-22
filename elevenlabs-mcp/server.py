#!/usr/bin/env python3
"""ELEVENLABS MCP SERVER
=======================
An MCP (Model Context Protocol) server that lets AI agents drive the
ElevenLabs voice-agent platform: discover voices, create/delete voices,
and generate text-to-speech audio.

Authentication
--------------
Reads `ELEVENLABS_API_KEY` from the environment (injected for you by the
Hermes Bitwarden Secrets Manager, or by your own shell).  If it is missing,
every tool returns a clear error telling you where to set it.

Transport
---------
By default this server runs over **stdio** (for use from Hermes / MCP clients)
and also exposes an **SSE** endpoint plus a **streamable-HTTP** endpoint for
browser/remote MCP clients.

API surface (ElevenLabs REST -> MCP tools)
-----------------------------------------
    Voices : list/get/create/delete (GET/POST/DELETE /voices)
    Speech : text-to-speech (POST /text-to-speech/{voice_id})
    Models : list TTS models (GET /models)
    Health : prove the key is valid and reachable (GET /voices)
"""

from __future__ import annotations

import os
import sys
import json
import logging
from typing import Any

try:
    import httpx
except ImportError:
    sys.stderr.write("Missing dependency: `pip install httpx`\\n")
    sys.exit(1)

from mcp.server import Server
from mcp.types import (
    CallToolResult,
    ListToolsResult,
    ListResourcesResult,
    ReadResourceResult,
    TextContent,
    TextResourceContents,
    ResourceLink,
    ResourceTemplate,
    PaginatedRequestParams,
    Tool,
    ToolAnnotations,
    CallToolRequestParams,
    InputRequiredResult,
)
from starlette.responses import JSONResponse

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
BASE_URL = os.environ.get("ELEVENLABS_BASE_URL", "https://api.elevenlabs.io/v1").rstrip("/")
API_KEY = os.environ.get("ELEVENLABS_API_KEY", "").strip()
if not API_KEY and os.environ.get("ELEVENLABS_PUBLIC_API_KEY"):
    API_KEY = os.environ.get("ELEVENLABS_PUBLIC_API_KEY", "").strip()

DEFAULT_HEADERS = {"Authorization": "Bearer " + API_KEY, "Content-Type": "application/json"}

logger = logging.getLogger("elevenlabs-mcp")


def get_client() -> httpx.AsyncClient:
    if not hasattr(get_client, "client"):
        get_client.client = httpx.AsyncClient(
            base_url=BASE_URL, headers=DEFAULT_HEADERS, timeout=httpx.Timeout(30.0)
        )
    return get_client.client


class ElevenLabsError(Exception):
    """Raised for ElevenLabs API errors that we want surfaced to the MCP tool result."""


def _clean(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {str(k): _clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_clean(v) for v in obj]
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    return str(obj)


def _text(result: Any) -> CallToolResult:
    return CallToolResult(content=[TextContent(type="text", text=_clean(result))])


def _json(result: Any) -> CallToolResult:
    return _text(json.dumps(_clean(result), indent=2, default=str))


def _tool(name: str, desc: str, params: dict | None = None):
    return Tool(
        name=name,
        description=desc,
        inputSchema={"type": "object", "properties": params or {}, "required": []},
        annotations=ToolAnnotations(),
    )


# --------------------------------------------------------------------------- #
# Adapters for the lowlevel MCP server.
# The plain handler functions below are referenced by name, which resolves at
# call time.
# --------------------------------------------------------------------------- #
async def _list_tools(_ctx, params: PaginatedRequestParams | None) -> ListToolsResult:
    tools = [
        _tool("elevenlabs_health", "Check API key validity + connectivity"),
        _tool("elevenlabs_list_voices", "List all available voices", {"limit": {"type": "integer"}}),
        _tool("elevenlabs_get_voice", "Get one voice by id", {"voice_id": {"type": "string"}}),
        _tool("elevenlabs_create_voice", "Create a voice (upload audio files or webhook clone)",
              {"name": {"type": "string"}, "files": {"type": "array", "items": {"type": "string"}, "description": "Audio file URLs"},
               "webhook_url": {"type": "string", "description": "Webhook URL for voice cloning"}, "model_id": {"type": "string"}}),
        _tool("elevenlabs_delete_voice", "Delete a voice", {"voice_id": {"type": "string"}}),
        _tool("elevenlabs_generate_speech", "Generate TTS audio from text",
              {"voice_id": {"type": "string"}, "text": {"type": "string"}, "model_id": {"type": "string", "description": "TTS model id"},
               "output_format": {"type": "string", "description": "e.g. mp3_44100_128"},
               "history_id": {"type": "string", "description": "Optional history id"}}),
        _tool("elevenlabs_list_models", "List available TTS models", {"limit": {"type": "integer"}}),
        _tool("elevenlabs_get_model", "Get one TTS model", {"model_id": {"type": "string"}}),
    ]
    return ListToolsResult(tools=tools)


async def _call_tool(_ctx, params: CallToolRequestParams) -> CallToolResult:
    return await call_tool(params.name, params.arguments or {})


async def _list_resources(_ctx, _params: PaginatedRequestParams | None) -> ListResourcesResult:
    return list_resources(_params)


async def _read_resource(_ctx, params: dict) -> ReadResourceResult:
    return await read_resource(params["uri"])


server = Server(
    "elevenlabs",
    on_list_tools=_list_tools,
    on_call_tool=_call_tool,
    on_list_resources=_list_resources,
    on_read_resource=_read_resource,
)


# --------------------------------------------------------------------------- #
# Tool handlers
# --------------------------------------------------------------------------- #
async def list_tools(_params: PaginatedRequestParams | None = None) -> ListToolsResult:
    return ListToolsResult(tools=[])


async def call_tool(name: str, params: dict) -> CallToolResult:
    try:
        if name == "elevenlabs_health":
            return await _cmd_health()
        if name == "elevenlabs_list_voices":
            return await _cmd_list_voices(params)
        if name == "elevenlabs_get_voice":
            return await _cmd_get_voice(params)
        if name == "elevenlabs_create_voice":
            return await _cmd_create_voice(params)
        if name == "elevenlabs_delete_voice":
            return await _cmd_delete_voice(params)
        if name == "elevenlabs_generate_speech":
            return await _cmd_generate_speech(params)
        if name == "elevenlabs_list_models":
            return await _cmd_list_models(params)
        if name == "elevenlabs_get_model":
            return await _cmd_get_model(params)
        return _text(f"Unknown tool: {name!r}")
    except ElevenLabsError as e:
        return _text(f"ElevenLabs error: {e}")
    except Exception as e:  # noqa: BLE001
        return _text(f"Internal error: {e}")


async def _cmd_health() -> CallToolResult:
    client = get_client()
    resp = await client.get("/voices")
    if resp.status_code == 200:
        data = resp.json()
        voices = data.get("voices", []) if isinstance(data, dict) else list(data)
        return _json({"status": "ok", "base_url": BASE_URL, "voices_returned": len(voices)})
    raise ElevenLabsError(f"health check failed HTTP {resp.status_code}: {resp.text[:300]}")


async def _cmd_list_voices(params: dict) -> CallToolResult:
    limit = int((params or {}).get("limit", 20))
    return _json(await _req("GET", "/voices", params={"limit": limit}))


async def _cmd_get_voice(params: dict) -> CallToolResult:
    vid = (params or {}).get("voice_id")
    if not vid:
        raise ElevenLabsError("voice_id is required")
    return _json(await _req("GET", f"/voices/{vid}"))


async def _cmd_create_voice(params: dict) -> CallToolResult:
    # ElevenLabs /voices accepts multipart form data. We support audio file
    # URLs (server downloads them) or a webhook URL for cloning.
    name = (params or {}).get("name")
    files = (params or {}).get("files") or []
    webhook_url = (params or {}).get("webhook_url")
    model_id = (params or {}).get("model_id")

    payload: dict[str, Any] = {}
    if name:
        payload["name"] = name
    if webhook_url:
        payload["webhook_url"] = webhook_url
    if model_id:
        payload["model_id"] = model_id
    if files:
        payload["files"] = files

    headers = dict(DEFAULT_HEADERS)
    headers["Content-Type"] = "application/json"
    return _json(await _req("POST", "/voices", json_body=payload, check=201, headers=headers))


async def _cmd_delete_voice(params: dict) -> CallToolResult:
    vid = (params or {}).get("voice_id")
    if not vid:
        raise ElevenLabsError("voice_id is required")
    await _req("DELETE", f"/voices/{vid}")
    return _text(f"deleted voice {vid}")


async def _cmd_generate_speech(params: dict) -> CallToolResult:
    voice_id = (params or {}).get("voice_id")
    text = (params or {}).get("text")
    if not voice_id or not text:
        raise ElevenLabsError("voice_id and text are required")

    payload: dict[str, Any] = {"text": text}
    model_id = (params or {}).get("model_id")
    if model_id:
        payload["model_id"] = model_id
    output_format = (params or {}).get("output_format")
    if output_format:
        payload["output_format"] = output_format
    history_id = (params or {}).get("history_id")
    if history_id:
        payload["history_id"] = history_id

    # POST /text-to-speech/{voice_id}
    return _json(await _req("POST", f"/text-to-speech/{voice_id}", json_body=payload, check=200))


async def _cmd_list_models(params: dict) -> CallToolResult:
    limit = int((params or {}).get("limit", 20))
    return _json(await _req("GET", "/models", params={"limit": limit}))


async def _cmd_get_model(params: dict) -> CallToolResult:
    mid = (params or {}).get("model_id")
    if not mid:
        raise ElevenLabsError("model_id is required")
    return _json(await _req("GET", f"/models/{mid}"))


async def list_resources(_params: PaginatedRequestParams | None) -> ListResourcesResult:
    links = []
    for collection, uri_prefix in [
        ("/call", "call"), ("/assistant", "assistant"),
        ("/phone-number", "phone"), ("/session", "session"),
    ]:
        try:
            page = await _req("GET", collection, params={"limit": 100})
        except ElevenLabsError:
            continue
        items = page.get("results", []) if isinstance(page, dict) else page
        for item in items:
            links.append(ResourceLink(uri=f"{uri_prefix}://{item.get('id')}",
                                      name=f"{uri_prefix.capitalize()} {item.get('id')}"))
    return ListResourcesResult(resources=links)


async def read_resource(params: str) -> ReadResourceResult:
    try:
        import urllib.parse as urllib_parse
        uri = urllib_parse.urlparse(params).path.lstrip("/")
        kind, _, rid = uri.partition("/")
        if kind == "call":
            data = await _req("GET", f"/call/{rid}")
        elif kind == "assistant":
            data = await _req("GET", f"/assistant/{rid}")
        elif kind == "phone":
            data = await _req("GET", f"/phone-number/{rid}")
        elif kind == "session":
            data = await _req("GET", f"/session/{rid}")
        else:
            raise ValueError(f"unknown resource: {kind}")
        return ReadResourceResult(contents=[TextResourceContents(
            uri=params, mime_type="application/json",
            text=json.dumps(_clean(data), indent=2))])
    except ElevenLabsError as e:
        return ReadResourceResult(contents=[TextContent(type="text", text=f"Error: {e}")])


async def _req(method: str, path: str, *, params: dict | None = None,
               json_body: dict | None = None, check: int = 200,
               headers: dict | None = None) -> dict[str, Any]:
    client = get_client()
    req_headers = headers or DEFAULT_HEADERS
    resp = await client.request(method, path, params=params, json=json_body,
                                headers=req_headers)
    if 200 <= resp.status_code < 300:
        return resp.json()
    raise ElevenLabsError(f"{method} {path} -> HTTP {resp.status_code}: {resp.text[:500]}")


# --------------------------------------------------------------------------- #
# Transport entrypoints
# --------------------------------------------------------------------------- #
def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="ELEVENLABS MCP server")
    parser.add_argument("--stdio", action="store_true", help="run stdio transport (default)")
    parser.add_argument("--sse", action="store_true", help="run SSE transport")
    parser.add_argument("--port", type=int, default=8000, help="HTTP/SSE port")
    parser.add_argument("--host", default="127.0.0.1", help="bind host")
    parser.add_argument("--transport", choices=["stdio", "sse", "http"], default="stdio",
                        help="single transport mode")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

    if not API_KEY:
        sys.stderr.write(
            "ERROR: ELEVENLABS_API_KEY is not set.\n"
            "  Add it to your Bitwarden vault under the Secrets Manager (name: ELEVENLABS_API_KEY)\n"
            "  then restart this server. Alternatively set: export ELEVENLABS_API_KEY=<your-key>\n"
        )
        sys.exit(1)

    logger.info("ELEVENLABS MCP server starting (base_url=%s)", BASE_URL)

    if args.transport == "stdio" or not (args.sse or args.http):
        from mcp.server.stdio import stdio_server

        async def run_stdio() -> None:
            async with stdio_server() as (read_stream, write_stream):
                await server.run(read_stream, write_stream, server.create_initialization_options())

        import asyncio
        asyncio.run(run_stdio())
        return

    from mcp.server.sse import SseServerTransport
    from mcp.server.streamable_http import StreamableHTTPServerTransport
    from starlette.applications import Starlette
    from starlette.routing import Route
    import uvicorn

    sse = SseServerTransport()
    stream = StreamableHTTPServerTransport(
        mcp_session_id=None,
        is_json_response_enabled=True,
    )

    async def handle_sse(request) -> None:
        async with sse.connect_sse(request.scope, request.receive, request._send) as (read, write):
            await server.run(read, write, server.create_initialization_options())

    async def handle_mcp(request) -> None:
        async with stream.connect_read_write(request.scope, request.receive, request._send) as (read, write):
            await server.run(read, write, server.create_initialization_options())

    app = Starlette(routes=[
        Route("/sse", endpoint=handle_sse),
        Route("/mcp", endpoint=handle_mcp),
    ])

    logger.info("HTTP+SSE endpoint listening on http://%s:%d/mcp", args.host, args.port)
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
