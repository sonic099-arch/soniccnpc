from datetime import datetime
from typing import Annotated,Literal
from uuid import UUID
from fastapi import APIRouter,Depends,HTTPException,Query
from pydantic import BaseModel,ConfigDict,Field,AwareDatetime,model_validator,ValidationError
from sqlalchemy import select,func,and_
from sqlalchemy.exc import IntegrityError
from app.api.crud import SessionDep
from app.core.database import get_analysis_session
from sqlalchemy.orm import Session
from app.models.entities import AnalysisRule,AnalysisRun,WellAnalysisResult,WellStatusSnapshot,WellAnomaly,Well,AnomalyReview
from app.services.rules import bootstrap_rules,selected_rules,rule_payload,publish_version
from app.services.analysis import execute_analysis,AnalysisFailed
from app.analysis.types import clean

router=APIRouter(prefix='/api/v1/analysis',tags=['分析引擎'])
AnalysisSession=Annotated[Session,Depends(get_analysis_session)]

class Confirmation(BaseModel):
    model_config=ConfigDict(extra='forbid')
    confirmed:Literal[True]

class AnalysisRequest(Confirmation):
    well_ids:list[UUID]|None=Field(default=None,min_length=1,max_length=5000)
    area:str|None=Field(default=None,min_length=1,max_length=80)
    window_start:AwareDatetime|None=None
    window_end:AwareDatetime|None=None

    @model_validator(mode='after')
    def valid_window(self):
        if self.window_start and self.window_end and self.window_start>=self.window_end:raise ValueError('结束必须晚于开始')
        return self

class RuleVersionRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    version:str=Field(pattern=r'^\d+\.\d+\.\d+$',max_length=30)
    configuration:dict
    applicable_states:list[str]=Field(default=['全部'],min_length=1)
    enabled:bool=True


def run_response(run):
    return clean({'id':str(run.id),'status':run.status,'window_start':run.window_start,'window_end':run.window_end,
                  'data_cutoff':run.data_cutoff,'completed_at':run.completed_at,'summary':run.summary,
                  'error_message':run.error_message,'rule_snapshot':run.rule_snapshot})

@router.post('/rules/bootstrap',summary='显式初始化演示规则，不覆盖已有配置')
def bootstrap(options:Confirmation,session:SessionDep):
    return bootstrap_rules(session)

@router.get('/rules',summary='查看当前规则、配置约束和版本')
def rules(session:SessionDep):
    try:return {'items':[rule_payload(r) for r in selected_rules(session)]}
    except ValueError as exc:
        session.rollback();raise HTTPException(409,str(exc))

@router.post('/rules/{code}/versions',status_code=201,summary='发布新规则版本并保留旧版审计')
def version(code:str,options:RuleVersionRequest,session:SessionDep):
    try:return rule_payload(publish_version(session,code,options))
    except (ValueError,ValidationError) as exc:
        session.rollback();raise HTTPException(422,'规则配置无效，请检查版本、完整配置项、数值范围和适用工况')
    except IntegrityError:
        session.rollback();raise HTTPException(409,'规则版本冲突，请刷新后重试')

@router.post('/execute',status_code=201,summary='执行分析；省略时间时以最新数据为参考')
def execute(options:AnalysisRequest,session:AnalysisSession):
    try:return run_response(execute_analysis(session,options))
    except ValueError as exc:
        session.rollback();raise HTTPException(409,str(exc))
    except AnalysisFailed as exc:
        raise HTTPException(500,str(exc))

@router.get('/runs',summary='分页查看分析任务')
def runs(session:SessionDep,offset:int=Query(0,ge=0),limit:int=Query(20,ge=1,le=100)):
    query=select(AnalysisRun).order_by(AnalysisRun.created_at.desc(),AnalysisRun.id.desc())
    return {'items':[run_response(r) for r in session.scalars(query.offset(offset).limit(limit))],
            'total':session.scalar(select(func.count()).select_from(AnalysisRun)),'offset':offset,'limit':limit}

@router.get('/runs/{run_id}',summary='查看任务及其规则快照')
def get_run(run_id:UUID,session:SessionDep):
    run=session.get(AnalysisRun,run_id)
    if not run:raise HTTPException(404,'分析任务不存在')
    return run_response(run)

