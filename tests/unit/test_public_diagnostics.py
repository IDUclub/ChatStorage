from fastapi.testclient import TestClient

from app.depndencies.dependencies import get_logs_path
from app.main import app


def test_diagnostic_reads_are_public_and_writes_require_auth(tmp_path, monkeypatch):
    log_file = tmp_path / "app.log"
    log_file.write_text("diagnostic log\n", encoding="utf-8")
    monkeypatch.setenv("DIAGNOSTIC_TEST_SETTING", "original")
    app.dependency_overrides[get_logs_path] = lambda: log_file
    try:
        # Avoid starting MongoDB and the outbound service-token refresh loop.
        client = TestClient(app)
        response = client.get("/system/logs")
        assert response.status_code == 200
        assert response.text == "diagnostic log\n"
        response = client.get("/system/env")
        assert response.status_code == 200
        assert response.json()["DIAGNOSTIC_TEST_SETTING"] == "original"
        response = client.get("/system/env/DIAGNOSTIC_TEST_SETTING")
        assert response.status_code == 200
        assert response.json()["value"] == "original"

        assert client.patch(
            "/system/env", json={"DIAGNOSTIC_TEST_SETTING": "changed"}
        ).status_code in {401, 403}
        assert client.put(
            "/system/env/DIAGNOSTIC_TEST_SETTING", json={"value": "changed"}
        ).status_code in {401, 403}
        assert (
            client.get("/system/env/DIAGNOSTIC_TEST_SETTING").json()["value"]
            == "original"
        )
    finally:
        app.dependency_overrides.pop(get_logs_path, None)
