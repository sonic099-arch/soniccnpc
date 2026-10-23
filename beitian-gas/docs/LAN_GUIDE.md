# 内网运行：Win11主机10.86.36.43

网页入口：**http://10.86.36.43:8080**。来源允许范围严格为 **10.86.36.1–10.86.36.255**，不包含10.86.36.0、不开放其他网段及原生IPv6。IPv4映射的IPv6按其IPv4检查。接口文档使用同一入口 `/docs`，所有网页、API、上传下载均受相同限制。

当前按Win11＋WSL2 Ubuntu24.04设计。版本0.4.1，仍属任务4增量；不修改分析算法、不新增迁移、不清理已有井和历史结果。

## 为什么使用Windows单一入口

```mermaid
flowchart LR
  A[内网客户端] --> B[Windows 10.86.36.43:8080]
  B --> C[防火墙限定来源范围]
  C --> D[网关按真实TCP对端IP检查]
  D --> E[本机127.0.0.1:8000]
  E --> F[WSL FastAPI及构建后的中文网页]
  F --> G[原work/dev-postgres数据库]
```

WSL默认NAT模式的端口转发可能隐藏外部客户端IP，不能仅凭后端看到的转发地址或可伪造的X-Forwarded-For判断权限。因此网关直接运行在Windows，直接接收内网连接，并检查套接字对端，不信任请求头。后端只监听127.0.0.1，内网只需开放8080，不开放Vite5173或数据库端口。

内网客户端使用浏览器即可，不安装Python。Windows网关只用Python标准库，支持Python3.12/3.14；WSL业务后端继续使用Python3.12。首次安装/构建需下载依赖，完成后网页、曲线及Swagger文档运行不依赖外网CDN。

## 1. Ubuntu更新代码并准备文件

先在原服务窗口Ctrl+C停止 `scripts/dev.py`，不要同时使用两个启动器操作同一演示数据库。进入实际的 `soniccnpc/beitian-gas` 项目目录：

```bash
git pull --ff-only
source .venv/bin/activate
python -m pip install --no-deps -e ./backend
npm --prefix frontend ci
mkdir -p /mnt/c/beitian-lan
cp scripts/lan_gateway.py scripts/start_lan.ps1 /mnt/c/beitian-lan/
python scripts/lan.py
```

最后一条构建网页及本地Swagger资源、执行迁移，再启动127.0.0.1:8000。保持终端运行。原1001口井和分析结果保留；不需要重新生成或导入。

复制命令仅把两个入口脚本复制到Windows的C:\beitian-lan，不复制数据库或.env。如果公司策略不允许建立这个文件夹，可在Ubuntu运行 `explorer.exe scripts`，手工把两个文件放到Windows有权限的同一目录；下文路径相应替换。

若git pull仍提示本地修改，先备份源码再拉取（这些目录不包含被忽略的.env、.venv、work）：

```bash
git stash push -u -m "内网更新前本地源码备份" -- AGENTS.md README.md backend docs frontend scripts
git pull --ff-only
```

暂不stash pop，以免恢复旧代码。GitHub网络不通时，使用先前的ZIP更新方式，保留.env、.venv、.git、work。

## 2. Windows启动受限入口

先在Windows浏览器打开 **http://localhost:8000/**，应看到系统首页；这验证WSL到Windows的本机转发，不是向其他电脑开放后端。

在开始菜单搜索 **PowerShell**，选择 **以管理员身份运行**，执行：

```powershell
powershell -ExecutionPolicy Bypass -File C:\beitian-lan\start_lan.ps1
```

管理员权限是Windows添加防火墙入站规则的要求。`-ExecutionPolicy Bypass`只影响这次脚本进程，不永久修改系统执行策略。

脚本会：

1. 确认Windows网卡具有10.86.36.43。
2. 确认本机后端与构建网页已启动。
3. 建立/更新本应用自己的防火墙规则BeitianGasLAN-8080，仅允许来源10.86.36.1–10.86.36.255访问本机10.86.36.43:8080；不关闭防火墙，不修改其他应用规则。
4. 使用Windows Python启动网关，所有到达请求再次按真实来源IP检查。范围外请求即使伪造Forwarded/X-Forwarded-For/X-Real-IP也被拒绝。

保持PowerShell窗口运行。网关HTTP请求体上限32MiB，兼容现有25MiB Excel限制，分析超时600秒。页面与API同源，不需要把CORS改成通配符。

如果不希望脚本管理防火墙，可由管理员手动添加等价规则，再在普通Windows终端执行 `py -3 C:\beitian-lan\lan_gateway.py`；默认监听地址、端口和范围相同。它不会自动修改防火墙。

## 3. 内网电脑访问

