## v0.4.1 (2026-08-24)

### Fix

- **migrations**: allow the space field before backfilling it (#33)

## v0.4.0 (2026-08-24)

### Feat

- persist executable compliance results (#29) (#30)
- persist executable compliance results (#29)
- **auth**: propagate service user identity (#25)
- **chat-context**: persist asynchronous dialogue snapshots (#23)
- **auth**: support service tokens (#20)
- **chat_history_service**: (#18)

## v0.2.0 (2026-06-26)

### Feat

- **migrations**: (#14) (#15)
- **file-link**: (#16)
- **pyproject**: - updated dependencies - upgraded version to 0.1.4
- **migrations**: (#14)
- **env-vars**: - db service updated on var update
- **env-vars**: - added env vars endpoints
- **chat_history_service**: - added mcp source to message part - version upgraded to 0.1.3

### Fix

- **lock**: - fixed lock file
- **mongo-auth**: - changed mongo auth

## v0.1.2 (2026-05-09)

### Feat

- **docs**: - added ai generated readme
- **docker**: - works from docker
- **docker**: - updated Dockerfile
- **tool_call_extraction**: - added tool call extraction for tool call from chain. - upgraded app version
- **chat_history_service**: - added unique chat titles endpoints - updated dev-runner
- **logs**: - updated logs formation logic - updated logic for default int retrieval - updated .env.example file - updated pypoject.roml - added docstring to system_controller
- **review**: - added logs to dockerignore and gitignore - added PROJECT_ROOT app config logging in startup - refactored auth client, made more readable - made int values loading from floats with zero-part - changed service naming in docker-compose.yaml - refactored PROJECT_ROOT search - moved .log to logs/.log folder
- **ignore**: - updated dockerignore
- **ignore**: - updated gitignore - updated dockerignore
- **chat-storage**: - adede minimal working chat storage service - updated toml
- **auth**: - auth via keycloak finished
- **auth**: - auth in progress
- **chat_storage**: - rest interface
- **mongo_init**: - mongo db structure in progress
- **0.0.1**: - initial commit - app structure created

### Fix

- **tool_call_extraction**: - fixed tool_call extraction
