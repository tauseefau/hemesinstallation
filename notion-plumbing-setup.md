# Notion Setup — Simple Plumber Business

> Complete, replicable Notion workspace setup for a plumbing business. All instructions for an agent to rebuild this in a fresh Notion workspace.

## 1. What was built

| Item | Purpose | Visibility |
|---|---|---|
| **Customers** database (private, workspace-level) | Store customer records, contact info, preferred contact method | Sidebar Databases section (not on any page) |
| **MW Bookings** database (private, workspace-level) + **Calendar view** | Handle maintenance & repair bookings, with customer and pricing links | Sidebar Databases section |
| **Pricing** database (private, workspace-level) | Editable rate card: hourly / afternoon / weekend rates + hours of operation | Sidebar Databases section |

All databases are **workspace-level parents**, so they appear only in the Notion sidebar → Databases, and never on a page.

## 2. Prerequisites

- Notion account + a page (any page) as the "home" for creating databases
- Notion API token with `read_content` + `write_content` scopes (create at https://www.notion.com/my-account)
- Notion API version **2025-09-03** (used in all API calls)

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
        "Pricing plan": {"relation": {"data_source_id": "<CUSTOMERS_DATA_SOURCE_ID>", "database_id": "<CUSTOMERS_DB_ID>", "single_property": {}, "type": "single_property"}},
        "Start time": {"date": {}},
        "End time": {"date": {}},
        "Time band": {"select": {"options": [
            {"name": "Hourly"}, {"name": "Afternoon"}, {"name": "Weekend"}
        ]}},
        "Rate applied": {"number": {"format": "number"}},
        "Duration (hrs)": {"formula": {"expression": "dateBetween(prop(\"End time\"), prop(\"Start time\"), \"hours\")", "type": "number"}},
        "Estimated total": {"formula": {"expression": "prop(\"Duration (hrs)\") * prop(\"Rate applied\")", "type": "number"}}
      }
    }
  }'
```

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
        "Hours of operation": {"rich_text": {}},
        "Notes": {"rich_text": {}}
      }
    }
  }'
```

Result: database id `1c11ce74-d9cd-4e57-9ef3-8ab732d6b71a`.

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
      "Hours of Operation": {"rich_text": [{"text": {"content": "Mon–Fri 08:00–18:00 · Sat 09:00–17:00 · Sun closed"}}]},
      "Notes": {"rich_text": [{"text": {"content": "Default card — replace these values with your own"}}] }
    }
  }'
```

Also add:
- **Weekend Rate**: Hourly 60, Afternoon 60, Weekend 75, Hours "Sat–Sun 09:00–17:00", Notes "Weekend surcharge applies"
- **After-hours Rate**: Hourly 85, Afternoon 85, Weekend 85, Hours "Outside normal hours (e.g. night calls / holidays)", Notes "Applied when job falls outside 08:00–18:00 Mon–Fri"

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
      {"object": "block", "type": "paragraph", "paragraph": {"rich_text": [{"type": "text", "text": {"content": "Your home plumbing doesn't have to be complicated. Here are simple, actionable tips for common plumbing issues."}}]}},
      {"object": "block", "type": "bulleted_list_item", "bulleted_list_item": {"rich_text": [{"type": "text", "text": {"content": "Fix a running toilet: Replace the flapper valve — usually a 5-minute DIY job."}}]}},
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

## 5. Key IDs (reference)

| Item | Id |
|---|---|
| Customers DB | `fffa5c0d-e48e-4178-91c2-8e035e91992b` |
| Customers data source | `60b42d2b-bee8-4292-b50f-e7d7e2e983ac` |
| MW Bookings DB | `0cf489e2-ff52-4a10-a1df-9c9d4cf6f554` |
| MW Bookings data source | `90953b03-ca18-43de-b6fd-c0692fbeb19a` |
| Pricing DB | `1c11ce74-d9cd-4e57-9ef3-8ab732d6b71a` |
| ACME customer | `4006a106-520f-810a-a515-ee41f490777d` |
| Standard Rate | `4006a106-520f-81b0-8bee-c0c53471d0f9` |
| Calendar view | `4006a106-520f-818c-b8e4-000c416aa1f9` |

## 6. Replicating from scratch

1. Create Customers database (workspace-level) with the properties listed in §4.1.
2. Create MW Bookings database (workspace-level) with the full property schema in §4.2.
3. Add the Calendar view (§4.2).
4. Create the Pricing rate card (§4.3) with the sample rates.
5. Add the sample customer + booking (§4.4).
6. Create the Simple Plumber page + Telegram share link (§4.5).
7. Trash any old duplicate page-level databases to avoid duplicates.

## 7. Troubleshooting

- **Database create rejected `properties` at top level**: wrap the schema in `initial_data_source.properties`. This is the only correct nesting.
- **Select option validation error on page create**: do not put `id`/`color` on select options in a page create — only `name` is required. Property definitions in the DB create can have `id`/`color`, but page property values only need the name.
- **Calendar view date_property_id "not found"**: must be the url-encoded property ID (e.g., `a%7D%40i` for `Date`), not the property name.
- **Append block children endpoint**: use `PATCH /v1/blocks/{block_id}/children` with body `{"children": [...]}`. Do NOT use `POST` for this endpoint.
- **Property PATCHes not reflected**: Notion API cannot set database properties beyond `initial_data_source` at create time. If you need a new property, you must create a new database (not patch an existing one).
- **Database update does not echo properties**: GET /v1/databases/{id} does not echo properties. Verify properties via the data-source query or child pages.

## 8. Useful API endpoints

- Create DB: `POST /v1/databases`
- Get DB: `GET /v1/databases/{id}`
- Query data source: `POST /v1/data_sources/{data_source_id}/query`
- Create page: `POST /v1/pages`
- Get page: `GET /v1/pages/{id}`
- Append block children: `PATCH /v1/blocks/{block_id}/children`

---

*Generated from a live Notion API session (Hermes Agent, 2026-10-21). Rebuilt clean to keep only workspace-level private databases and one calendar view.*
