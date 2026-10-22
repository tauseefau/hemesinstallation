# Notion Setup — Simple Plumber Business

> Complete, replicable Notion workspace setup for a plumbing business, plus the
> Vapi voice-agent wiring that books into it. All instructions for an agent to
> rebuild this in a fresh Notion workspace.

## 1. What was built

| Item | Purpose | Visibility |
|---|---|---|
| **Customers** database (private, workspace-level) | Store customer records, contact info, preferred contact method | Sidebar Databases section (not on any page) |
| **MW Bookings** database (private, workspace-level) + **Calendar view** | Handle maintenance & repair bookings, with customer and pricing links | Sidebar Databases section |
| **Pricing** database (private, workspace-level) | Editable rate card: hourly / afternoon / weekend rates, **callout charges** + hours of operation | Sidebar Databases section |
| **Vapi voice agent** (phone receptionist) | Answers calls, checks availability, books appointments, quotes callout charges | Vapi assistant wired to the bridge endpoint (§5) |

All databases are **workspace-level parents**, so they appear only in the Notion
sidebar → Databases, and never on a page.

## 2. Prerequisites

- Notion account + a page (any page) as the "home" for creating databases
- Notion API token with `read_content` + `write_content` scopes (create at https://www.notion.com/my-account)
- Notion API version **2025-09-03** (used in all API calls)
- For the voice agent (§5): a Vapi account, a phone number, and Node/nginx/PHP
  for the bridge (see §5.4)

Placeholder used in this documentation: `{{NOTION_TOKEN}}` — substitute with your actual token.

---

## 3. API version note

Notion API for database creation uses:

```json
{
  "parent": {"type": "workspace", "workspace": true},
  "title": [{"type": "text", "text": {"content": "DATABASE NAME"}}],
  "initial_data_source": {"properties": {...}}
}
```

Properties are defined inside `initial_data_source.properties`. **Do not use top-level `properties` on the database create call** — the API rejects it. And do **not** use `"properties"` at the top level for database creation.

> **Databases now expose a `data_source`.** Query rows with
> `POST /v1/data_sources/{data_source_id}/query` (the *data source* id, not the
> database id). A database create response echoes `data_sources[0].id` — store it.
> You *can* add a property later by `PATCH /v1/data_sources/{data_source_id}` with
> a `properties` object (see §8); older docs claiming otherwise are out of date.

---

## 4. Step-by-step build

### 4.1 Customers database (private)

Create database (POST /v1/databases):

```bash
curl -s -X POST "https://api.notion.com/v1/databases" \
  -H "Authorization: Bearer {{NOTION_TOKEN}}" \
  -H "Notion-Version: 2025-09-03" \
  -H "Content-Type: application/json" \
  -d '{
    "parent": {"type": "workspace", "workspace": true},
    "title": [{"type": "text", "text": {"content": "Customers"}}],
    "initial_data_source": {
      "properties": {
        "Name": {"title": {}},
        "Company": {"title": {}},
        "Phone": {"rich_text": {}},
        "Email": {"rich_text": {}},
        "Address": {"rich_text": {}},
        "Preferred contact": {"select": {"options": [{"name": "Email", "color": "default"}, {"name": "Phone", "color": "default"}, {"name": "Both", "color": "default"}]}},
        "Notes": {"rich_text": {}},
        "Date added": {"date": {}}
      }
    }
  }'
```

> Note: the bridge (§5) writes `Phone` as a **phone_number** property and `Email`
> as an **email** property. The schema above declares them as `rich_text` for
> simplicity; if you want the bridge's typed writes to validate, declare
> `"Phone": {"phone_number": {}}` and `"Email": {"email": {}}` instead.

Result: database id `fffa5c0d-e48e-4178-91c2-8e035e91992b` (id changes each time). Note this id — you will reference it in the relation.

### 4.2 MW Bookings database (private) with Calendar view

Create database (POST /v1/databases) with the full schema including pricing fields:

```bash
curl -s -X POST "https://api.notion.com/v1/databases" \
  -H "Authorization: Bearer {{NOTION_TOKEN}}" \
  -H "Notion-Version: 2025-09-03" \
  -H "Content-Type: application/json" \
  -d '{
    "parent": {"type": "workspace", "workspace": true},
    "title": [{"type": "text", "text": {"content": "MW Bookings"}}],
    "initial_data_source": {
      "properties": {
        "Booking": {"title": {}},
        "Customer": {"relation": {"data_source_id": "<CUSTOMERS_DATA_SOURCE_ID>", "database_id": "<CUSTOMERS_DB_ID>", "single_property": {}, "type": "single_property"}},
        "Date": {"date": {}},
        "Time": {"select": {"options": [
            {"name": "09:00", "color": "default"}, {"name": "10:00"}, {"name": "11:00"},
            {"name": "12:00"}, {"name": "13:00"}, {"name": "14:00"},
            {"name": "15:00"}, {"name": "16:00"}, {"name": "17:00"}
        ]}},
        "Job": {"rich_text": {}},
        "Status": {"select": {"options": [
            {"name": "Confirmed", "color": "green"}, {"name": "Booking", "color": "blue"},
            {"name": "In progress", "color": "yellow"}, {"name": "Completed", "color": "gray"},
            {"name": "Cancelled", "color": "red"}
        ]}},
        "Workers": {"multi_select": {"options": [
            {"name": "John Rivera"}, {"name": "Jane Smith"}, {"name": "Mike Johnson"}
        ]}},
        "Notes": {"rich_text": {}},
        "Pricing plan": {"relation": {"data_source_id": "<PRICING_DATA_SOURCE_ID>", "database_id": "<PRICING_DB_ID>", "single_property": {}, "type": "single_property"}},
        "Start time": {"date": {}},
        "End time": {"date": {}},
        "Time band": {"select": {"options": [
            {"name": "Hourly"}, {"name": "Afternoon"}, {"name": "Weekend"}, {"name": "After-hours"}
        ]}},
        "Rate applied": {"number": {"format": "number"}},
        "Duration (hrs)": {"formula": {"expression": "dateBetween(prop(\"End time\"), prop(\"Start time\"), \"hours\")", "type": "number"}},
        "Estimated total": {"formula": {"expression": "prop(\"Duration (hrs)\") * prop(\"Rate applied\")", "type": "number"}}
      }
    }
  }'
```

> Correction vs the original build: the `Pricing plan` relation points at the
> **Pricing** database (not Customers). Relate a booking to the rate card that was
> applied. Order matters — create Pricing (§4.3) before MW Bookings if you want
> the relation id at create time, or create the relation property afterwards with
> a data-source PATCH.

Result: database id `0cf489e2-ff52-4a10-a1df-9c9d4cf6f554`.

**Add the Calendar view** (POST /v1/views):

```bash
curl -s -X POST "https://api.notion.com/v1/views" \
  -H "Authorization: Bearer {{NOTION_TOKEN}}" \
  -H "Notion-Version: 2025-09-03" \
  -H "Content-Type: application/json" \
  -d '{
    "database_id": "<MW_BOOKINGS_DB_ID>",
    "data_source_id": "<MW_BOOKINGS_DATA_SOURCE_ID>",
    "name": "MW Calendar",
    "type": "calendar",
    "properties": {
      "Booking": {"type": "title"},
      "Date": {"type": "date"},
      "Status": {"type": "select"},
      "Time": {"type": "select"},
      "Workers": {"type": "multi_select"},
      "Customer": {"type": "relation"}
    },
    "configuration": {
      "type": "calendar",
      "date_property_id": "a%7D%40i",
      "show_time": true,
      "group_by": [{"property": "Status"}],
      "visible_properties": ["Booking", "Date", "Status", "Time", "Workers", "Customer"]
    }
  }'
```

Note: `date_property_id` must be the **property ID** (url-encoded), not the property name. The Date property id in `90953b03-ca18-43de-b6fd-c0692fbeb19a` is `a%7D%40i`.

**Workspace-level parent**: after creation, PATCH the database to set parent to workspace (already workspace in the create call above, but if you started with a page parent, run):

```bash
curl -s -X PATCH "https://api.notion.com/v1/databases/<MW_BOOKINGS_DB_ID>" \
  -H "Authorization: Bearer {{NOTION_TOKEN}}" \
  -H "Notion-Version: 2025-09-03" \
  -H "Content-Type: application/json" \
  -d '{"parent": {"type": "workspace", "workspace": true}}'
```

### 4.3 Pricing (Rate Card) database (private)

Create database (POST /v1/databases):

```bash
curl -s -X POST "https://api.notion.com/v1/databases" \
  -H "Authorization: Bearer {{NOTION_TOKEN}}" \
  -H "Notion-Version: 2025-09-03" \
  -H "Content-Type: application/json" \
  -d '{
    "parent": {"type": "workspace", "workspace": true},
    "title": [{"type": "text", "text": {"content": "Pricing"}}],
    "initial_data_source": {
      "properties": {
        "Name": {"title": {}},
        "Hourly rate": {"number": {"format": "number"}},
        "Afternoon rate": {"number": {"format": "number"}},
        "Weekend rate": {"number": {"format": "number"}},
        "Callout charge (business hours)": {"number": {"format": "number"}},
        "Callout charge (after hours)": {"number": {"format": "number"}},
        "Hours of operation": {"rich_text": {}},
        "Notes": {"rich_text": {}}
      }
    }
  }'
```

Result: database id `1c11ce74-d9cd-4e57-9ef3-8ab732d6b71a`;
data source id `3087438d-379c-40e5-9dd6-20ef0b39b045`.

**Add sample rates** (POST /v1/pages):

```bash
# Standard Rate
curl -s -X POST "https://api.notion.com/v1/pages" \
  -H "Authorization: Bearer {{NOTION_TOKEN}}" \
  -H "Notion-Version: 2025-09-03" \
  -H "Content-Type: application/json" \
  -d '{
    "parent": {"type": "database_id", "database_id": "1c11ce74-d9cd-4e57-9ef3-8ab732d6b71a"},
    "properties": {
      "Name": {"title": [{"text": {"content": "Standard Rate"}}]},
      "Hourly rate": {"number": 45},
      "Afternoon rate": {"number": 35},
      "Weekend rate": {"number": 60},
      "Callout charge (business hours)": {"number": 45},
      "Hours of operation": {"rich_text": [{"text": {"content": "Mon-Fri 08:00-18:00 / Sat 09:00-17:00 / Sun closed"}}]},
      "Notes": {"rich_text": [{"text": {"content": "Default card - replace these values with your own"}}] }
    }
  }'
```

Also add:

- **Weekend Rate**: Hourly 60, Afternoon 60, Weekend 75, Hours "Sat-Sun 09:00-17:00", Notes "Weekend surcharge applies"
- **After-hours Rate**: Hourly 85, Afternoon 85, Weekend 85, **Callout charge (after hours) 85**, Hours "Outside normal hours (e.g. night calls / holidays)", Notes "Applied when job falls outside 08:00-18:00 Mon-Fri"

#### Callout charges (what the phone agent quotes)

A **callout charge** is the fee to attend site, quoted separately from labour:

| Band | Callout charge | When it applies |
|---|---|---|
| Business hours | **$45** | Mon-Fri 08:00-18:00, Sat 09:00-17:00 |
| After hours | **$85** | Evenings, Sundays, public holidays |

The phone agent (§5.2) quotes exactly these two numbers and nothing else. When the
rate card changes, update both the Notion rows above and the agent's prompt — they
are two sources that must agree.

### 4.4 Sample data (Customers + Bookings)

Create the customer "Acme Repair Co.":

```bash
curl -s -X POST "https://api.notion.com/v1/pages" \
  -H "Authorization: Bearer {{NOTION_TOKEN}}" \
  -H "Notion-Version: 2025-09-03" \
  -H "Content-Type: application/json" \
  -d '{
    "parent": {"type": "database_id", "database_id": "<CUSTOMERS_DB_ID>"},
    "properties": {
      "Name": {"title": [{"text": {"content": "Acme Repair Co."}}]},
      "Company": {"title": [{"text": {"content": "Acme Repair Co."}}]},
      "Phone": {"rich_text": [{"text": {"content": "+1-555-0102"}}]},
      "Email": {"rich_text": [{"text": {"content": "hello@acme.repair"}}]},
      "Address": {"rich_text": [{"text": {"content": ""}}]},
      "Preferred contact": {"select": {"name": "Email"}},
      "Notes": {"rich_text": [{"text": {"content": "Emergency jobs weekday 8-12"}}]},
      "Date added": {"date": {"start": "2026-10-21"}}
    }
  }'
```

Create the booking "A/C not cooling - Acme":

```bash
curl -s -X POST "https://api.notion.com/v1/pages" \
  -H "Authorization: Bearer {{NOTION_TOKEN}}" \
  -H "Notion-Version: 2025-09-03" \
  -H "Content-Type: application/json" \
  -d '{
    "parent": {"type": "database_id", "database_id": "<MW_BOOKINGS_DB_ID>"},
    "properties": {
      "Booking": {"title": [{"text": {"content": "A/C not cooling - Acme"}}]},
      "Customer": {"relation": [{"id": "<ACME_CUSTOMER_ID>"}]},
      "Date": {"date": {"start": "2026-10-23"}},
      "Time": {"select": {"name": "10:00"}},
      "Workers": {"multi_select": [{"name": "John Rivera"}]},
      "Status": {"select": {"name": "Confirmed"}},
      "Job": {"rich_text": [{"text": {"content": "Diagnose & repair A/C unit"}}]},
      "Pricing plan": {"relation": [{"id": "<STANDARD_RATE_ID>"}]},
      "Start time": {"date": {"start": "2026-10-23T10:00:00"}},
      "End time": {"date": {"start": "2026-10-23T12:00:00"}},
      "Time band": {"select": {"name": "Afternoon"}},
      "Rate applied": {"number": 35}
    }
  }'
```

### 4.5 Simple Plumber reference page

Create a page (POST /v1/pages) with parent type `page_id` pointing to any existing page, then add child blocks with plumbing content:

```bash
curl -s -X POST "https://api.notion.com/v1/pages" \
  -H "Authorization: Bearer {{NOTION_TOKEN}}" \
  -H "Notion-Version: 2025-09-03" \
  -H "Content-Type: application/json" \
  -d '{
    "parent": {"type": "page_id", "page_id": "<EXISTING_PAGE_ID>"},
    "properties": {
      "title": [{"text": {"content": "Simple Plumber"}}]
    }
  }'
```

Then append child blocks (PATCH /v1/blocks/{page_id}/children):

```bash
curl -s -X PATCH "https://api.notion.com/v1/blocks/<PAGE_ID>/children" \
  -H "Authorization: Bearer {{NOTION_TOKEN}}" \
  -H "Notion-Version: 2025-09-03" \
  -H "Content-Type: application/json" \
  -d '{
    "children": [
      {"object": "block", "type": "heading_1", "heading_1": {"rich_text": [{"type": "text", "text": {"content": "Simple Plumber"}}]}},
      {"object": "block", "type": "paragraph", "paragraph": {"rich_text": [{"type": "text", "text": {"content": "Your home plumbing does not have to be complicated. Here are simple, actionable tips for common plumbing issues."}}]}},
      {"object": "block", "type": "bulleted_list_item", "bulleted_list_item": {"rich_text": [{"type": "text", "text": {"content": "Fix a running toilet: Replace the flapper valve - usually a 5-minute DIY job."}}]}},
      {"object": "block", "type": "bulleted_list_item", "bulleted_list_item": {"rich_text": [{"type": "text", "text": {"content": "Clear slow drains: Pour 1/2 cup baking soda followed by 1/2 cup vinegar, let sit 15 minutes, then flush with hot water."}}]}},
      {"object": "block", "type": "bulleted_list_item", "bulleted_list_item": {"rich_text": [{"type": "text", "text": {"content": "Prevent frozen pipes: Insulate exposed pipes and let faucets drip during hard freezes."}}]}},
      {"object": "block", "type": "bulleted_list_item", "bulleted_list_item": {"rich_text": [{"type": "text", "text": {"content": "Check water pressure: Normal range is 40-60 psi; install a pressure gauge to monitor."}}]}},
      {"object": "block", "type": "paragraph", "paragraph": {"rich_text": [{"type": "text", "text": {"content": "For repairs beyond simple DIY, call our licensed plumbers. We service all of our service area with same-day emergency calls available."}}]}}
    ]
  }'
```

**Telegram share link**:

```
https://t.me/share/url?url=https://app.notion.com/p/Simple-Plumber-4006a106520f81cfb230f9ab05c2545f&text=Simple+Plumber
```

### 4.6 Cleanup — old duplicate databases (private, not trashed on page)

When rebuilding from scratch, old duplicate databases created on pages must be moved to workspace-level (or trashed) so they don't show as page children. Archive old database pages and their child databases.

---

## 5. Voice agent integration (Vapi)

The phone receptionist books into MW Bookings through a small bridge, and quotes
callout charges. Three moving parts:

```
Caller --phone--> Vapi assistant --tool-call webhook--> bridge PHP --Notion API--> MW Bookings + Customers
```

### 5.1 Knowing today's date (relative dates must not drift)

**The bug this fixes:** a bare LLM does not know the current date. Ask it for
"tomorrow" and it answers from its training data (e.g. a June-2024 date), then
books a call in the wrong year.

**The fix:** inject the current date into the assistant's system prompt using
Vapi **dynamic variables** (LiquidJS), and tell the model to convert every
relative day into `YYYY-MM-DD` before calling a tool:

```
Today is {{ "now" | date: "%A, %B %d, %Y" }} ({{ "now" | date: "%Y-%m-%d" }}); current time {{time}} UTC.

When the caller says a relative day - "today", "tomorrow", "the day after tomorrow",
"next Monday", "this weekend" - work out the real calendar date from the date above
and convert it to YYYY-MM-DD before calling checkAvailability or bookAppointment.
Never guess a date, and never use a year other than the one above.
```

Built-in variables (UTC): `{{now}}`, `{{date}}`, `{{time}}`, `{{month}}`, `{{day}}`,
`{{year}}`. Format any of them with the LiquidJS `date` filter, e.g.
`{{ "now" | date: "%Y-%m-%d" }}` -> `2026-10-23`, `{{ "now" | date: "%A" }}` -> `Friday`.
Default variables are filled automatically — do not pass them in `variableValues`.

### 5.2 Callout charges

The assistant answers a callout-charge question with **both** bands, and invents
no other price:

```
Callout charges (state only if the caller asks):
- If the caller asks about a callout charge, a visit fee, or what it costs to come out,
  tell them: $45 during business hours (Mon-Fri 08:00-18:00 and Sat 09:00-17:00), and
  $85 after hours (evenings, Sundays and public holidays).
- Quote just those two amounts. Do not invent, guess or negotiate any other price.
```

Keep the prompt numbers and the Pricing rows (§4.3) in sync.

### 5.3 Assistant tools

Tools live in `model.tools` (there is no top-level `assistant.tools`). Each is
`{"type":"function","server":{"url":...,"headers":{...},"timeoutSeconds":20},"function":{"name","description","parameters"}}`.
Two tools: `checkAvailability` and `bookAppointment`, both pointing at the bridge
URL with an `X-Booking-Token` header. Update the assistant with
`PATCH https://api.vapi.ai/assistant/<ASSISTANT_ID>` (Bearer `VAPI_API_KEY`);
partial top-level updates are merged, but re-send the whole `model` object so the
tools are not dropped. Verify by re-fetching and diffing the prompt + tool list.

### 5.4 Bridge

An HTTP endpoint that receives Vapi `tool-calls` webhooks and writes Notion:
`vapi-plumbing-booking.php`, deployed at the site root, with secrets (Notion
token, webhook token) in a sibling `private/` dir outside the docroot, `chmod 0600`.

- Auth: Vapi sends `X-Booking-Token`; the endpoint rejects a mismatch with 401.
- It reuses a customer matched by phone, else creates one, then creates the MW
  Bookings row and returns a spoken confirmation.
- `checkAvailability` queries MW Bookings by date and returns the free hourly slots.
- Test it without a phone: POST a fake `tool-calls` payload and confirm the Notion
  write lands (see the repo's demo package).

---

## 6. Key IDs (reference)

| Item | Id |
|---|---|
| Customers DB | `fffa5c0d-e48e-4178-91c2-8e035e91992b` |
| Customers data source | `60b42d2b-bee8-4292-b50f-e7d7e2e983ac` |
| MW Bookings DB | `0cf489e2-ff52-4a10-a1df-9c9d4cf6f554` |
| MW Bookings data source | `90953b03-ca18-43de-b6fd-c0692fbeb19a` |
| Pricing DB | `1c11ce74-d9cd-4e57-9ef3-8ab732d6b71a` |
| Pricing data source | `3087438d-379c-40e5-9dd6-20ef0b39b045` |
| Calendar view | `4006a106-520f-818c-b8e4-000c416aa1f9` |
| ACME customer | `4006a106-520f-810a-a515-ee41f490777d` |
| Standard Rate | `4006a106-520f-81b0-8bee-c0c53471d0f9` |
| After-hours Rate | `4006a106-520f-813d-b5c8-e9c7ee195433` |

## 7. Replicating from scratch

1. Create Customers database (workspace-level) with the properties listed in §4.1.
2. Create Pricing rate card (§4.3) with the sample rates **and callout charges**.
3. Create MW Bookings database (workspace-level) with the full property schema in §4.2 (relate `Pricing plan` to the Pricing data source).
4. Add the Calendar view (§4.2).
5. Add the sample customer + booking (§4.4).
6. Create the Simple Plumber page + Telegram share link (§4.5).
7. Trash any old duplicate page-level databases to avoid duplicates.
8. Wire the Vapi assistant (§5): date variables in the prompt, callout charges,
   the two tools pointing at the bridge.

## 8. Troubleshooting

- **Database create rejected `properties` at top level**: wrap the schema in `initial_data_source.properties`. This is the only correct nesting.
- **Select option validation error on page create**: do not put `id`/`color` on select options in a page create — only `name` is required. Property definitions in the DB create can have `id`/`color`, but page property values only need the name.
- **Calendar view date_property_id "not found"**: must be the url-encoded property ID (e.g., `a%7D%40i` for `Date`), not the property name.
- **Append block children endpoint**: use `PATCH /v1/blocks/{block_id}/children` with body `{"children": [...]}`. Do NOT use `POST` for this endpoint.
- **Need a new property on an existing database**: `PATCH /v1/data_sources/{data_source_id}` with `{"properties": {"New name": {"number": {...}}}}` adds it. (Property renames/type changes are still constrained; adding is safe.) The older advice that a property is create-time only is out of date.
- **Database update does not echo properties**: `GET /v1/databases/{id}` does not echo properties. Verify properties via the data-source query or child pages.
- **Agent books the wrong year ("tomorrow" -> 2024)**: the assistant prompt is
  missing the current-date variables (§5.1). Add `{{ "now" | date: "%Y-%m-%d" }}`
  and re-verify after a fresh PATCH.
- **Agent quotes a price it was not told**: the callout section is missing or the
  model is improvising. Restate the two fixed amounts and forbid other prices (§5.2).

## 9. Useful API endpoints

- Create DB: `POST /v1/databases`
- Get DB: `GET /v1/databases/{id}`
- Query data source: `POST /v1/data_sources/{data_source_id}/query`
- Add/update property: `PATCH /v1/data_sources/{data_source_id}`
- Create page: `POST /v1/pages`
- Update page: `PATCH /v1/pages/{id}`
- Get page: `GET /v1/pages/{id}`
- Append block children: `PATCH /v1/blocks/{block_id}/children`
- Create view: `POST /v1/views`

---

*Generated from a live Notion API session (Hermes Agent, 2026-10-21); updated
2026-10-22 with callout charges and Vapi relative-date handling.*
