from app.models import entities as m

# slug、实体及中文文档标签，是全部 CRUD 资源的唯一注册表。
RESOURCES = [
    ("wells", m.Well, "气井基本信息"),
    ("well-configs", m.WellConfigHistory, "生产配置历史"),
    ("well-tools", m.WellTool, "井筒工具"),
    ("measurements", m.WellMeasurement, "动态生产参数"),
    ("measure-events", m.WellMeasureEvent, "排采措施事件"),
    ("operation-events", m.WellOperationEvent, "开关井操作"),
    ("fault-histories", m.WellFaultHistory, "历史故障"),
    ("baselines", m.WellBaseline, "正常生产基线"),
    ("rules", m.AnalysisRule, "分析规则"),
    ("analysis-runs", m.AnalysisRun, "分析任务"),
    ("anomalies", m.WellAnomaly, "异常事件"),
    ("reviews", m.AnomalyReview, "人工复核"),
    ("import-jobs", m.DataImportJob, "数据导入记录"),
    ("status-snapshots", m.WellStatusSnapshot, "最新状态"),
]
