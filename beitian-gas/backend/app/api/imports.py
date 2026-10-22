from datetime import datetime, timezone
from io import BytesIO
from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field, AwareDatetime, field_validator
from sqlalchemy import select
from app.api.crud import SessionDep
from app.data_sources.excel import FIELDS, ALLOWED_UNITS, MAX_UPLOAD
from app.data_sources.mock import MockDataSource, SCENARIOS, DISCLAIMER
from app.models.entities import DataImportJob
from app.services.imports import stage_upload, confirm_import, build_report
from app.services.demo import template_bytes, load_dataset

router = APIRouter(prefix="/api/v1", tags=["数据接入"])

class ImportConfirmation(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    confirmed: Literal[True]
    mapping: dict[str, str]
    units: dict[str, str]
    timezone: str = "Asia/Shanghai"
    is_demo: bool = True
    create_missing_wells: bool = False
    default_area: str = Field(default="演示导入工区", min_length=1, max_length=80)

    @field_validator("timezone")
    @classmethod
    def valid_zone(cls, value):
        try: ZoneInfo(value)
        except (ZoneInfoNotFoundError,ValueError) as exc: raise ValueError("无效时区") from exc
        return value

class DemoRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    confirmed: Literal[True]
    count: int = Field(default=1000, ge=13, le=1000)
    days: int = Field(default=14, ge=4, le=31)
    seed: int = Field(default=20261021, ge=0, le=2**32-1)
    start: AwareDatetime = datetime(2026,10,1,tzinfo=timezone.utc)


class ImportJobResponse(BaseModel):
    id: UUID
    filename: str | None
    status: str
    total_rows: int
    success_rows: int
    failed_rows: int
    duplicate_rows: int
    errors: list[dict]
    error_count: int
    mapping: dict
    file_sha256: str | None
    report_url: str


def job_response(job, include_errors=True):
    return {"id":str(job.id),"filename":job.filename,"status":job.status,"total_rows":job.total_rows,
            "success_rows":job.success_rows,"failed_rows":job.failed_rows,"duplicate_rows":job.duplicate_rows,
            "errors":job.errors[:100] if include_errors else [],"error_count":len(job.errors),
            "mapping":job.mapping,"file_sha256":job.file_sha256,
            "report_url":f"/api/v1/excel/jobs/{job.id}/report"}

@router.get("/excel/fields", summary="获取标准字段及支持单位")
def fields():
    return [{"key":k,"label":v[0],"unit":v[1],"allowed_units":ALLOWED_UNITS.get(k,[]),"required":k in ("well_number","measured_at")} for k,v in FIELDS.items()]

@router.get("/excel/template", summary="下载标准Excel模板或演示样例")
def template(example: bool = False):
    return Response(template_bytes(example), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition":f'attachment; filename="beitian-{"example" if example else "template"}.xlsx"'})

@router.post("/excel/preview", response_model=ImportJobResponse, status_code=201, summary="上传并识别字段（不导入数据）")
def preview(session: SessionDep, file: UploadFile=File(...), sheet: str | None=Form(None)):
    try:
        if not file.filename or not file.filename.lower().endswith(".xlsx"): raise ValueError("只支持xlsx文件")
        data = file.file.read(MAX_UPLOAD+1)
        job = stage_upload(session,data,file.filename,sheet)
        return job_response(job)
    except ValueError as exc:
        session.rollback()
        raise HTTPException(422,str(exc))
    finally:
        file.file.close()

@router.post("/excel/jobs/{job_id}/confirm", response_model=ImportJobResponse, summary="确认字段映射和单位后执行幂等导入")
def confirm(job_id: UUID, options: ImportConfirmation, session: SessionDep):
    # 同一个任务的重复点击串行处理；已完成任务直接返回原报告。
    job = session.scalar(select(DataImportJob).where(DataImportJob.id==job_id).with_for_update())
    if job is None: raise HTTPException(404,"导入任务不存在")
    try:
        return job_response(confirm_import(session,job,options))
    except ValueError as exc:
        session.rollback()
        raise HTTPException(422,str(exc))

@router.get("/excel/jobs/{job_id}", response_model=ImportJobResponse, summary="查询导入结果和前100条错误")
def get_job(job_id: UUID, session: SessionDep):
    job = session.get(DataImportJob,job_id)
    if job is None: raise HTTPException(404,"导入任务不存在")
    return job_response(job)

@router.get("/excel/jobs/{job_id}/report", summary="下载完整导入结果及错误行报告")
def report(job_id: UUID, session: SessionDep):
    job=session.get(DataImportJob,job_id)
    if job is None: raise HTTPException(404,"导入任务不存在")
    return Response(build_report(job),media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition":f'attachment; filename="import-report-{job.id}.xlsx"'})

@router.get("/demo/scenarios", summary="获取演示场景的预期状态和标签")
def scenarios():
    return {"warning":DISCLAIMER,"scenarios":[dict(code=c,name=n,production_state=s,screening_status=t,expected_labels=labels) for c,n,s,t,labels in SCENARIOS]}

@router.post("/demo/generate", status_code=201, summary="显式生成并加载演示井及措施、配置、测量记录")
def generate(options: DemoRequest, session: SessionDep):
    try:
        result=load_dataset(session,MockDataSource(options.count,options.days,options.seed,options.start).generate())
        return {**result,"warning":DISCLAIMER}
    except ValueError as exc:
        session.rollback()
        raise HTTPException(409,str(exc))
