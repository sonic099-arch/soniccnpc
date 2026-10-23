# 北田公司气井智能分析系统

当前交付至 **任务4：首页、气井列表、异常列表和单井7参数曲线**，默认演示规模已扩容至 **1000口井**。后端 Python 3.12 / FastAPI / SQLAlchemy / PostgreSQL，前端 Vue3 / TypeScript / Element Plus，已安装 ECharts，数据处理使用 Pandas / NumPy / OpenPyXL。

已实现15个实体、基础CRUD、迁移、1000井确定性模拟数据、Excel确认导入，以及10个分析模块、11条版本化规则、逐井筛查和证据追溯。网页现已接入首页统计、全部气井列表、按井去重的异常列表、逐事件证据，以及单井7参数原始曲线。Excel导入、运行分析和规则配置继续可用；独立生产措施管理页面尚未实现，留待任务5联调补齐。

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

需要GitHub认证时使用你自己的凭据，不要将令牌写入仓库URL或源码：

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

### 已有代码时如何更新

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

如果项目不在上述路径，替换为实际路径。`git pull` 提示本地修改时，先保存自己的改动，不要强制覆盖。任务4无新表或迁移，继续使用任务3的 `0002_analysis_results`。快捷启动器会升级到head并保留已有井、测量与事件；不要删除数据库。手动部署需先运行 `alembic upgrade head`。

## 网页验证任务2

进入左侧 **Excel导入**：

1. 下载“演示样例”，得到三行测量数据。
2. 选择这个xlsx文件，点击“上传并识别字段”。此时没有写入测量数据。
3. 核对字段、源单位和时区。样例是新井，勾选“允许创建新井”，填写工区，保留“演示数据”。
4. 勾选“我已确认映射、源单位、时区和数据性质”，点击“确认并导入”。首次预期成功3、失败0；再次上传同文件应重复3、新增0。
5. 下载完整报告；有失败时，按Excel原始行号修正源文件后重新上传。
6. 页面底部勾选演示数据确认，点击“生成并加载1000口演示井”。预期1000口井、335538条测量记录，以及配置、工具、措施和开关井事件。耗时可能为几十秒到几分钟，请等待。

可通过Swagger的 `GET /api/v1/wells` 查询井，通过 `GET /api/v1/measurements?well_id=某井UUID` 查询测量，通过 `GET /api/v1/measure-events?well_id=某井UUID` 查询措施。数据加载后，按下节执行任务3分析。

## 网页验证任务3

如果已经看到“生成完成：1000口井，335538条测量记录”，不要再次清库或重新生成，直接分析已有数据：

1. 进入左侧 **运行分析**（http://localhost:5173/analysis），点击“初始化演示规则”。已有规则不会被覆盖。
2. 工区、数据窗口先留空。勾选运行确认，点击“执行分析”，等待任务完成。
3. 默认1000井批次预期：可信正常308、疑似异常385、措施影响77、数据待核实230、工况待核实0。额外导入/手动创建的井也参与分析，结果可能不同。
4. 下方列表排除可信正常井；点击“证据”，查看规则版本、采样值、措施关联与技术追溯记录。
5. 进入 **规则配置**，修改阈值并发布新版本，再回到运行分析重新执行；历史任务保留原规则和判断。

默认分析窗口为2026-10-01至2026-10-15 UTC，按最新采样确定终点，不是当前实时时刻。时间窗口结束不含；网页结果显示北京时间。规则仍为演示参数，不能当作现场标准。

详细规则、接口、测试和边界见 [任务3说明](docs/TASK3_GUIDE.md) 与 [任务3验收报告](docs/TASK3_REPORT.md)。

## 网页验证任务4

已有1001井且分析得到308/385/77/231的用户，更新并重启即可查看，不需要重新导入或生成。

- 系统首页 `/`：全部登记井、可信正常、疑似异常、措施影响、数据待核实、工况待核实及未分析数量；状态卡可进入井列表；同时展示状态分布和工区统计。
- 气井列表 `/wells`：井号、工区、状态、生产状态与事件类型；井号搜索、工区/状态/异常类型筛选、事件时间过滤、分页及查看曲线。
- 异常井列表 `/anomalies`：默认一井一行、排除可信正常井，措施影响和待核实也保留；可切换逐事件列表，打开规则证据。
- 单井 `/wells/井UUID`：七条ECharts原始曲线，末7/14/30天或自选范围，统一时间轴联动缩放；蓝线标措施开始、浅蓝区标有效期、橙线标异常开始。查看措施、操作、异常和全部规则执行结果。

四页使用相同“分析任务”口径，默认取最近完成的一次引擎任务（按完成时间），可以切换历史任务查看不同窗口。此默认值与旧 `/analysis/results` 的按数据窗口最新快照接口不同，避免先分析10月22日再改回10月15日后，首页仍显示旧窗口结果。原快照保护策略保持不变。

