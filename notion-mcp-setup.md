# Notion MCP Server — Setup for Hermes Agent

> Self-contained, reusable setup guide. Any Hermes Agent instance can follow this
> file to get Notion tools (`mcp__notion__*`) live in a session. Nothing here is
> specific to a project, workspace, or business — substitute your own IDs.

---

## 1. What you get

A local **stdio MCP server** (`@notionhq/notion-mcp-server`) that Hermes launches
as a child process and talks to over stdio. Once wired, the agent can search,
read, create, and update Notion pages and databases in-session through normal
tool calls — no curl, no manual token juggling per request.

```
Hermes Agent  ──stdio──>  notion-mcp-server  ──HTTPS──>  api.notion.com
```

Two independent paths exist. Pick one or both:

| Path | Use it for |
|---|---|
| **MCP server** (this doc) | Let the agent call Notion structurally, in-session |
| **`ntn` CLI** (§8) | Quick one-off shell calls, file uploads, Workers |

---

## 2. Prerequisites

- A Notion account where you can create integrations
- Node.js + npm (the server is an npm package)
- Hermes Agent installed, with write access to `~/.hermes/config.yaml`
- A place to store the token: Bitwarden Secrets Manager (recommended) or the
  Hermes env file. Never paste the token into a repo or a chat message.

---

## 3. Step 1 — Create the Notion integration and copy the token

1. Open <https://notion.so/my-integrations> → **New integration**.
2. Name it something identifiable (e.g. `Hermes Agent`), select the workspace,
   and set capabilities: **Read content**, **Update content**, **Insert content**.
3. Copy the **Internal Integration Secret**. It starts with `ntn_` (newer) or
   `secret_` (legacy).
4. Treat it as a bearer token: full read/write on anything shared with it.

### Step 2 — Share content with the integration (this is the step people skip)

Creating the integration grants access to **nothing**. Every page or database the
agent should touch must be connected explicitly:

- Open the page/database → `...` menu → **Connections** → **Connect to** →
  select your integration.
- For a whole subtree, connect at the top-level page; children inherit.

Symptom of a skipped share: `404 object_not_found` from the API even though the
ID is correct and the token is valid. A 404 from Notion almost always means
"not shared", not "does not exist".

### Step 3 — Install the MCP server

```bash
node --version                     # v20+ recommended
npm install -g @notionhq/notion-mcp-server
which notion-mcp-server            # must resolve on PATH
notion-mcp-server --version        # reference: 2.5.2
```

If `which` fails after a global install, npm's global bin dir is not on PATH.
Fix it rather than hardcoding a path in the config:

```bash
npm bin -g                         # e.g. /usr/local/bin
export PATH="$(npm bin -g):$PATH"  # add to ~/.bashrc to persist
```

### Step 4 — Store the token

**Option A — Bitwarden Secrets Manager (recommended).** Add a secret named
`NOTION_API_KEY` to the project Hermes reads at startup. Hermes exports it into
the environment automatically, so no token ever lives in `config.yaml`.

**Option B — Hermes env file.** Put `NOTION_API_KEY=ntn_...` in `~/.hermes/.env`
and `chmod 600 ~/.hermes/.env`.

Either way the config below references `${NOTION_API_KEY}` and never the literal
value.

### Step 5 — Wire the server into Hermes

Add to `~/.hermes/config.yaml`:

```yaml
mcp_servers:
  notion:
    command: "notion-mcp-server"
    args: ["--transport", "stdio"]
    env:
      NOTION_TOKEN: "${NOTION_API_KEY}"
    timeout: 120
```

Notes:

- The server's own env var is `NOTION_TOKEN`; Hermes' stored secret is
  `NOTION_API_KEY`. The mapping above bridges them — don't rename either side.
- `timeout: 120` is deliberate: Notion occasionally takes 10–30 s on large
  searches, and the default timeout kills those mid-flight.
- Do not also set `NOTION_TOKEN` globally in the shell; the config mapping is the
  single source of truth and avoids drift.
- Never hand-edit MCP config through a tool that rewrites the YAML wholesale; use
  the Hermes MCP/config flow if one is available in your version.

### Step 6 — Restart and verify registration

Restart Hermes Agent. The MCP server is started by Hermes at boot; editing the
config without a restart changes nothing.

Verification, cheapest first:

```bash
# 1. the process can start at all with the token present
NOTION_TOKEN="$NOTION_API_KEY" notion-mcp-server --transport stdio <<< '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"probe","version":"1"}}}'
```

Expect a JSON-RPC `initialize` result with `serverInfo` and a `capabilities`
object. An auth error here is a token problem, not a Hermes problem.

```bash
# 2. the token itself is valid against the API
curl -s https://api.notion.com/v1/users/me \
  -H "Authorization: Bearer $NOTION_API_KEY" \
  -H "Notion-Version: 2025-09-03" | head -c 300
```

Expect `{"object":"user", ...}`. `{"object":"error","code":"unauthorized"}`
means a bad/revoked token.

3. In the Hermes session, the Notion tools should now be listed. Registration is
   confirmed when `tool_search` / the tool list shows the `mcp__notion__` family
   (see §5). If the server started but tools are missing, check the Hermes log for
   the MCP handshake before touching anything else.

---

## 4. First real call — prove end-to-end write access

Registration only proves the handshake. Prove the token + sharing with one
harmless call on a **test page you own**:

1. `mcp__notion__API_post_search` with a query string → confirm results include
   the page you shared. Empty results = not shared, or the wrong account.
2. `mcp__notion__API_retrieve_page_property` / `API_retrieve_page_markdown` on
   that page's ID → confirm body text comes back.
