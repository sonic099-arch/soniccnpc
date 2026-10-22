"""1000井分析验收：真实临时PostgreSQL、真实API依赖、逐场景对照和重算。"""
import argparse
from collections import Counter,defaultdict
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import shutil
import tempfile
import time
from uuid import UUID
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from pgserver import get_server
from sqlalchemy import create_engine,select,func
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from app.data_sources.mock import MockDataSource
from app.services.demo import load_dataset
from app.models.entities import WellAnalysisResult,WellAnomaly,WellStatusSnapshot,AnalysisRun,WellBaseline


def verify(report):
    root=Path(__file__).resolve().parents[1]
    temp=Path(tempfile.mkdtemp(prefix='beitian-analysis-verify-'))
    server=get_server(temp/'cluster',cleanup_mode='delete')
    url=make_url(server.get_uri()).set(drivername='postgresql+psycopg')
    os.environ['DATABASE_URL']=url.render_as_string(hide_password=False)
    from app.core.config import get_settings
    from app.core.database import get_engine
    get_settings.cache_clear();get_engine.cache_clear()
    from app.main import create_app
    cfg=Config(str(root/'backend/alembic.ini'));cfg.set_main_option('script_location',str(root/'backend/migrations'))
    engine=create_engine(url,isolation_level='REPEATABLE READ')
    started=time.monotonic()
    output={'warning':'模拟数据验收，不代表现场筛查准确率','checks':[]}
    try:
        command.upgrade(cfg,'head')
        print('生成并装载1000井演示数据…',flush=True)
        data=MockDataSource().generate()
        with Session(engine) as session:loaded=load_dataset(session,data)
        assert loaded['measurement_count']==335538
        app=create_app()
        with TestClient(app) as client:
            response=client.post('/api/v1/analysis/rules/bootstrap',json={'confirmed':True});assert response.status_code==200,response.text
            print('通过真实API执行1000井分析（REPEATABLE READ事务）…',flush=True)
            first=client.post('/api/v1/analysis/execute',json={'confirmed':True})
            assert first.status_code==201,first.text
            first=first.json()
            output['checks'].append({'check':'1000井任务完成','pass':first['status']=='已完成' and first['summary']['total_wells']==1000})
            output['first_run']=first
            with Session(engine) as session:
                statuses={str(r.well_id):r for r in session.scalars(select(WellAnalysisResult).where(WellAnalysisResult.analysis_run_id==UUID(first['id'])))}
                events=defaultdict(list)
                for event in session.scalars(select(WellAnomaly).where(WellAnomaly.analysis_run_id==UUID(first['id']))):events[str(event.well_id)].append(event)
                by_number={w['well_number']:str(w['id']) for w in data.wells}
                failures=[];scenario=defaultdict(lambda:dict(total=0,passed=0,failed=0))
                for expected in data.expected:
                    well_id=by_number[expected['well_number']];actual=statuses[well_id]
                    labels={e.anomaly_type for e in events[well_id]}
                    for result in actual.evidence['rule_results']:labels.update(result['metrics'].get('observed_tags',[]))
                    reasons=[]
                    if actual.screening_status!=expected['expected_screening_status']:reasons.append('筛查状态不符')
                    if actual.production_state!=expected['expected_production_state']:reasons.append('生产状态不符')
                    if not set(expected['expected_labels']).issubset(labels):reasons.append('缺少预期辅助标签')
                    if actual.screening_status=='可信正常' and events[well_id]:reasons.append('可信正常井存在异常事件')
                    if not actual.evidence.get('input_digest') or len(actual.evidence.get('rule_results',[]))!=11:reasons.append('规则证据不完整')
                    for event in events[well_id]:
                        if not event.rule_snapshot.get('version') or not event.evidence.get('provenance',{}).get('input_digest'):reasons.append('异常缺少规则或输入证据')
                    summary=scenario[expected['scenario_name']];summary['total']+=1
                    summary['failed' if reasons else 'passed']+=1
                    if reasons:failures.append({'well_number':expected['well_number'],'scenario':expected['scenario_name'],'expected':expected['expected_screening_status'],'actual':actual.screening_status,'production':actual.production_state,'labels':sorted(labels),'reasons':reasons})
                output.update(samples_total=len(data.wells),samples_passed=len(data.wells)-len(failures),samples_failed=len(failures),failure_reasons=failures,scenarios=dict(scenario))
                output['checks'].append({'check':'13场景1000样本状态及标签对照','pass':not failures})
                if failures:
                    report.parent.mkdir(parents=True,exist_ok=True);report.write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
                assert not failures,failures[:3]
                first_fingerprints={e.fingerprint for records in events.values() for e in records}
            print('验证默认异常列表筛除正常井与第二次重算…',flush=True)
            all_events=[]
            for offset in range(0,len(first_fingerprints),500):
                page=client.get('/api/v1/analysis/anomalies',params={'offset':offset,'limit':500}).json()
                all_events.extend(page['items'])
            assert all(e['screening_status']!='可信正常' for e in all_events)
            assert len(all_events)==len(first_fingerprints)
            output['checks'].append({'check':'默认异常列表不含可信正常井且完整分页','pass':True,'events':len(all_events)})
            second=client.post('/api/v1/analysis/execute',json={'confirmed':True});assert second.status_code==201,second.text
            second=second.json();assert second['summary']['status_counts']==first['summary']['status_counts']
            assert client.get('/api/v1/analysis/anomalies').json()['total']==len(first_fingerprints)
            with Session(engine) as session:
                assert session.scalar(select(func.count()).select_from(WellAnalysisResult))==2000
                assert session.scalar(select(func.count()).select_from(WellStatusSnapshot))==1000
                second_prints=set(session.scalars(select(WellAnomaly.fingerprint).where(WellAnomaly.analysis_run_id==UUID(second['id']))))
                assert second_prints==first_fingerprints
                assert session.scalar(select(func.count()).select_from(WellBaseline))==2000
            output['checks'].append({'check':'重复分析保留2000条历史结果，最新快照1000条，列表不重复','pass':True})
            # 使用API发布规则，不覆盖历史配置，再执行整批重算。
            print('验证发布新规则版本并整批重算…',flush=True)
            current=next(r for r in client.get('/api/v1/analysis/rules').json()['items'] if r['code']=='FL001')
            changed=client.post('/api/v1/analysis/rules/FL001/versions',json={'version':'1.0.1','configuration':{**current['configuration'],'decline_ratio':.95}})
            assert changed.status_code==201,changed.text
            third=client.post('/api/v1/analysis/execute',json={'confirmed':True});assert third.status_code==201,third.text
            third=third.json()
            abnormal=next(e for e in data.expected if e['scenario']=='abnormal_decline')
            check=client.get('/api/v1/analysis/results',params={'run_id':third['id'],'search':abnormal['well_number']}).json()['items'][0]
            assert check['screening_status']=='可信正常'
            old=client.get('/api/v1/analysis/results',params={'run_id':first['id'],'search':abnormal['well_number']}).json()['items'][0]
            assert old['screening_status']=='疑似异常'
            output['checks'].append({'check':'新版本重算生效且历史结论与规则快照保留','pass':True})
            output['recalculated_run_id']=third['id']
            assert client.get('/ready').json()['revision']=='0002_analysis_results'
            output['checks'].append({'check':'新迁移及服务就绪','pass':True})
        output['elapsed_seconds']=round(time.monotonic()-started,2)
        report.parent.mkdir(parents=True,exist_ok=True);report.write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
        print(json.dumps({k:v for k,v in output.items() if k not in ('first_run',)},ensure_ascii=False,indent=2))
    finally:
        engine.dispose()
        if get_engine.cache_info().currsize:get_engine().dispose();get_engine.cache_clear()
        server.cleanup();shutil.rmtree(temp,ignore_errors=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report',type=Path,default=Path('work/task3-full-check.json'))
    verify(parser.parse_args().report)