已分析数量只计本次任务覆盖的井；未参与本次任务的登记井显示“未分析”，不借用旧任务结论。事件时间按区间重叠筛选，不重新分析。切换曲线范围也不会重新计算规则。曲线显示当前数据库保存的源采样，历史规则证据另存快照，二者不承诺源数据修改后的完整重放。

详细操作、更新时间和浏览器验收见 [任务4使用说明](docs/TASK4_GUIDE.md) 与 [任务4验收报告](docs/TASK4_REPORT.md)。

## 生成Excel与场景预期文件

在项目根目录、已激活虚拟环境时执行：

```bash
python scripts/generate_mock.py --count 1000 --days 14 --seed 20261021 --output work/mock1000
```

生成：

- `standard-template.xlsx`：标准空模板。
- `example.xlsx`：三行简单样例。
- `mock-data.xlsx`：完整测量数据、井信息、配置、工具、措施、操作和场景预期工作表。
- `manifest.json`：井/事件关联及逐井预期状态、标签和场景起点。

参数支持13至5000口井、4至90天，单批最多100万条测量记录。默认固定起始时间2026-10-01 UTC、种子20261021。相同参数的记录、UUID、预期清单和xlsx字节均可重复。包含13类场景，详见 `docs/TASK2_GUIDE.md`。

仓库 `examples/` 已提供标准模板、三行样例、13场景小样及其预期清单；完整1000井文件约23MiB，运行脚本本地生成，不将大量重复演示文件提交Git。

如需脚本向 `.env` 或 `DATABASE_URL` 指定的开发库显式加载，先完成迁移，再添加 `--load`：

```bash
python scripts/generate_mock.py --count 1000 --days 14 --output work/mock1000 --load
```

快捷启动器使用的本地集群由网页“生成1000井”按钮加载最方便；`--load`读取的是调用脚本时的数据库配置，不会自动接管快捷启动器的地址。同一配置重复加载不会重复写入；保持种子、天数和起始时间不变，可以把旧版600口演示井扩容为1000口，只追加400口和134214条测量，保留原井ID、曲线及事件。更换种子/日期、人工井号冲突、井号已改或原数据不完整时会拒绝扩容。

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

后端测试只使用临时独立PostgreSQL，不访问`.env`数据库。前端测试包括导入确认、执行分析、证据展示及规则版本发布的真实组件交互。修改核心分析算法后必须运行全部回归测试。

可选的1000井整批验证（运行数分钟，独立临时数据库，结束后清理）：

```bash
python scripts/verify_demo.py --workbook work/mock1000/mock-data.xlsx --report work/scale-full-check.json
```

不传 `--workbook` 则自动生成默认1000井文件在内存中验证。静态接口契约位于 `docs/openapi.json`；历史报告保留，1000井扩容结果见 `docs/SCALE_1000_REPORT.md`。

任务3的1000井分析验收（独立临时数据库，不改变已有开发库）：

```bash
python scripts/verify_analysis.py --report work/task3-full-check.json
```

该脚本加载335538条测量，执行三次完整分析，验证场景预期、默认列表去重、历史证据和新规则版本重算；耗时约两分钟，取决于机器性能。

任务4完整API与真实Chromium页面验收（临时独立数据库，含1000演示井及1口手工井）：

```bash
# 首次运行浏览器测试时安装Chromium；普通启动网页不需要这一步
cd frontend
npx playwright install chromium
cd ..
python scripts/verify_web.py --report work/task4-full-check.json
```

若系统已安装Chromium，可设置 `PLAYWRIGHT_CHROMIUM_EXECUTABLE=/usr/bin/chromium`。可加 `--skip-browser` 仅运行全量API核验；不能将跳过浏览器的结果表述为浏览器测试通过。测试脚本通过临时随机端口启动服务，不接触已有work/dev-postgres或真实生产库。只测试当前已运行网页时可在frontend执行 `npm run test:e2e`，该测试要求固定1001井演示场景，勿用于真实生产环境。

## 目录与后续

`backend/app/models`为15实体；`api`和`schemas`为基础接口；`data_sources`为Excel/Mock/Database统一接入；`analysis`为分析算法与默认规则；`services`为导入、演示装载及分析持久化；`migrations`为Alembic；`frontend/src/views`包含首页、井列表、异常列表、单井曲线、导入、运行分析与规则配置页；`scripts`为启动、生成、验证和文档导出；`examples`为标准模板与模拟样本；`AGENTS.md`记录长期约束。

代码同步至用户授权仓库 `sonic099-arch/soniccnpc` 的 `beitian-gas/`，保留仓库根README和历史；不提交 `.env`、虚拟环境、node_modules、本地数据库或用户上传的Excel。Excel暂存默认在 `work/imports`，可用 `IMPORT_STORAGE_DIR`更改，当前须由开发者按需清理；删除暂存文件后，未确认任务须重新上传。

本次交付到任务4。下一步任务5进行联调、错误修复、完整验收和运行文档，补齐独立措施管理页面。
