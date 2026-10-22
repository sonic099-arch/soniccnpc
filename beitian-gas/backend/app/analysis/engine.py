"""只消费标准动态参数和生产上下文，不读取模拟场景或预期标签。"""
from dataclasses import asdict
from datetime import timedelta,timezone
from hashlib import sha256
import json
import numpy as np
import pandas as pd
from app.analysis.config import DEFINITIONS,validate_rule
from app.analysis.types import RuleResult,PARAMETERS,ENGINE_VERSION,clean,points
from app.analysis.operation import OperationStateResolver
from app.analysis.quality import DataQualityAnalyzer
from app.analysis.baseline import BaselineCalculator
from app.analysis.trends import FlowTrendAnalyzer,PressureTrendAnalyzer,TemperatureTrendAnalyzer
from app.analysis.measures import MeasureEffectAnalyzer
from app.analysis.aggregate import AnomalyAggregator,WellStatusClassifier

class AnomalyRuleEngine:
    def __init__(self,rules):
        self.rules={rule.code:rule for rule in rules}
        if set(DEFINITIONS)-self.rules.keys():raise ValueError('规则不完整，请先初始化全部规则')
        self.configs={code:validate_rule(rule) for code,rule in self.rules.items()}
        if not self.rules['SYS001'].enabled:raise ValueError('工况与基线策略必须启用')

    def applies(self,code,mode):
        rule=self.rules[code]
        return bool(rule.enabled and ('全部' in rule.applicable_states or mode in rule.applicable_states))

    def analyze(self,ctx):
        for attr in ('start','end','data_cutoff'):
            value=getattr(ctx,attr)
            if value.tzinfo is None:raise ValueError('分析时间必须包含时区')
            setattr(ctx,attr,value.astimezone(timezone.utc))
        for records in (ctx.configurations,ctx.tools,ctx.measures,ctx.operations,ctx.faults):
            for record in records:
                for key in ('effective_start','effective_end'):
                    if record.get(key) is not None:record[key]=record[key].astimezone(timezone.utc)
        frame=ctx.frame.copy()
        if 'quality_flags' not in frame:frame['quality_flags']=[[] for _ in range(len(frame))]
        for column in PARAMETERS:
            frame[column]=pd.to_numeric(frame[column],errors='coerce') if column in frame else np.nan
        if 'measured_at' not in frame:frame['measured_at']=pd.NaT
        frame['measured_at']=pd.to_datetime(frame.measured_at,utc=True,errors='coerce')
        ctx.frame=frame.sort_values('measured_at',kind='stable').reset_index(drop=True)
        policy=self.configs['SYS001']
        state=OperationStateResolver().resolve(ctx,policy,self.configs['OP001'],self.configs['ME001']['recovery_hours'])
        unknown_measures=[e.get('id') for e in ctx.measures if e['measure_type'] not in policy['known_measures'] and (e.get('effective_end') is None or e['effective_end']>=ctx.end-timedelta(hours=self.configs['ME002']['effect_horizon_hours']))]
        if unknown_measures:
            state.known=False;state.context_metrics['reasons'].append('近期存在未识别的排采措施')
            state.context_metrics['unknown_measure_ids']=unknown_measures
        quality=DataQualityAnalyzer().analyze(ctx,policy,self.configs['DQ001'],self.configs['DQ002'],self.configs['DQ003'])
        quality_trusted=all(self.applies(code,state.mode) for code in ('DQ001','DQ002','DQ003')) and not any(r.events for r in quality)
        baseline=BaselineCalculator().calculate(ctx,state,policy)
        system=RuleResult('SYS001',metrics={'context':state.context_metrics,'baseline':baseline.statistics})
        if not state.known or not baseline.valid:
            system.event('工况或基线待核实',ctx.start,ctx.end,'verify_state',
                         {'context':state.context_metrics,'baseline':baseline.statistics})
        if not quality_trusted or not state.known:
            state.result.events=[];state.result.outcome='数据不足';state.result.coverage=False
            state.result.message='数据或工况不可信，不自动判断非计划停井'
        eligible=ctx.frame.loc[(ctx.frame.measured_at>=ctx.end-timedelta(hours=policy['evaluation_hours']))&~state.planned_mask&~state.measure_mask]
        period,effect=MeasureEffectAnalyzer().analyze(ctx,state,policy,self.configs['ME001'],self.configs['ME002'])
        if quality_trusted and state.known and baseline.valid:
            flow=FlowTrendAnalyzer().analyze(ctx,eligible,baseline,policy,self.configs['FL001'],self.configs['DQ001']['max_gap_hours'])
            pressure,linked=PressureTrendAnalyzer().analyze(ctx,eligible,baseline,policy,self.configs['PR001'],self.configs['PR002'])
            temperature=TemperatureTrendAnalyzer().analyze(ctx,eligible,baseline,policy,self.configs['TP001'],self.configs['DQ001']['max_gap_hours'])
        else:
            flow,pressure,linked,temperature=[RuleResult(code,'数据不足','数据、工况或基线不足，未执行生产异常判断',coverage=False) for code in ('FL001','PR001','PR002','TP001')]
            effect=RuleResult('ME002','数据不足','数据或工况不可信，不直接判断措施失败',coverage=False)
        results=[system,*quality,state.result,flow,pressure,linked,temperature,period,effect]
        for result in results:
            if not self.applies(result.code,state.mode):
                result.events=[];result.coverage=False
                result.outcome='已禁用' if not self.rules[result.code].enabled else '不适用'
                result.message='规则已禁用或当前生产方式不在适用范围，不能据此排除异常'
        uncovered=[r.code for r in results if not r.coverage]
        if uncovered:
            action='verify_data' if any(c in uncovered for c in ('DQ001','DQ002','DQ003')) else 'verify_state'
            system.event('规则覆盖不足',ctx.start,ctx.end,action,{'uncovered_rule_codes':uncovered,'reason':'未执行或不适用的规则不能视为通过'})
        if baseline.valid and baseline.statistics['use_trend_prediction'] and state.production_state=='正常生产' and policy['natural_decline_label_daily']<baseline.statistics['natural_decline_daily']<=policy['max_natural_decline_daily']:
            state.production_state='自然递减生产'
        status,production=WellStatusClassifier().classify(state,baseline,results)
        digest_frame=ctx.frame[[c for c in ['measurement_id','measured_at',*PARAMETERS,'quality_flags'] if c in ctx.frame]]
        # 上下文已在接入层去除演示标签，只保留可解释的生产配置与时间区间。
        context_snapshot=clean({'configurations':ctx.configurations,'tools':ctx.tools,'measures':ctx.measures,'operations':ctx.operations,'faults':ctx.faults})
        digest=sha256(json.dumps(clean({'rows':digest_frame.to_dict('records'),'context':context_snapshot}),sort_keys=True,ensure_ascii=False,allow_nan=False).encode()).hexdigest()
        events=AnomalyAggregator().aggregate(ctx.well_id,results,self.rules,policy['merge_gap_hours'])
        provenance=clean({'engine_version':ENGINE_VERSION,'input_digest':digest,'well_id':ctx.well_id,'well_number':ctx.well_number,
                          'window_start':ctx.start,'window_end':ctx.end,'data_cutoff':ctx.data_cutoff,
                          'sample_count':len(ctx.frame),'context':context_snapshot,'baseline':baseline.statistics,
                          'is_demo':ctx.is_demo,'requires_manual_review':status!='可信正常'})
        for event in events:
            event['evidence']={**event['evidence'],'provenance':provenance,'recent_points':points(ctx.frame.tail(int(np.ceil(policy['evaluation_hours']*60/policy['sample_minutes']))))}
        evaluations=[]
        for result in results:
            rule=self.rules[result.code]
            evaluations.append(clean({'code':result.code,'name':rule.name,'version':rule.version,'outcome':result.outcome,
                                      'message':result.message,'coverage':result.coverage,'metrics':result.metrics,'event_count':len(result.events)}))
        return {'screening_status':status,'production_state':production,'production_mode':state.mode,'events':events,'baseline':baseline,
                'evidence':{**provenance,'rule_results':evaluations},'rule_results':evaluations}
