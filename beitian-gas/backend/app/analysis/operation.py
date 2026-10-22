from datetime import timedelta
import numpy as np
import pandas as pd
from app.analysis.types import OperationState,RuleResult,active_at,clean

class OperationStateResolver:
    def resolve(self,ctx,policy,operation_config,recovery_hours):
        frame=ctx.frame;times=pd.DatetimeIndex(frame.measured_at)
        moment=ctx.end-timedelta(microseconds=1)
        configs=[c for c in ctx.configurations if active_at(c,moment)]
        known=len(configs)==1
        config=configs[0] if known else None
        mode=config.get('production_mode') if config else None
        reasons=[]
        if not known: reasons.append('当前生产配置缺失或有效区间冲突')
        if mode not in policy['valid_modes']:
            known=False;reasons.append('生产方式未受当前策略覆盖')
        active_tools=[t for t in ctx.tools if active_at(t,moment)]
        if any(t['tool_type'] not in policy['known_tools'] for t in active_tools):
            known=False;reasons.append('存在未识别的井筒工具')
        planned=np.zeros(len(frame),dtype=bool)
        for op in ctx.operations:
            if op.get('planned'):
                end=op.get('effective_end') or ctx.end
                if op['operation_type']=='关井': planned|=(times>=op['effective_start'])&(times<end)
                guard=timedelta(hours=policy['transition_guard_hours'])
                planned|=(times>=op['effective_start']-guard)&(times<op['effective_start']+guard)
                if op.get('effective_end'):
                    planned|=(times>=end-guard)&(times<end+guard)
        cycle_closed=False
        if mode=='间歇':
            cycle=(config.get('configuration') or {}).get('cycle',{})
            try:
                period=float(cycle['period_hours']);opened=float(cycle['open_hours']);anchor=pd.Timestamp(cycle['anchor'])
                if not np.isfinite([opened,period]).all() or not 0<opened<period or anchor.tzinfo is None: raise ValueError()
                phases=((times-anchor).total_seconds()/3600)%period
                planned|=np.asarray(phases>=opened)
                cycle_closed=((pd.Timestamp(moment)-anchor).total_seconds()/3600)%period>=opened
            except (KeyError,ValueError,TypeError):
                known=False;reasons.append('周期计划缺失或无法解释')
        affected=np.zeros(len(frame),dtype=bool)
        active=[]
        for event in ctx.measures:
            end=(event.get('effective_end') or ctx.end)+timedelta(hours=recovery_hours)
            affected|=(times>=event['effective_start'])&(times<end)
            if event['effective_start']<=moment<end: active.append(event)
        if any(e['measure_type'] not in policy['known_measures'] for e in active):
            known=False;reasons.append('存在未识别的有效排采措施')
        operations=[e for e in ctx.operations if active_at(e,moment)]
        if len(operations)>1:
            known=False;reasons.append('有效开关井操作区间冲突')
        reported=operations[0] if len(operations)==1 else None
        tail=frame.loc[frame.measured_at>=ctx.end-timedelta(hours=operation_config['stopped_hours'])]
        required=int(np.ceil(operation_config['stopped_hours']*60/policy['sample_minutes']))
        trustworthy_flow=not tail.empty and tail.instantaneous_flow_m3_h.notna().all()
        stopped=trustworthy_flow and len(tail)>=required and bool((tail.instantaneous_flow_m3_h<=policy['zero_flow']).all())
        state='正常生产'
        result=RuleResult('OP001')
        if active:
            state='泡排措施期间' if any(e['measure_type']=='泡排' for e in active) else '措施期间'
        elif mode=='间歇' and known:
            state='按计划周期生产'
            if cycle_closed and trustworthy_flow and not stopped:
                known=False;reasons.append('周期关井计划与实际流量不一致')
            if not cycle_closed and stopped:
                result.event('非计划停井',tail.measured_at.iloc[0],ctx.end,'abnormal',{'reason':'周期计划应开井，但持续近零流量','points':[]})
                state='非计划关井'
        elif reported and reported['operation_type']=='关井' and reported['planned']:
            state='计划关井'
            if trustworthy_flow and not stopped:
                known=False;reasons.append('计划关井记录与实际流量不一致')
        elif stopped:
            state='非计划关井'
            result.event('非计划停井',tail.measured_at.iloc[0],ctx.end,'abnormal',{'reason':'持续近零流量且无有效计划关井记录','operation_id':reported.get('id') if reported else None})
        elif reported and reported['operation_type'] not in ('开井','关井'):
            known=False;reasons.append('开关井操作类型无法解释')
        if reported and reported['operation_type']=='开井' and stopped and not active:
            state='非计划关井'
        faults=[f for f in ctx.faults if active_at(f,moment)]
        if faults:
            known=False;reasons.append('存在未闭环的历史故障记录，需要人工核实')
        metrics=clean({'production_mode':mode,'config_id':config.get('id') if config else None,
                      'active_tool_ids':[t.get('id') for t in active_tools],'active_measure_ids':[e.get('id') for e in active],
                      'active_operation_ids':[e.get('id') for e in operations],'active_fault_ids':[f.get('id') for f in faults],
                      'reasons':reasons,'stopped':stopped,'planned_samples':int(planned.sum()),'measure_affected_samples':int(affected.sum())})
        result.metrics=metrics
        return OperationState(known,mode,state,planned,affected,config,active,result,metrics)
