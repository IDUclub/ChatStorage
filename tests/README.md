# Tests

```
tests/
  unit/          # pure-Python, no external services — always runnable
  integration/   # require a live MongoDB (marked @pytest.mark.integration)
  conftest.py    # shared Mongo fixtures (skip when DB is unavailable)
```

## Run

```bash
uv sync                       # installs pytest + pytest-asyncio (dev group)

uv run pytest                 # unit tests run; integration tests skip if no DB
uv run pytest tests/unit      # unit only
uv run pytest -m integration  # integration only
```

## Integration tests

Integration tests need a MongoDB. Point them at one with `TEST_MONGO_URL`;
without it (or if the server is unreachable) they are **skipped**, never failed.

```bash
# Throwaway Mongo (or reuse the docker-compose one: admin:admin@localhost:27017)
docker run -d --rm --name cs_test_mongo -p 27018:27017 \
  -e MONGO_INITDB_ROOT_USERNAME=admin -e MONGO_INITDB_ROOT_PASSWORD=admin \
  mongo:8.0.21-rc1-noble

TEST_MONGO_URL="mongodb://admin:admin@localhost:27018/?authSource=admin" \
  uv run pytest -m integration

docker stop cs_test_mongo
```

The fixtures create a uniquely-named throwaway database (seeded with the
production validators from `mongo/init/01-init.js` / `app/common/db/migrations.py`)
and drop it on teardown, so nothing persists between runs.
```
