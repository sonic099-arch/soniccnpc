# API 使用说明

基础地址 `http://localhost:8000`，业务接口统一 `/api/v1`。Swagger `/docs`、ReDoc `/redoc`、静态契约 `openapi.json`。所有对象以 UUID 关联。

| 资源 | 实体 |
|---|---|
| wells | Well |
| well-configs | WellConfigHistory |
| well-tools | WellTool |
| measurements | WellMeasurement |
| measure-events | WellMeasureEvent |
| operation-events | WellOperationEvent |
| fault-histories | WellFaultHistory |
| baselines | WellBaseline |
| rules | AnalysisRule |
| analysis-runs | AnalysisRun |
| anomalies | WellAnomaly |
| reviews | AnomalyReview |
| import-jobs | DataImportJob |
| status-snapshots | WellStatusSnapshot |

每类资源支持：`GET /资源`、`POST /资源`、`GET /资源/{id}`、`PATCH /资源/{id}`、`DELETE /资源/{id}`。

列表响应 `{"items":[],"total":0,"offset":0,"limit":50}`。分页参数 `offset>=0`、`1<=limit<=500`。气井列表支持 `search`（井号包含匹配）和 `area`（工区精确匹配）；依井实体支持 `well_id`。创建成功201、读取/更新200、删除204、无记录404、约束冲突409、参数错误422、数据库不可用503。

`PATCH` 只更新提供字段；不接受 id 或 created_at。非法/缺少时区的时间被拒绝。更新合并后再次验证区间。JSON配置字段传对象，适用工况、规则输入、规则任务快照、错误行、质量标记传数组。

创建演示井：

```bash
curl -X POST http://localhost:8000/api/v1/wells \
  -H 'Content-Type: application/json' \
  -d '{"well_number":"演示-001","area":"演示工区","is_demo":true}'
```

将返回的 UUID 用于后续测量：

```json
{
  "well_id":"替换为气井UUID",
  "measured_at":"2026-01-01T08:00:00+08:00",
  "tubing_pressure_mpa":6.2,
  "casing_pressure_mpa":7.0,
  "back_pressure_mpa":2.1,
  "instantaneous_flow_m3_h":800.0,
  "cumulative_flow_m3":19200.0,
  "gas_temperature_c":18.5,
  "liquid_rate_m3_d":0.8,
  "is_demo":true,
  "source_type":"manual"
}
```

以上数值仅用于演示接口，不能作为现场标准。任务1没有异常分析结果，直接新增异常只是验证存储契约，不代表系统计算了该结论。

## 任务2新增数据接入接口

| 方法 | 路径（均带 /api/v1） | 作用 |
|---|---|---|
| GET | /excel/fields | 标准字段与单位 |
| GET | /excel/template?example=false | 标准模板，example=true返回演示样例 |
| POST | /excel/preview | multipart上传并预览，不写入测量 |
| POST | /excel/jobs/{id}/confirm | 显式确认后导入 |
| GET | /excel/jobs/{id} | 统计及前100条错误 |
| GET | /excel/jobs/{id}/report | 完整错误行xlsx |
| GET | /demo/scenarios | 13个场景及测试预期 |
| POST | /demo/generate | 确认后生成并加载模拟批次 |

映射、单位、时区、报告及幂等语义详见 `TASK2_GUIDE.md`。任务3后 `/health` 的stage为“任务3”，`/ready` 要求迁移0002_analysis_results。

## 任务3分析接口

| 方法 | 路径（均带 /api/v1/analysis） | 作用 |
|---|---|---|
| POST | /rules/bootstrap | `{"confirmed":true}` 初始化11条演示规则，不覆盖现有配置 |
| GET | /rules | 当前规则及数值配置约束 |
| POST | /rules/{code}/versions | 发布新版本，须传完整configuration；停用旧版 |
| POST | /execute | `{"confirmed":true}` 同步执行，可传well_ids、area、window_start/window_end |
| GET | /runs | 分页查看历史任务 |
| GET | /runs/{id} | 任务、时间窗、统计和规则快照 |
| GET | /results | 逐井结果；默认最新，支持run_id、well_id、search、area、screening_status |
| GET | /results/{id} | 全部规则判断和生产上下文 |
| GET | /anomalies | 默认最新且排除可信正常井；支持run_id、well_id、search、area、anomaly_type |
| GET | /anomalies/{id} | 原始代表采样、规则快照和同指纹跨任务复核记录 |

所有执行时间须含时区。默认窗口终点为所选井最新采样加一个采样周期，最长窗口由SYS001配置限制。1000井执行是同步请求，前端超时设为10分钟。并发分析用PostgreSQL事务锁互斥，已有执行返回409；失败回滚结果后保留失败任务。服务进程被强制终止时事务回滚，当前没有队列、恢复或取消接口。

基础CRUD继续供开发使用，但已使用规则的内容不能改写或删除，启用标记可调整；推荐版本接口。引擎任务、结果及已有复核记录不可改写，返回409。人工复核仍通过 `POST /api/v1/reviews` 追加；新实体WellAnalysisResult仅通过分析接口写入和读取，不开放通用CRUD。

更多请求样例和规则见 `TASK3_GUIDE.md`，静态OpenAPI已更新。
