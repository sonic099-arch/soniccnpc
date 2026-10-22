from collections import Counter,defaultdict
from datetime import datetime,timezone,timedelta
from uuid import uuid4,UUID
import pandas as pd
from sqlalchemy import select,func,text,or_
from sqlalchemy.dialects.postgresql import insert
from app.analysis.engine import AnomalyRuleEngine
from app.analysis.types import WellContext,PARAMETERS,ENGINE_VERSION,clean
from app.models.entities import (Well,WellConfigHistory,WellTool,WellMeasureEvent,WellOperationEvent,WellFaultHistory,
                                WellMeasurement,WellBaseline,AnalysisRun,WellAnalysisResult,WellStatusSnapshot,WellAnomaly)
from app.services.rules import selected_rules

STATUSES=['可信正常','疑似异常','措施影响','数据待核实','工况待核实']

class AnalysisFailed(Exception):
    def __init__(self,run_id):
        self.run_id=run_id
        super().__init__(f'分析任务失败，未更新最新状态；任务ID：{run_id}')


def event_records(session,model,well_ids,start,end,cutoff):
    groups=defaultdict(list)
    query=select(model).where(model.well_id.in_(well_ids),model.effective_start<end,
                              or_(model.effective_end.is_(None),model.effective_end>start),model.created_at<=cutoff).order_by(model.well_id,model.effective_start,model.id)
    for row in session.scalars(query):
        record={'id':str(row.id),'effective_start':row.effective_start,'effective_end':row.effective_end}
        if model is WellConfigHistory:
            record.update(production_mode=row.production_mode,configuration={k:v for k,v in row.configuration.items() if k=='cycle'})
        elif model is WellTool:record.update(tool_type=row.tool_type,depth_m=row.depth_m)
        elif model is WellMeasureEvent:record.update(measure_type=row.measure_type)
        elif model is WellOperationEvent:record.update(operation_type=row.operation_type,planned=row.planned)
        else:record.update(fault_type=row.fault_type,confirmed=row.confirmed)
        groups[row.well_id].append(record)
    return groups


