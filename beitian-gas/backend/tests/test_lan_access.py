"""内网边界、伪造头、静态页面和实际HTTP代理测试；不改宿主防火墙。"""
from concurrent.futures import ThreadPoolExecutor
from http.client import HTTPConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import json
from pathlib import Path
import sys
from threading import Thread
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.api.web import mount_web

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('beitian_lan_gateway',ROOT/'scripts/lan_gateway.py')
gateway=importlib.util.module_from_spec(spec);sys.modules[spec.name]=gateway;spec.loader.exec_module(gateway)

@pytest.mark.parametrize('ip,expected',[
 ('10.86.36.1',True),('10.86.36.43',True),('10.86.36.254',True),('10.86.36.255',True),
 ('10.86.36.0',False),('10.86.35.255',False),('10.86.37.1',False),('192.168.1.1',False),
 ('127.0.0.1',False),('::1',False),('::ffff:10.86.36.43',True),('::ffff:10.86.37.1',False),
 ('10.86.36.43.evil',False),('unknown',False),('2001:db8::1',False)])
def test_exact_inclusive_address_range(ip,expected):
    assert gateway.allowed_client(ip) is expected

class Upstream(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path=='/redirect':
            self.send_response(307);self.send_header('Location',f'http://127.0.0.1:{self.server.server_port}/wells/');self.end_headers();return
        if self.path=='/chunked':
            self.protocol_version='HTTP/1.1';self.send_response(200);self.send_header('Transfer-Encoding','chunked');self.end_headers();self.wfile.write(b'5\r\nhello\r\n0\r\n\r\n');return
        self.reply()
    def do_POST(self):self.reply()
    do_PATCH=do_DELETE=do_OPTIONS=do_HEAD=do_POST
    def reply(self):
        body=self.rfile.read(int(self.headers.get('Content-Length','0')))
        result=json.dumps({'path':self.path,'method':self.command,'body':body.decode(),'headers':dict(self.headers)}).encode()
        self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(result)));self.end_headers()
        if self.command!='HEAD':self.wfile.write(result)
    def log_message(self,*args):pass

@pytest.fixture
def servers():
    upstream=ThreadingHTTPServer(('127.0.0.1',0),Upstream)
    config=gateway.GatewayConfig(listen='127.0.0.1',port=0,upstream_port=upstream.server_port,
        allowed_start='127.0.0.1',allowed_end='127.0.0.1',max_body_bytes=1024)
    entry=gateway.GatewayServer(config)
    threads=[Thread(target=s.serve_forever,daemon=True) for s in (upstream,entry)]
    for t in threads:t.start()
    yield upstream,entry
    for s in (entry,upstream):s.shutdown();s.server_close()
    for t in threads:t.join(timeout=5)


def call(entry,path='/',method='GET',body=None,headers=None,source='127.0.0.1'):
    c=HTTPConnection('127.0.0.1',entry.server_port,source_address=(source,0),timeout=5)
    c.request(method,path,body,headers or {})
    r=c.getresponse();result=(r.status,r.read(),dict(r.getheaders()));c.close();return result

@pytest.mark.parametrize('path',['/','/wells/uuid','/assets/app.js','/docs','/openapi.json','/api/v1/wells'])
def test_disallowed_source_blocked_for_every_resource_even_with_forged_headers(servers,path):
    _,entry=servers
    code,body,_=call(entry,path,source='127.0.0.2',headers={'X-Forwarded-For':'127.0.0.1','X-Real-IP':'127.0.0.1','Forwarded':'for=127.0.0.1'})
    assert code==403 and '访问被拒绝' in body.decode()

