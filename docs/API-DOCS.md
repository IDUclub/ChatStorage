# ChatStorage API reference

REST API of the **IDU LLM Chat History** service. The service persists LLM chat
history in the IDU-shared format and replays/executes stored MCP tool-call chains.

- Base URL (Docker): `http://localhost:8010`
- Interactive docs: `GET /` → redirects to `/docs` (Swagger UI); OpenAPI JSON at `/openapi.json`
- All dates are ISO-8601 with timezone. `chat_id` / `message_id` / `user_id` are UUID strings (36 chars).

## Authentication

All `/api/v1/chat_history/*` endpoints require a Keycloak-issued JWT:

```
Authorization: Bearer <access_token>
```

- The user is resolved from the token on the backend — clients never pass `user_id`.
- Verification is toggled by `AUTH_VERIFY` (validated against `AUTH_SERVER_URL`,
  `AUTH_CLIENT_ID`, `AUTH_VALID_AUDIENCES`). With `AUTH_VERIFY=false` the signature
  is not checked, but a token carrying a user id is still required.
- `401` is returned when the bearer token is missing or carries no user id.

`/system/*` requires a verified service token. `/ping` and `/` remain unauthenticated for health
checks and navigation.

## Data model

```ts
type MessageRole = "user" | "assistant" | "system" | "tool";
type MessagePartKind =
  | "text"
  | "tool_call"
  | "tool_result"
  | "status"
  | "data"
  | "file";

type MessagePart = {
  part_seq: number;                  // 1-based order inside a message
  kind: MessagePartKind;
  payload: Record<string, unknown>;  // shape depends on kind
  mcp_source?: string | null;        // MCP server that produced/executes the part
  created_at: string;
};

type Message = {
  message_id: string;
  chat_id: string;
  seq: number;                       // 1-based order inside a chat
  role: MessageRole;
  parts: MessagePart[];
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

type ChatSummary = {
  chat_id: string;
  title: string | null;
  scenario_id: string | number | null;
  project_id: string | number | null;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

type Chat = ChatSummary & { messages: Message[] };
```

### Part payloads by `kind`

| kind | payload shape | notes |
|---|---|---|
| `text` | `{ "text": string }` | plain message text |
| `status` | `{ "status": string, "text"?: string }` | progress / status element |
| `tool_call` | `{ "calls": ToolCall[] }` | also accepts `tool_calls`; executable via the execute endpoint |
| `tool_result` | free-form | result of a tool call |
| `data` | free-form | scenario-specific; **not validated** by the service |
| `file` | `{ "url": string, "filename"?, "mime_type"?, "size_bytes"?, "source_service"?, … }` | **`url` is required and validated** (`422` otherwise). ChatStorage stores only the reference, never the bytes |

> A simple text message sent as `content` is stored and returned as `parts[0]`
> with `kind: "text"` and `payload.text`.

---

## Chat history endpoints

Prefix: `/api/v1/chat_history`

### List chats

```http
GET /api/v1/chat_history/chats?limit=50&offset=0&scenario_id=772&project_id=42
Authorization: Bearer <token>
```

Query parameters:

| name | type | default | notes |
|---|---|---|---|
| `limit` | int | `50` | `1`–`100` |
| `offset` | int | `0` | `≥ 0` |
| `scenario_id` | string | — | optional; matches both string and int storage (`772` ↔ `"772"`) |
| `project_id` | string | — | optional; same matching logic |

Sorted by `updated_at` descending. Response `200`:

```json
{ "items": [ /* ChatSummary */ ], "limit": 50, "offset": 0 }
```

### List unique chat titles

```http
GET /api/v1/chat_history/chats/titles
Authorization: Bearer <token>
```

Response `200`: `{ "items": string[] }` — non-empty unique titles, alphabetically sorted.

### Create chat

```http
POST /api/v1/chat_history/create_chat
Authorization: Bearer <token>
Content-Type: application/json
```

Body (optional):

```json
{
  "title": "New assistant chat",
  "scenario_id": "default",
  "project_id": 42,
  "metadata": { "source": "web" }
}
```

Response `201`: `ChatSummary`. `409` on a rare id collision (retry).

### Get chat with messages

```http
GET /api/v1/chat_history/{chat_id}
Authorization: Bearer <token>
```

Response `200`: `Chat` (messages ordered by `seq` ascending; no pagination). `404` if not found for this user.

### Add message

```http
POST /api/v1/chat_history/{chat_id}/message
Authorization: Bearer <token>
Content-Type: application/json
```

Provide **either** `content` (simple text) **or** explicit `parts`:

```ts
type CreateMessageRequest = {
  role: MessageRole;
  content?: string;            // min length 1
  parts?: {
    kind?: MessagePartKind;    // defaults to "text"
    payload: Record<string, unknown>;
    mcp_source?: string | null;
  }[];
  metadata?: Record<string, unknown>;
};
```

Example with a file attachment:

```json
{
  "role": "assistant",
  "parts": [
    { "kind": "text", "payload": { "text": "Here is the generated report." } },
    {
      "kind": "file",
      "payload": {
        "url": "https://files.example.org/reports/effects.docx",
        "filename": "effects.docx",
        "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "size_bytes": 184320,
        "source_service": "ObjectEffectsAPI"
      }
    }
  ],
  "metadata": { "model": "assistant" }
}
```

Response `201`: the stored `Message`. Errors: `404` (chat not found), `409` (sequence
collision, retry), `422` (neither `content` nor `parts`, or a `file` part without `url`).

### Get one message part

```http
GET /api/v1/chat_history/{chat_id}/messages/{message_id}/parts/{part_seq}
Authorization: Bearer <token>
```

Response `200`: `MessagePart`. `404` if the part does not exist. Useful for lazily
loading a heavy `data`/`tool_result`/`file` part by click.

### Execute a stored tool call

```http
GET /api/v1/chat_history/messages/{message_id}/parts/{part_seq}/tool_calls/{tool_call}/execute?scenario_id=772&project_id=42
Authorization: Bearer <token>
```

Rebuilds the dependency chain for the target tool call and executes it (and its
prerequisites) against the relevant MCP server (IDU MCP by default, or the part's
`mcp_source`), feeding earlier results forward as MCP `meta`.

Path parameters:

| name | notes |
|---|---|
| `message_id` | message holding the `tool_call` part |
| `part_seq` | part number inside the message |
| `tool_call` | 1-based index of the call inside the part |

Query: `scenario_id`, `project_id` — optional; fall back to `message.metadata`,
then to the chat.

Expected `tool_call` part payload:

```json
{
  "kind": "tool_call",
  "payload": {
    "calls": [
      { "step": 1, "tool_name": "GetServices", "arguments": { "services_names": ["school"] } }
    ]
  }
}
```

(`payload.tool_calls` is also accepted; the tool name may be in `tool_name`, `name`
or `function.name`.)

Response `200`:

```ts
type ToolCallExecutionResult = {
  target: ToolCall;
  execution_chain: ToolCallExecutionStep[];
  missing_dependencies: string[];
  steps: ToolCallResultStep[];
  result: Record<string, unknown> | null;   // last step's result
};

type ToolCall = { step: number | null; tool_name: string; arguments: Record<string, unknown> };
type ToolCallExecutionStep = {
  order: number; tool_call: ToolCall; depends_on: number[]; requires: string[]; provides: string[];
};
type ToolCallResultStep = {
  order: number; tool_call: ToolCall; meta: Record<string, unknown>; result: Record<string, unknown>;
};
```

Errors: `404` (message / part / tool call step not found), `422` (missing
dependencies — body includes `missing_dependencies` and `execution_chain`),
`503` (no MCP URL configured).

### Delete chat

```http
DELETE /api/v1/chat_history/{chat_id}
Authorization: Bearer <token>
```

Response `200`: `{ "chat_id": string, "deleted_messages": number }`. `404` if not found.

---

## System endpoints

Prefix: `/system` — operational helpers protected by a verified service token.

| Method & path | Description |
|---|---|
| `GET /system/logs` | Download the current loguru log file (`FileResponse`) |
| `GET /system/env` | All process environment variables as a key/value map |
| `PATCH /system/env` | Bulk-set env vars (`{"KEY": "value", …}`); reinitializes the DB client if any `MONGO_*` changes |
| `GET /system/env/{key}` | Value of one env var (`404` if absent) |
| `PUT /system/env/{key}` | Set one env var (body `{"value": "…"}`); reinitializes the DB client for `MONGO_*` keys |

---

## Service endpoints

| Method & path | Description |
|---|---|
| `GET /ping` | Health check → `{ "status": "ok", "message": "pong" }` |
| `GET /` | Redirects to `/docs` |

---

## Error format

FastAPI `HTTPException`:

```json
{ "detail": "Chat f47ac10b-… not found" }
```

Unhandled errors (via `ExceptionHandlerMiddleware`):

```json
{ "message": "Internal server error", "error_type": "RuntimeError", "detail": "…" }
```

Common status codes: `401` (no/invalid token), `404` (not found for this user),
`409` (id/sequence collision — retry), `422` (invalid body/query or missing tool-call
dependencies), `500` (internal), `503` (MCP URL not configured).

## See also

- [Frontend guide / гайд для фронтенда](frontend-chat-history.md) — UI integration flow and a minimal API client.
