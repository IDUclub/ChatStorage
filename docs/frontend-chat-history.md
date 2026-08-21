# Frontend guide: работа с историей чата

Документ описывает контракт Chat Storage API для фронтенда: как создать чат, загрузить список чатов, открыть историю сообщений, сохранить новые сообщения и повторно выполнить сохраненный tool call.

## Базовые правила

- Base URL сервиса зависит от окружения фронта. В локальной разработке обычно используется `http://localhost:<port>`.
- Все методы истории требуют заголовок `Authorization: Bearer <access_token>`.
- Пользователь определяется на backend по токену. Фронт не передает `user_id` в query/body.
- **Сервисные токисны (M2M).** Если запрос выполняется с сервисным токеном Keycloak
  (client-credentials, `preferred_username` вида `service-account-<client-id>`), то
  backend не может определить пользователя по токену, поэтому нужно передать заголовок
  `X-User-Id: <user_id>` — под этим пользователем будет вестись чтение/запись истории.
  Для обычных пользовательских токенов заголовок `X-User-Id` игнорируется (используется
  subject токена), что не даёт одному пользователю действовать от имени другого.
- Все даты приходят в ISO-формате `datetime` с timezone.
- `chat_id` и `message_id` - UUID-строки длиной 36 символов.
- Чаты в списке отсортированы backend по `updated_at` от новых к старым.
- Сообщения внутри чата отсортированы backend по `seq` от старых к новым.
- CORS включен для всех origins, credentials не используются.

## Модель данных

### ChatSummary

```ts
type ChatSummary = {
  chat_id: string;
  title: string | null;
  scenario_id: string | number | null;
  project_id: string | number | null;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};
```

Используется в списке чатов и как результат создания чата.

### Chat

```ts
type Chat = ChatSummary & {
  messages: Message[];
  has_more: boolean;
  next_before_seq: number | null;
};
```

### Message

```ts
type MessageRole = "user" | "assistant" | "system" | "tool";
type MessagePartKind =
  | "text"
  | "tool_call"
  | "tool_result"
  | "status"
  | "data"
  | "table"
  | "file"
  | "plan"
  | "plan_revision"
  | "artifact_ref"
  | "validation"
  | "failure"
  | "check_plan"
  | "requirement_resolution"
  | "compliance_result"
  | "compliance_summary";

type Message = {
  message_id: string;
  chat_id: string;
  seq: number;
  role: MessageRole;
  parts: MessagePart[];
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

type MessagePart = {
  part_seq: number;
  kind: MessagePartKind;
  payload: Record<string, unknown>;
  created_at: string;
};
```

`parts` - основной формат контента сообщения. Простое текстовое сообщение backend тоже возвращает как `parts[0]` с `kind: "text"` и `payload.text`.

Compliance parts валидируются структурно: `check_plan` содержит версию схемы,
шаблон и источник нормы; `requirement_resolution` — effective/resolved/missing
requirements; `compliance_result` — раздельные verification/compliance статусы,
coverage и версии; `compliance_summary` — агрегаты запроса. Не вычисляйте вердикт
повторно из соседнего текстового part.

## Endpoints

### Получить список чатов

```http
GET /api/v1/chat_history/chats?limit=50&offset=0
Authorization: Bearer <token>
```

Query:

- `limit` - от `1` до `100`, по умолчанию `50`.
- `offset` - от `0`, по умолчанию `0`.
- `scenario_id` - необязательный фильтр по сценарию. Совпадает и со строковым, и с числовым значением (`772` найдёт чаты, где сохранено как `"772"` или `772`).
- `project_id` - необязательный фильтр по проекту, по той же логике совпадения.

Фильтры можно комбинировать. Чаты всегда отсортированы по `updated_at` от новых к старым, независимо от фильтров.

Ответ:

```ts
type ChatListResponse = {
  items: ChatSummary[];
  limit: number;
  offset: number;
};
```

Пример:

```json
{
  "items": [
    {
      "chat_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
      "title": "New assistant chat",
      "scenario_id": "default",
      "project_id": 42,
      "metadata": { "source": "web" },
      "created_at": "2026-05-08T14:00:00Z",
      "updated_at": "2026-05-08T14:10:00Z"
    }
  ],
  "limit": 50,
  "offset": 0
}
```