def execute_analysis(session,options):
    # 同步任务避免并发快照竞态；不等待另一个长任务，明确告知稍后重试。
    if not session.scalar(select(text('pg_try_advisory_xact_lock(1862400301)'))):raise ValueError('已有分析任务运行中，请稍后重试')
    rules=selected_rules(session)
    engine=AnomalyRuleEngine(rules);policy=engine.configs['SYS001']
    cutoff=datetime.now(timezone.utc)
    scope=select(Well).where(Well.created_at<=cutoff).order_by(Well.well_number)
    if options.well_ids is not None:scope=scope.where(Well.id.in_(options.well_ids))
    if options.area is not None:scope=scope.where(Well.area==options.area)
    wells=list(session.scalars(scope))
    if not wells:raise ValueError('没有符合条件的气井，请先加载或导入数据')
    if options.well_ids is not None and options.area is None and len(wells)!=len(set(options.well_ids)):
        raise ValueError('部分气井ID不存在，请检查分析范围')
    well_ids=[w.id for w in wells]
    latest=session.scalar(select(func.max(WellMeasurement.measured_at)).where(WellMeasurement.well_id.in_(well_ids),WellMeasurement.created_at<=cutoff))
    end=options.window_end or (latest+timedelta(minutes=policy['sample_minutes']) if latest else cutoff)
    end=end.astimezone(timezone.utc)
    start=(options.window_start or end-timedelta(hours=policy['lookback_hours'])).astimezone(timezone.utc)
    if not start<end or (end-start).total_seconds()/3600>policy['max_window_hours']:
        raise ValueError('分析时间窗口无效或超过策略允许范围')
    snapshot=clean([{'id':str(r.id),'code':r.code,'name':r.name,'version':r.version,'function_key':r.function_key,
                    'configuration':r.configuration,'applicable_states':r.applicable_states,'input_parameters':r.input_parameters,'enabled':r.enabled} for r in rules])
    run=AnalysisRun(id=uuid4(),window_start=start,window_end=end,data_cutoff=cutoff,status='运行中',rule_snapshot=snapshot,
                     summary={'engine_version':ENGINE_VERSION,'total_wells':len(wells),'reference':'指定数据窗口' if options.window_end else '以选定井最新采样为窗口终点，不表示当前实时状态'})
    session.add(run);session.flush()
    run_id=run.id
    try:
        contexts=[event_records(session,model,well_ids,start,end,cutoff) for model in (WellConfigHistory,WellTool,WellMeasureEvent,WellOperationEvent,WellFaultHistory)]
        query=select(WellMeasurement.id.label('measurement_id'),WellMeasurement.well_id,WellMeasurement.measured_at,
                     *(getattr(WellMeasurement,k) for k in PARAMETERS),WellMeasurement.quality_flags).where(WellMeasurement.well_id.in_(well_ids),
                     WellMeasurement.measured_at>=start,WellMeasurement.measured_at<end,WellMeasurement.created_at<=cutoff).order_by(WellMeasurement.well_id,WellMeasurement.measured_at)
        frame=pd.DataFrame(session.execute(query).mappings(),columns=['measurement_id','well_id','measured_at',*PARAMETERS,'quality_flags'])
        frame['measurement_id']=frame.measurement_id.astype(str)
        frames={key:group.drop(columns=['well_id']).reset_index(drop=True) for key,group in frame.groupby('well_id',sort=False)}
        empty=frame.drop(columns=['well_id']).iloc[:0]
        results,baselines,anomalies,snapshots=[],[],[],[]
        counts=Counter();by_code=Counter();run_lookup={r.code:r for r in rules}
        for well in wells:
            ctx=WellContext(str(well.id),well.well_number,frames.get(well.id,empty),start,end,cutoff,
                            *(group.get(well.id,[]) for group in contexts),is_demo=well.is_demo)
            output=engine.analyze(ctx)
            counts[output['screening_status']]+=1
            payload=dict(id=uuid4(),well_id=well.id,analysis_run_id=run_id,as_of=end,
                         screening_status=output['screening_status'],production_state=output['production_state'],evidence=clean(output['evidence']))
            results.append(payload);snapshots.append({**payload,'id':uuid4()})
            baseline=output['baseline']
            if baseline.valid:
                baselines.append(dict(id=uuid4(),well_id=well.id,analysis_run_id=run_id,window_start=baseline.start,window_end=baseline.end,
                                      production_mode=output['production_mode'],algorithm_version=ENGINE_VERSION,
                                      statistics=baseline.statistics,sample_count=baseline.sample_count))
            for event in output['events']:
                by_code[event['code']]+=1
                rule=run_lookup[event['code']]
                anomalies.append(dict(id=uuid4(),well_id=well.id,analysis_run_id=run_id,rule_id=rule.id,
                    anomaly_type=event['anomaly_type'],severity=event['severity'],started_at=event['started_at'],ended_at=event['ended_at'],
                    evidence=clean(event['evidence']),rule_snapshot=next(r for r in snapshot if r['code']==event['code']),fingerprint=event['fingerprint']))
        for model,rows in ((WellAnalysisResult,results),(WellBaseline,baselines),(WellAnomaly,anomalies)):
            for offset in range(0,len(rows),250):session.execute(insert(model),rows[offset:offset+250])
        for offset in range(0,len(snapshots),250):
            statement=insert(WellStatusSnapshot).values(snapshots[offset:offset+250])
            statement=statement.on_conflict_do_update(constraint='uq_snapshot_well',
                set_={k:getattr(statement.excluded,k) for k in ('analysis_run_id','as_of','screening_status','production_state','evidence')},
                where=statement.excluded.as_of>=WellStatusSnapshot.as_of)
            session.execute(statement)
        run.status='已完成';run.completed_at=datetime.now(timezone.utc)
        run.summary={**run.summary,'status_counts':{s:counts[s] for s in STATUSES},'anomaly_events':len(anomalies),
                     'rules_triggered':dict(by_code),'baseline_count':len(baselines),'is_demo':all(w.is_demo for w in wells),
                     'warning':'模拟筛查结果不代表现场准确率；积液、冻堵仅辅助提示，所有异常需人工复核。'}
        session.commit();session.refresh(run)
        return run
    except Exception as exc:
        session.rollback()
        # 独立事务保留失败记录；不发布一半结果，也不泄露SQL或数据库凭据。
        failed=AnalysisRun(id=run_id,window_start=start,window_end=end,data_cutoff=cutoff,status='失败',rule_snapshot=snapshot,
                           completed_at=datetime.now(timezone.utc),summary={'engine_version':ENGINE_VERSION,'failure_type':type(exc).__name__},
                           error_message='计算或写入失败，已回滚本次结果；请检查服务日志与输入配置')
        session.add(failed);session.commit()
        import logging
        logging.getLogger(__name__).error('分析任务失败 %s，异常类型 %s',run_id,type(exc).__name__)
        raise AnalysisFailed(str(run_id)) from exc