@router.get('/results',summary='查询逐井筛查结果；默认最新，支持历史任务')
def results(session:SessionDep,run_id:UUID|None=None,well_id:UUID|None=None,screening_status:str|None=None,
            search:str|None=None,area:str|None=None,offset:int=Query(0,ge=0),limit:int=Query(50,ge=1,le=500)):
    query=select(WellAnalysisResult,Well.well_number,Well.area).join(Well,Well.id==WellAnalysisResult.well_id)
    if run_id:query=query.where(WellAnalysisResult.analysis_run_id==run_id)
    else:query=query.join(WellStatusSnapshot,and_(WellStatusSnapshot.well_id==WellAnalysisResult.well_id,WellStatusSnapshot.analysis_run_id==WellAnalysisResult.analysis_run_id))
    if well_id:query=query.where(Well.id==well_id)
    if screening_status:query=query.where(WellAnalysisResult.screening_status==screening_status)
    if search:query=query.where(Well.well_number.contains(search,autoescape=True))
    if area:query=query.where(Well.area==area)
    total=session.scalar(select(func.count()).select_from(query.subquery()))
    items=[{'id':str(r.id),'well_id':str(r.well_id),'well_number':number,'area':a,'analysis_run_id':str(r.analysis_run_id),
             'screening_status':r.screening_status,'production_state':r.production_state,'as_of':r.as_of} for r,number,a in session.execute(query.order_by(Well.well_number).offset(offset).limit(limit))]
    return clean({'items':items,'total':total,'offset':offset,'limit':limit})

@router.get('/results/{result_id}',summary='追溯单井所有规则结果、上下文及证据')
def result_detail(result_id:UUID,session:SessionDep):
    row=session.get(WellAnalysisResult,result_id)
    if not row:raise HTTPException(404,'单井分析结果不存在')
    return clean({'id':str(row.id),'well_id':str(row.well_id),'analysis_run_id':str(row.analysis_run_id),
                  'screening_status':row.screening_status,'production_state':row.production_state,'evidence':row.evidence})

@router.get('/anomalies',summary='异常及待核实事件列表，默认排除可信正常井并去除旧任务重复')
def anomalies(session:SessionDep,run_id:UUID|None=None,well_id:UUID|None=None,anomaly_type:str|None=None,
              search:str|None=None,area:str|None=None,offset:int=Query(0,ge=0),limit:int=Query(50,ge=1,le=500)):
    query=select(WellAnomaly,Well.well_number,Well.area,WellAnalysisResult.screening_status).join(Well,Well.id==WellAnomaly.well_id).join(WellAnalysisResult,and_(WellAnalysisResult.well_id==WellAnomaly.well_id,WellAnalysisResult.analysis_run_id==WellAnomaly.analysis_run_id)).where(WellAnalysisResult.screening_status!='可信正常')
    if run_id:query=query.where(WellAnomaly.analysis_run_id==run_id)
    else:query=query.join(WellStatusSnapshot,and_(WellStatusSnapshot.well_id==WellAnomaly.well_id,WellStatusSnapshot.analysis_run_id==WellAnomaly.analysis_run_id))
    if well_id:query=query.where(Well.id==well_id)
    if anomaly_type:query=query.where(WellAnomaly.anomaly_type==anomaly_type)
    if search:query=query.where(Well.well_number.contains(search,autoescape=True))
    if area:query=query.where(Well.area==area)
    total=session.scalar(select(func.count()).select_from(query.subquery()))
    rows=session.execute(query.order_by(WellAnomaly.started_at.desc(),WellAnomaly.id).offset(offset).limit(limit))
    return clean({'items':[{'id':str(r.id),'well_id':str(r.well_id),'well_number':number,'area':a,'screening_status':s,
                 'anomaly_type':r.anomaly_type,'started_at':r.started_at,'ended_at':r.ended_at,'severity':r.severity,
                 'rule_code':r.rule_snapshot.get('code'),'rule_version':r.rule_snapshot.get('version'),'fingerprint':r.fingerprint,
                 'analysis_run_id':str(r.analysis_run_id)} for r,number,a,s in rows], 'total':total,'offset':offset,'limit':limit})

@router.get('/anomalies/{anomaly_id}',summary='查看异常原始证据、规则快照和跨任务复核记录')
def anomaly_detail(anomaly_id:UUID,session:SessionDep):
    row=session.get(WellAnomaly,anomaly_id)
    if not row:raise HTTPException(404,'异常事件不存在')
    versions=select(WellAnomaly.id).where(WellAnomaly.fingerprint==row.fingerprint,WellAnomaly.well_id==row.well_id)
    reviews=session.scalars(select(AnomalyReview).where(AnomalyReview.anomaly_id.in_(versions)).order_by(AnomalyReview.reviewed_at))
    return clean({'id':str(row.id),'well_id':str(row.well_id),'analysis_run_id':str(row.analysis_run_id),'anomaly_type':row.anomaly_type,
        'evidence':row.evidence,'rule_snapshot':row.rule_snapshot,'fingerprint':row.fingerprint,
        'reviews':[{'id':str(r.id),'anomaly_id':str(r.anomaly_id),'reviewer':r.reviewer,'decision':r.decision,'comment':r.comment,'reviewed_at':r.reviewed_at} for r in reviews]})