@pytest.mark.parametrize('method',['GET','POST','PATCH','DELETE','HEAD','OPTIONS'])
def test_allowed_methods_forward_real_payload_and_strip_spoofed_hop_headers(servers,method):
    _,entry=servers
    code,body,_=call(entry,'/api/v1/analysis/execute',method,body=b'{"confirmed":true}',headers={
        'Content-Type':'application/json','X-Forwarded-For':'10.86.36.43','Forwarded':'for=10.86.36.43',
        'Connection':'X-Evil','X-Evil':'discard','X-Real-IP':'10.86.36.43'})
    assert code==200
    if method=='HEAD':assert body==b'';return
    r=json.loads(body);lower={k.lower() for k in r['headers']}
    assert r['body']=='{"confirmed":true}' and r['method']==method
    assert not lower.intersection({'x-forwarded-for','forwarded','x-evil','x-real-ip'})


def test_host_header_and_outside_source_cannot_bypass(servers):
    _,entry=servers
    assert call(entry,headers={'Host':'evil.example'})[0]==403
    assert call(entry,headers={'Host':entry.public_authority},source='127.0.0.2')[0]==403


def test_redirect_rewritten_and_chunked_response_decoded(servers):
    _,entry=servers
    code,_,headers=call(entry,'/redirect');assert code==307
    assert headers['Location']==f'http://{entry.public_authority}/wells/'
    code,body,headers=call(entry,'/chunked');assert code==200 and body==b'hello'
    assert 'Transfer-Encoding' not in headers


def test_oversized_requests_and_upgrade_are_refused(servers):
    _,entry=servers
    assert call(entry,method='POST',body=b'x'*1025)[0]==413
    assert call(entry,headers={'Upgrade':'websocket'})[0]==400
    assert call(entry,headers={'Transfer-Encoding':'chunked'})[0]==400
    assert call(entry,headers={'Content-Length':'-1'})[0]==400


def test_concurrent_requests_remain_isolated(servers):
    _,entry=servers
    with ThreadPoolExecutor(max_workers=4) as pool:
        results=list(pool.map(lambda i:call(entry,f'/api/v1/wells?offset={i}'),range(8)))
    assert all(r[0]==200 for r in results)
    assert len({json.loads(r[1])['path'] for r in results})==8


def test_unavailable_backend_returns_chinese_error(servers):
    upstream,entry=servers;upstream.shutdown();upstream.server_close()
    code,body,_=call(entry)
    assert code==502 and 'Ubuntu' in body.decode()

@pytest.fixture
def static_app(tmp_path):
    (tmp_path/'docs-assets').mkdir();(tmp_path/'assets').mkdir()
    (tmp_path/'index.html').write_text('<html><body>北田测试</body></html>')
    for name in ['swagger-ui-bundle.js','swagger-ui.css','favicon-32x32.png']:(tmp_path/'docs-assets'/name).write_bytes(b'local-asset')
    (tmp_path/'assets'/'app.js').write_text('console.log("offline")')
    app=FastAPI(docs_url=None,redoc_url=None)
    @app.get('/api/v1/wells')
    def wells():return {'items':[]}
    mount_web(app,tmp_path)
    return app


def test_static_spa_routes_and_api_are_separate(static_app):
    with TestClient(static_app) as c:
        for p in ['/','/wells','/wells/well-id','/anomalies','/analysis']:
            assert '北田测试' in c.get(p).text
        assert c.get('/api/v1/wells').json()=={'items':[]}
        for p in ['/api/v1/no-such-route','/assets/missing.js','/.env','/.git/config','/../secret.txt','/docs-assets/missing.js']:
            assert c.get(p).status_code==404
        assert c.get('/assets/app.js').text=='console.log("offline")'


def test_swagger_uses_only_local_assets(static_app):
    with TestClient(static_app) as c:
        html=c.get('/docs').text
        assert '/docs-assets/swagger-ui-bundle.js' in html
        assert 'cdn.jsdelivr.net' not in html and 'https://' not in html
        assert c.get('/docs-assets/swagger-ui.css').content==b'local-asset'
        assert c.get('/redoc',follow_redirects=False).headers['location']=='/docs'


def test_missing_build_does_not_start_static_server(tmp_path):
    with pytest.raises(RuntimeError,match='缺少内网构建文件'):mount_web(FastAPI(),tmp_path)