Рекомендация для UI: используйте `offset + items.length` для загрузки следующей страницы. Если `items.length < limit`, следующей страницы нет.

### Получить уникальные названия чатов

```http
GET /api/v1/chat_history/chats/titles
Authorization: Bearer <token>
```

Ответ:

```ts
type ChatTitleListResponse = {
  items: string[];
};
```

Метод полезен для автодополнения или фильтров по уже использованным названиям. Backend возвращает только непустые уникальные `title`, отсортированные по алфавиту.

### Создать пустой чат

```http
POST /api/v1/chat_history/create_chat
Authorization: Bearer <token>
Content-Type: application/json
```

Body необязателен. Если данных нет, чат будет создан с пустыми `title`, `scenario_id`, `project_id` и `metadata`.

```ts
type CreateChatRequest = {
  title?: string | null;
  scenario_id?: string | number | null;
  project_id?: string | number | null;
  metadata?: Record<string, unknown>;
};
```

`project_id` опционален, но фронту следует передавать его всегда, когда задан `scenario_id`.

Пример:

```json
{
  "title": "New assistant chat",
  "scenario_id": "default",
  "project_id": 42,
  "metadata": {
    "source": "web"
  }
}
```

Ответ: `ChatSummary`, HTTP `201`.

В данный момент необходимо только на бэкэнде, чаты сами создаются, если не задавать chat_id в запросах к gMART.

### Получить чат с сообщениями

```http
GET /api/v1/chat_history/{chat_id}
Authorization: Bearer <token>
```

Без query-параметров endpoint сохраняет прежнее поведение и возвращает все сообщения.
Для больших диалогов используйте обратную пагинацию:

```http
GET /api/v1/chat_history/{chat_id}?message_limit=40
GET /api/v1/chat_history/{chat_id}?message_limit=40&before_seq=121
```

- `message_limit` — размер страницы от `1` до `100`. Первая страница содержит последние сообщения.
- `before_seq` — вернуть сообщения с `seq` меньше указанного значения.
- Сообщения в каждой странице всегда отсортированы по `seq` от старых к новым.
- Если `has_more=true`, следующую страницу нужно запросить с `before_seq=next_before_seq`.

Ответ: `Chat`.

Пример:

```json
{
  "chat_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "title": "New assistant chat",
  "scenario_id": "default",
  "project_id": 42,
  "metadata": {},
  "created_at": "2026-05-08T14:00:00Z",
  "updated_at": "2026-05-08T14:10:00Z",
  "has_more": false,
  "next_before_seq": null,
  "messages": [
    {
      "message_id": "8ec7f7b8-ec3f-4bb9-a6c4-89f7a930bda1",
      "chat_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
      "seq": 1,
      "role": "user",
      "parts": [
        {
          "part_seq": 1,
          "kind": "text",
          "payload": { "text": "Что можно узнать об этом проекте?" },
          "created_at": "2026-05-08T14:01:00Z"
        }
      ],
      "metadata": { "client_message_id": "local-1" },
      "created_at": "2026-05-08T14:01:00Z",
      "updated_at": "2026-05-08T14:01:00Z"
    }
  ]
}
```

### Получить отдельную часть сообщения

```http
GET /api/v1/chat_history/{chat_id}/messages/{message_id}/parts/{part_seq}
Authorization: Bearer <token>
```

Ответ: `MessagePart`.

Метод полезен, если UI хранит компактную версию сообщения и хочет дозагрузить тяжелый `data` или `tool_result` part по клику.

## Актуальный контекст диалога

Scenario-data хранит отдельно от сообщений опубликованный сжатый контекст в двух
представлениях: русский `summary` и структурированный объект с подтверждёнными
фактами, решениями, маппингами, наборами данных, выполненными задачами и открытыми
вопросами. Геометрии, полные таблицы, токены и внутренние рассуждения туда не входят.

```http
GET /api/v1/chat_context/{chat_id}?tail_limit=100
Authorization: Bearer <token>
```

Ответ содержит опубликованную `revision`, `content`, `updated_through_seq` и
необработанный `tail`. Для большого хвоста используются `tail_has_more` и
`tail_next_after_seq`. После финализации сообщения gMART ставит неблокирующую задачу:

