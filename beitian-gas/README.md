# 北田公司气井智能分析系统

当前交付：**任务1，可运行的项目骨架**。已实现14个实体、70个基础 CRUD 操作、Alembic 初始迁移、中文前端导航和服务连通检查。没有实现模拟数据、Excel导入或异常分析，也不展示虚构统计结果。

## 环境

- Python **3.12**、Node.js **22或24**、npm。
- 常规开发使用 PostgreSQL **16** 与 Docker Compose；也可使用现有本地 PostgreSQL。
- 自动测试使用 pgserver 启动临时独立 PostgreSQL 16.2 集群，无需 Docker，不连接任何已有数据库。此方式已在 Linux x86_64 验证；其他平台若 pgserver 无兼容包，请使用支持的平台运行测试。

## 安装

在解压后的项目根目录执行：

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements-dev.lock
python -m pip install --no-deps -e ./backend
cd frontend
npm ci
cd ..
```

Python 依赖锁定文件由本次 Linux / Python 3.12 环境验证生成。`backend/pyproject.toml` 是直接依赖定义，后续更新依赖时需重新生成锁文件并回归。Windows 使用 `.venv\Scripts\activate`，推荐在 Linux 或 WSL2 启动测试与快捷开发模式。

## 快捷启动（本地演示，不需要 Docker）

安装上述开发依赖后，在根目录运行：

```bash
python scripts/dev.py
```

自动创建 `work/dev-postgres` 专用本地演示集群，执行迁移，再启动前后端。数据保存在此目录；Ctrl+C 停止服务。该模式忽略 `.env` 中的数据库地址，以避免连接已有数据库。数据库仅用于本机开发，不要暴露到公网。

- 网页：http://localhost:5173
- Swagger API文档：http://localhost:8000/docs
- ReDoc：http://localhost:8000/redoc
- 存活检查：http://localhost:8000/health
- 数据库与迁移就绪检查：http://localhost:8000/ready

## 使用 Docker PostgreSQL 或现有 PostgreSQL

```bash
cp .env.example .env
```

修改 `.env` 中的密码及 `DATABASE_URL`，保持 Compose 和 URL 的用户名、密码、库名一致。URL 的特殊字符必须编码。密码只放 `.env`，不会提交 Git。

```bash
docker compose up -d --wait db
cd backend
alembic upgrade head
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

另开终端，在项目根目录执行：

```bash
cd frontend
npm run dev
```

如使用已有 PostgreSQL，先创建独立开发数据库，跳过 `docker compose`。应用启动不会自动建表；必须显式执行迁移。`alembic downgrade base` 会删除当前库全部业务表，只能对可丢弃的开发库执行。

前端开发代理 `/api`、`/health` 和 `/ready` 到 `127.0.0.1:8000`；生产构建需由后续部署阶段配置反向代理。当前管理接口没有登录与权限体系，只绑定本机，适用于开发骨架验收。

## 验证

```bash
cd backend
pytest --junitxml=../work/backend-tests.xml
cd ../frontend
npm test
npm run build
cd ..
python scripts/export_openapi.py
```

后端测试自行创建并清理临时 PostgreSQL 集群，不使用 `.env` 数据库。测试覆盖14类实体的完整 CRUD、迁移往返和模型一致性、外键、去重约束、时区、时间区间、版本及证据存取等。测试数据都是合成样本，不能作为现场筛查准确率。任务3再添加异常规则和算法回归测试。

`docs/openapi.json` 是可直接导入接口工具的静态 API 文档；`docs/API.md` 提供资源表与调用示例。

## 文件结构

```text
backend/
  app/core/             环境配置、连接池和会话
  app/models/           14个SQLAlchemy实体及关系
  app/schemas/          有类型的请求、更新和响应契约
  app/api/              资源注册、基础CRUD
  app/data_sources/     标准记录接口、数据库测试桩
  app/analysis/         任务3预留目录，当前无算法
  migrations/           Alembic初始迁移
  tests/                隔离PostgreSQL集成测试
frontend/src/           Vue、TypeScript、Element Plus导航和占位页面
scripts/               无Docker开发启动、API文档导出
docs/                  架构、数据字典、接口契约和任务1验收记录
compose.yaml           PostgreSQL开发服务
.env.example           配置模板（占位密码）
AGENTS.md              长期开发约束
```

## Git 与交付边界

源码压缩包保留本地 `.git` 历史，可执行 `git log -1 --oneline` 和 `git status --short` 检查。未配置任何外部代码托管地址。`work/`、虚拟环境、node_modules、真实环境配置均不入库。

- 任务2：600井确定性模拟生成、场景预期标签、Excel模板及映射确认导入。
- 任务3：分析模块、可配置规则、事件归并、证据链与规则回归。
- 任务4：首页统计、气井/异常列表、单井曲线与筛选。
- 任务5：联调、验收和完整运行文档。

七个参数中的第七项暂定为“产液量 m³/d”；原任务书明确列出了其余六项。此项需要在任务2生成模板前确认。演示参数不能作为现场工艺判定标准。
