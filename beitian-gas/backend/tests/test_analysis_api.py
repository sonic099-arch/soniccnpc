from copy import deepcopy
from datetime import datetime,timezone,timedelta
from uuid import UUID,uuid4
from sqlalchemy import select,func
import pytest
from app.data_sources.mock import MockDataSource
from app.services.demo import load_dataset
from app.models.entities import (Well,WellMeasurement,WellMeasureEvent,AnalysisRun,AnalysisRule,
                                 WellAnalysisResult,WellAnomaly,WellBaseline,WellStatusSnapshot,AnomalyReview)

@pytest.fixture
def loaded(client,session):
    data=MockDataSource(count=13,days=14).generate()
    load_dataset(session,data)
    response=client.post('/api/v1/analysis/rules/bootstrap',json={'confirmed':True})
    assert response.status_code==200 and response.json()['added']==11
    return data


def execute(client,**kwargs):
    response=client.post('/api/v1/analysis/execute',json={'confirmed':True,**kwargs})
    assert response.status_code==201,response.text
    return response.json()


def test_analysis_writes_run_baseline_history_and_latest_snapshot(client,session,loaded):
    run=execute(client)
    assert run['status']=='已完成'
    assert run['summary']['status_counts']=={'可信正常':4,'疑似异常':5,'措施影响':1,'数据待核实':3,'工况待核实':0}
    assert run['window_end']=='2026-10-15T00:00:00+00:00'
    assert len(run['rule_snapshot'])==11
    assert session.scalar(select(func.count()).select_from(WellAnalysisResult))==13
    assert session.scalar(select(func.count()).select_from(WellStatusSnapshot))==13
    assert session.scalar(select(func.count()).select_from(WellBaseline))==13
    assert session.scalar(select(func.count()).select_from(WellAnomaly))>0
    rows=client.get('/api/v1/analysis/results',params={'run_id':run['id']}).json()
    assert rows['total']==13
    detail=client.get('/api/v1/analysis/results/'+rows['items'][0]['id']).json()
    assert len(detail['evidence']['rule_results'])==11


def test_normal_excluded_and_expected_anomalies_in_list(client,loaded):
    run=execute(client)
    items=client.get('/api/v1/analysis/anomalies',params={'run_id':run['id'],'limit':500}).json()['items']
    numbers={item['well_number'] for item in items}
    for expected in loaded.expected:
        if expected['expected_screening_status']=='可信正常':assert expected['well_number'] not in numbers
        else:assert expected['well_number'] in numbers
    assert all(item['screening_status']!='可信正常' for item in items)


def test_evidence_captures_measure_ids_rule_version_values(client,loaded):
    run=execute(client)
    items=client.get('/api/v1/analysis/anomalies',params={'anomaly_type':'措施后未恢复','run_id':run['id']}).json()['items']
    assert len(items)==1
    detail=client.get('/api/v1/analysis/anomalies/'+items[0]['id']).json()
    assert detail['rule_snapshot']['code']=='ME002'
    evidence=detail['evidence']['merged_evidence'][0]
    assert evidence['pre_flow_m3_h']>evidence['post_flow_m3_h']
    assert evidence['measure_id']
    assert evidence['before_points'][0]['measurement_id']
    assert evidence['after_points'][0]['measurement_id']
    assert detail['evidence']['provenance']['context']['measures'][0]['id']==evidence['measure_id']


def test_repeated_analysis_deduplicates_default_list_keeps_historical_results(client,session,loaded):
    first=execute(client)
    before=client.get('/api/v1/analysis/anomalies',params={'limit':500}).json()
    second=execute(client)
    after=client.get('/api/v1/analysis/anomalies',params={'limit':500}).json()
    assert first['id']!=second['id']
    assert before['total']==after['total']
    assert {x['fingerprint'] for x in before['items']}=={x['fingerprint'] for x in after['items']}
    assert client.get('/api/v1/analysis/results',params={'run_id':first['id']}).json()['total']==13
    assert session.scalar(select(func.count()).select_from(WellAnalysisResult))==26
    assert session.scalar(select(func.count()).select_from(WellStatusSnapshot))==13
    assert client.get('/api/v1/analysis/runs').json()['total']==2


