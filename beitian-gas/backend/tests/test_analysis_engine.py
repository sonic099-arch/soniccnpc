from copy import deepcopy
from datetime import datetime,timezone,timedelta
from types import SimpleNamespace
from uuid import uuid5,NAMESPACE_URL
import json
import numpy as np
import pandas as pd
import pytest
from app.data_sources.mock import MockDataSource,SCENARIOS
from app.analysis.config import default_profile,DEFINITIONS,CONFIG_TYPES
from app.analysis.engine import AnomalyRuleEngine
from app.analysis.types import WellContext,RuleResult
from app.analysis.aggregate import AnomalyAggregator

START=datetime(2026,10,1,tzinfo=timezone.utc)
END=START+timedelta(days=14)
CUTOFF=datetime(2026,10,22,tzinfo=timezone.utc)

@pytest.fixture(scope='module')
def analysis_data():return MockDataSource(count=13,days=14).generate()

@pytest.fixture
def rule_objects():
    return [SimpleNamespace(**{k:v for k,v in r.items() if k!='required_for_normal'},id=uuid5(NAMESPACE_URL,r['code']),enabled=True) for r in default_profile()['rules']]

@pytest.fixture
def make_context(analysis_data):
    def make(code='stable'):
        expected=next(e for e in analysis_data.expected if e['scenario']==code)
        well=next(w for w in analysis_data.wells if w['well_number']==expected['well_number'])
        frame=analysis_data.measurements.loc[analysis_data.measurements.well_number==well['well_number']].copy()
        frame['measurement_id']=[str(uuid5(NAMESPACE_URL,well['well_number']+str(i))) for i in range(len(frame))]
        def records(items):
            rows=[]
            for i,record in enumerate(items):
                if record['well_id']!=well['id']:continue
                row={k:deepcopy(v) for k,v in record.items() if k not in ('well_id','parameters')}
                row['id']=str(uuid5(NAMESPACE_URL,well['well_number']+str(i)+str(record.get('production_mode'))))
                if 'configuration' in row:row['configuration']={k:v for k,v in row['configuration'].items() if k=='cycle'}
                rows.append(row)
            return rows
        return WellContext(str(well['id']),well['well_number'],frame,START,END,CUTOFF,
                           records(analysis_data.configurations),records(analysis_data.tools),records(analysis_data.measures),records(analysis_data.operations))
    return make

def labels(output):
    kinds={e['anomaly_type'] for e in output['events']}
    for result in output['rule_results']:kinds.update(result['metrics'].get('observed_tags',[]))
    return kinds

def recalculate_cumulative(ctx):
    q=ctx.frame.instantaneous_flow_m3_h.to_numpy()
    ctx.frame['cumulative_flow_m3']=10000+np.r_[0,np.cumsum((q[1:]+q[:-1])/2)]

@pytest.mark.parametrize('code,name,state,status,expected_labels',SCENARIOS)
def test_all_scenarios_independent_of_expected_tags(make_context,rule_objects,code,name,state,status,expected_labels):
    output=AnomalyRuleEngine(rule_objects).analyze(make_context(code))
    assert output['screening_status']==status
    assert output['production_state']==state
    assert set(expected_labels).issubset(labels(output))
    assert len(output['rule_results'])==len(DEFINITIONS)
    if status=='可信正常':assert output['events']==[] and all(r['coverage'] for r in output['rule_results'])
    for event in output['events']:
        assert event['ended_at']>event['started_at']
        assert event['evidence']['provenance']['input_digest']

@pytest.mark.parametrize('code',list(DEFINITIONS))
def test_every_rule_has_unique_metadata_config_and_automatic_test(rule_objects,code):
    rule=next(r for r in rule_objects if r.code==code)
    assert rule.name and rule.version and rule.applicable_states and rule.input_parameters and rule.function_key
    assert CONFIG_TYPES[code].model_validate(rule.configuration)

