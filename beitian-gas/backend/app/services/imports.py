"""已确认Excel导入服务。数据库唯一键负责最终幂等，冲突值不覆盖历史。"""
from datetime import datetime, timezone
from hashlib import sha256
from io import BytesIO
import json
import math
from pathlib import Path
from uuid import uuid4
from openpyxl import Workbook
from sqlalchemy import select, tuple_
from sqlalchemy.dialects.postgresql import insert
from app.core.config import get_settings
from app.data_sources.excel import ExcelDataSource, FIELDS, cell_json
from app.data_sources.mock import PARAMETERS
from app.models.entities import DataImportJob, Well, WellMeasurement


def staged_path(job_id):
    return get_settings().import_storage_dir / (str(job_id) + ".xlsx")


def stage_upload(session, data, filename, sheet=None):
    preview = ExcelDataSource(data, sheet=sheet).preview()
    job = DataImportJob(id=uuid4(), source_type="excel", filename=Path(filename).name[:255],
                        file_sha256=sha256(data).hexdigest(), status="待确认",
                        total_rows=preview["total_rows"], mapping={"preview": preview})
    path = staged_path(job.id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    try:
        session.add(job)
        session.commit()
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return job


def same_values(row, values):
    for key in PARAMETERS:
        left, right = getattr(row, key), values.get(key)
        if left is None or right is None:
            if left is not None or right is not None: return False
        elif not math.isclose(left, right, rel_tol=1e-10, abs_tol=1e-9): return False
    return True


def confirm_import(session, job, options):
    if job.status in ("已完成", "部分失败", "失败"):
        return job
    if job.status != "待确认" or job.source_type != "excel": raise ValueError("该任务不能执行Excel导入确认")
    path = staged_path(job.id)
    if not path.exists(): raise ValueError("暂存文件不存在，请重新上传")
    data = path.read_bytes()
    if sha256(data).hexdigest() != job.file_sha256: raise ValueError("文件校验失败，请重新上传")
    source = ExcelDataSource(data, mapping=options.mapping, units=options.units,
                              timezone_name=options.timezone, sheet=job.mapping["preview"]["sheet"], is_demo=options.is_demo)
    iterator = source.rows()
    _, meta = next(iterator)
    source.validate_mapping(meta["headers"])
    job.mapping = {**job.mapping, "confirmed": True, "fields": options.mapping, "units": options.units,
                   "timezone": options.timezone, "is_demo": options.is_demo,
                   "create_missing_wells": options.create_missing_wells, "default_area": options.default_area}
    job.status = "导入中"
    errors, success, duplicates, total = [], 0, 0, 0
    # 首次查井，后续只缓存已遇到的井号，避免逐条访问数据库。
    well_cache = {w.well_number: w for w in session.scalars(select(Well))}
    seen, batch = {}, []

    def failure(rowno, reason, raw):
        errors.append({"row": rowno, "reason": reason, "values": {k: cell_json(v) for k,v in raw.items()}})

    def flush_batch():
        nonlocal success, duplicates
        if not batch: return
        values = [item[1] for item in batch]
        stmt = insert(WellMeasurement).values(values).on_conflict_do_nothing(constraint="uq_measurement_well_time")
        inserted = set(session.execute(stmt.returning(WellMeasurement.well_id, WellMeasurement.measured_at)).all())
        conflicts = [(v["well_id"], v["measured_at"]) for v in values if (v["well_id"], v["measured_at"]) not in inserted]
        existing = {}
        if conflicts:
            existing = {(r.well_id,r.measured_at):r for r in session.scalars(select(WellMeasurement).where(tuple_(WellMeasurement.well_id,WellMeasurement.measured_at).in_(conflicts)))}
        for rowno, value, raw in batch:
            key = value["well_id"], value["measured_at"]
            if key in inserted:
                success += 1
            elif same_values(existing[key], value):
                duplicates += 1
            else:
                failure(rowno, "同井同时间已有不同数值，未覆盖原记录", raw)
        batch.clear()

    for rowno, raw in iterator:
        total += 1
        try:
            record, flags = source.parse_row(raw)
            well = well_cache.get(record.well_number)
            if well is None:
                if not options.create_missing_wells: raise ValueError("井号不存在，请先建井或显式允许创建新井")
                well = Well(id=uuid4(), well_number=record.well_number, area=options.default_area,
                            is_demo=options.is_demo, description="Excel映射确认后创建")
                # 并发导入同一新井时依井号唯一键合并，保留首次创建的信息。
                result = session.execute(insert(Well).values(id=well.id,well_number=well.well_number,area=well.area,is_demo=well.is_demo,description=well.description).on_conflict_do_nothing(index_elements=[Well.well_number]).returning(Well.id)).scalar_one_or_none()
                well = session.get(Well, result) if result else session.scalar(select(Well).where(Well.well_number==record.well_number))
                well_cache[record.well_number] = well
            value = record.model_dump(exclude={"well_number"})
            value.update(id=uuid4(), well_id=well.id, quality_flags=flags, source_type="excel", import_job_id=job.id)
            key = well.id, record.measured_at
            signature = tuple(value.get(k) for k in PARAMETERS)
            if key in seen:
                if seen[key] == signature: duplicates += 1
                else: failure(rowno, "文件内同井同时间数值冲突，保留第一条有效记录", raw)
                continue
            seen[key] = signature
            batch.append((rowno, value, raw))
            if len(batch) >= 500: flush_batch()
        except ValueError as exc:
            failure(rowno, str(exc), raw)
    flush_batch()
    job.total_rows, job.success_rows, job.failed_rows, job.duplicate_rows = total, success, len(errors), duplicates
    job.errors = errors
    job.status = "部分失败" if errors and success+duplicates else "失败" if errors else "已完成"
    job.completed_at = datetime.now(timezone.utc)
    session.commit()
    session.refresh(job)
    return job


def build_report(job):
    book = Workbook()
    summary = book.active; summary.title = "导入结果"
    for row in [("任务ID",str(job.id)),("文件名",job.filename),("状态",job.status),("总行数",job.total_rows),
                ("成功",job.success_rows),("失败",job.failed_rows),("重复",job.duplicate_rows)]: summary.append(row)
    sheet = book.create_sheet("错误行")
    sheet.append(["Excel行号", "错误原因", "原始数据（JSON，按文本保存）"])
    for error in job.errors:
        sheet.append([error["row"], error["reason"], json.dumps(error["values"], ensure_ascii=False)])
    # 用户输入始终作为文本写入，避免报告中的字符串成为Excel公式。
    for ws in book:
        for row in ws:
            for cell in row:
                if isinstance(cell.value, str): cell.data_type = "s"
        ws.freeze_panes = "A2"
        ws.column_dimensions["A"].width = 36
        ws.column_dimensions["B"].width = 60
        ws.column_dimensions["C"].width = 100
    output = BytesIO(); book.save(output)
    return output.getvalue()
