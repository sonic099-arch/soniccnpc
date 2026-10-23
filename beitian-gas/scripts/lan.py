"""WSL内网服务：构建静态网页，复用原演示库，后端仅监听127.0.0.1。"""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
from pgserver import get_server
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]


def build_frontend(skip=False):
    dist = ROOT / 'frontend' / 'dist'
    if not skip:
        subprocess.run(['npm', 'run', 'build'], cwd=ROOT / 'frontend', check=True)
        source = ROOT / 'frontend' / 'node_modules' / 'swagger-ui-dist'
        target = dist / 'docs-assets'
        target.mkdir(exist_ok=True)
        for name in ['swagger-ui-bundle.js', 'swagger-ui.css', 'favicon-32x32.png', 'LICENSE', 'NOTICE']:
            shutil.copyfile(source / name, target / name)
    required = [dist / 'index.html', dist / 'docs-assets' / 'swagger-ui-bundle.js', dist / 'docs-assets' / 'swagger-ui.css', dist / 'docs-assets' / 'favicon-32x32.png']
    if not all(p.is_file() for p in required):
        raise RuntimeError('缺少网页或离线接口文档构建文件，请先npm ci，再运行 python scripts/lan.py')
    return dist


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--skip-build', action='store_true', help='复用已构建网页和离线文档，断网启动时使用')
    args = parser.parse_args()
    dist = build_frontend(args.skip_build)
    work = ROOT / 'work'
    work.mkdir(exist_ok=True)
    # 与scripts/dev.py使用完全相同的库目录，不生成、删除或覆盖任何业务数据。
    server = get_server(work / 'dev-postgres', cleanup_mode='stop')
    url = make_url(server.get_uri()).set(drivername='postgresql+psycopg')
    env = {**os.environ, 'DATABASE_URL': url.render_as_string(hide_password=False),
           'SERVE_FRONTEND': 'true', 'WEB_DIST_DIR': str(dist)}
    subprocess.run([sys.executable, '-m', 'alembic', 'upgrade', 'head'], cwd=ROOT / 'backend', env=env, check=True)
    child = None
    try:
        child = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1',
            '--port', '8000', '--no-proxy-headers'], cwd=ROOT / 'backend', env=env)
        print('本机后端 http://127.0.0.1:8000 · Windows内网入口 http://10.86.36.43:8080', flush=True)
        print('请在Windows运行start_lan.ps1；此终端保持运行，Ctrl+C停止，原数据库保留。', flush=True)
        code = child.wait()
        if code:
            raise SystemExit(code)
    except KeyboardInterrupt:
        pass
    finally:
        if child and child.poll() is None:
            child.terminate()
            try:child.wait(timeout=10)
            except subprocess.TimeoutExpired:child.kill();child.wait()
        del server

if __name__ == '__main__':
    main()