@pytest.mark.parametrize('kind',['missing_config','overlapping_config','unknown_mode','unknown_tool','unknown_measure','recent_tool_change','active_fault'])
def test_unknown_context_never_default_normal(make_context,rule_objects,kind):
    ctx=make_context()
    if kind=='missing_config':ctx.configurations=[]
    if kind=='overlapping_config':ctx.configurations.append({**ctx.configurations[0],'id':'another'})
    if kind=='unknown_mode':ctx.configurations[0]['production_mode']='未知工艺'
    if kind=='unknown_tool':ctx.tools[0]['tool_type']='未知工具'
    if kind=='unknown_measure':ctx.measures.append({'id':'unknown','measure_type':'未知措施','effective_start':END-timedelta(hours=30),'effective_end':END-timedelta(hours=24)})
    if kind=='recent_tool_change':ctx.tools[0]['effective_start']=END-timedelta(hours=6)
    if kind=='active_fault':ctx.faults=[{'id':'fault','fault_type':'历史待复核','confirmed':False,'effective_start':START,'effective_end':None}]
    output=AnomalyRuleEngine(rule_objects).analyze(ctx)
    assert output['screening_status']=='工况待核实'

@pytest.mark.parametrize('kind',['empty','null','negative','infinite','future','duplicate','quality_flag'])
def test_untrustworthy_data_not_normal_or_diagnosed(make_context,rule_objects,kind):
    ctx=make_context()
    if kind=='empty':ctx.frame=ctx.frame.iloc[:0]
    elif kind=='null':ctx.frame.loc[ctx.frame.index[-24:],'gas_temperature_c']=np.nan
    elif kind=='negative':ctx.frame.loc[ctx.frame.index[-1],'tubing_pressure_mpa']=-1
    elif kind=='infinite':ctx.frame.loc[ctx.frame.index[-1],'casing_pressure_mpa']=float('inf')
    elif kind=='future':ctx.frame.loc[ctx.frame.index[-1],'measured_at']=CUTOFF+timedelta(days=1)
    elif kind=='duplicate':ctx.frame=pd.concat([ctx.frame,ctx.frame.tail(1)],ignore_index=True)
    elif kind=='quality_flag':ctx.frame['quality_flags']=[[] for _ in range(len(ctx.frame))];ctx.frame.at[ctx.frame.index[-1],'quality_flags']=['传感器故障']
    output=AnomalyRuleEngine(rule_objects).analyze(ctx)
    assert output['screening_status']=='数据待核实'
    assert all(e['code'] not in ('FL001','PR001','PR002','TP001','OP001') for e in output['events'])

def test_pressure_step_has_values_and_measurement_ids(make_context,rule_objects):
    ctx=make_context();ctx.frame.loc[ctx.frame.index[-1],'tubing_pressure_mpa']+=3
    output=AnomalyRuleEngine(rule_objects).analyze(ctx)
    event=next(e for e in output['events'] if e['anomaly_type']=='压力突变')
    evidence=event['evidence']['merged_evidence'][0]
    assert evidence['observed_step_mpa']>evidence['threshold_mpa']
    assert all(p['measurement_id'] for p in evidence['points'])


def test_pressure_volatility_detected(make_context,rule_objects):
    ctx=make_context();tail=ctx.frame.index[-24:]
    ctx.frame.loc[tail,'tubing_pressure_mpa']=np.linspace(5,8,len(tail))
    output=AnomalyRuleEngine(rule_objects).analyze(ctx)
    assert '压力异常波动' in labels(output)


def test_single_temperature_change_does_not_diagnose_freeze(make_context,rule_objects):
    ctx=make_context();ctx.frame.loc[ctx.frame.index[-12:],'gas_temperature_c']=-10
    output=AnomalyRuleEngine(rule_objects).analyze(ctx)
    assert '疑似冻堵辅助提示' not in labels(output)
    assert '温度变化待核实' in labels(output)
    assert output['screening_status']=='工况待核实'


def test_intermittent_dips_not_combined_into_sustained_decline(make_context,rule_objects):
    ctx=make_context();idx=ctx.frame.index[-24::2];ctx.frame.loc[idx,'instantaneous_flow_m3_h']*=.5
    recalculate_cumulative(ctx)
    output=AnomalyRuleEngine(rule_objects).analyze(ctx)
    assert '持续减产' not in labels(output)


def test_foam_period_masks_pressure_and_flow_faults(make_context,rule_objects):
    ctx=make_context('foam_normal');idx=ctx.frame.index[-12:]
    ctx.frame.loc[idx,'tubing_pressure_mpa']+=3
    output=AnomalyRuleEngine(rule_objects).analyze(ctx)
    assert output['screening_status']=='措施影响'
    assert labels(output)=={'措施影响'}


