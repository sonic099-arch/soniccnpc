from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4
import pytest
from sqlalchemy import select, insert
from app.data_sources.mock import MockDataSource
from app.services.demo import load_dataset
from app.models.entities import Well, WellMeasurement, WellStatusSnapshot, WellAnalysisResult

BASE='/api/v1/screening'
START='2026-10-01T00:00:00Z'
END='2026-10-15T00:00:00Z'

@pytest.fixture
def batch(client, session):
    data=MockDataSource(count=13,days=14).generate()
    load_dataset(session,data)
    client.post('/api/v1/analysis/rules/bootstrap',json={'confirmed':True})
    run=client.post('/api/v1/analysis/execute',json={'confirmed':True}).json()
    return data,run


def well_id(data,scenario):
    number=next(e['well_number'] for e in data.expected if e['scenario']==scenario)
    return str(next(w['id'] for w in data.wells if w['well_number']==number))


def test_empty_database_never_fabricates_normal(client):
    r=client.get(BASE+'/dashboard').json()
    assert r['total_wells']==0 and r['run'] is None
    assert not any(r['status_counts'].values())
    assert client.get(BASE+'/options').json()['runs']==[]
    assert client.get(BASE+'/wells').json()['items']==[]


def test_registered_without_analysis_explicitly_unanalyzed(client,session):
    session.add(Well(well_number='演示-未分析',area='测试'));session.commit()
    assert client.get(BASE+'/dashboard').json()['status_counts']['未分析']==1
    assert client.get(BASE+'/wells').json()['items'][0]['screening_status']=='未分析'


def test_dashboard_counts_registered_analyzed_and_unanalyzed(client,session,batch):
    session.add(Well(well_number='演示-额外井',area='新增'));session.commit()
    r=client.get(BASE+'/dashboard').json()
    assert r['total_wells']==14 and r['analyzed_wells']==13
    assert r['status_counts']=={'可信正常':4,'疑似异常':5,'措施影响':1,'数据待核实':3,'工况待核实':0,'未分析':1}
    assert sum(x['count'] for x in r['areas'])==14
    assert client.get(BASE+'/options').json()['selected_run']['id']==batch[1]['id']


def test_latest_executed_report_does_not_use_newer_data_snapshot(client,session,batch):
    # 模拟用户先分析未来窗口，再明确回到演示窗口。最新状态表保留未来as_of，报表必须取最新执行任务。
    future=client.post('/api/v1/analysis/execute',json={'confirmed':True,'window_start':'2026-10-08T00:00:00Z','window_end':'2026-10-22T00:00:00Z'}).json()
    assert future['summary']['status_counts']['数据待核实']==13
    correct=client.post('/api/v1/analysis/execute',json={'confirmed':True,'window_start':START,'window_end':END}).json()
    assert all(str(r.analysis_run_id)==future['id'] for r in session.scalars(select(WellStatusSnapshot)))
    r=client.get(BASE+'/dashboard').json()
    assert r['run']['id']==correct['id'] and r['status_counts']['可信正常']==4
    assert client.get(BASE+'/dashboard',params={'run_id':future['id']}).json()['status_counts']['数据待核实']==13


def test_partial_analysis_leaves_other_wells_unanalyzed_in_report(client,batch):
    data,_=batch
    client.post('/api/v1/analysis/execute',json={'confirmed':True,'well_ids':[well_id(data,'stable')]})
    r=client.get(BASE+'/dashboard').json()
    assert r['total_wells']==13 and r['analyzed_wells']==1 and r['status_counts']['未分析']==12


def test_well_search_area_status_and_pagination(client,batch):
    data,_=batch
    r=client.get(BASE+'/wells',params={'limit':5}).json()
    p=client.get(BASE+'/wells',params={'limit':5,'offset':5}).json()
    assert r['total']==13 and len(r['items'])==5
    assert {x['well_id'] for x in r['items']}.isdisjoint(x['well_id'] for x in p['items'])
    item=r['items'][0]
    found=client.get(BASE+'/wells',params={'search':item['well_number'],'area':item['area']}).json()
    assert found['total']==1 and found['items'][0]['well_id']==item['well_id']
    assert client.get(BASE+'/wells',params={'search':'%'}).json()['total']==0
    assert client.get(BASE+'/wells',params={'screening_status':'可信正常'}).json()['total']==4
    assert client.get(BASE+'/wells',params={'non_normal':True}).json()['total']==9
    assert client.get(BASE+'/dashboard',params={'area':'不存在'}).json()['total_wells']==0


def test_anomaly_wells_unique_and_event_list_normal_excluded(client,batch):
    wells=client.get(BASE+'/wells',params={'non_normal':True}).json()['items']
    assert len(wells)==len({x['well_id'] for x in wells})==9
    events=client.get(BASE+'/anomalies',params={'limit':500}).json()
    assert all(x['screening_status']!='可信正常' for x in events['items'])
    assert len(events['items'])>9
    kind=events['items'][0]['anomaly_type']
    matched=client.get(BASE+'/anomalies',params={'anomaly_type':kind}).json()
    assert matched['total']>0 and all(x['anomaly_type']==kind for x in matched['items'])
    assert all(kind in x['anomaly_types'] for x in client.get(BASE+'/wells',params={'anomaly_type':kind}).json()['items'])