3. Optional write: create a child page or a row in a **throwaway** database, then
   read it back. Delete it afterwards.

Only after a read *and* a write succeed is the setup done. Reads succeeding and
writes 403-ing means the integration lacks Insert/Update content capability.

---

## 5. Tool surface (reference)

The server exposes roughly two dozen tools, registered as
`mcp__notion__<name>`. The common ones:

| Tool | Purpose |
|---|---|
| `mcp__notion__API_post_search` | Search pages/databases by title |
| `mcp__notion__API_retrieve_a_page` | Page metadata |
| `mcp__notion__API_retrieve_page_markdown` | Page contents as markdown (best for agent reading) |
| `mcp__notion__API_get_block_children` | Raw block JSON of a page/block |
| `mcp__notion__API_post_page` | Create a page (page parent or database parent) |
| `mcp__notion__API_patch_page` | Update page properties / archive |
| `mcp__notion__API_update_page_markdown` | Replace/append page content as markdown |
| `mcp__notion__API_patch_block_children` | Append child blocks |
| `mcp__notion__API_query_data_source` | Query database rows with filters/sorts |
| `mcp__notion__API_retrieve_a_database` | Database schema |
| `mcp__notion__API_retrieve_a_data_source` | Data-source schema |
| `mcp__notion__API_create_a_data_source` | Add a data source to a database |
| `mcp__notion__API_get_self` / `API_get_users` | Integration identity, user list |
| `mcp__notion__API_create_a_comment` | Comment on a page |

Call them with `tool_describe` → `tool_call`, passing IDs you obtained from a
search. Never invent a page or database ID.

---

## 6. Notion API rules that break agent code

These are API-level, independent of MCP:

- **`Notion-Version: 2025-09-03`** is required on raw HTTP calls. The MCP server
  and `ntn` set it for you; hand-rolled curl must include it.
- **Database vs data source.** Databases now carry `data_source`s. Create rows
  with `parent: {"type":"database_id","database_id":"<DB_ID>"}`. Query rows with
  `POST /v1/data_sources/{data_source_id}/query` — the *data source* ID, which is
  not the database ID. The create response echoes `data_source_id`; store it.
- **Property definitions go in `initial_data_source.properties`** on database
  create. A top-level `properties` key is rejected.
- **Database properties are create-time only.** You cannot add a property by
  PATCHing an existing database; create a new one and migrate.
- **Page property values need only `name`** for select/multi_select — no `id` or
  `color`. Those belong on the schema definition.
- **Append blocks is `PATCH /v1/blocks/{id}/children`**, not POST.
- **Rate limit ~3 requests/second** per integration, shared by CLI and MCP.
  Batch reads; back off on 429.
- **Views cannot be filtered via API**; view filters are UI-only. Calendar
  `date_property_id` must be the url-encoded *property ID*, not the name.
- **`GET /v1/databases/{id}` does not echo properties.** Verify a schema through
  the data source or by reading a row.

---

## 7. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| No `mcp__notion__*` tools at all | Config not saved, or Hermes not restarted. Check the MCP section of the Hermes log. |
| Server starts, every call 401 | `NOTION_API_KEY` empty or stale at boot. Verify with §3 step 6.2, then restart. |
| Every call 404 `object_not_found` | Content not shared with the integration (§3 step 2). |
| Reads work, writes 403 | Integration lacks Insert/Update content capability. |
| `command not found: notion-mcp-server` | Global npm bin not on PATH; see §3 step 3. |
| Calls time out around 30 s | Raise `timeout` on the server entry; large searches are slow. |
| Tools existed, then vanished after a Hermes upgrade | Global npm package removed or Node bumped. Reinstall, restart. |
| Search returns nothing but you know the page exists | Integration is in a different workspace than the page, or the page is in Trash. |

---

## 8. Optional — the `ntn` CLI

Same token, different transport. Useful for one-liners and file uploads.

```bash
curl -fsSL https://ntn.dev | bash
ntn --version

export NOTION_API_TOKEN="$NOTION_API_KEY"
export NOTION_KEYRING=0      # headless: skip the OS keychain

ntn api v1/search query="page title"
ntn api v1/pages/{page_id}/markdown
ntn files create < photo.png   # one-line upload
```

`ntn` reads `NOTION_API_TOKEN` (different name from the MCP server's
`NOTION_TOKEN`). Both come from the same integration secret.

---

## 9. Security checklist

- Token lives in Bitwarden Secrets Manager or a `chmod 600` env file — never in
  `config.yaml`, a repo, or a chat message.
- Commit nothing containing `ntn_`/`secret_` tokens. Scan before pushing:
  `git diff --cached | grep -iE 'ntn_[A-Za-z0-9]{10,}|secret_[A-Za-z0-9]{20,}'`
- The integration sees only what you share with it. Share the narrowest page
  subtree that does the job, not the whole workspace.
- Rotate immediately if a token was ever written to disk in a tracked path, even
  if the commit was later amended — history retains it.
- Notion is a live shared workspace: reads are safe, writes are visible to
  humans. Test writes on a scratch database.

---

## 10. Minimal reproducible path

1. Create integration → copy token.
2. Share target pages/databases with the integration.
3. `npm install -g @notionhq/notion-mcp-server`; confirm `which`.
4. Store `NOTION_API_KEY`.
5. Add the `mcp_servers.notion` block to `~/.hermes/config.yaml`.
6. Restart Hermes.
7. Probe with `initialize`, then `curl /v1/users/me`, then a search in-session.
8. Read + write one test page, then clean up.

Done when a search returns a shared page and a test write round-trips.
