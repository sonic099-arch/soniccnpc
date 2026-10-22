from datetime import timedelta
import numpy as np
import pandas as pd
from app.analysis.types import Baseline,PARAMETERS,active_at,clean

class BaselineCalculator:
    def calculate(self,ctx,state,policy):
        if not state.known or not state.config:return Baseline(False,{'reason':'工况无法核实'})
        frame=ctx.frame
        trusted=np.isfinite(frame[PARAMETERS[:6]].to_numpy(dtype=float)).all(axis=1)
        trusted&=(frame[PARAMETERS[:5]]>=0).all(axis=1).to_numpy()
        eligible=trusted&~state.planned_mask&~state.measure_mask&(frame.instantaneous_flow_m3_h>policy['zero_flow'])
        eligible&=(frame.measured_at>=state.config['effective_start'])
        eligible&=(frame.measured_at<ctx.end-timedelta(hours=policy['baseline_guard_hours']))
        for config in ctx.configurations:
            if config.get('id')!=state.config.get('id'):
                end=config.get('effective_end') or ctx.end
                eligible&=~((frame.measured_at>=config['effective_start'])&(frame.measured_at<end))
        moment=ctx.end-timedelta(microseconds=1)
        for tool in ctx.tools:
            end=tool.get('effective_end') or ctx.end
            if active_at(tool,moment):
                eligible&=(frame.measured_at>=tool['effective_start'])&(frame.measured_at<end)
            else:
                eligible&=~((frame.measured_at>=tool['effective_start'])&(frame.measured_at<end))
        for fault in ctx.faults:
            end=fault.get('effective_end') or ctx.end
            eligible&=~((frame.measured_at>=fault['effective_start'])&(frame.measured_at<end))
        candidate=frame.loc[eligible]
        if len(candidate):
            candidate=candidate.loc[candidate.measured_at<candidate.measured_at.iloc[0]+timedelta(hours=policy['baseline_hours'])]
        if len(candidate)<policy['baseline_min_samples']:
            return Baseline(False,{'reason':'可用基线样本不足','available_samples':len(candidate),'required_samples':policy['baseline_min_samples']})
        origin=candidate.measured_at.iloc[0]
        x=(candidate.measured_at-origin).dt.total_seconds().to_numpy()/3600
        q=candidate.instantaneous_flow_m3_h.to_numpy(dtype=float)
        log_q=np.log(q)
        slope,intercept=np.polyfit(x,log_q,1)
        residual=float(np.square(log_q-(slope*x+intercept)).sum())
        total=float(np.square(log_q-log_q.mean()).sum())
        r2=max(0.0,min(1.0,1-residual/total)) if total>0 else 1.0
        statistics=clean({'origin':origin,'log_flow_slope_hour':float(slope),'log_flow_intercept':float(intercept),
                         'natural_decline_daily':float(1-np.exp(slope*24)),
                         'flow_trend_r2':r2,'use_trend_prediction':r2>=policy['natural_decline_min_r2'],
                         'medians':candidate[PARAMETERS].median().to_dict(),
                         'sample_count':len(candidate),'reference_type':'按当前生产配置筛选的历史参照，未经现场确认'})
        return Baseline(True,statistics,len(candidate),candidate.measured_at.iloc[0],candidate.measured_at.iloc[-1]+timedelta(minutes=policy['sample_minutes']))
