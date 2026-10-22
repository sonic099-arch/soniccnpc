from datetime import timedelta
import numpy as np
from app.analysis.types import RuleResult,PRESSURES,intervals,points,clean

class FlowTrendAnalyzer:
    def analyze(self,ctx,frame,baseline,policy,config,gap_hours):
        result=RuleResult('FL001')
        if frame.empty:
            result.outcome='不适用';result.message='近期处于已知计划停井或措施影响区间';return result
        predicted=baseline.expected_flow(frame.measured_at)
        ratios=frame.instantaneous_flow_m3_h.to_numpy()/predicted
        decline=1-ratios
        result.metrics=clean(dict(observed_flow_m3_h=float(frame.instantaneous_flow_m3_h.median()),
                         predicted_flow_m3_h=float(np.median(predicted)),median_ratio=float(np.median(ratios)),
                         baseline_daily_decline=baseline.statistics['natural_decline_daily']))
        mask=decline>=config['decline_ratio']
        for start,end in intervals(frame,mask,policy['sample_minutes'],gap_hours):
            if (end-start).total_seconds()/3600>=config['sustain_hours']:
                rows=frame.loc[(frame.measured_at>=start)&(frame.measured_at<end)]
                result.event('持续减产',start,end,'abnormal',{**result.metrics,'threshold_decline_ratio':config['decline_ratio'],
                             'sustain_hours':(end-start).total_seconds()/3600,'points':points(rows)})
        if baseline.statistics['natural_decline_daily']>policy['max_natural_decline_daily']:
            result.event('基线期间快速下降',baseline.start,baseline.end,'abnormal',
                         {**result.metrics,'allowed_daily_decline':policy['max_natural_decline_daily']})
        return result

class PressureTrendAnalyzer:
    def analyze(self,ctx,frame,baseline,policy,config,correlation):
        pressure=RuleResult('PR001');linked=RuleResult('PR002')
        if frame.empty:
            for result in [pressure,linked]:
                result.outcome='不适用';result.message='已知计划或措施区间不直接作生产故障判断'
            return [pressure,linked]
        changes={}
        for column in PRESSURES:
            interval=frame.measured_at.diff().dt.total_seconds()/3600
            steps=frame[column].diff().abs().where(interval<=config['max_step_interval_hours'])
            changes[column]={'largest_step_mpa':float(steps.max()) if steps.notna().any() else 0,
                             'range_mpa':float(frame[column].max()-frame[column].min())}
            mask=steps>config['step_mpa']
            if mask.any():
                pos=int(np.flatnonzero(mask.to_numpy())[0]);row=frame.iloc[pos]
                pressure.event('压力突变',row.measured_at,min(ctx.end,row.measured_at+timedelta(minutes=policy['sample_minutes'])),
                               'abnormal',{'parameter':column,'observed_step_mpa':changes[column]['largest_step_mpa'],
                               'threshold_mpa':config['step_mpa'],'points':points(frame.iloc[max(0,pos-1):pos+1])})
            elif changes[column]['range_mpa']>config['range_mpa']:
                pressure.event('压力异常波动',frame.measured_at.iloc[0],ctx.end,'abnormal',
                               {'parameter':column,'observed_range_mpa':changes[column]['range_mpa'],'threshold_mpa':config['range_mpa'],'points':points(frame)})
        pressure.metrics=changes
        medians=baseline.statistics['medians']
        q_ratio=float(np.median(frame.instantaneous_flow_m3_h.to_numpy()/baseline.expected_flow(frame.measured_at)))
        gap=float((frame.casing_pressure_mpa-frame.tubing_pressure_mpa).median())
        growth=gap-(medians['casing_pressure_mpa']-medians['tubing_pressure_mpa'])
        oil_change=float(frame.tubing_pressure_mpa.median()-medians['tubing_pressure_mpa'])
        liquid_growth=float(frame.liquid_rate_m3_d.median()-medians['liquid_rate_m3_d']) if frame.liquid_rate_m3_d.notna().any() and medians['liquid_rate_m3_d'] is not None else None
        linked.metrics=clean(dict(flow_ratio=q_ratio,gap_growth_mpa=growth,oil_pressure_change_mpa=oil_change,liquid_growth_m3_d=liquid_growth))
        if q_ratio<correlation['flow_ratio']:
            linked.metrics['observed_tags']=['压力流量关联异常'] if growth>correlation['gap_growth_mpa'] or abs(oil_change)>correlation['pressure_change_mpa'] else []
            if growth>correlation['gap_growth_mpa']:
                kind='疑似积液辅助提示' if liquid_growth is not None and liquid_growth>correlation['liquid_growth_m3_d'] else '压力流量关联异常'
                linked.event(kind,frame.measured_at.iloc[0],ctx.end,'abnormal',
                             {**linked.metrics,'diagnosis':False,'requires_manual_review':True,'explanation':'仅记录减产、压差及产液关联，不能据此确诊积液','points':points(frame)})
            elif abs(oil_change)>correlation['pressure_change_mpa']:
                linked.event('压力流量关联异常',frame.measured_at.iloc[0],ctx.end,'abnormal',
                             {**linked.metrics,'diagnosis':False,'requires_manual_review':True,'points':points(frame)})
        return [pressure,linked]

class TemperatureTrendAnalyzer:
    def analyze(self,ctx,frame,baseline,policy,config,gap_hours):
        result=RuleResult('TP001')
        if frame.empty:
            result.outcome='不适用';result.message='近期处于计划或措施影响区间';return result
        medians=baseline.statistics['medians']
        q_ratio=frame.instantaneous_flow_m3_h.to_numpy()/baseline.expected_flow(frame.measured_at)
        cooling=medians['gas_temperature_c']-frame.gas_temperature_c
        upstream=frame.tubing_pressure_mpa-medians['tubing_pressure_mpa']
        mask=(frame.gas_temperature_c<config['low_temperature_c'])&(cooling>config['temperature_drop_c'])&(q_ratio<config['flow_ratio'])&(upstream>config['pressure_growth_mpa'])
        result.metrics=clean(dict(minimum_temperature_c=float(frame.gas_temperature_c.min()),baseline_temperature_c=medians['gas_temperature_c'],
                                 maximum_drop_c=float(cooling.max()),associated_samples=int(mask.sum())))
        for start,end in intervals(frame,mask,policy['sample_minutes'],gap_hours):
            if (end-start).total_seconds()/3600>=config['sustain_hours']:
                result.metrics['observed_tags']=['低温及压力流量关联异常']
                result.event('疑似冻堵辅助提示',start,end,'abnormal',
                             {**result.metrics,'diagnosis':False,'requires_manual_review':True,
                              'explanation':'低温、减产和上游压力变化关联，仅供人工进一步核查','points':points(frame.loc[mask])})
        if not result.events:
            changed=(cooling>config['temperature_drop_c'])|(-cooling>config['temperature_rise_c'])
            for start,end in intervals(frame,changed,policy['sample_minutes'],gap_hours):
                if (end-start).total_seconds()/3600>=config['sustain_hours']:
                    result.event('温度变化待核实',start,end,'verify_state',
                                 {**result.metrics,'diagnosis':False,'explanation':'温差异常但缺少冻堵关联证据，不作确诊','points':points(frame.loc[changed])})
        return result