def test_anomaly_time_overlap_half_open_and_timezone(client,batch):
    events=client.get(BASE+'/anomalies',params={'anomaly_type':'非计划停井'}).json()['items']
    item=events[0]
    assert client.get(BASE+'/anomalies',params={'anomaly_type':'非计划停井','event_end':item['started_at']}).json()['total']==0
    assert client.get(BASE+'/anomalies',params={'anomaly_type':'非计划停井','event_start':item['ended_at']}).json()['total']==0
    a=client.get(BASE+'/anomalies',params={'event_start':'2026-10-14T00:00:00Z','event_end':END}).json()
    b=client.get(BASE+'/anomalies',params={'event_start':'2026-10-14T08:00:00+08:00','event_end':'2026-10-15T08:00:00+08:00'}).json()
    assert [x['id'] for x in a['items']]==[x['id'] for x in b['items']]
    assert client.get(BASE+'/anomalies',params={'event_start':END,'event_end':START}).status_code==422


def test_single_well_detail_ids_and_history(client,batch):
    data,run=batch;wid=well_id(data,'foam_poor')
    d=client.get(BASE+'/wells/'+wid).json()
    assert d['well']['id']==wid and d['run']['id']==run['id']
    assert len(d['result']['evidence']['rule_results'])==11
    assert d['result']['screening_status']=='疑似异常'
    client.patch('/api/v1/wells/'+wid,json={'well_number':'演示-改号'})
    d=client.get(BASE+'/wells/'+wid,params={'run_id':run['id']}).json()
    assert d['well']['well_number']=='演示-改号'
    assert d['result']['evidence']['well_number']!='演示-改号'


@pytest.mark.parametrize('scenario',['stable','missing_data','counter_reset','foam_poor'])
def test_seven_raw_parameters_and_event_linkage(client,batch,scenario):
    data,run=batch;wid=well_id(data,scenario)
    r=client.get(BASE+'/wells/'+wid+'/series').json()
    expected=data.measurements.loc[data.measurements.well_number==next(w['well_number'] for w in data.wells if str(w['id'])==wid)]
    assert r['total']==len(expected)
    assert all(p in r['measurements'][0] for p in ('tubing_pressure_mpa','casing_pressure_mpa','back_pressure_mpa','instantaneous_flow_m3_h','cumulative_flow_m3','gas_temperature_c','liquid_rate_m3_d'))
    assert r['contains_demo'] and r['sample_minutes']==60
    assert r['measurements'][0]['measurement_id']
    assert r['measurements']==sorted(r['measurements'],key=lambda x:x['measured_at'])
    if scenario=='foam_poor':
        assert r['measures'] and any(e['anomaly_type']=='措施后未恢复' for e in r['anomalies'])
        assert dtime(r['measures'][0]['effective_start'])>=dtime(r['window_start'])
    if scenario=='counter_reset':
        values=[x['cumulative_flow_m3'] for x in r['measurements']]
        assert any(b<a for a,b in zip(values,values[1:]))


def dtime(value):return datetime.fromisoformat(value.replace('Z','+00:00'))


def test_curve_custom_window_excludes_end_and_keeps_overlapping_measures(client,batch):
    wid=well_id(batch[0],'foam_normal')
    r=client.get(BASE+'/wells/'+wid+'/series',params={'window_start':'2026-10-14T12:00:00Z','window_end':END}).json()
    assert r['total']==12 and all(dtime(x['measured_at'])<dtime(END) for x in r['measurements'])
    assert r['measures'] # 措施开始早于窗口，也须保留有效时间区间
    assert dtime(r['measures'][0]['effective_start'])<dtime(r['window_start'])


def test_bad_scope_windows_and_no_measurement_well(client,session,batch):
    wid=well_id(batch[0],'stable')
    assert client.get(BASE+'/wells/'+str(uuid4())).status_code==404
    assert client.get(BASE+'/dashboard',params={'run_id':str(uuid4())}).status_code==404
    assert client.get(BASE+'/wells',params={'screening_status':'随意正常'}).status_code==422
    assert client.get(BASE+'/wells/'+wid+'/series',params={'window_start':END,'window_end':START}).status_code==422
    assert client.get(BASE+'/wells/'+wid+'/series',params={'window_start':'2026-01-01T00:00:00Z','window_end':END}).status_code==422
    assert client.get(BASE+'/wells/'+wid+'/series',params={'window_start':'2026-10-01T00:00:00'}).status_code==422
    empty=Well(well_number='演示-空曲线',area='测试');session.add(empty);session.commit()
    assert client.get(BASE+'/wells/'+str(empty.id)).json()['result'] is None
    assert client.get(BASE+'/wells/'+str(empty.id)+'/series').json()['measurements']==[]


def test_raw_point_limit_never_silently_truncates(client,session):
    w=Well(well_number='演示-高频',area='测试');session.add(w);session.flush()
    origin=datetime(2026,10,1,tzinfo=timezone.utc)
    session.execute(insert(WellMeasurement),[{'well_id':w.id,'measured_at':origin+timedelta(seconds=i)} for i in range(20001)])
    session.commit()
    assert client.get(BASE+'/wells/'+str(w.id)+'/series',params={'window_start':START,'window_end':END}).status_code==422
