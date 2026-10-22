# 北田公司气井智能分析系统

当前交付至 **任务2：可运行骨架、模拟数据生成与Excel确认导入**。后端 Python 3.12 / FastAPI / SQLAlchemy / PostgreSQL，前端 Vue3 / TypeScript / Element Plus，已安装 ECharts，数据处理使用 Pandas / NumPy / OpenPyXL。

已实现14个实体、基础CRUD、迁移、600井确定性模拟数据及带映射确认的Excel导入。异常分析引擎在任务3实现；首页统计、气井列表、异常列表及单井曲线在任务4实现。当前除Excel导入页外，业务页面仍明确显示占位提示。

所有模拟数据、曲线、参数和预期标签均为演示用途，不构成现场工艺判定标准，也不能用于宣传生产异常筛查准确率。第七动态参数暂定“产液量”，尚待现场口径确认。

## Win11 + WSL2 Ubuntu 24.04 LTS

以下命令在Ubuntu终端执行；项目建议放在Linux目录 `~/projects`，不与Windows共用虚拟环境。Python 3.14不在当前支持范围内。

先安装 Python 3.12、Git及Node.js 22或24。已有这些工具可跳过：

```bash
sudo apt update
sudo apt install -y python3.12 python3.12-venv git curl build-essential
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt install -y nodejs
```

下载私有仓库需使用你自己的GitHub认证，不要将令牌写入仓库URL或源码：

```bash
mkdir -p ~/projects
cd ~/projects
git clone https://github.com/sonic099-arch/soniccnpc.git
cd soniccnpc/beitian-gas
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r backend/requirements-dev.lock
python -m pip install --no-deps -e ./backend
cd frontend
npm ci
cd ..
python scripts/dev.py
```

快捷启动器在项目 `work/dev-postgres` 建立独立演示PostgreSQL，执行迁移，再启动前后端；忽略 `.env` 中的数据库地址。Ctrl+C停止，演示数据保留。该方式无需额外安装PostgreSQL或Docker，已在Linux x86_64 / Python3.12 / PostgreSQL16.2验证。原生Windows请使用WSL2，或按下文分别启动现有PostgreSQL与服务；pgserver未在原生Windows验证。

- 网页：http://localhost:5173
- Excel导入页：http://localhost:5173/import
- Swagger接口调试：http://localhost:8000/docs
- ReDoc：http://localhost:8000/redoc
- 存活检查 `/health`；数据库迁移就绪 `/ready`。

### 已有任务1代码时如何更新

先在原启动终端按Ctrl+C，再执行：

```bash
cd ~/projects/soniccnpc/beitian-gas
git pull --ff-only
source .venv/bin/activate
python -m pip install -r backend/requirements-dev.lock
python -m pip install --no-deps -e ./backend
cd frontend
npm ci
cd ..
python scripts/dev.py
```

如果项目不在上述路径，替换为实际路径。`git pull` 提示本地修改时，先保存自己的改动，不要强制覆盖。任务2未改变实体列结构，现有 `0001_initial` 迁移仍适用，不需要删除数据库。

## 网页验证任务2

进入左侧 **Excel导入**：

1. 下载“演示样例”，得到三行测量数据。
2. 选择这个xlsx文件，点击“上传并识别字段”。此时没有写入测量数据。
3. 核对字段、源单位和时区。样例是新井，勾选“允许创建新井”，填写工区，保留“演示数据”。
4. 勾选“我已确认映射、源单位、时区和数据性质”，点击“确认并导入”。首次预期成功3、失败0；再次上传同文件应重复3、新增0。
5. 下载完整报告；有失败时，按Excel原始行号修正源文件后重新上传。
6. 页面底部勾选演示数据确认，点击“生成并加载600口演示井”。预期600口井、201324条测量记录，以及配置、工具、措施和开关井事件。耗时可能为几十秒到几分钟，请等待。

可通过Swagger的 `GET /api/v1/wells` 查询井，通过 `GET /api/v1/measurements?well_id=某井UUID` 查询测量，通过 `GET /api/v1/measure-events?well_id=某井UUID` 查询措施。这里只验证数据接入，尚未输出异常分析结果。

