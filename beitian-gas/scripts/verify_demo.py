"""独立全量验收，不连接.env数据库。生成/加载600井并验证整批Excel幂等。"""
import argparse
import json
import os
from pathlib import Path
import shutil
import tempfile
import time
from alembic import command
from alembic.config import Config
from pgserver import get_server
from sqlalchemy import create_engine, select, func, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.data_sources.mock import MockDataSource
from app.models.entities import Well, WellMeasurement, WellConfigHistory, WellTool, WellMeasureEvent, WellOperationEvent
from app.services.demo import load_dataset, workbook_bytes
from app.services.imports import stage_upload, confirm_import


def verify(workbook, report):
    root = Path(__file__).resolve().parents[1]
    started = time.monotonic()
    temp = Path(tempfile.mkdtemp(prefix="beitian-demo-verify-"))
    server = get_server(temp/"cluster", cleanup_mode="delete")
    url = make_url(server.get_uri()).set(drivername="postgresql+psycopg")
    os.environ["DATABASE_URL"] = url.render_as_string(hide_password=False)
    os.environ["IMPORT_STORAGE_DIR"] = str(temp/"imports")
    get_settings.cache_clear()
    from app.api.imports import ImportConfirmation
    config = Config(str(root/"backend/alembic.ini"))
    config.set_main_option("script_location", str(root/"backend/migrations"))
    engine = create_engine(url)
    result = {"checks": []}
    try:
        command.upgrade(config,"head")
        with Session(engine) as session:
            result["database"] = session.scalar(text("SELECT version()"))
            dataset = MockDataSource().generate()
            loaded = load_dataset(session,dataset)
            assert loaded["well_count"] == 600 and loaded["measurement_count"] == 201324
            result["checks"].append({"check":"600井全量入库","pass":True,"details":loaded})
            assert load_dataset(session,dataset)["already_loaded"]
            result["checks"].append({"check":"模拟批次重复加载","pass":True})
            payload = workbook.read_bytes() if workbook else workbook_bytes(dataset)
            job = stage_upload(session,payload,"600井演示.xlsx")
            preview = job.mapping["preview"]
            options = ImportConfirmation(confirmed=True,mapping=preview["suggested_mapping"],units=preview["suggested_units"])
            imported = confirm_import(session,job,options)
            assert imported.failed_rows == 0, imported.errors[:3]
            assert imported.duplicate_rows == 201324 and imported.success_rows == 0
            result["checks"].append({"check":"600井Excel全量重复导入","pass":True,"total_rows":imported.total_rows,"duplicates":imported.duplicate_rows,"inserted":imported.success_rows,"errors":imported.failed_rows})
            models = [Well,WellMeasurement,WellConfigHistory,WellTool,WellMeasureEvent,WellOperationEvent]
            counts = {m.__tablename__:session.scalar(select(func.count()).select_from(m)) for m in models}
            assert counts["wells"] == 600 and counts["well_measurements"] == 201324
            result["checks"].append({"check":"全量记录及事件数量核对","pass":True,"counts":counts})
        result["elapsed_seconds"] = round(time.monotonic()-started,2)
        report.parent.mkdir(parents=True,exist_ok=True)
        report.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
        print(json.dumps(result,ensure_ascii=False,indent=2))
    finally:
        engine.dispose()
        server.cleanup()
        shutil.rmtree(temp,ignore_errors=True)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workbook",type=Path,help="可选，使用已生成的默认600井14天xlsx")
    parser.add_argument("--report",type=Path,default=Path("work/task2-full-check.json"))
    args=parser.parse_args()
    verify(args.workbook,args.report)
