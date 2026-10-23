"""任务4只读展示接口；报表按一次完成任务取值，不混合不同时间窗的快照。"""
from datetime import datetime, timedelta, timezone
from typing import Annotated, Literal
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import AwareDatetime
from sqlalchemy import select, func, and_, or_, exists, cast
from sqlalchemy.dialects.postgresql import JSONB
from app.api.crud import SessionDep
from app.models.entities import (Well, AnalysisRun, WellAnalysisResult, WellAnomaly,
                                WellMeasurement, WellMeasureEvent, WellOperationEvent)
from app.analysis.types import PARAMETERS, clean
from app.services.analysis import STATUSES
from app.api.analysis import run_response

router = APIRouter(prefix='/api/v1/screening', tags=['筛查展示'])
Status = Literal['可信正常', '疑似异常', '措施影响', '数据待核实', '工况待核实', '未分析']


def completed_runs():
    return select(AnalysisRun).where(AnalysisRun.status == '已完成',
        cast(AnalysisRun.summary, JSONB).has_key('engine_version'))


def resolve_run(session, run_id):
    if run_id:
        run = session.scalar(completed_runs().where(AnalysisRun.id == run_id))
        if not run:
            raise HTTPException(404, '已完成的引擎分析任务不存在')
        return run
    return session.scalar(completed_runs().order_by(AnalysisRun.completed_at.desc(), AnalysisRun.created_at.desc(), AnalysisRun.id.desc()).limit(1))


class Filters:
    def __init__(self, run_id: UUID | None = None, search: str | None = Query(None, max_length=80),
                 area: str | None = Query(None, max_length=80), screening_status: Status | None = None,
                 anomaly_type: str | None = Query(None, max_length=60),
                 event_start: AwareDatetime | None = None, event_end: AwareDatetime | None = None):
        if event_start and event_end and event_start >= event_end:
            raise HTTPException(422, '事件时间结束必须晚于开始')
        self.run_id, self.search, self.area = run_id, search, area
        self.status, self.anomaly_type = screening_status, anomaly_type
        self.start, self.end = event_start, event_end

FilterDep = Annotated[Filters, Depends()]


def event_conditions(f, run):
    conditions = [WellAnomaly.analysis_run_id == (run.id if run else None)]
    if f.anomaly_type:
        conditions.append(WellAnomaly.anomaly_type == f.anomaly_type)
    if f.start:
        conditions.append(or_(WellAnomaly.ended_at.is_(None), WellAnomaly.ended_at > f.start))
    if f.end:
        conditions.append(WellAnomaly.started_at < f.end)
    return conditions


def well_query(f, run):
    query = select(Well.id.label('well_id'), Well.well_number, Well.area, Well.is_demo,
                   WellAnalysisResult.id.label('result_id'), WellAnalysisResult.production_state,
                   func.coalesce(WellAnalysisResult.screening_status, '未分析').label('screening_status'),
                   WellAnalysisResult.as_of).outerjoin(WellAnalysisResult, and_(
                       WellAnalysisResult.well_id == Well.id,
                       WellAnalysisResult.analysis_run_id == (run.id if run else None)))
    if f.search:
        query = query.where(Well.well_number.contains(f.search, autoescape=True))
    if f.area:
        query = query.where(Well.area == f.area)
    if f.status == '未分析':
        query = query.where(WellAnalysisResult.id.is_(None))
    elif f.status:
        query = query.where(WellAnalysisResult.screening_status == f.status)
    if f.anomaly_type or f.start or f.end:
        query = query.where(exists(select(WellAnomaly.id).where(
            WellAnomaly.well_id == Well.id, *event_conditions(f, run))))
    return query


def paged(session, query, offset, limit):
    total = session.scalar(select(func.count()).select_from(query.order_by(None).subquery()))
    items = [dict(row) for row in session.execute(query.offset(offset).limit(limit)).mappings()]
    return clean({'items': items, 'total': total, 'offset': offset, 'limit': limit})


