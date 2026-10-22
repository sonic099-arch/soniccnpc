# 数据字典（任务1至3）

所有实体均有UUID主键id、创建时间created_at。字段名携带单位；详细请求与响应类型以openapi.json为准。

## Well — 气井基本信息

表：`wells`；接口：`/api/v1/wells`。

| 字段 | SQL类型 | 允许空 | 关联/约束 |
|---|---|---|---|
| well_number | VARCHAR(80) | 否 | 唯一 |
| name | VARCHAR(120) | 是 |  |
| area | VARCHAR(80) | 否 |  |
| is_demo | BOOLEAN | 否 |  |
| description | TEXT | 是 |  |
| id | CHAR(32) | 否 | 主键 |
| created_at | DATETIME | 否 |  |

复合约束：

- `ck_wells_number_not_blank`：`length(trim(well_number)) > 0`
- `uq_wells_well_number`：`well_number`

索引：

- `ix_wells_area`：area

## WellConfigHistory — 生产配置历史

表：`well_config_histories`；接口：`/api/v1/well-configs`。

| 字段 | SQL类型 | 允许空 | 关联/约束 |
|---|---|---|---|
| production_mode | VARCHAR(40) | 否 |  |
| configuration | JSON | 否 |  |
| id | CHAR(32) | 否 | 主键 |
| created_at | DATETIME | 否 |  |
| well_id | CHAR(32) | 否 | wells.id |
| effective_start | DATETIME | 否 |  |
| effective_end | DATETIME | 是 |  |

复合约束：

- `ck_well_config_histories_effective_range`：`effective_end IS NULL OR effective_end > effective_start`

索引：

- `ix_config_well_effective`：well_id, effective_start, effective_end
- `ix_well_config_histories_well_id`：well_id

## WellTool — 井筒工具

表：`well_tools`；接口：`/api/v1/well-tools`。

| 字段 | SQL类型 | 允许空 | 关联/约束 |
|---|---|---|---|
| tool_type | VARCHAR(60) | 否 |  |
| tool_name | VARCHAR(120) | 否 |  |
| depth_m | FLOAT | 是 |  |
| parameters | JSON | 否 |  |
| id | CHAR(32) | 否 | 主键 |
| created_at | DATETIME | 否 |  |
| well_id | CHAR(32) | 否 | wells.id |
| effective_start | DATETIME | 否 |  |
| effective_end | DATETIME | 是 |  |

复合约束：

- `ck_well_tools_nonnegative_depth`：`depth_m IS NULL OR depth_m >= 0`
- `ck_well_tools_effective_range`：`effective_end IS NULL OR effective_end > effective_start`

索引：

- `ix_well_tools_well_id`：well_id
- `ix_tool_well_effective`：well_id, effective_start, effective_end

## WellMeasurement — 动态生产参数

表：`well_measurements`；接口：`/api/v1/measurements`。

| 字段 | SQL类型 | 允许空 | 关联/约束 |
|---|---|---|---|
| measured_at | DATETIME | 否 |  |
| tubing_pressure_mpa | FLOAT | 是 |  |
| casing_pressure_mpa | FLOAT | 是 |  |
| back_pressure_mpa | FLOAT | 是 |  |
| instantaneous_flow_m3_h | FLOAT | 是 |  |
| cumulative_flow_m3 | FLOAT | 是 |  |
| gas_temperature_c | FLOAT | 是 |  |
| liquid_rate_m3_d | FLOAT | 是 |  |
| quality_flags | JSON | 否 |  |
| source_type | VARCHAR(30) | 否 |  |
| is_demo | BOOLEAN | 否 |  |
| import_job_id | CHAR(32) | 是 | data_import_jobs.id |
| id | CHAR(32) | 否 | 主键 |
| created_at | DATETIME | 否 |  |
| well_id | CHAR(32) | 否 | wells.id |

复合约束：

- `uq_measurement_well_time`：`well_id, measured_at`

索引：

- `ix_well_measurements_well_id`：well_id

## WellMeasureEvent — 排采措施事件

表：`well_measure_events`；接口：`/api/v1/measure-events`。

| 字段 | SQL类型 | 允许空 | 关联/约束 |
|---|---|---|---|
| measure_type | VARCHAR(60) | 否 |  |
| parameters | JSON | 否 |  |
| notes | TEXT | 是 |  |
| id | CHAR(32) | 否 | 主键 |
| created_at | DATETIME | 否 |  |
| well_id | CHAR(32) | 否 | wells.id |
| effective_start | DATETIME | 否 |  |
| effective_end | DATETIME | 是 |  |

复合约束：

- `ck_well_measure_events_effective_range`：`effective_end IS NULL OR effective_end > effective_start`

索引：

- `ix_measure_well_effective`：well_id, effective_start, effective_end
- `ix_well_measure_events_well_id`：well_id

## WellOperationEvent — 开关井操作

表：`well_operation_events`；接口：`/api/v1/operation-events`。

