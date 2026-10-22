# 任务3：分析引擎与规则使用说明

本阶段只交付分析引擎、规则版本管理、执行与证据工作台和自动测试。完整首页、井列表、独立异常页与单井曲线在任务4实施。所有默认数值仅为演示，不能作为现场工艺标准。

## 更新与执行

Win11用户在WSL2 Ubuntu 24.04终端执行；使用Python3.12。先停止原服务，在项目目录执行：

```bash
git pull --ff-only
source .venv/bin/activate
python -m pip install --no-deps -e ./backend
npm --prefix frontend ci
python scripts/dev.py
```

快捷启动器自动执行Alembic迁移，任务3只新增历史结果表，不删除现有1000井和335538条测量。使用自管数据库时，激活虚拟环境后先在backend目录运行 `alembic upgrade head`，再启动uvicorn。

打开 `http://localhost:5173/analysis`，先初始化规则，再勾选确认执行；已装载1000井的用户不需要重新生成数据。工区、时间先留空。旧样例额外井也会分析，因没有有效生产配置可显示待核实。执行是同步请求，保持后端运行；若浏览器超时，先刷新任务记录核对，不要连续重复点击。

默认数据起点2026-10-01 UTC，共14天。系统以最新采样加一个采样周期确定结束（不含），不以电脑当前日期推断历史井况。网页窗口选择使用浏览器本地时区，传输带时区ISO时间；结果表显示北京时间。支持按工区或API well_ids分析子集；默认结果列表始终每井最新，历史任务按run_id读取。

在 `/rules` 修改数值阈值、适用工况或启用状态并发布高于现有版本的新版本；数组策略可通过Swagger版本接口提交完整configuration。发布后重新执行才生效，旧任务不变。停用关键规则或缩小适用范围会产生“规则覆盖不足”，相关井不自动归为正常。

## 分析过程与状态

1. DataQualityAnalyzer：采样覆盖、缺失/空值/非有限数、冻结、未来时间、重复与累计量一致性。六个核心参数不能通过配置省略；产液量可缺，但缺少辅助证据时不作积液提示。
2. OperationStateResolver：按有效配置、工具、计划操作、周期计划、措施及故障解析工况。冲突配置、未知生产方式/工具/近期措施、未关闭历史故障等均不能默认正常。
3. BaselineCalculator：只用决策之前、当前配置及工具可比较且排除措施/计划停井/故障的历史样本；估计中位数和流量对数趋势。趋势需达到可配置R²才用于自然递减外推，避免随机斜率误命名。
4. FlowTrendAnalyzer：比较趋势基线，要求连续减产；间断短时低值不能拼成连续事件。
5. PressureTrendAnalyzer：压力相邻突变、范围波动、流量与套油压差/油压/产液关联。跨大时间缺口不作压力单步比较。
6. TemperatureTrendAnalyzer：温度持续变化；只有低温、降温、减产及压力关联证据共同满足时才提示疑似冻堵，单温度异常输出工况待核实。
7. MeasureEffectAnalyzer：措施执行及恢复缓冲期间的合理波动单列“措施影响”；充分前后样本支持时提示“措施后未恢复”。
8. AnomalyRuleEngine：统一校验并执行注册规则；生产异常判断依赖可信数据、工况和可用基线。
9. AnomalyAggregator：同井、同规则版本和同事件类型按可配置间隔合并，稳定指纹支持重复分析列表去重。
10. WellStatusClassifier：优先数据待核实，其次工况/规则/基线待核实，再疑似异常、措施影响，只有证据充分且规则覆盖完整才可信正常。

“疑似积液（辅助提示）”“疑似冻堵（辅助提示）”均保存 `diagnosis:false`。模型没有现场确诊能力。计量复位井先列计量待核实；计划停井和周期性休井不标为非计划停井；无记录的持续零流量在可信输入下标为非计划停井。

## 规则登记表

所有规则默认版本1.0.0，默认适用工况“全部”。“全部”只覆盖引擎已识别的生产方式，不使未知工况变正常。函数通过固定注册表执行，不支持上传或eval任意代码。配置在 `backend/app/analysis/default_rules.json`，数据库中每个编号只选一个启用版本。SYS001必须启用，其他规则停用也不能当作通过。