```http
POST /api/v1/chat_context/{chat_id}/jobs
Authorization: Bearer <token>
Content-Type: application/json

{"target_seq": 42, "model": "gpt-oss-20b", "prompt_version": "scenario-data-v1"}
```

Внутренние endpoints claim/source/complete/fail доступны только context worker с
проверенным Keycloak service token. Worker читает хвост порциями и иерархически
сворачивает их в один контекст. Публикация защищена CAS по `updated_through_seq`;
хранится до десяти ревизий не старше семи дней, задача повторяется не более трёх раз.

### Выполнить сохраненный tool call

```http
GET /api/v1/chat_history/messages/{message_id}/parts/{part_seq}/tool_calls/{tool_call}/execute?scenario_id=772&project_id=42
Authorization: Bearer <token>
```

Для новых compliance-инструментов сервис сначала повторно получает сохранённые
исходные слои, затем подставляет их в аргумент `layers` геометрического вызова.
Сохранённый компактный tool call при этом не изменяется. Выполнение идёт по текущему
состоянию сценария: это повторный расчёт, а не гарантированное историческое
воспроизведение без immutable revision или снимка данных.

Path:

- `message_id` - id сообщения, где лежит part с tool calls.
- `part_seq` - номер part внутри сообщения.
- `tool_call` - порядковый номер tool call внутри part, начиная с `1`.

Источник вызова берётся из `part.mcp_source`. ChatStorage понимает как короткие ключи,
так и сохраняемые gMART обозначения (`IDU_MCP_URL`, `OBJECTS_EFFECTS_MCP_URL`,
`DVD_MCP_URL`, `NORM_GRAPH_MCP_URL`, `URBAN_MCP/<group>`). Они сопоставляются с
одноимёнными переменными окружения; неизвестный источник использует `IDU_MCP_URL`.

Query:

- `scenario_id` - необязательный. Если не передать, backend попробует взять его из `message.metadata.scenario_id`, затем из `chat.scenario_id`.
- `project_id` - необязательный. Если не передать, backend попробует взять его из `message.metadata.project_id`, затем из `chat.project_id`.

Ожидаемый формат `tool_call` part:

```json
{
  "kind": "tool_call",
  "payload": {
    "calls": [
      {
        "step": 1,
        "tool_name": "GetServices",
        "arguments": {
          "services_names": ["school"]
        }
      }
    ]
  }
}
```

Backend также понимает `payload.tool_calls` вместо `payload.calls`, а имя инструмента может быть в `tool_name`, `name` или `function.name`.

Ответ:

```ts
type ToolCallExecutionResult = {
  target: ToolCall;
  execution_chain: ToolCallExecutionStep[];
  missing_dependencies: string[];
  steps: ToolCallResultStep[];
  result: Record<string, unknown> | null;
};

type ToolCall = {
  step: number | null;
  tool_name: string;
  arguments: Record<string, unknown>;
};

type ToolCallExecutionStep = {
  order: number;
  tool_call: ToolCall;
  depends_on: number[];
  requires: string[];
  provides: string[];
};

type ToolCallResultStep = {
  order: number;
  tool_call: ToolCall;
  meta: Record<string, unknown>;
  result: Record<string, unknown>;
};
```

Рекомендация для UI: показывайте кнопку "Повторить" или "Выполнить" только для `part.kind === "tool_call"`. Пока запрос выполняется, блокируйте повторный клик для того же `message_id + part_seq + tool_call`.

## Рендеринг parts

Рекомендуемая логика отображения:

```ts
function getTextFromPart(part: MessagePart): string | null {
  if (part.kind !== "text") return null;

  const text = part.payload.text;
  return typeof text === "string" ? text : null;
}
```

Обработка по типам:

