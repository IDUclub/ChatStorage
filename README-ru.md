# ChatStorage — История чатов IDU LLM

FastAPI-сервис, который **сохраняет историю LLM-чатов** пользователей градостроительной
платформы IDU в формате, общем для сервисов IDU, и **воспроизводит/выполняет цепочки
MCP tool-call**, извлечённые из этой истории. Хранилище — MongoDB.

🇬🇧 [Documentation in English](README.md)

## Что делает сервис

Две зоны ответственности:

1. **CRUD истории чатов** — хранение и выдача чатов, сообщений и упорядоченных
   *частей* сообщения (текст, вызовы инструментов, результаты, статусы, данные,
   ссылки на файлы).
2. **Выполнение tool-call** — восстановление цепочки зависимостей сохранённого
   вызова инструмента и его выполнение на MCP-сервере (gMART IDU MCP или Object
   Effects MCP) с передачей предыдущих результатов вперёд через MCP `meta`.

Сообщения состоят из типизированных **частей**. Часть с типом `file` хранит
*ссылку* (URL + метаданные) на файл — сами байты файла ChatStorage не хранит.

## Технологический стек

- **Python 3.11**, управление зависимостями через **uv** (`uv.lock`, `pyproject.toml`)
- **FastAPI** + Starlette, запуск через **uvicorn**
- **MongoDB** через `pymongo` (асинхронный клиент)
- **FastMCP** `Client` — исходящие вызовы к MCP-серверам для выполнения инструментов
- **python-jose[cryptography]** — проверка JWT через Keycloak
- `loguru`, `tenacity`, `cachetools`, `aiohttp`

## Структура проекта

```
app/
  main.py                # FastAPI-приложение, middleware, роутеры, /ping, / -> /docs
  routers/v1/            # chat_history_router (/api/v1/chat_history)
  routers/system_controller.py   # /system (логи, env)
  services/              # chat_history_service, tool_call_execution_service
  schema/ dto/           # схемы ответов / входные DTO
  common/db/             # клиент Mongo, типы документов, стартовые миграции
  common/auth/ config/ middlewares/ ...
docs/                    # API-DOCS.md, frontend-chat-history.md
mongo/init/              # скрипты инициализации схемы и пользователя Mongo
tests/                   # наборы unit/ и integration/ (см. tests/README.md)
```

## Конфигурация

Настраивается через переменные окружения (см. [`.env.example`](.env.example)):

| Переменная | Назначение |
|---|---|
| `MONGO_URL` | MongoDB `host:port` или полный URI `mongodb://`/`mongodb+srv://` |
| `MONGO_USER`, `MONGO_PASSWORD`, `MONGO_DB` | Учётные данные и имя базы MongoDB |
| `IDU_MCP_URL` | База gMART IDU MCP — цель по умолчанию для воспроизведения tool-call |
| `OBJECTS_EFFECTS_MCP_URL` | База Object Effects MCP — альтернативная цель |
| `DVD_MCP_URL`, `NORM_GRAPH_MCP_URL` | MCP-серверы документов и нормативного графа для воспроизведения |
| `URBAN_<GROUP>_MCP_URL` | Один из шести grouped Urban MCP endpoints (`PROJECTS`, `TERRITORIES`, `PHYSICAL_OBJECTS`, `DICTIONARIES`, `INDICATORS`, `SOC_GROUPS`) |
| `AUTH_VERIFY` | Включение/выключение проверки подписи JWT |
| `AUTH_SERVER_URL`, `AUTH_CLIENT_ID`, `AUTH_VALID_AUDIENCES` | Realm Keycloak + проверка audience |
| `CHATSTORAGE_LOG_DIR`, `CHATSTORAGE_LOG_FILE` | Расположение файла логов |

## Запуск

### Docker (рекомендуется)

Сначала должна существовать внешняя сеть `localnet`; `docker-compose.yaml`
загружает `.env.example` и поднимает сервис вместе с MongoDB.

```bash
docker network create localnet           # один раз
docker compose up -d --build             # chat_storage (8010->8000) + mongo (27017)
```

Swagger UI: <http://localhost:8010/docs>

### Локально (uv)

```bash
uv sync                                            # установка зависимостей (с dev-группой)
APP_PORT=8000 uv run python -m app.dev_runner      # dev_runner читает APP_PORT
# или эквивалентно:
uv run uvicorn app.main:app --reload --port 8000
```

> `dev_runner.py` читает `APP_PORT` без значения по умолчанию — всегда экспортируйте
> его (или используйте команду uvicorn выше). MongoDB должна быть доступна согласно
> настройкам `MONGO_*`.

## API

Сервис предоставляет CRUD истории чатов, эндпоинт выполнения сохранённого tool-call
и операционные эндпоинты `/system`. Проверка состояния: `GET /ping`.

📖 **Полный справочник эндпоинтов: [docs/API-DOCS.md](docs/API-DOCS.md)**
· Гайд для фронтенда: [docs/frontend-chat-history.md](docs/frontend-chat-history.md)

## Тесты

```bash
uv run pytest                 # unit-тесты; интеграционные пропускаются без БД
uv run pytest -m integration  # нужна живая MongoDB (задайте TEST_MONGO_URL)
```

Настройка интеграционных тестов описана в [tests/README.md](tests/README.md).

## Качество кода

Форматирование обязательно: `black` + `isort --profile black`:

```bash
uv run pre-commit run --all-files
```

## Контекст

ChatStorage — один из четырёх сервисов градостроительной платформы IDU **ICII**.
Его вызывают **агенты gMART** для сохранения истории диалога, а сам он обращается к
MCP-серверам **gMART IDU MCP** / **ObjectEffectsAPI MCP** для выполнения сохранённых
вызовов инструментов.
