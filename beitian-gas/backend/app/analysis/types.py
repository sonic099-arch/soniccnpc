from dataclasses import dataclass, field
from datetime import datetime, timedelta
import math
from typing import Any
import numpy as np
import pandas as pd

PARAMETERS=['tubing_pressure_mpa','casing_pressure_mpa','back_pressure_mpa','instantaneous_flow_m3_h',
            'cumulative_flow_m3','gas_temperature_c','liquid_rate_m3_d']
PRESSURES=PARAMETERS[:3]
ENGINE_VERSION='screening-v1'

@dataclass
class WellContext:
    well_id: str
    well_number: str
    frame: pd.DataFrame
    start: datetime
    end: datetime
    data_cutoff: datetime
    configurations: list[dict]=field(default_factory=list)
    tools: list[dict]=field(default_factory=list)
    measures: list[dict]=field(default_factory=list)
    operations: list[dict]=field(default_factory=list)
    faults: list[dict]=field(default_factory=list)
    is_demo: bool=True

@dataclass
class RuleResult:
    code: str
    outcome: str='通过'
    message: str='未发现本规则定义的异常'
    metrics: dict=field(default_factory=dict)
    events: list[dict]=field(default_factory=list)
    coverage: bool=True

    def event(self, kind, start, end, action, evidence, severity='关注'):
        self.outcome='命中'
        self.events.append(dict(anomaly_type=kind,started_at=start,ended_at=end,action=action,
                                severity=severity,evidence=evidence))
        return self

@dataclass
class OperationState:
    known: bool
    mode: str | None
    production_state: str
    planned_mask: np.ndarray
    measure_mask: np.ndarray
    config: dict | None
    active_measures: list[dict]
    result: RuleResult
    context_metrics: dict

@dataclass
class Baseline:
    valid: bool
    statistics: dict
    sample_count: int=0
    start: datetime | None=None
    end: datetime | None=None

    def expected_flow(self, times):
        if not self.statistics['use_trend_prediction']:
            return np.full(len(times),self.statistics['medians']['instantaneous_flow_m3_h'])
        elapsed=(pd.DatetimeIndex(times)-pd.Timestamp(self.statistics['origin'])).total_seconds()/3600
        logarithms=self.statistics['log_flow_intercept']+self.statistics['log_flow_slope_hour']*np.asarray(elapsed)
        bounds=np.log([np.finfo(float).tiny,np.finfo(float).max])
        return np.exp(np.clip(logarithms,*bounds))


def clean(value: Any):
    if isinstance(value,dict): return {str(k):clean(v) for k,v in value.items()}
    if isinstance(value,(list,tuple,np.ndarray)): return [clean(v) for v in value]
    if isinstance(value,(datetime,pd.Timestamp)): return value.isoformat()
    if isinstance(value,(np.bool_,bool)): return bool(value)
    if isinstance(value,(np.integer,)): return int(value)
    if isinstance(value,(float,np.floating)): return float(value) if math.isfinite(value) else None
    return value


def recent_frame(ctx,policy):
    return ctx.frame.loc[ctx.frame.measured_at>=ctx.end-timedelta(hours=policy['evaluation_hours'])]


def points(frame,limit=5):
    if frame.empty:return []
    positions=np.unique(np.linspace(0,len(frame)-1,min(limit,len(frame)),dtype=int))
    selected=frame.iloc[positions]
    columns=[x for x in ['measurement_id','measured_at',*PARAMETERS,'quality_flags'] if x in frame]
    return clean(selected[columns].to_dict('records'))


def intervals(frame,mask,cadence_minutes,max_gap_hours):
    positions=np.flatnonzero(np.asarray(mask,dtype=bool))
    if not len(positions):return []
    first=int(positions[0]);start=previous=frame.measured_at.iloc[first];last_position=first
    result=[]
    for position in positions[1:]:
        current=frame.measured_at.iloc[int(position)]
        if int(position)!=last_position+1 or (current-previous).total_seconds()/3600>max_gap_hours:
            result.append((start,previous+timedelta(minutes=cadence_minutes)));start=current
        previous=current;last_position=int(position)
    result.append((start,previous+timedelta(minutes=cadence_minutes)))
    return result


def active_at(record,time):
    return record['effective_start']<=time and (record.get('effective_end') is None or time<record['effective_end'])