在范围内其他电脑浏览器打开：

- 系统首页：http://10.86.36.43:8080/
- 气井列表：http://10.86.36.43:8080/wells
- 异常井列表：http://10.86.36.43:8080/anomalies
- 接口文档：http://10.86.36.43:8080/docs

本机也使用10.86.36.43:8080访问网关。不要通过localhost:8080访问，因为入口绑定指定网卡且不允许127.0.0.1作为远端客户地址。

ReDoc路径 `/redoc` 在内网模式跳转到本地Swagger，避免依赖外部CDN。生产网页是已构建静态资源，不开放Vite开发服务器或热更新连接。

范围内客户端可使用系统当前管理功能；IP限制不是账号权限系统。当前没有用户级角色控制。网关前面不要再放置隐藏客户端真实来源的端口转发或反向代理；如需公司统一代理，应重新设计可信代理和访问策略，不把伪造请求头当作授权依据。

## 4. 停止、重启和更新

停止时：先在Windows入口窗口Ctrl+C，再在Ubuntu服务窗口Ctrl+C；数据库保留。重启时先运行Ubuntu `python scripts/lan.py --skip-build`，再启动Windows入口脚本。`--skip-build`只复用已构建页面和文档，适合断网重启；更新前端源码后必须重新运行不带该参数的启动器完成构建。

代码更新后按第一步重新复制两个Windows脚本，避免入口仍使用旧版本。不要删除work/dev-postgres，不要同时运行两个数据库启动器。仅本机调试仍可按README使用原 `scripts/dev.py`。

Windows防火墙规则会保留；网关退出后端口不再监听。需要撤销本应用规则时，在管理员PowerShell执行：

```powershell
Remove-NetFirewallRule -Name BeitianGasLAN-8080
```

不需要netsh portproxy，也不要把后端、Vite、数据库改为对所有网卡监听。

## 5. 排查与现场验证

| 现象 | 检查 |
|---|---|
| Windows localhost:8000打不开 | 先看Ubuntu启动日志，确认原8000服务已停止、WSL localhost转发正常；用户之前可打开Swagger时通常已具备此条件 |
| 入口提示Windows没有10.86.36.43 | 在Windows运行ipconfig确认网卡地址；若DHCP改变地址，需同步调整监听、公布URL和防火墙本地地址 |
| 缺少Windows Python | Windows运行py -3 --version；网关可用3.12或3.14，业务后端不要改用3.14 |
| 防火墙规则添加被拒绝 | 确认管理员PowerShell；受公司策略管理时由公司管理员建立同等范围规则 |
| 同事访问超时 | 检查两窗口都在运行、Windows防火墙及公司网络是否允许到达8080，确认客户端实际源IP属于指定范围 |
| 返回403 | 检查客户端实际IP，使用公布的IP和8080端口，避免隐藏源IP的代理/VPN/端口转发；不要通过修改请求头绕过 |
| 返回502 | Windows入口运行，但无法连接本机后端，检查Ubuntu服务 |
| 更新后仍显示旧页面 | 重新构建（不带--skip-build）、重启、浏览器Ctrl+Shift+R |

请在真实网络验证：范围内另一台电脑能打开首页、列表、7参数曲线、上传预览和接口文档；范围外电脑不能访问（防火墙丢弃时可能表现为超时，到达应用时返回403）。10.86.36.0明确拒绝；.255按指定范围包含，但在常见/24网络中是广播地址，不作为普通终端地址分配。

本开发环境不能直接操作你的Win11电脑、公司防火墙或10.86.36网段，因此真实Windows连通性与防火墙效果需要以上现场步骤确认；自动测试不冒充现场验证。

## 自动测试

```bash
python -m pytest backend/tests --junitxml=work/lan-backend.xml
npm --prefix frontend test -- --reporter=junit --outputFile=../work/lan-frontend.xml
# 首次准备浏览器需安装Chromium，或使用系统已安装的Chromium
cd frontend
npx playwright install chromium
cd ..
# 先准备静态网页与离线文档；不启动现有开发库
python -c "from scripts.lan import build_frontend; build_frontend()"
python scripts/verify_web.py --lan --report work/lan-full-check.json
```

新35项访问测试覆盖字面范围边界、IPv4映射、网段外请求、伪造头、网页/API/静态/文档全入口、方法/上传正文、并发、重定向、下载和上游故障。真实HTTP集成在临时回环地址模拟允许/拒绝两种TCP来源，不修改宿主防火墙，也不尝试连接真实内网。浏览器使用构建网页经网关访问，阻断所有外部资源验证离线文档。

完整统计与环境限制见LAN_REPORT；这不是任务5全部验收，也不代表现场异常筛查准确率。