@router.get('/options', summary='工区、近期完成任务及所选任务的事件类型')
def options(session: SessionDep, run_id: UUID | None = None):
    run = resolve_run(session, run_id)
    runs = list(session.scalars(completed_runs().order_by(AnalysisRun.completed_at.desc(), AnalysisRun.created_at.desc(), AnalysisRun.id.desc()).limit(100)))
    if run and run.id not in {r.id for r in runs}:
        runs.insert(0, run)
    types = list(session.scalars(select(WellAnomaly.anomaly_type).where(
        WellAnomaly.analysis_run_id == (run.id if run else None)).distinct().order_by(WellAnomaly.anomaly_type)))
    return clean({'areas': list(session.scalars(select(Well.area).distinct().order_by(Well.area))),
        'runs': [run_response(r) for r in runs], 'selected_run': run_response(run) if run else None,
        'anomaly_types': types, 'statuses': [*STATUSES, '未分析']})


@router.get('/dashboard', summary='一次分析任务的真实筛查统计，包含未分析井')
def dashboard(session: SessionDep, filters: FilterDep):
    run = resolve_run(session, filters.run_id)
    scope = well_query(filters, run).subquery()
    counts = {s: 0 for s in [*STATUSES, '未分析']}
    counts.update(dict(session.execute(select(scope.c.screening_status, func.count()).group_by(scope.c.screening_status)).all()))
    areas = [dict(row) for row in session.execute(select(scope.c.area, scope.c.screening_status,
        func.count().label('count')).group_by(scope.c.area, scope.c.screening_status).order_by(scope.c.area)).mappings()]
    total = sum(counts.values())
    return clean({'run': run_response(run) if run else None, 'total_wells': total,
        'analyzed_wells': total - counts['未分析'], 'status_counts': counts, 'areas': areas,
        'demo_wells': session.scalar(select(func.count()).select_from(scope).where(scope.c.is_demo.is_(True))),
        'reference': '按所选分析任务展示；未参与本次任务的登记井单列未分析，历史结果不代表当前实时井况'})


@router.get('/wells', summary='登记气井与所选任务筛查状态，按井分页')
def wells(session: SessionDep, filters: FilterDep, non_normal: bool = False,
          offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=500)):
    run = resolve_run(session, filters.run_id)
    query = well_query(filters, run)
    if non_normal:
        query = query.where(or_(WellAnalysisResult.id.is_(None), WellAnalysisResult.screening_status != '可信正常'))
    page = paged(session, query.order_by(Well.well_number, Well.id), offset, limit)
    # 仅为本页查询事件，避免每行独立访问数据库，也不返回大的证据JSON。
    ids = [UUID(row['well_id']) if isinstance(row['well_id'], str) else row['well_id'] for row in page['items']]
    types = {}
    if ids and run:
        for well_id, kind in session.execute(select(WellAnomaly.well_id, WellAnomaly.anomaly_type).where(
            WellAnomaly.well_id.in_(ids), *event_conditions(filters, run)).distinct()):
            types.setdefault(str(well_id), []).append(kind)
    for row in page['items']:
        row['anomaly_types'] = sorted(types.get(str(row['well_id']), []))
    return {**page, 'run': run_response(run) if run else None}


@router.get('/anomalies', summary='所选任务事件分页，默认不包含可信正常井')
def anomalies(session: SessionDep, filters: FilterDep,
              offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=500)):
    run = resolve_run(session, filters.run_id)
    scope = well_query(filters, run).subquery()
    query = select(WellAnomaly.id, WellAnomaly.well_id, scope.c.well_number, scope.c.area,
        scope.c.screening_status, WellAnomaly.anomaly_type, WellAnomaly.started_at,
        WellAnomaly.ended_at, WellAnomaly.severity, WellAnomaly.rule_snapshot,
        WellAnomaly.analysis_run_id).join(scope, scope.c.well_id == WellAnomaly.well_id).where(
            *event_conditions(filters, run), scope.c.screening_status != '可信正常')
    page = paged(session, query.order_by(WellAnomaly.started_at.desc(), WellAnomaly.id), offset, limit)
    for row in page['items']:
        snapshot = row.pop('rule_snapshot')
        row.update(rule_code=snapshot.get('code'), rule_version=snapshot.get('version'))
    return {**page, 'run': run_response(run) if run else None}


