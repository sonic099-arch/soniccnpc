"""历史分析和已使用规则只追加版本，不通过基础CRUD改写。"""
from sqlalchemy import select,cast
from sqlalchemy.dialects.postgresql import JSONB
from fastapi import HTTPException
from app.models.entities import AnalysisRule,AnalysisRun,WellAnomaly,WellBaseline,WellStatusSnapshot,AnomalyReview

def protect_update(session,row,fields=None,deleting=False):
    if not deleting:
        protect_create(session,type(row),fields or {})
    if isinstance(row,AnalysisRule):
        used=session.scalar(select(AnalysisRun.id).where(cast(AnalysisRun.rule_snapshot,JSONB).contains([{'id':str(row.id)}])).limit(1))
        if used and (deleting or set(fields or {})-{'enabled'}):
            raise HTTPException(409,'已参与分析的规则不可改写或删除，请发布新版本')
        return
    if isinstance(row,AnalysisRun):run=row
    elif isinstance(row,(WellAnomaly,WellBaseline,WellStatusSnapshot)):
        run=session.get(AnalysisRun,row.analysis_run_id) if row.analysis_run_id else None
    elif isinstance(row,AnomalyReview):
        anomaly=session.get(WellAnomaly,row.anomaly_id)
        run=session.get(AnalysisRun,anomaly.analysis_run_id) if anomaly else None
    else:return
    if run and run.summary.get('engine_version'):
        raise HTTPException(409,'引擎生成的历史结果和复核记录不可改写或删除；请重新分析或追加复核记录')


def protect_create(session,model,values):
    if model is AnalysisRun and values.get('summary',{}).get('engine_version'):
        raise HTTPException(409,'引擎任务标识由分析接口生成，不能通过基础接口伪造')
    if model in (WellAnomaly,WellBaseline,WellStatusSnapshot) and values.get('analysis_run_id'):
        run=session.get(AnalysisRun,values['analysis_run_id'])
        if run and run.summary.get('engine_version'):
            raise HTTPException(409,'引擎任务的结果由引擎统一写入，不能通过基础接口追加')
