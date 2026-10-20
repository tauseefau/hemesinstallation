#!/usr/bin/env python3
"""VAPI MCP Server
===============
An MCP (Model Context Protocol) server that lets AI agents drive the Vapi
voice-agent platform: discover assistants and phone numbers, create transient
or saved voice agents, and make/receive phone calls.

Authentication
--------------
Reads `VAPI_API_KEY` from the environment (injected for you by the Hermes
Bitwarden Secrets Manager, or by your own shell).  If it is missing, every
tool returns a clear error telling you where to set it.

Transport
---------
By default this server runs over **stdio** (for use from Hermes / MCP clients)
and also exposes an **SSE** endpoint plus a **streamable-HTTP** endpoint for
browser/remote MCP clients.  See ``main()`` for the flags.

Usage
-----
    # 1. point the client at this file (stdio):
    VAPI_API_KEY=<your-key> python -m vapi_mcp

    # 2. or run the HTTP/SSE server (no token needed on the wire):
    VAPI_API_KEY=<your-key> uvicorn vapi_mcp.server:app --host 0.0.0.0 --port 8000

API surface (Vapi REST -> MCP tools)
------------------------------------
    Assistants : list/get/create/update/delete (POST/GET/PATCH/DELETE /assistant)
    Phone-Number : list/get/create (GET/POST /phone-number)
    Calls      : list/get/create (GET/POST /call), end (DELETE /call/{id})
    Sessions   : list/create web SDK session tokens (GET/POST /session)
    Health     : prove the key is valid and reachable (GET /internal/health)

All tool results are returned as JSON text blocks.
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
    sys.stderr.write("Missing dependency: `pip install httpx`\n")
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
)
from starlette.responses import JSONResponse

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
BASE_URL = os.environ.get("VAPI_BASE_URL", "https://api.vapi.ai").rstrip("/")
API_KEY = os.environ.get("VAPI_API_KEY", "").strip()
if not API_KEY and os.environ.get("VAPI_PUBLIC_API_KEY"):
    API_KEY = os.environ.get("VAPI_PUBLIC_API_KEY", "").strip()

DEFAULT_HEADERS = {"Authorization": "Bearer " + API_KEY, "Content-Type": "application/json"}

logger = logging.getLogger("vapi-mcp")


def get_client() -> httpx.AsyncClient:
    if not hasattr(get_client, "client"):
        get_client.client = httpx.AsyncClient(
            base_url=BASE_URL, headers=DEFAULT_HEADERS, timeout=httpx.Timeout(30.0)
        )
    return get_client.client


class VapiError(Exception):
    """Raised for Vapi API errors that we want surfaced to the MCP tool result."""


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
def _list_tools(_ctx, params: PaginatedRequestParams | None) -> ListToolsResult:
    tools = [
        _tool("vapi_health", "Check API key validity + connectivity"),
        _tool("vapi_list_assistants", "List all voice assistants", {"limit": {"type": "integer"}}),
        _tool("vapi_get_assistant", "Get one assistant by id", {"assistant_id": {"type": "string"}}),
        _tool("vapi_create_assistant", "Create a (transient) voice assistant for a call",
              {"model": {"type": "string", "description": "Model preset e.g. openai/gpt-4o-mini"},
               "voice": {"type": "string", "description": "Voice preset e.g. elevenlabs/Antoni"},
               "transcriber": {"type": "string", "description": "Transcriber preset, default deepgram"},
               "first_message": {"type": "string", "description": "Optional opening line"}}),
        _tool("vapi_update_assistant", "Update an existing assistant",
              {"assistant_id": {"type": "string"}, "patch": {"type": "string"}}),
        _tool("vapi_delete_assistant", "Delete an assistant", {"assistant_id": {"type": "string"}}),
        _tool("vapi_list_phone_numbers", "List purchased/imported phone numbers", {"limit": {"type": "integer"}}),
        _tool("vapi_get_phone_number", "Get one phone number", {"phone_id": {"type": "string"}}),
        _tool("vapi_create_phone_number", "Create a Vapi phone number", {"name": {"type": "string"}}),
        _tool("vapi_list_calls", "List recent calls", {"limit": {"type": "integer"}}),
        _tool("vapi_get_call", "Get a call's full state", {"call_id": {"type": "string"}}),
        _tool("vapi_create_call", "Make a call. Provide an assistant (or assistant_id) and "
              "a transport (web/websocket or phone). Returns the call id.",
              {"assistant": {"type": "string", "description": "Transient assistant JSON (no id needed)"},
               "assistant_id": {"type": "string", "description": "Saved assistant id"},
               "transport": {"type": "string", "description": "'web' (default) or 'phone'"},
               "phone_number_id": {"type": "string", "description": "For phone transport"},
               "customer_phone": {"type": "string", "description": "For phone transport: destination number"},
               "name": {"type": "string", "description": "Call reference name"},
               "first_message": {"type": "string", "description": "Optional first message"}}),
        _tool("vapi_end_call", "End (hang up) a live call", {"call_id": {"type": "string"}}),
        _tool("vapi_list_sessions", "List SDK web sessions", {"limit": {"type": "integer"}}),
        _tool("vapi_create_session", "Create a web SDK session (join token)",
              {"assistant_id": {"type": "string"}, "customer_phone": {"type": "string"}}),
    ]
    return ListToolsResult(tools=tools)


def _call_tool(_ctx, params: dict) -> CallToolResult:
    return call_tool(params["name"], params.get("arguments") or {})


def _list_resources(_ctx, _params: PaginatedRequestParams | None) -> ListResourcesResult:
    return list_resources(_params)


def _read_resource(_ctx, params: dict) -> ReadResourceResult:
    return read_resource(params["uri"])


server = Server(
    "vapi",
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
        if name == "vapi_health":
            return await _cmd_health()
        if name == "vapi_list_assistants":
            return await _cmd_list_assistants(params)
        if name == "vapi_get_assistant":
            return await _cmd_get_assistant(params)
        if name == "vapi_create_assistant":
            return await _cmd_create_assistant(params)
        if name == "vapi_update_assistant":
            return await _cmd_update_assistant(params)
        if name == "vapi_delete_assistant":
            return await _cmd_delete_assistant(params)
        if name == "vapi_list_phone_numbers":
            return await _cmd_list_phone_numbers(params)
        if name == "vapi_get_phone_number":
            return await _cmd_get_phone_number(params)
        if name == "vapi_create_phone_number":
            return await _cmd_create_phone_number(params)
        if name == "vapi_list_calls":
            return await _cmd_list_calls(params)
        if name == "vapi_get_call":
            return await _cmd_get_call(params)
        if name == "vapi_create_call":
            return await _cmd_create_call(params)
        if name == "vapi_end_call":
            return await _cmd_end_call(params)
        if name == "vapi_list_sessions":
            return await _cmd_list_sessions(params)
        if name == "vapi_create_session":
            return await _cmd_create_session(params)
        return _text(f"Unknown tool: {name!r}")
    except VapiError as e:
        return _text(f"Vapi error: {e}")
    except Exception as e:  # noqa: BLE001
        return _text(f"Internal error: {e}")


async def _cmd_health() -> CallToolResult:
    client = get_client()
    resp = await client.get("/assistant")
    if resp.status_code == 200:
        data = resp.json()
        assistants = data.get("results", []) if isinstance(data, dict) else list(data)
        return _json({"status": "ok", "base_url": BASE_URL,
                      "assistants_returned": len(assistants)})
    raise VapiError(f"health check failed HTTP {resp.status_code}: {resp.text[:300]}")


async def _cmd_list_assistants(params: dict) -> CallToolResult:
    limit = int((params or {}).get("limit", 50))
    return _json(await _req("GET", "/assistant", params={"limit": limit}))


async def _cmd_get_assistant(params: dict) -> CallToolResult:
    aid = (params or {}).get("assistant_id")
    if not aid:
        raise VapiError("assistant_id is required")
    return _json(await _req("GET", f"/assistant/{aid}"))


async def _cmd_create_assistant(params: dict) -> CallToolResult:
    payload = {"model": "gpt-4.1", "voice": "elevenlabs/Antoni",
               "transcriber": "deepgram", "firstMessage": None}
    payload.update({k: v for k, v in params.items() if v is not None})
    if payload.get("transcriber") == "deepgram":
        payload["transcriber"] = {"provider": "deepgram", "model": "nova-2", "language": "en"}
    elif payload.get("transcriber") == "elevenlabs":
        payload["transcriber"] = {"provider": "elevenlabs", "model": "silero-v1", "language": "en"}
    # model is a Vapi model preset (e.g. "gpt-4.1", "claude-3-5-sonnet"); do not add a prefix
    return _json(await _req("POST", "/assistant", json_body=payload))


async def _cmd_update_assistant(params: dict) -> CallToolResult:
    aid = (params or {}).get("assistant_id")
    if not aid:
        raise VapiError("assistant_id is required")
    patch = (params or {}).get("patch")
    body = json.loads(patch) if isinstance(patch, str) else dict(patch or {})
    return _json(await _req("PATCH", f"/assistant/{aid}", json_body=body))


async def _cmd_delete_assistant(params: dict) -> CallToolResult:
    aid = (params or {}).get("assistant_id")
    if not aid:
        raise VapiError("assistant_id is required")
    await _req("DELETE", f"/assistant/{aid}")
    return _text(f"deleted assistant {aid}")


async def _cmd_list_phone_numbers(params: dict) -> CallToolResult:
    limit = int((params or {}).get("limit", 20))
    return _json(await _req("GET", "/phone-number", params={"limit": limit}))


async def _cmd_get_phone_number(params: dict) -> CallToolResult:
    pid = (params or {}).get("phone_id")
    if not pid:
        raise VapiError("phone_id is required")
    return _json(await _req("GET", f"/phone-number/{pid}"))


async def _cmd_create_phone_number(params: dict) -> CallToolResult:
    name = (params or {}).get("name")
    payload = {"name": name} if name else {}
    return _json(await _req("POST", "/phone-number", json_body=payload, check=201))


async def _cmd_list_calls(params: dict) -> CallToolResult:
    limit = int((params or {}).get("limit", 20))
    return _json(await _req("GET", "/call", params={"limit": limit}))


async def _cmd_get_call(params: dict) -> CallToolResult:
    cid = (params or {}).get("call_id")
    if not cid:
        raise VapiError("call_id is required")
    return _json(await _req("GET", f"/call/{cid}"))


async def _cmd_create_call(params: dict) -> CallToolResult:
    assistant = (params or {}).get("assistant")
    assistant_obj = None

    # Parse assistant from a JSON string if the caller passed one
    if assistant is not None:
        if isinstance(assistant, str):
            try:
                assistant_obj = json.loads(assistant)
            except Exception:
                return _text("assistant must be a valid JSON object string")
        else:
            assistant_obj = assistant

    # Top-level parameters apply to the *call*, not to an assistant
    body = {}
    for k, v in (params or {}).items():
        if k in ("assistant", "assistant_id", "phone_number_id", "customer_phone",
                 "name", "first_message", "model", "voice", "transport"):
            continue
        body[k] = v

    if (params or {}).get("assistant_id"):
        body["assistantId"] = (params or {}).get("assistant_id")
    if (params or {}).get("phone_number_id"):
        body["phoneNumberId"] = (params or {}).get("phone_number_id")
    if (params or {}).get("customer_phone"):
        body["customer"] = {"phoneNumber": (params or {}).get("customer_phone")}
    if (params or {}).get("name"):
        body["name"] = (params or {}).get("name")

    # Build a transient assistant when needed. Accept both snake_case and
    # camelCase keys for the model/voice/firstMessage fields.
    fm = (params or {}).get("first_message") or (params or {}).get("firstMessage")
    md = (params or {}).get("model") or (params or {}).get("model")
    vs = (params or {}).get("voice") or (params or {}).get("voice")

    if assistant_obj is not None:
        body["assistant"] = assistant_obj
    elif fm or md or vs:
        body["assistant"] = {
            "model": md or "gpt-4.1",
            "voice": vs or "jennifer-playht",
            "firstMessage": fm,
        }
    else:
        return _text("Provide an 'assistant' JSON object, or 'assistant_id' "
                     "or 'model'/'voice'/'first_message' to build a transient assistant.")

    transport = (params or {}).get("transport", "web")
    if transport == "phone":
        if not body.get("phoneNumberId") and not body.get("phoneNumber"):
            return _text("phone transport requires phone_number_id or customer_phone")
    else:
        body["transport"] = {"provider": "vapi.websocket", "conversationType": "voice"}

    return _json(await _req("POST", "/call", json_body=body, check=201))


async def _cmd_end_call(params: dict) -> CallToolResult:
    cid = (params or {}).get("call_id")
    if not cid:
        raise VapiError("call_id is required")
    await _req("DELETE", f"/call/{cid}")
    return _text(f"ended call {cid}")


async def _cmd_list_sessions(params: dict) -> CallToolResult:
    limit = int((params or {}).get("limit", 20))
    return _json(await _req("GET", "/session", params={"limit": limit}))


async def _cmd_create_session(params: dict) -> CallToolResult:
    body = {k: v for k, v in params.items() if v is not None}
    if "assistant_id" in body and "assistantId" not in body:
        body["assistantId"] = body.pop("assistant_id")
    return _json(await _req("POST", "/session", json_body=body, check=201))


async def list_resources(_params: PaginatedRequestParams | None = None) -> ListResourcesResult:
    links = []
    for collection, uri_prefix in [
        ("/call", "call"), ("/assistant", "assistant"),
        ("/phone-number", "phone"), ("/session", "session"),
    ]:
        try:
            page = await _req("GET", collection, params={"limit": 100})
        except VapiError:
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
    except VapiError as e:
        return ReadResourceResult(contents=[TextContent(type="text", text=f"Error: {e}")])


async def _req(method: str, path: str, *, params: dict | None = None,
               json_body: dict | None = None, check: int = 200) -> dict[str, Any]:
    client = get_client()
    resp = await client.request(method, path, params=params, json=json_body)
    if 200 <= resp.status_code < 300:
        return resp.json()
    raise VapiError(f"{method} {path} -> HTTP {resp.status_code}: {resp.text[:500]}")


# --------------------------------------------------------------------------- #
# Transport entrypoints
# --------------------------------------------------------------------------- #
def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="VAPI MCP server")
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
            "ERROR: VAPI_API_KEY is not set.\n"
            "  Add it to your Bitwarden vault under the Secrets Manager (name: VAPI_API_KEY)\n"
            "  then restart this server. Alternatively set: export VAPI_API_KEY=<your-key>\n"
        )
        sys.exit(1)

    logger.info("VAPI MCP server starting (base_url=%s)", BASE_URL)

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
