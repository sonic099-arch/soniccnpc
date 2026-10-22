from datetime import timedelta
import numpy as np
import pandas as pd
from app.analysis.types import RuleResult,PARAMETERS,recent_frame,points,clean

class DataQualityAnalyzer:
    def analyze(self,ctx,policy,quality,freeze,meter):
        frame=ctx.frame;recent=recent_frame(ctx,policy)
        quality_result=RuleResult('DQ001');frozen=RuleResult('DQ002');counting=RuleResult('DQ003')
        required=quality['required_fields']
        finite=np.isfinite(recent[required].to_numpy(dtype=float)) if len(recent) else np.empty((0,len(required)),bool)
        valid_count=int(finite.all(axis=1).sum())
        expected=int(np.ceil(policy['evaluation_hours']*60/policy['sample_minutes']))
        coverage=valid_count/expected
        missing={column:int((~np.isfinite(recent[column].to_numpy(dtype=float))).sum()) for column in required}
        def untrusted(flags):
            if not isinstance(flags,list):return True
            return any(not (isinstance(flag,str) and flag.startswith('缺失:') and flag[3:] not in required and flag[3:] in PARAMETERS) for flag in flags)
        flagged_count=int(recent.quality_flags.map(untrusted).sum())
        reasons=[]
        if flagged_count:reasons.append('来源数据带有待核实的质量标记')
        if len(recent) and not finite.all():reasons.append('现有采样含空值或非有限必需参数')
        if frame.measured_at.isna().any():reasons.append('存在无效采样时间')
        if len(frame)<policy['minimum_samples']:reasons.append('分析样本数量不足')
        if coverage<quality['minimum_recent_coverage']:reasons.append('近期采样缺失或参数为空')
        duplicate_count=int(frame.measured_at.duplicated().sum())
        if duplicate_count:reasons.append('存在重复时间戳')
        gaps=recent.measured_at.diff().dt.total_seconds()/3600
        trailing_gap=(ctx.end-frame.measured_at.max()).total_seconds()/3600 if len(frame) else policy['lookback_hours']
        max_gap=max(float(gaps.max()) if gaps.notna().any() else 0,trailing_gap)
        if max_gap>quality['max_gap_hours']:reasons.append('采样间隔过大或末端数据缺失')
        negative_fields=[x for x in required if x!='gas_temperature_c' and bool((recent[x]<0).any())]
        if negative_fields:reasons.append('存在负压力或负流量等不可信数值')
        future_count=int((frame.measured_at>ctx.data_cutoff+timedelta(minutes=quality['future_minutes'])).sum())
        if future_count:reasons.append('采样时间超前于分析任务时间')
        quality_result.metrics=clean(dict(expected_recent_samples=expected,actual_recent_samples=len(recent),valid_recent_samples=valid_count,
                     coverage=coverage,missing_by_parameter=missing,duplicate_timestamps=duplicate_count,
                     max_gap_hours=max_gap,negative_fields=negative_fields,future_samples=future_count,total_samples=len(frame),flagged_samples=flagged_count,reasons=reasons))
        if reasons:
            kind='数据缺失' if coverage<quality['minimum_recent_coverage'] or len(frame)<policy['minimum_samples'] else '数据不可信'
            quality_result.event(kind,max(ctx.start,ctx.end-timedelta(hours=policy['evaluation_hours'])),ctx.end,'verify_data',
                                 {**quality_result.metrics,'points':points(recent)})
        frozen_tail=frame.loc[frame.measured_at>=ctx.end-timedelta(hours=freeze['freeze_hours'])]
        freeze_expected=int(np.ceil(freeze['freeze_hours']*60/policy['sample_minutes']))
        if len(frozen_tail)>=freeze_expected and np.isfinite(frozen_tail[PARAMETERS].to_numpy(dtype=float)).all():
            spans=frozen_tail[PARAMETERS].max()-frozen_tail[PARAMETERS].min()
            if bool((spans<=freeze['value_tolerance']).all()) and float(frozen_tail.instantaneous_flow_m3_h.median())>policy['zero_flow']:
                frozen.event('数据冻结',frozen_tail.measured_at.iloc[0],ctx.end,'verify_data',{'duration_hours':freeze['freeze_hours'],'spans':clean(spans.to_dict()),'points':points(frozen_tail)})
        if len(frame)>1:
            delta=frame.measured_at.diff().dt.total_seconds()/3600
            increments=frame.cumulative_flow_m3.diff()
            reset=increments < -meter['reset_tolerance_m3']
            if reset.any():
                rows=frame.loc[reset]
                pos=int(np.flatnonzero(reset.to_numpy())[0])
                counting.event('累计量复位',rows.measured_at.iloc[0],min(ctx.end,rows.measured_at.iloc[-1]+timedelta(minutes=policy['sample_minutes'])),
                               'verify_data',{'negative_increment_m3':float(increments.loc[reset].min()),'reset_count':int(reset.sum()),'points':points(frame.iloc[max(0,pos-1):pos+1])})
            expected_volume=(frame.instantaneous_flow_m3_h+frame.instantaneous_flow_m3_h.shift())/2*delta
            tolerance=np.maximum(meter['absolute_tolerance_m3'],abs(expected_volume)*meter['relative_tolerance'])
            valid=(delta>0)&(delta<=meter['max_interval_hours'])&increments.notna()&expected_volume.notna()&~reset
            mismatched=valid&((increments-expected_volume).abs()>tolerance)
            counting.metrics=clean(dict(checked_pairs=int(valid.sum()),mismatched_pairs=int(mismatched.sum()),reset_pairs=int(reset.sum())))
            if mismatched.any():
                rows=frame.loc[mismatched];pos=int(np.flatnonzero(mismatched.to_numpy())[0])
                counting.event('累计与瞬时流量不一致',rows.measured_at.iloc[0],min(ctx.end,rows.measured_at.iloc[-1]+timedelta(minutes=policy['sample_minutes'])),
                               'verify_data',{'mismatched_pairs':int(mismatched.sum()),'observed_increment_m3':float(increments.iloc[pos]),'expected_increment_m3':float(expected_volume.iloc[pos]),'points':points(frame.iloc[max(0,pos-1):pos+1])})
        return [quality_result,frozen,counting]
