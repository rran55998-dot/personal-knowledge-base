from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture()
def client(tmp_path, monkeypatch):
    import app.config as config
    import app.db as db
    import app.services.document_service as document_service_module
    import app.services.vector_store as vector_store_module

    data_dir = tmp_path / "data"
    upload_dir = data_dir / "uploads"
    vector_dir = data_dir / "vectors"
    db_path = data_dir / "test.db"
    data_dir.mkdir(parents=True, exist_ok=True)
    upload_dir.mkdir(parents=True, exist_ok=True)
    vector_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(config, "DATA_DIR", data_dir)
    monkeypatch.setattr(config, "UPLOAD_DIR", upload_dir)
    monkeypatch.setattr(config, "VECTOR_DIR", vector_dir)
    monkeypatch.setattr(config, "DB_PATH", db_path)
    monkeypatch.setattr(db, "DB_PATH", db_path)
    monkeypatch.setattr(document_service_module, "UPLOAD_DIR", upload_dir)

    config.get_settings.cache_clear()
    vector_store_module.reset_vector_store()

    from app.main import app

    db.init_db()
    with TestClient(app) as test_client:
        yield test_client

    config.get_settings.cache_clear()
    vector_store_module.reset_vector_store()
