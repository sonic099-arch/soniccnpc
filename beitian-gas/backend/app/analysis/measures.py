from datetime import timedelta
from app.analysis.types import RuleResult,points,clean

class MeasureEffectAnalyzer:
    def analyze(self,ctx,state,policy,period_config,effect_config):
        period=RuleResult('ME001');effect=RuleResult('ME002')
        period.metrics={'active_measure_ids':[e.get('id') for e in state.active_measures],
                        'affected_samples':int(state.measure_mask.sum()),'recovery_hours':period_config['recovery_hours']}
        for event in state.active_measures:
            period.event('措施影响',event['effective_start'],min(ctx.end,(event.get('effective_end') or ctx.end)+timedelta(hours=period_config['recovery_hours'])),
                         'measure',{'measure_id':event.get('id'),'measure_type':event['measure_type'],
                         'effective_start':event['effective_start'],'effective_end':event.get('effective_end'),
                         'explanation':'措施及恢复期间的合理波动不直接判为故障'},severity='提示')
        evaluated=[]
        for event in ctx.measures:
            end=event.get('effective_end')
            if not end or end>=ctx.end:continue
            age=(ctx.end-end).total_seconds()/3600
            if age>effect_config['effect_horizon_hours'] or age<effect_config['post_hours']:continue
            before=ctx.frame.loc[(ctx.frame.measured_at>=event['effective_start']-timedelta(hours=effect_config['pre_hours']))&(ctx.frame.measured_at<event['effective_start'])]
            after_start=max(end+timedelta(hours=period_config['recovery_hours']),ctx.end-timedelta(hours=effect_config['post_hours']))
            after=ctx.frame.loc[(ctx.frame.measured_at>=after_start)&(ctx.frame.measured_at<ctx.end)]
            before=before.loc[before.instantaneous_flow_m3_h>policy['zero_flow']]
            after=after.loc[after.instantaneous_flow_m3_h.notna()]
            if len(before)<effect_config['minimum_post_samples'] or len(after)<effect_config['minimum_post_samples']:
                effect.outcome='数据不足';effect.coverage=False;effect.message='措施前后有效样本不足，效果待核实';continue
            pre=float(before.instantaneous_flow_m3_h.median());post=float(after.instantaneous_flow_m3_h.median());ratio=post/pre
            metrics=clean(dict(measure_id=event.get('id'),measure_type=event['measure_type'],pre_flow_m3_h=pre,post_flow_m3_h=post,
                               recovery_ratio=ratio,required_ratio=effect_config['recovery_ratio'],pre_samples=len(before),post_samples=len(after)))
            evaluated.append(metrics)
            if ratio<effect_config['recovery_ratio']:
                effect.event('措施后未恢复',after.measured_at.iloc[0],ctx.end,'abnormal',
                             {**metrics,'effective_start':event['effective_start'],'effective_end':end,'before_points':points(before),'after_points':points(after)})
        effect.metrics={'evaluated_measures':evaluated}
        if not evaluated and effect.outcome=='通过':
            effect.outcome='不适用';effect.message='没有处于当前效果评估窗口的已结束措施'
        return [period,effect]