| 字段 | SQL类型 | 允许空 | 关联/约束 |
|---|---|---|---|
| operation_type | VARCHAR(40) | 否 |  |
| planned | BOOLEAN | 否 |  |
| reason | TEXT | 是 |  |
| id | CHAR(32) | 否 | 主键 |
| created_at | DATETIME | 否 |  |
| well_id | CHAR(32) | 否 | wells.id |
| effective_start | DATETIME | 否 |  |
| effective_end | DATETIME | 是 |  |

复合约束：

- `ck_well_operation_events_effective_range`：`effective_end IS NULL OR effective_end > effective_start`

索引：

- `ix_well_operation_events_well_id`：well_id
- `ix_operation_well_effective`：well_id, effective_start, effective_end

## WellFaultHistory — 历史故障

表：`well_fault_histories`；接口：`/api/v1/fault-histories`。

| 字段 | SQL类型 | 允许空 | 关联/约束 |
|---|---|---|---|
| fault_type | VARCHAR(80) | 否 |  |
| confirmed | BOOLEAN | 否 |  |
| evidence | JSON | 否 |  |
| notes | TEXT | 是 |  |
| id | CHAR(32) | 否 | 主键 |
| created_at | DATETIME | 否 |  |
| well_id | CHAR(32) | 否 | wells.id |
| effective_start | DATETIME | 否 |  |
| effective_end | DATETIME | 是 |  |

复合约束：

- `ck_well_fault_histories_effective_range`：`effective_end IS NULL OR effective_end > effective_start`

索引：

- `ix_well_fault_histories_well_id`：well_id

## WellBaseline — 正常生产基线

表：`well_baselines`；接口：`/api/v1/baselines`。

| 字段 | SQL类型 | 允许空 | 关联/约束 |
|---|---|---|---|
| window_start | DATETIME | 否 |  |
| window_end | DATETIME | 否 |  |
| production_mode | VARCHAR(40) | 否 |  |
| algorithm_version | VARCHAR(30) | 否 |  |
| statistics | JSON | 否 |  |
| sample_count | INTEGER | 否 |  |
| analysis_run_id | CHAR(32) | 是 | analysis_runs.id |
| id | CHAR(32) | 否 | 主键 |
| created_at | DATETIME | 否 |  |
| well_id | CHAR(32) | 否 | wells.id |

复合约束：

- `ck_well_baselines_positive_samples`：`sample_count > 0`
- `ck_well_baselines_window_range`：`window_end > window_start`

索引：

- `ix_well_baselines_well_id`：well_id
- `ix_baseline_well_window`：well_id, window_start, window_end

## AnalysisRule — 分析规则

表：`analysis_rules`；接口：`/api/v1/rules`。

| 字段 | SQL类型 | 允许空 | 关联/约束 |
|---|---|---|---|
| code | VARCHAR(60) | 否 |  |
| name | VARCHAR(120) | 否 |  |
| version | VARCHAR(30) | 否 |  |
| applicable_states | JSON | 否 |  |
| input_parameters | JSON | 否 |  |
| configuration | JSON | 否 |  |
| function_key | VARCHAR(120) | 否 |  |
| enabled | BOOLEAN | 否 |  |
| id | CHAR(32) | 否 | 主键 |
| created_at | DATETIME | 否 |  |

复合约束：

- `uq_rule_code_version`：`code, version`

索引：

主键/唯一约束自动索引。

## AnalysisRun — 分析任务

表：`analysis_runs`；接口：`/api/v1/analysis-runs`。

| 字段 | SQL类型 | 允许空 | 关联/约束 |
|---|---|---|---|
| window_start | DATETIME | 否 |  |
| window_end | DATETIME | 否 |  |
| status | VARCHAR(30) | 否 |  |
| rule_snapshot | JSON | 否 |  |
| data_cutoff | DATETIME | 是 |  |
| completed_at | DATETIME | 是 |  |
| summary | JSON | 否 |  |
| error_message | TEXT | 是 |  |
| id | CHAR(32) | 否 | 主键 |
| created_at | DATETIME | 否 |  |

复合约束：

- `ck_analysis_runs_window_range`：`window_end > window_start`

索引：

主键/唯一约束自动索引。

## WellAnomaly — 异常事件

表：`well_anomalies`；接口：`/api/v1/anomalies`。

| 字段 | SQL类型 | 允许空 | 关联/约束 |
|---|---|---|---|
| analysis_run_id | CHAR(32) | 否 | analysis_runs.id |
| rule_id | CHAR(32) | 否 | analysis_rules.id |
| anomaly_type | VARCHAR(60) | 否 |  |
| severity | VARCHAR(30) | 否 |  |
| started_at | DATETIME | 否 |  |
| ended_at | DATETIME | 是 |  |
| evidence | JSON | 否 |  |
| rule_snapshot | JSON | 否 |  |
| fingerprint | VARCHAR(128) | 否 |  |
| id | CHAR(32) | 否 | 主键 |
| created_at | DATETIME | 否 |  |
| well_id | CHAR(32) | 否 | wells.id |

复合约束：