def test_new_rule_version_recalculates_and_old_evidence_unchanged(client,session,loaded):
    first=execute(client)
    expected=next(e for e in loaded.expected if e['scenario']=='abnormal_decline')
    old=client.get('/api/v1/analysis/results',params={'run_id':first['id'],'search':expected['well_number']}).json()['items'][0]
    assert old['screening_status']=='疑似异常'
    current=next(x for x in client.get('/api/v1/analysis/rules').json()['items'] if x['code']=='FL001')
    configuration={**current['configuration'],'decline_ratio':.95}
    response=client.post('/api/v1/analysis/rules/FL001/versions',json={'version':'1.0.1','configuration':configuration})
    assert response.status_code==201,response.text
    second=execute(client)
    new=client.get('/api/v1/analysis/results',params={'run_id':second['id'],'search':expected['well_number']}).json()['items'][0]
    assert new['screening_status']=='可信正常'
    old_detail=client.get('/api/v1/analysis/results/'+old['id']).json()
    assert old_detail['screening_status']=='疑似异常'
    first_rule=next(r for r in client.get('/api/v1/analysis/runs/'+first['id']).json()['rule_snapshot'] if r['code']=='FL001')
    second_rule=next(r for r in second['rule_snapshot'] if r['code']=='FL001')
    assert first_rule['version']=='1.0.0' and second_rule['version']=='1.0.1'
    assert first_rule['configuration']['decline_ratio']==.25


def test_rule_config_invalid_and_publish_duplicate_roll_back(client,loaded):
    items=client.get('/api/v1/analysis/rules').json()['items'];rule=next(r for r in items if r['code']=='FL001')
    for data in ({'version':'1.0.1','configuration':{}},{'version':'1.0.0','configuration':rule['configuration']},
                 {'version':'0.0.1','configuration':rule['configuration']},{'version':'1.0.1','configuration':{**rule['configuration'],'decline_ratio':-1}}):
        assert client.post('/api/v1/analysis/rules/FL001/versions',json=data).status_code==422
    assert next(r for r in client.get('/api/v1/analysis/rules').json()['items'] if r['code']=='FL001')['enabled']


def test_bootstrap_idempotent_does_not_reset_user_configuration(client,loaded):
    rule=next(r for r in client.get('/api/v1/analysis/rules').json()['items'] if r['code']=='FL001')
    response=client.post('/api/v1/analysis/rules/FL001/versions',json={'version':'1.0.1','configuration':{**rule['configuration'],'decline_ratio':.5}})
    assert response.status_code==201
    assert client.post('/api/v1/analysis/rules/bootstrap',json={'confirmed':True}).json()['added']==0
    rule=next(r for r in client.get('/api/v1/analysis/rules').json()['items'] if r['code']=='FL001')
    assert rule['configuration']['decline_ratio']==.5


def test_missing_rules_and_unknown_custom_rule_never_default_normal(client,session):
    assert client.post('/api/v1/analysis/execute',json={'confirmed':True}).status_code==409
    assert client.post('/api/v1/analysis/rules/bootstrap',json={'confirmed':False}).status_code==422
    client.post('/api/v1/analysis/rules/bootstrap',json={'confirmed':True})
    session.add(AnalysisRule(code='CUSTOM',name='未注册',version='1.0.0',function_key='unsupported',configuration={},applicable_states=['全部'],input_parameters=[],enabled=True));session.commit()
    response=client.post('/api/v1/analysis/execute',json={'confirmed':True})
    assert response.status_code==409 and '未注册' in response.json()['detail']


def test_partial_scope_and_unknown_well_filters(client,loaded):
    well=loaded.wells[0]
    run=execute(client,well_ids=[str(well['id'])])
    assert run['summary']['total_wells']==1
    assert client.get('/api/v1/analysis/results',params={'area':well['area'],'search':well['well_number']}).json()['total']==1
    assert client.get('/api/v1/analysis/results',params={'screening_status':'疑似异常'}).json()['total']==0
    response=client.post('/api/v1/analysis/execute',json={'confirmed':True,'well_ids':[str(uuid4())]})
    assert response.status_code==409
    assert client.post('/api/v1/analysis/execute',json={'confirmed':True,'window_start':'2026-10-15T00:00:00Z','window_end':'2026-10-01T00:00:00Z'}).status_code==422


def test_old_window_cannot_overwrite_latest_status(client,session,loaded):
    first=execute(client)
    second=execute(client,window_end='2026-10-14T00:00:00Z')
    snapshots=list(session.scalars(select(WellStatusSnapshot)))
    assert all(str(s.analysis_run_id)==first['id'] for s in snapshots)
    assert client.get('/api/v1/analysis/results',params={'run_id':second['id']}).json()['total']==13