@router.get('/wells/{well_id}', summary='单井基本信息与所选任务的全部规则结果')
def well_detail(well_id: UUID, session: SessionDep, run_id: UUID | None = None):
    well = session.get(Well, well_id)
    if not well:
        raise HTTPException(404, '气井不存在')
    run = resolve_run(session, run_id)
    result = session.scalar(select(WellAnalysisResult).where(WellAnalysisResult.well_id == well_id,
        WellAnalysisResult.analysis_run_id == (run.id if run else None)))
    latest = session.scalar(select(func.max(WellMeasurement.measured_at)).where(WellMeasurement.well_id == well_id))
    return clean({'well': {'id': str(well.id), 'well_number': well.well_number, 'name': well.name,
        'area': well.area, 'is_demo': well.is_demo, 'description': well.description},
        'run': run_response(run) if run else None, 'latest_measurement_at': latest,
        'result': {'id': str(result.id), 'screening_status': result.screening_status,
            'production_state': result.production_state, 'as_of': result.as_of, 'evidence': result.evidence} if result else None})


@router.get('/wells/{well_id}/series', summary='单井七参数原始曲线及措施、操作、异常时间标记')
def series(well_id: UUID, session: SessionDep, run_id: UUID | None = None,
           window_start: AwareDatetime | None = None, window_end: AwareDatetime | None = None):
    well = session.get(Well, well_id)
    if not well:
        raise HTTPException(404, '气井不存在')
    run = resolve_run(session, run_id)
    latest = session.scalar(select(func.max(WellMeasurement.measured_at)).where(WellMeasurement.well_id == well_id))
    sample_minutes = next((r['configuration']['sample_minutes'] for r in (run.rule_snapshot if run else []) if r.get('code') == 'SYS001'), None)
    end = window_end or (run.window_end if run else (latest + timedelta(microseconds=1) if latest else datetime.now(timezone.utc)))
    start = window_start or (run.window_start if run else end - timedelta(days=14))
    if start >= end or end - start > timedelta(days=90):
        raise HTTPException(422, '曲线窗口须为开始早于结束，且不超过90天')
    conditions = [WellMeasurement.well_id == well_id, WellMeasurement.measured_at >= start, WellMeasurement.measured_at < end]
    total = session.scalar(select(func.count()).select_from(WellMeasurement).where(*conditions))
    if total > 20000:
        raise HTTPException(422, '该窗口超过20000个原始采样，请缩短时间范围以保留原始曲线')
    rows = [dict(r) for r in session.execute(select(WellMeasurement.id.label('measurement_id'),
        WellMeasurement.measured_at, *(getattr(WellMeasurement, p) for p in PARAMETERS),
        WellMeasurement.quality_flags, WellMeasurement.is_demo).where(*conditions).order_by(WellMeasurement.measured_at)).mappings()]
    def events(model):
        return session.scalars(select(model).where(model.well_id == well_id, model.effective_start < end,
            or_(model.effective_end.is_(None), model.effective_end > start)).order_by(model.effective_start, model.id))
    measures = [{'id': str(e.id), 'measure_type': e.measure_type, 'effective_start': e.effective_start,
                 'effective_end': e.effective_end, 'notes': e.notes} for e in events(WellMeasureEvent)]
    operations = [{'id': str(e.id), 'operation_type': e.operation_type, 'planned': e.planned,
                   'effective_start': e.effective_start, 'effective_end': e.effective_end} for e in events(WellOperationEvent)]
    anomalies = [{'id': str(e.id), 'anomaly_type': e.anomaly_type, 'started_at': e.started_at, 'ended_at': e.ended_at,
                  'rule_code': e.rule_snapshot.get('code'), 'rule_version': e.rule_snapshot.get('version')} for e in session.scalars(
        select(WellAnomaly).where(WellAnomaly.well_id == well_id, WellAnomaly.analysis_run_id == (run.id if run else None),
            WellAnomaly.started_at < end, or_(WellAnomaly.ended_at.is_(None), WellAnomaly.ended_at > start)).order_by(WellAnomaly.started_at, WellAnomaly.id))]
    return clean({'well_id': str(well_id), 'window_start': start, 'window_end': end,
        'sample_minutes': sample_minutes, 'total': total, 'measurements': rows, 'measures': measures,
        'operations': operations, 'anomalies': anomalies,
        'contains_demo': well.is_demo or any(r['is_demo'] for r in rows),
        'source_note': '曲线为当前库保存的原始采样，规则证据为分析时快照；未插值、未平滑，空值与采样缺口断线'})