- `uq_anomaly_run_fingerprint`：`analysis_run_id, fingerprint`
- `ck_well_anomalies_event_range`：`ended_at IS NULL OR ended_at > started_at`

索引：

- `ix_well_anomalies_anomaly_type`：anomaly_type
- `ix_well_anomalies_well_id`：well_id
- `ix_anomaly_well_start`：well_id, started_at
- `ix_well_anomalies_analysis_run_id`：analysis_run_id
- `ix_well_anomalies_rule_id`：rule_id

## AnomalyReview — 人工复核

表：`anomaly_reviews`；接口：`/api/v1/reviews`。

| 字段 | SQL类型 | 允许空 | 关联/约束 |
|---|---|---|---|
| anomaly_id | CHAR(32) | 否 | well_anomalies.id |
| reviewer | VARCHAR(80) | 否 |  |
| decision | VARCHAR(60) | 否 |  |
| comment | TEXT | 否 |  |
| reviewed_at | DATETIME | 否 |  |
| id | CHAR(32) | 否 | 主键 |
| created_at | DATETIME | 否 |  |

复合约束：

无额外复合约束。

索引：

- `ix_anomaly_reviews_anomaly_id`：anomaly_id

## DataImportJob — 数据导入记录

表：`data_import_jobs`；接口：`/api/v1/import-jobs`。

| 字段 | SQL类型 | 允许空 | 关联/约束 |
|---|---|---|---|
| source_type | VARCHAR(30) | 否 |  |
| filename | VARCHAR(255) | 是 |  |
| file_sha256 | VARCHAR(64) | 是 |  |
| mapping | JSON | 否 |  |
| status | VARCHAR(30) | 否 |  |
| total_rows | INTEGER | 否 |  |
| success_rows | INTEGER | 否 |  |
| failed_rows | INTEGER | 否 |  |
| duplicate_rows | INTEGER | 否 |  |
| errors | JSON | 否 |  |
| completed_at | DATETIME | 是 |  |
| id | CHAR(32) | 否 | 主键 |
| created_at | DATETIME | 否 |  |

复合约束：

- `ck_data_import_jobs_row_counts`：`total_rows >= 0 AND success_rows >= 0 AND failed_rows >= 0 AND duplicate_rows >= 0 AND success_rows + failed_rows + duplicate_rows <= total_rows`

索引：

- `ix_data_import_jobs_file_sha256`：file_sha256

## WellStatusSnapshot — 最新状态

表：`well_status_snapshots`；接口：`/api/v1/status-snapshots`。

| 字段 | SQL类型 | 允许空 | 关联/约束 |
|---|---|---|---|
| analysis_run_id | CHAR(32) | 否 | analysis_runs.id |
| as_of | DATETIME | 否 |  |
| screening_status | VARCHAR(40) | 否 |  |
| production_state | VARCHAR(40) | 否 |  |
| evidence | JSON | 否 |  |
| id | CHAR(32) | 否 | 主键 |
| created_at | DATETIME | 否 |  |
| well_id | CHAR(32) | 否 | wells.id |

复合约束：

- `uq_snapshot_well`：`well_id`
- `ck_well_status_snapshots_screening_status`：`screening_status IN ('可信正常', '疑似异常', '措施影响', '数据待核实', '工况待核实')`

索引：

- `ix_well_status_snapshots_well_id`：well_id
- `ix_well_status_snapshots_analysis_run_id`：analysis_run_id
- `ix_well_status_snapshots_screening_status`：screening_status


## WellAnalysisResult — 每次分析的单井历史结果（任务3新增）

表 `well_analysis_results`，迁移 `0002_analysis_results`。读取 `/api/v1/analysis/results` 与 `/api/v1/analysis/results/{id}`；不开放基础CRUD，写入由分析服务统一完成。

| 字段 | PostgreSQL类型 | 约束或含义 |
|---|---|---|
| id | UUID | 主键 |
| created_at | TIMESTAMPTZ | 创建时间 |
| well_id | UUID | 外键wells.id，RESTRICT |
| analysis_run_id | UUID | 外键analysis_runs.id，RESTRICT |
| as_of | TIMESTAMPTZ | 本次分析窗口结束时间（不含） |
| screening_status | VARCHAR(40) | 五种筛查状态CHECK |
| production_state | VARCHAR(40) | 中文生产状态 |
| evidence | JSON | 逐条规则结果、上下文、基线、原始输入摘要 |

唯一约束 `uq_analysis_result_run_well(analysis_run_id, well_id)`；索引well_id、analysis_run_id、screening_status。与Well、AnalysisRun都是多对一。保留历史正常与异常井结果；WellStatusSnapshot仍是一井一条最新状态。重复分析创建新任务，默认异常列表仅关联最新快照，历史任务显式按run_id读取。

数据库总计15个业务实体、15张业务表，另有Alembic版本表。历史表格中的CHAR(32)、DATETIME为通用SQLAlchemy显示；PostgreSQL实际UUID、TIMESTAMPTZ口径不变。
