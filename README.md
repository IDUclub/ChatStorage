# ChatStorage — IDU LLM Chat History

FastAPI service that **persists LLM chat history** for IDU urban-planning users in a
format shared across IDU services, and **replays/executes MCP tool-call chains**
extracted from that history. Storage is MongoDB.

🇷🇺 [Документация на русском](README-ru.md)

## What it does

Two responsibilities:

1. **Chat history CRUD** — store and retrieve chats, messages and ordered message
   *parts* (text, tool calls, tool results, status, data, file references).
2. **Tool-call execution** — rebuild the dependency chain of a stored tool call and
   execute it against an MCP server (gMART IDU MCP or Object Effects MCP), feeding
   earlier results forward as MCP `meta`.

Messages are made of typed **parts**. The `file` part kind stores a *reference*
(URL + metadata) to a file — ChatStorage never stores the file bytes themselves.

## Tech stack

- **Python 3.11**, dependency management with **uv** (`uv.lock`, `pyproject.toml`)
- **FastAPI** + Starlette, served by **uvicorn**
- **MongoDB** via `pymongo` (async client)
- **FastMCP** `Client` — outbound calls to MCP servers for tool execution
- **python-jose[cryptography]** — JWT verification against Keycloak
- `loguru`, `tenacity`, `cachetools`, `aiohttp`

## Project layout

```
app/
  main.py                # FastAPI app, middleware, routers, /ping, / -> /docs
  routers/v1/            # chat_history_router (/api/v1/chat_history)
  routers/system_controller.py   # /system (logs, env)
  services/              # chat_history_service, tool_call_execution_service
  schema/ dto/           # response schemas / input DTOs
  common/db/             # Mongo client, document types, startup migrations
  common/auth/ config/ middlewares/ ...
docs/                    # API-DOCS.md, frontend-chat-history.md
mongo/init/              # Mongo schema + user init scripts
tests/                   # unit/ and integration/ suites (see tests/README.md)
```

## Configuration

Configured via environment variables (see [`.env.example`](.env.example)):

| Variable | Purpose |
|---|---|
| `MONGO_URL` | MongoDB `host:port`, or a full `mongodb://`/`mongodb+srv://` URI |
| `MONGO_USER`, `MONGO_PASSWORD`, `MONGO_DB` | MongoDB credentials and database |
| `IDU_MCP_URL` | gMART IDU MCP base — default target for tool-call replay |
| `OBJECTS_EFFECTS_MCP_URL` | Object Effects MCP base — alternate replay target |
| `AUTH_VERIFY` | Toggle JWT signature verification on/off |
| `AUTH_SERVER_URL`, `AUTH_CLIENT_ID`, `AUTH_VALID_AUDIENCES` | Keycloak realm + audience validation |
| `CHATSTORAGE_LOG_DIR`, `CHATSTORAGE_LOG_FILE` | Log file location |

## Running

### Docker (recommended)

The external `localnet` network must exist first; `docker-compose.yaml` loads
`.env.example` and starts the service together with MongoDB.

```bash
docker network create localnet           # once
docker compose up -d --build             # chat_storage (8010->8000) + mongo (27017)
```

Swagger UI: <http://localhost:8010/docs>

### Local (uv)

```bash
uv sync                                            # install deps (incl. dev group)
APP_PORT=8000 uv run python -m app.dev_runner      # dev_runner reads APP_PORT
# or, equivalently:
uv run uvicorn app.main:app --reload --port 8000
```

> `dev_runner.py` reads `APP_PORT` with no default — always export it (or use the
> uvicorn command above). MongoDB must be reachable per your `MONGO_*` settings.

## API

The service exposes chat-history CRUD, a stored-tool-call execution endpoint, and
operational `/system` endpoints. Health check: `GET /ping`.

📖 **Full endpoint reference: [docs/API-DOCS.md](docs/API-DOCS.md)**
· Frontend integration guide: [docs/frontend-chat-history.md](docs/frontend-chat-history.md)

## Tests

```bash
uv run pytest                 # unit tests; integration tests skip without a DB
uv run pytest -m integration  # needs a live MongoDB (set TEST_MONGO_URL)
```

See [tests/README.md](tests/README.md) for the integration-test setup.

## Quality

Formatting is enforced with `black` + `isort --profile black`:

```bash
uv run pre-commit run --all-files
```

## Context

ChatStorage is one of four services in the **ICII** IDU urban-planning platform.
It is called by the **gMART agents** to persist conversation history, and it calls
the **gMART IDU MCP** / **ObjectEffectsAPI MCP** servers to execute stored tool calls.
