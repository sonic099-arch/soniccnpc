"""任务4真实浏览器验收：独立PostgreSQL，1000演示井+1手工测试井，不读取或清理现有库。"""
import argparse
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from urllib.request import urlopen
from uuid import UUID
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from pgserver import get_server
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from app.data_sources.mock import MockDataSource
from app.services.demo import load_dataset
from app.models.entities import Well,WellMeasurement

def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0))
        return sock.getsockname()[1]

def wait_http(url,process):
    for _ in range(150):
        if process.poll() is not None:raise RuntimeError('验证服务提前退出，请查看work/task4-server.log')
        try:
            with urlopen(url,timeout=2) as response:
                if response.status==200:return
        except OSError:pass
        time.sleep(.2)
    raise RuntimeError('验证服务启动超时')

def verify(report,skip_browser=False):
    root=Path(__file__).resolve().parents[1];work=root/'work';work.mkdir(exist_ok=True)
    temp=Path(tempfile.mkdtemp(prefix='beitian-web-verify-'))
    server=get_server(temp/'cluster',cleanup_mode='delete')
    url=make_url(server.get_uri()).set(drivername='postgresql+psycopg')
    os.environ['DATABASE_URL']=url.render_as_string(hide_password=False)
    from app.core.config import get_settings
    from app.core.database import get_engine
    get_settings.cache_clear();get_engine.cache_clear()
    from app.main import create_app
    cfg=Config(str(root/'backend/alembic.ini'));cfg.set_main_option('script_location',str(root/'backend/migrations'))
    engine=create_engine(url);children=[];log=None;started=time.monotonic()
    result={'warning':'仅为模拟数据和开发环境验收，不代表现场准确率','checks':[]}
    def check(name,passed,**values):
        result['checks'].append({'check':name,'pass':bool(passed),**values})
        if not passed:raise AssertionError(name)
    try:
        command.upgrade(cfg,'head')
        print('装载1000井335538条测量及额外手工测试井…',flush=True)
        data=MockDataSource().generate()
        with Session(engine) as session:
            load_dataset(session,data)
            extra=Well(well_number='演示-手工测试井',area='手工测试工区',is_demo=True)
            session.add(extra);session.flush()
            session.add(WellMeasurement(well_id=extra.id,measured_at=datetime(2026,10,22,tzinfo=timezone.utc),instantaneous_flow_m3_h=100,is_demo=True))
            session.commit()
        with TestClient(create_app()) as client:
            client.post('/api/v1/analysis/rules/bootstrap',json={'confirmed':True})
            print('重现较新手工采样推晚窗口，再返回指定演示窗口…',flush=True)
            late=client.post('/api/v1/analysis/execute',json={'confirmed':True});assert late.status_code==201,late.text
            check('重现默认较晚窗口1001井数据待核实',late.json()['summary']['status_counts']['数据待核实']==1001)
            correct=client.post('/api/v1/analysis/execute',json={'confirmed':True,'window_start':'2026-10-01T00:00:00Z','window_end':'2026-10-15T00:00:00Z'})
            assert correct.status_code==201,correct.text
            run=correct.json();result['run_id']=run['id']
            dashboard=client.get('/api/v1/screening/dashboard').json();result['dashboard']=dashboard
            expected={'可信正常':308,'疑似异常':385,'措施影响':77,'数据待核实':231,'工况待核实':0,'未分析':0}
            check('首页默认最新完成任务且1001井状态统计准确',dashboard['run']['id']==run['id'] and dashboard['status_counts']==expected)
            wells=client.get('/api/v1/screening/wells',params={'non_normal':True,'limit':500}).json()
            check('默认需复核井按井去重共693口',wells['total']==693 and len({w['well_id'] for w in wells['items']})==len(wells['items']) and all(w['screening_status']!='可信正常' for w in wells['items']))
            check('历史任务可切换且旧结论保留',client.get('/api/v1/screening/dashboard',params={'run_id':late.json()['id']}).json()['status_counts']['数据待核实']==1001)
            problems=[]
            for item in data.expected:
                rows=client.get('/api/v1/screening/wells',params={'search':item['well_number']}).json()['items']
                if len(rows)!=1 or rows[0]['screening_status']!=item['expected_screening_status']:problems.append(item['well_number'])
            result.update(samples_total=1000,samples_passed=1000-len(problems),samples_failed=len(problems),failure_reasons=problems)
            check('1000演示井展示状态逐井对照',not problems)
            for scenario in ['foam_poor','missing_data','counter_reset']:
                exp=next(x for x in data.expected if x['scenario']==scenario)
                wid=next(str(w['id']) for w in data.wells if w['well_number']==exp['well_number'])
                curve=client.get(f'/api/v1/screening/wells/{wid}/series').json()
                assert curve['total']==(330 if scenario=='missing_data' else 336)
                assert len([k for k in curve['measurements'][0] if k in ('tubing_pressure_mpa','casing_pressure_mpa','back_pressure_mpa','instantaneous_flow_m3_h','cumulative_flow_m3','gas_temperature_c','liquid_rate_m3_d')])==7
            check('七参数全量原始曲线及缺失/复位/措施场景',True)
        if not skip_browser:
            print('启动隔离前后端并执行Chromium浏览器测试…',flush=True)
            api_port,web_port=free_port(),free_port()
            env={**os.environ,'BEITIAN_API_URL':f'http://127.0.0.1:{api_port}','BEITIAN_WEB_URL':f'http://127.0.0.1:{web_port}'}
            if not env.get('PLAYWRIGHT_CHROMIUM_EXECUTABLE') and shutil.which('chromium'):
                env['PLAYWRIGHT_CHROMIUM_EXECUTABLE']=shutil.which('chromium')
            log=(work/'task4-server.log').open('w')
            api=subprocess.Popen([sys.executable,'-m','uvicorn','app.main:app','--host','127.0.0.1','--port',str(api_port)],cwd=root/'backend',env=env,stdout=log,stderr=log)
            children.append(api);wait_http(f'http://127.0.0.1:{api_port}/ready',api)
            web=subprocess.Popen(['node','node_modules/vite/bin/vite.js','--host','127.0.0.1','--port',str(web_port),'--strictPort'],cwd=root/'frontend',env=env,stdout=log,stderr=log)
            children.append(web);wait_http(env['BEITIAN_WEB_URL'],web)
            browser=subprocess.run(['npm','run','test:e2e'],cwd=root/'frontend',env=env)
            check('Chromium六项真实页面端到端测试',browser.returncode==0)
        result['elapsed_seconds']=round(time.monotonic()-started,2)
    finally:
        for child in children:
            child.terminate()
        for child in children:
            try:child.wait(timeout=10)
            except subprocess.TimeoutExpired:child.kill();child.wait()
        if log:log.close()
        engine.dispose()
        if get_engine.cache_info().currsize:get_engine().dispose();get_engine.cache_clear()
        server.cleanup();shutil.rmtree(temp,ignore_errors=True)
        report.parent.mkdir(parents=True,exist_ok=True);report.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps(result,ensure_ascii=False,indent=2),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report',type=Path,default=Path('work/task4-full-check.json'))
    parser.add_argument('--skip-browser',action='store_true',help='仅运行全量API验证，不启动浏览器')
    args=parser.parse_args();verify(args.report,args.skip_browser)