def test_generated_results_rules_and_reviews_are_immutable(client,loaded):
    run=execute(client)
    anomaly=client.get('/api/v1/analysis/anomalies').json()['items'][0]
    assert client.patch('/api/v1/analysis-runs/'+run['id'],json={'status':'待执行'}).status_code==409
    assert client.delete('/api/v1/analysis-runs/'+run['id']).status_code==409
    assert client.patch('/api/v1/anomalies/'+anomaly['id'],json={'evidence':{}}).status_code==409
    rule=next(r for r in run['rule_snapshot'] if r['code']=='FL001')
    assert client.patch('/api/v1/rules/'+rule['id'],json={'configuration':{}}).status_code==409
    assert client.delete('/api/v1/rules/'+rule['id']).status_code==409
    review=client.post('/api/v1/reviews',json={'anomaly_id':anomaly['id'],'reviewer':'演示复核员','decision':'待现场核实','comment':'保留原证据','reviewed_at':'2026-10-22T00:00:00Z'})
    assert review.status_code==201
    assert client.patch('/api/v1/reviews/'+review.json()['id'],json={'comment':'改写'}).status_code==409
    assert client.get('/api/v1/analysis/anomalies/'+anomaly['id']).json()['reviews'][0]['comment']=='保留原证据'
    execute(client)
    latest=client.get('/api/v1/analysis/anomalies',params={'limit':500}).json()['items']
    matching=next(x for x in latest if x['fingerprint']==anomaly['fingerprint'])
    assert client.get('/api/v1/analysis/anomalies/'+matching['id']).json()['reviews'][0]['comment']=='保留原证据'


def test_failed_task_retained_without_partial_snapshot_updates(client,session,loaded,monkeypatch):
    first=execute(client)
    from app.analysis.engine import AnomalyRuleEngine
    monkeypatch.setattr(AnomalyRuleEngine,'analyze',lambda self,ctx:(_ for _ in ()).throw(RuntimeError('模拟内部故障')))
    response=client.post('/api/v1/analysis/execute',json={'confirmed':True})
    assert response.status_code==500
    failed=session.scalar(select(AnalysisRun).where(AnalysisRun.status=='失败'))
    assert failed is not None and 'RuntimeError'==failed.summary['failure_type']
    assert session.scalar(select(func.count()).select_from(WellAnalysisResult))==13
    assert all(str(s.analysis_run_id)==first['id'] for s in session.scalars(select(WellStatusSnapshot)))


def test_well_number_change_retains_analysis_association(client,loaded):
    first=execute(client)
    well=loaded.wells[0]
    assert client.patch('/api/v1/wells/'+str(well['id']),json={'well_number':'演示-改号后'}).status_code==200
    rows=client.get('/api/v1/analysis/results',params={'run_id':first['id'],'well_id':str(well['id'])}).json()['items']
    assert rows[0]['well_number']=='演示-改号后'
    detail=client.get('/api/v1/analysis/results/'+rows[0]['id']).json()
    assert detail['evidence']['well_number']==well['well_number']


def test_no_measurements_well_still_in_results_as_unverified(client,session,loaded):
    extra=Well(well_number='演示-无数据',area='演示',is_demo=True)
    session.add(extra);session.commit()
    run=execute(client)
    rows=client.get('/api/v1/analysis/results',params={'run_id':run['id'],'well_id':str(extra.id)}).json()['items']
    assert rows[0]['screening_status']=='数据待核实'


def test_cannot_inject_generated_anomaly_or_forge_engine_run(client,loaded):
    run=execute(client)
    well_id=str(loaded.wells[0]['id'])
    rule=next(r for r in run['rule_snapshot'] if r['code']=='FL001')
    response=client.post('/api/v1/anomalies',json={'well_id':well_id,'analysis_run_id':run['id'],'rule_id':rule['id'],
                       'anomaly_type':'伪造结果','started_at':'2026-10-14T00:00:00Z','evidence':{},'rule_snapshot':{},'fingerprint':'fake'})
    assert response.status_code==409
    fake=client.post('/api/v1/analysis-runs',json={'window_start':'2026-10-01T00:00:00Z','window_end':'2026-10-15T00:00:00Z','summary':{'engine_version':'screening-v1'}})
    assert fake.status_code==409
    manual=client.post('/api/v1/analysis-runs',json={'window_start':'2026-10-01T00:00:00Z','window_end':'2026-10-15T00:00:00Z'}).json()
    assert client.patch('/api/v1/analysis-runs/'+manual['id'],json={'summary':{'engine_version':'screening-v1'}}).status_code==409
    manual_event=client.post('/api/v1/anomalies',json={'well_id':well_id,'analysis_run_id':manual['id'],'rule_id':rule['id'],'anomaly_type':'手工记录','started_at':'2026-10-14T00:00:00Z','fingerprint':'manual','evidence':{},'rule_snapshot':{}})
    assert manual_event.status_code==201,manual_event.text
    manual_event=manual_event.json()
    assert client.patch('/api/v1/anomalies/'+manual_event['id'],json={'analysis_run_id':run['id']}).status_code==409


def test_disabled_rule_version_leads_to_unverified_not_normal(client,loaded):
    rule=next(r for r in client.get('/api/v1/analysis/rules').json()['items'] if r['code']=='FL001')
    assert client.post('/api/v1/analysis/rules/FL001/versions',json={'version':'1.0.1','configuration':rule['configuration'],'enabled':False}).status_code==201
    run=execute(client)
    assert run['summary']['status_counts']['可信正常']==0