- `text` - показать `payload.text`.
- `status` - показать статус выполнения, если UI поддерживает такие элементы. Часто поля: `payload.status`, `payload.text`.
- `tool_call` - показать компактный блок с названием инструмента и аргументами; дополнительно можно дать action на execute endpoint.
- `tool_result` - показать результат инструмента, если он нужен пользователю.
- `data` - рендерить по внутреннему контракту конкретного сценария; Chat Storage не валидирует форму `payload`.
- `table` - отрисовать таблицу по строгому контракту `payload.columns` + `payload.rows`. См. раздел ниже.
- `file` - показать вложение (имя, иконку по `mime_type`, размер) со ссылкой на скачивание `payload.url`. См. раздел ниже.

Если фронт не знает тип part или структуру payload, лучше показать безопасный fallback: collapsed JSON/debug view для разработческих окружений или пропустить part в production UI.

## Part с таблицей (`kind: "table"`)

Таблицы формируются сервисами (например, provision-агентом gMART) детерминированно —
названия колонок фиксированы в коде сервиса и не генерируются LLM, поэтому UI может
опираться на стабильные `key` колонок.

Форма `payload` для `kind: "table"`:

```ts
type TableColumn = {
  key: string;   // машинный ключ колонки, стабилен между запросами
  label: string; // человекочитаемый заголовок (рус.)
};

type TablePartPayload = {
  name: string;            // машинный идентификатор таблицы, напр. "provision_summary"
  title?: string;          // заголовок таблицы для UI
  columns: TableColumn[];  // порядок колонок задаёт порядок отображения
  rows: Record<string, unknown>[]; // значения по ключам колонок
  // допускаются дополнительные поля, специфичные для сервиса-источника
};
```

Backend **валидирует** payload: обязательны непустые `name` и `columns` (у каждой
колонки `key` и `label`), иначе сохранение сообщения вернёт `422`.

Известные таблицы provision-агента:

- `provision_summary` — сводка дефицитов/профицитов по сервисам; колонки
  `service`, `capacity`, `demand`, `deficit`, `surplus`, `balance`; строки
  отсортированы по убыванию дефицита.
- `provision_metrics` — показатели обеспеченности одним сервисом; колонки
  `metric`, `value`.
- `effects_pivot` — сводные показатели эффектов проекта; колонки `metric`, `value`.

Пример:

```json
{
  "kind": "table",
  "payload": {
    "name": "provision_summary",
    "title": "Сводка обеспеченности сервисами",
    "columns": [
      { "key": "service", "label": "Сервис" },
      { "key": "capacity", "label": "Вместимость (чел)" },
      { "key": "demand", "label": "Спрос (чел)" },
      { "key": "deficit", "label": "Дефицит (чел)" },
      { "key": "surplus", "label": "Профицит (чел)" },
      { "key": "balance", "label": "Баланс (чел)" }
    ],
    "rows": [
      { "service": "Школы", "capacity": 1200, "demand": 1450, "deficit": 250, "surplus": 0, "balance": -250 },
      { "service": "Детские сады", "capacity": 800, "demand": 620, "deficit": 0, "surplus": 180, "balance": 180 }
    ]
  }
}
```

## Part с файлом (`kind: "file"`)

Chat Storage **не хранит сами файлы — только ссылку на них**. Байты файла лежат в
отдельном хранилище (его наполняет сервис-источник), а в истории сохраняется лишь
референс. Это держит документы сообщений компактными (в MongoDB лимит 16 МБ на документ,
а весь чат отдаётся одним запросом).

Форма `payload` для `kind: "file"`:

```ts
type FilePartPayload = {
  url: string;            // обязателен: ссылка на файл
  filename?: string;      // отображаемое имя
  mime_type?: string;     // для выбора иконки/превью
  size_bytes?: number;    // размер в байтах
  source_service?: string; // какой сервис породил файл
  // допускаются дополнительные поля, специфичные для сервиса-источника
};
```

В отличие от `data`, для `file` backend **валидирует** payload: поле `url` обязательно
и непустое, иначе сохранение сообщения вернёт `422`. Остальные поля опциональны и
служат для рендера вложения в UI без скачивания.

Пример сообщения ассистента с текстом и файлом:

