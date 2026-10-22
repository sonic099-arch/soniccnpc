"""仅使用临时目录内独立 PostgreSQL 集群；不读取真实生产数据库。"""
import os
from pathlib import Path
import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from pgserver import get_server

os.environ["DATABASE_URL"] = "postgresql+psycopg:///beitian_test_unused"
from app.core.config import get_settings
from app.core.database import get_session
from app.main import app

@pytest.fixture(scope="session")
def migrated_database(tmp_path_factory):
    directory = tmp_path_factory.mktemp("isolated_pg")
    server = get_server(directory / "cluster", cleanup_mode="delete")
    url = make_url(server.get_uri()).set(drivername="postgresql+psycopg")
    previous = os.environ["DATABASE_URL"]
    os.environ["DATABASE_URL"] = url.render_as_string(hide_password=False)
    get_settings.cache_clear()
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    config.set_main_option("script_location", str(Path(__file__).parents[1] / "migrations"))
    command.upgrade(config, "head")
    engine = create_engine(url)
    yield engine, config
    engine.dispose()
    command.downgrade(config, "base")
    os.environ["DATABASE_URL"] = previous
    get_settings.cache_clear()

@pytest.fixture
def engine(migrated_database):
    return migrated_database[0]

@pytest.fixture
def session(engine):
    with engine.connect() as connection:
        transaction = connection.begin()
        with Session(bind=connection, join_transaction_mode="create_savepoint") as db:
            yield db
        transaction.rollback()

@pytest.fixture
def client(session, engine, monkeypatch):
    app.dependency_overrides[get_session] = lambda: session
    monkeypatch.setattr("app.main.get_engine", lambda: engine)
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()

T0 = "2026-01-01T00:00:00Z"
T1 = "2026-01-02T00:00:00Z"

@pytest.fixture
def records(client):
    cache = {}
    def payload(slug):
        def id_of(name):
            return create(name)["id"]
        if slug == "wells":
            return {"well_number": "演示-001", "area": "演示工区"}
        if slug == "rules":
            return {"code": "DEMO-R001", "name": "演示规则", "version": "1.0", "function_key": "demo_rule"}
        if slug == "analysis-runs":
            return {"window_start": T0, "window_end": T1}
        if slug == "import-jobs":
            return {"source_type": "excel", "filename": "演示.xlsx"}
        if slug == "reviews":
            return {"anomaly_id": id_of("anomalies"), "reviewer": "测试人员", "decision": "待核实", "comment": "演示复核", "reviewed_at": T1}
        data = {"well_id": id_of("wells")}
        if slug in {"well-configs", "well-tools", "measure-events", "operation-events", "fault-histories"}:
            data.update(effective_start=T0, effective_end=T1)
        data.update({
            "well-configs": {"production_mode": "自喷"},
            "well-tools": {"tool_type": "柱塞", "tool_name": "演示工具", "depth_m": 1000},
            "measurements": {"measured_at": T0, "instantaneous_flow_m3_h": 100.0, "import_job_id": id_of("import-jobs") if slug == "measurements" else None},
            "measure-events": {"measure_type": "泡排", "parameters": {"演示": True}},
            "operation-events": {"operation_type": "关井", "planned": True},
            "fault-histories": {"fault_type": "演示故障"},
            "baselines": {"window_start": T0, "window_end": T1, "production_mode": "自喷", "algorithm_version": "demo-v1", "statistics": {"flow_mean":100}, "sample_count": 24},
            "anomalies": {"analysis_run_id": id_of("analysis-runs") if slug == "anomalies" else None,
                          "rule_id": id_of("rules") if slug == "anomalies" else None,
                          "anomaly_type": "演示提示", "started_at": T0, "evidence": {"value": 100, "unit": "m³/h", "note": "仅为追溯测试"},
                          "rule_snapshot": {"code": "DEMO-R001", "version": "1.0"}, "fingerprint": "demo-event"},
            "status-snapshots": {"analysis_run_id": id_of("analysis-runs") if slug == "status-snapshots" else None, "as_of": T1},
        }[slug])
        return data
    def create(slug):
        if slug not in cache:
            response = client.post("/api/v1/" + slug, json=payload(slug))
            assert response.status_code == 201, response.text
            cache[slug] = response.json()
        return cache[slug]
    return create, payload
