"""无 Docker 的本地骨架启动器。仅使用项目 work/ 内的演示 PostgreSQL。"""
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
from pgserver import get_server
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]

def main():
    work = ROOT / "work"
    work.mkdir(exist_ok=True)
    server = get_server(work / "dev-postgres", cleanup_mode="stop")
    url = make_url(server.get_uri()).set(drivername="postgresql+psycopg")
    env = {**os.environ, "DATABASE_URL": url.render_as_string(hide_password=False)}
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=ROOT / "backend", env=env, check=True)
    children = []
    try:
        children.append(subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"], cwd=ROOT / "backend", env=env))
        children.append(subprocess.Popen(["npm", "run", "dev", "--", "--strictPort"], cwd=ROOT / "frontend", start_new_session=True))
        print("前端 http://localhost:5173 · API文档 http://localhost:8000/docs · Ctrl+C停止", flush=True)
        while True:
            for child in children:
                code = child.poll()
                if code is not None:
                    raise RuntimeError(f"服务进程提前退出，状态码：{code}")
            threading.Event().wait(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        for child in children:
            if child.poll() is None:
                if child is children[-1] and len(children) == 2:
                    os.killpg(child.pid, signal.SIGTERM)
                else:
                    child.terminate()
        for child in children:
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                child.kill()
        # server 句柄在本进程结束时停止项目专用集群，不删除演示记录。
        del server

if __name__ == "__main__":
    main()