```json
{
  "role": "assistant",
  "parts": [
    {
      "kind": "text",
      "payload": { "text": "Готов отчёт по эффектам." }
    },
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

## Рекомендуемый frontend flow

### Открытие страницы чата

1. Загрузить список чатов: `GET /chats?limit=50&offset=0`.
2. Если в URL есть `chat_id`, загрузить полный чат: `GET /{chat_id}`.
3. Если `chat_id` нет, показать пустой composer без создания чата.
4. Создавать чат только перед первым сохраненным сообщением.

### Отправка первого сообщения

1. Если `chat_id` еще нет, вызвать `POST /create_chat`.
2. Оптимистично добавить сообщение пользователя в UI с локальным `client_message_id`.
3. Вызвать `POST /{chat_id}/message`.
4. Заменить локальное сообщение серверным `Message`.
5. Обновить sidebar: новый чат поставить вверх или перезагрузить первую страницу списка.

### Дозагрузка истории

Сейчас endpoint полного чата возвращает все сообщения без пагинации. Поэтому для длинных историй фронту стоит:

- показывать skeleton/loader на время открытия чата;
- виртуализировать список сообщений на клиенте, если сообщений много;
- не запрашивать чат повторно после каждого локального добавления сообщения, а добавлять ответ `POST /message` в локальный cache.

## Ошибки

Типичные статусы:

- `400` - сервисный токен передан без заголовка `X-User-Id`.
- `401` - нет Bearer-токена или токен не содержит user id.
- `404` - чат, сообщение или part не найден для текущего пользователя.
- `409` - редкая коллизия id/sequence; можно повторить запрос.
- `422` - невалидный body/query/path или не хватает зависимостей для tool call.
- `500` - внутренняя ошибка сервиса.
- `503` - `IDU_MCP_URL` не настроен при выполнении tool call.

Для `HTTPException` FastAPI обычно возвращает:

```json
{
  "detail": "Chat f47ac10b-58cc-4372-a567-0e02b2c3d479 not found"
}
```

Для необработанных ошибок middleware возвращает:

```json
{
  "message": "Internal server error",
  "error_type": "RuntimeError",
  "detail": "..."
}
```

Рекомендация для UI:

- на `401` отправлять пользователя в auth flow;
- на `404` удалять чат из локального списка или показывать "чат недоступен";
- на `422` подсвечивать проблему в форме или показывать текст из `detail`;
- на `503` для tool call показывать, что выполнение инструментов временно недоступно.

## Минимальный API client

```ts
const API_BASE_URL = import.meta.env.VITE_CHAT_STORAGE_URL;

async function request<T>(
  path: string,
  token: string,
  init: RequestInit = {},
): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
      ...init.headers,
    },
  });

  if (!response.ok) {
    const errorBody = await response.json().catch(() => null);
    throw new Error(
      errorBody?.detail?.message ??
        errorBody?.detail ??
        errorBody?.message ??
        `Chat Storage request failed: ${response.status}`,
    );
  }

  return response.json() as Promise<T>;
}

export function getChats(
  token: string,
  limit = 50,
  offset = 0,
  filters: { scenario_id?: string | number; project_id?: string | number } = {},
) {
  const params = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  });
  if (filters.scenario_id != null)
    params.set("scenario_id", String(filters.scenario_id));
  if (filters.project_id != null)
    params.set("project_id", String(filters.project_id));

  return request<ChatListResponse>(
    `/api/v1/chat_history/chats?${params.toString()}`,
    token,
  );
}

export function createChat(token: string, body: CreateChatRequest = {}) {
  return request<ChatSummary>("/api/v1/chat_history/create_chat", token, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function getChat(token: string, chatId: string) {
  return request<Chat>(`/api/v1/chat_history/${chatId}`, token);
}

export function addMessage(
  token: string,
  chatId: string,
  body: CreateMessageRequest,
) {
  return request<Message>(`/api/v1/chat_history/${chatId}/message`, token, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function deleteChat(token: string, chatId: string) {
  return request<{ chat_id: string; deleted_messages: number }>(
    `/api/v1/chat_history/${chatId}`,
    token,
    { method: "DELETE" },
  );
}
```

## Удаление чата

```http
DELETE /api/v1/chat_history/{chat_id}
Authorization: Bearer <token>
```

Ответ:

```json
{
  "chat_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "deleted_messages": 12
}
```

Рекомендация для UI: после успешного удаления убрать чат из sidebar и, если он был открыт, сбросить текущий диалог в пустое состояние.