## 生成Excel与场景预期文件

在项目根目录、已激活虚拟环境时执行：

```bash
python scripts/generate_mock.py --count 600 --days 14 --seed 20261021 --output work/mock600
```

生成：

- `standard-template.xlsx`：标准空模板。
- `example.xlsx`：三行简单样例。
- `mock-data.xlsx`：完整测量数据、井信息、配置、工具、措施、操作和场景预期工作表。
- `manifest.json`：井/事件关联及逐井预期状态、标签和场景起点。

参数支持13至5000口井、4至90天，单批最多100万条测量记录。默认固定起始时间2026-10-01 UTC、种子20261021。相同参数的记录、UUID、预期清单和xlsx字节均可重复。包含13类场景，详见 `docs/TASK2_GUIDE.md`。

仓库 `examples/` 已提供标准模板、三行样例、13场景小样及其预期清单；完整600井文件约14MiB，运行脚本本地生成，不将大量重复演示文件提交Git。

如需脚本向 `.env` 或 `DATABASE_URL` 指定的开发库显式加载，先完成迁移，再添加 `--load`：

```bash
python scripts/generate_mock.py --count 600 --days 14 --output work/mock600 --load
```

快捷启动器使用的本地集群由网页“生成600井”按钮加载最方便；`--load`读取的是调用脚本时的数据库配置，不会自动接管快捷启动器的地址。同一配置重复加载不会重复写入；修改种子/井数/日期但占用相同演示井号会拒绝操作，避免混合两个模拟批次。

## 常规PostgreSQL或Docker启动

```bash
cp .env.example .env
```

修改占位密码及数据库地址，使Compose和 `DATABASE_URL` 的用户、密码、库名一致；URL特殊字符须编码。仅供本机开发，管理接口当前没有认证权限体系。

```bash
docker compose up -d --wait db
cd backend
alembic upgrade head
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

另开终端启动前端：

```bash
cd frontend
npm run dev
```

如已有PostgreSQL16，先建立独立开发库，跳过Compose。应用不自动建表，必须显式迁移。`alembic downgrade base` 会删除业务表，只能对可丢弃开发库使用。前端开发代理 `/api`、`/health`、`/ready`；部署反向代理在后续阶段处理。

## 自动验证

```bash
cd backend
pytest --junitxml=../work/backend-tests.xml
cd ../frontend
npm test
npm run build
cd ..
python scripts/export_openapi.py
```

后端测试只使用临时独立PostgreSQL，不访问`.env`数据库。前端测试包括真实组件交互，检查预览不写入、勾选确认后才允许提交、换文件清除旧确认状态。

可选的600井整批验证（运行数分钟，独立临时数据库，结束后清理）：

```bash
python scripts/verify_demo.py --workbook work/mock600/mock-data.xlsx --report work/task2-full-check.json
```

不传 `--workbook` 则自动生成默认600井文件在内存中验证。静态接口契约位于 `docs/openapi.json`；历史任务1报告保留，任务2结果见 `docs/TASK2_REPORT.md`。

## 目录与后续

`backend/app/models`为14实体；`api`和`schemas`为基础接口；`data_sources`为Excel/Mock/Database统一接入；`services`为确认导入和演示装载；`migrations`为Alembic；`frontend/src/views/DataImport.vue`为可用导入页；`scripts`为启动、生成、验证和文档导出；`examples`为标准模板与模拟样本；`AGENTS.md`记录长期约束。

代码同步至授权私有仓库 `sonic099-arch/soniccnpc` 的 `beitian-gas/`，保留仓库根README和历史；不提交 `.env`、虚拟环境、node_modules、本地数据库或用户上传的Excel。Excel暂存默认在 `work/imports`，可用 `IMPORT_STORAGE_DIR`更改，当前须由开发者按需清理；删除暂存文件后，未确认任务须重新上传。

接下来按顺序完成任务3分析引擎、任务4业务页面及曲线、任务5联调验收；本次只交付到任务2。