| 编号 | 中文名称 | 输入参数 | 注册分析函数 | 自动测试 |
|---|---|---|---|---|
| SYS001 | 工况与基线策略 | 生产配置、工具、措施、操作、历史故障 | `context_policy` | 规则元数据/参数校验及场景回归 |
| DQ001 | 采样完整性与可信度 | 时间、油压、套压、回压、瞬时流量、累计流量、温度 | `data_quality` | 规则元数据/参数校验及场景回归 |
| DQ002 | 数据冻结识别 | 七参数、时间 | `data_freeze` | 规则元数据/参数校验及场景回归 |
| DQ003 | 累计量与瞬时流量一致性 | 瞬时流量、累计流量、时间 | `meter_consistency` | 规则元数据/参数校验及场景回归 |
| OP001 | 计划与非计划停井识别 | 瞬时流量、开关井操作、周期计划 | `operation_state` | 规则元数据/参数校验及场景回归 |
| FL001 | 持续减产与自然递减区分 | 瞬时流量、基线、生产方式 | `flow_trend` | 规则元数据/参数校验及场景回归 |
| PR001 | 压力突变与异常波动 | 油压、套压、回压 | `pressure_trend` | 规则元数据/参数校验及场景回归 |
| PR002 | 压力流量关联辅助提示 | 瞬时流量、油压、套压、回压、产液量 | `pressure_flow` | 规则元数据/参数校验及场景回归 |
| TP001 | 低温压流关联辅助提示 | 温度、瞬时流量、油压 | `temperature_trend` | 规则元数据/参数校验及场景回归 |
| ME001 | 措施期间与恢复期识别 | 措施类型、措施有效区间、动态参数 | `measure_period` | 规则元数据/参数校验及场景回归 |
| ME002 | 措施后恢复效果评估 | 措施前后流量、措施有效区间 | `measure_effect` | 规则元数据/参数校验及场景回归 |

每条规则返回编号、版本、执行状态、覆盖标记、指标、证据和事件数量。事件保存规则配置、开始/结束、判断动作、代表采样ID与原始数值、基线、有效时间上下文和SHA256输入摘要。单井历史结果保存所有规则，包括通过和未执行项。

## 配置项、单位与演示默认值

以下配置与代码中的Pydantic约束一致，缺项、额外项、非法范围、NaN/Infinity被拒绝。值是演示策略，不是生产标准。

### SYS001 工况与基线策略

| 配置键 | 中文含义/单位 | 演示值 |
|---|---|---|
| `sample_minutes` | 采样间隔（分钟） | 60 |
| `lookback_hours` | 默认回看窗口（小时） | 336 |
| `evaluation_hours` | 近期评估窗口（小时） | 24 |
| `baseline_hours` | 基线最大跨度（小时） | 168 |
| `baseline_guard_hours` | 基线与窗口末端隔离（小时） | 72 |
| `minimum_samples` | 最低分析样本数 | 48 |
| `baseline_min_samples` | 最低基线样本数 | 24 |
| `zero_flow` | 近零流量界限（m³/h） | 1.0 |
| `max_natural_decline_daily` | 允许自然递减上限（每天比例） | 0.03 |
| `natural_decline_label_daily` | 自然递减状态提示下限（每天比例） | 0.001 |
| `valid_modes` | 支持的生产方式 | ["自喷", "泡排", "间歇", "注醇", "其他排采"] |
| `known_tools` | 已识别工具类型 | ["井下节流器", "速度管柱", "柱塞", "其他"] |
| `known_measures` | 已识别措施类型 | ["泡排", "注醇", "机械排液", "其他排采"] |
| `transition_guard_hours` | 计划操作边界缓冲（小时） | 2 |
| `merge_gap_hours` | 同类事件合并间隔（小时） | 3 |
| `max_window_hours` | 最大分析窗口（小时） | 2160 |
| `natural_decline_min_r2` | 自然递减趋势拟合可信度下限（R²） | 0.8 |

### DQ001 采样完整性与可信度

| 配置键 | 中文含义/单位 | 演示值 |
|---|---|---|
| `required_fields` | 必需动态参数 | ["tubing_pressure_mpa", "casing_pressure_mpa", "back_pressure_mpa", "instantaneous_flow_m3_h", "cumulative_flow_m3", "gas_temperature_c"] |
| `minimum_recent_coverage` | 近期有效采样覆盖率下限 | 1.0 |
| `max_gap_hours` | 最大允许采样间隔（小时） | 2 |
| `future_minutes` | 未来时间容差（分钟） | 5 |

### DQ002 数据冻结识别

| 配置键 | 中文含义/单位 | 演示值 |
|---|---|---|
| `freeze_hours` | 冻结持续时间（小时） | 12 |
| `value_tolerance` | 参数恒定比较容差 | 1e-06 |

### DQ003 累计量与瞬时流量一致性

| 配置键 | 中文含义/单位 | 演示值 |
|---|---|---|
| `relative_tolerance` | 累计增量相对误差容差 | 0.05 |
| `absolute_tolerance_m3` | 累计增量绝对误差容差（m³） | 1 |
| `reset_tolerance_m3` | 累计复位负跳变容差（m³） | 0.01 |
| `max_interval_hours` | 积分检查最大采样间隔（小时） | 2 |

### OP001 计划与非计划停井识别

| 配置键 | 中文含义/单位 | 演示值 |
|---|---|---|
| `stopped_hours` | 停井判断持续时间（小时） | 3 |

