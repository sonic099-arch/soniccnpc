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