def test_missing_evidence_cannot_confirm_liquid(make_context,rule_objects):
    ctx=make_context('liquid_hint');ctx.frame['liquid_rate_m3_d']=np.nan
    output=AnomalyRuleEngine(rule_objects).analyze(ctx)
    assert '疑似积液辅助提示' not in labels(output)
    assert '压力流量关联异常' in labels(output)

@pytest.mark.parametrize('code',['DQ001','DQ002','DQ003','FL001','PR001','ME002'])
def test_disabled_required_rule_blocks_trusted_normal(make_context,rule_objects,code):
    next(r for r in rule_objects if r.code==code).enabled=False
    output=AnomalyRuleEngine(rule_objects).analyze(make_context())
    assert output['screening_status']!='可信正常'
    assert '规则覆盖不足' in labels(output)


def test_out_of_scope_rule_blocks_normal(make_context,rule_objects):
    next(r for r in rule_objects if r.code=='FL001').applicable_states=['泡排']
    output=AnomalyRuleEngine(rule_objects).analyze(make_context())
    assert output['screening_status']=='工况待核实'


def test_configuration_change_recalculates_actual_rule(make_context,rule_objects):
    engine=AnomalyRuleEngine(rule_objects)
    assert engine.analyze(make_context('abnormal_decline'))['screening_status']=='疑似异常'
    next(r for r in rule_objects if r.code=='FL001').configuration['decline_ratio']=.95
    output=AnomalyRuleEngine(rule_objects).analyze(make_context('abnormal_decline'))
    assert output['screening_status']=='可信正常'


def test_simulation_tags_do_not_change_results(make_context,rule_objects):
    ctx=make_context('abnormal_decline')
    first=AnomalyRuleEngine(rule_objects).analyze(deepcopy(ctx))
    ctx.well_number='完全不同的井号'
    ctx.configurations[0]['configuration'].update(demo_scenario='stable',expected_screening_status='可信正常')
    second=AnomalyRuleEngine(rule_objects).analyze(ctx)
    assert first['screening_status']==second['screening_status']
    assert labels(first)==labels(second)
    assert first['production_state']==second['production_state']


def test_equal_window_timezone_has_equal_event_fingerprints(make_context,rule_objects):
    ctx=make_context('abnormal_decline');other=deepcopy(ctx)
    other.end=other.end.astimezone(timezone(timedelta(hours=8)))
    first=AnomalyRuleEngine(rule_objects).analyze(ctx);second=AnomalyRuleEngine(rule_objects).analyze(other)
    assert [e['fingerprint'] for e in first['events']]==[e['fingerprint'] for e in second['events']]


def test_aggregation_merges_duplicate_overlapping_events(rule_objects):
    result=RuleResult('FL001')
    for start,end in [(START,START+timedelta(hours=12)),(START+timedelta(hours=11),START+timedelta(hours=24))]:
        result.event('持续减产',start,end,'abnormal',{'reason':'重复检测证据'})
    events=AnomalyAggregator().aggregate('well',[result],{r.code:r for r in rule_objects},3)
    assert len(events)==1 and events[0]['ended_at']==START+timedelta(hours=24)
    assert len(events[0]['evidence']['merged_evidence'])==2

@pytest.mark.parametrize('code,change',[('SYS001',{'valid_modes':['尚未支持的工艺']}),('DQ001',{'required_fields':['instantaneous_flow_m3_h']}),('FL001',{'decline_ratio':-1}),('TP001',{'temperature_drop_c':float('nan')})])
def test_invalid_or_incomplete_rule_config_rejected(rule_objects,code,change):
    next(r for r in rule_objects if r.code==code).configuration.update(change)
    with pytest.raises(ValueError):AnomalyRuleEngine(rule_objects)


def test_random_drift_is_not_named_natural_decline(make_context,rule_objects):
    data=MockDataSource(count=40,days=14).generate()
    ctx=make_context()
    well=data.wells[39]
    ctx.well_id=str(well['id']);ctx.well_number=well['well_number']
    ctx.frame=data.measurements.loc[data.measurements.well_number==well['well_number']].copy()
    output=AnomalyRuleEngine(rule_objects).analyze(ctx)
    assert output['baseline'].statistics['natural_decline_daily']>.001
    assert not output['baseline'].statistics['use_trend_prediction']
    assert output['production_state']=='正常生产' and output['screening_status']=='可信正常'