### FL001 持续减产与自然递减区分

| 配置键 | 中文含义/单位 | 演示值 |
|---|---|---|
| `decline_ratio` | 低于趋势基线的减产比例 | 0.25 |
| `sustain_hours` | 减产最短持续时间（小时） | 12 |

### PR001 压力突变与异常波动

| 配置键 | 中文含义/单位 | 演示值 |
|---|---|---|
| `step_mpa` | 压力单步变化界限（MPa） | 1.2 |
| `range_mpa` | 近期压力波动范围（MPa） | 2.0 |
| `max_step_interval_hours` | 压力突变比较最大采样间隔（小时） | 2 |

### PR002 压力流量关联辅助提示

| 配置键 | 中文含义/单位 | 演示值 |
|---|---|---|
| `flow_ratio` | 流量相对基线比例上限 | 0.65 |
| `gap_growth_mpa` | 套油压差扩大界限（MPa） | 1.0 |
| `pressure_change_mpa` | 油压变化界限（MPa） | 1.5 |
| `liquid_growth_m3_d` | 辅助产液量增长界限（m³/d） | 0.5 |

### TP001 低温压流关联辅助提示

| 配置键 | 中文含义/单位 | 演示值 |
|---|---|---|
| `low_temperature_c` | 低温界限（℃） | 0 |
| `temperature_drop_c` | 相对基线降温界限（℃） | 8 |
| `flow_ratio` | 减产关联比例上限 | 0.65 |
| `pressure_growth_mpa` | 油压关联增量（MPa） | 1.0 |
| `sustain_hours` | 关联低温最短持续时间（小时） | 3 |
| `temperature_rise_c` | 相对基线升温界限（℃） | 8 |

### ME001 措施期间与恢复期识别

| 配置键 | 中文含义/单位 | 演示值 |
|---|---|---|
| `recovery_hours` | 措施恢复缓冲（小时） | 12 |

### ME002 措施后恢复效果评估

| 配置键 | 中文含义/单位 | 演示值 |
|---|---|---|
| `pre_hours` | 措施前参照窗口（小时） | 24 |
| `post_hours` | 措施后评估窗口（小时） | 24 |
| `minimum_post_samples` | 措施后最低样本数 | 12 |
| `effect_horizon_hours` | 措施效果回看上限（小时） | 96 |
| `recovery_ratio` | 措施后恢复比例下限 | 0.8 |

## Swagger调试

打开 `http://localhost:8000/docs` 的“分析引擎”分组，使用Try it out：

1. `POST /api/v1/analysis/rules/bootstrap`，请求 `{"confirmed":true}`。
2. `POST /api/v1/analysis/execute`，请求 `{"confirmed":true}`；复制返回的id作为run_id，可查看本次历史结果。
3. `GET /api/v1/analysis/results?run_id=返回ID` 读逐井状态；`GET /api/v1/analysis/anomalies?run_id=返回ID` 读事件。
4. 取事件id调用 `GET /api/v1/analysis/anomalies/{id}`，查看证据、规则及措施关联；用 `POST /api/v1/reviews` 追加复核记录。
5. `GET /api/v1/analysis/rules` 取完整configuration；`POST /api/v1/analysis/rules/FL001/versions` 提交新version、完整configuration、enabled与applicable_states；重新execute。

例如通过原配置仅将FL001的decline_ratio从0.25调整到0.95并发布1.0.1，演示持续减产判据会改变。此值只是验证“配置变更会重算”的测试，不是推荐业务阈值。

## 自动测试与运行边界

```bash
python -m pytest backend/tests --junitxml=work/task3-backend.xml
npm --prefix frontend test -- --reporter=junit --outputFile=../work/task3-frontend.xml
npm --prefix frontend run build
python scripts/verify_analysis.py --report work/task3-full-check.json
python scripts/export_openapi.py
```

测试使用临时PostgreSQL并自动清理，不连接`.env`中的生产数据库。verify_analysis实际装载1000井及关联事件、运行三次完整分析，检查13种场景、重复运行、默认列表分页、新版本重算和旧结论保留。场景预期只在测试比较使用，分析代码不读demo_scenario或expected标签。

执行使用数据库一致性读快照、数据截止时间和互斥事务锁。整批成功后写入，失败回滚并保留失败任务；更早窗口不会覆盖较新快照。没有后台队列和断点恢复，服务进程强制中止时数据库事务回滚。证据保存关键代表采样，不是所有源数据的不可变备份。

规则内容和引擎生成的历史结果不可通过基础CRUD改写；人工复核只追加。源测量/配置仍可由开发接口修改，需重新分析才能反映变化。当前没有认证和生产部署体系，只用于本机开发。定时调度、现场标定、真实库接入及真实准确率验证均不在本次交付范围。
