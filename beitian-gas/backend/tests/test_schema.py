from datetime import datetime, timezone, timedelta
import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from alembic import command
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError
from app.models.base import Base
from app.data_sources.base import DatabaseDataSource, MeasurementRecord


def test_migration_model_no_drift(engine):
    with engine.connect() as conn:
        assert compare_metadata(MigrationContext.configure(conn, opts={"compare_type":True}), Base.metadata) == []
    assert len(inspect(engine).get_table_names()) == 16  # 15实体 + alembic_version


def test_migration_upgrade_downgrade_roundtrip(migrated_database):
    engine, config = migrated_database
    # 数据库为专用临时集群；所有API用例均由外层事务回滚。
    command.downgrade(config, "base")
    assert inspect(engine).get_table_names() == ["alembic_version"]
    command.upgrade(config, "head")
    assert len(inspect(engine).get_table_names()) == 16


def test_actual_postgresql(engine):
    assert engine.dialect.name == "postgresql"
    with engine.connect() as conn:
        assert "PostgreSQL" in conn.scalar(text("select version()"))


def test_database_constraint_without_api(session):
    with pytest.raises(IntegrityError):
        with session.begin_nested():
            session.execute(text("INSERT INTO wells (id, well_number, area, is_demo) VALUES ('00000000-0000-0000-0000-000000000001', ' ', '演示', true)"))


def test_database_source_stub_half_open_interval():
    start = datetime(2026,1,1,tzinfo=timezone.utc)
    end = start + timedelta(days=1)
    a = MeasurementRecord(well_number="演示-001", measured_at=start)
    b = MeasurementRecord(well_number="演示-001", measured_at=end)
    assert list(DatabaseDataSource((a,b)).read_measurements(start,end)) == [a]
