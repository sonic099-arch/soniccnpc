"""任务1领域模型。数值为空代表缺失；质量标记独立保存，避免把缺失填成零。"""
import uuid
from datetime import datetime
from sqlalchemy import (String, Text, Float, Integer, Boolean, DateTime, JSON,
                        ForeignKey, UniqueConstraint, CheckConstraint, Index)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, IdentityMixin, EffectiveMixin

class Well(IdentityMixin, Base):
    __tablename__ = "wells"
    well_number: Mapped[str] = mapped_column(String(80), unique=True)
    name: Mapped[str | None] = mapped_column(String(120))
    area: Mapped[str] = mapped_column(String(80), index=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=True)
    description: Mapped[str | None] = mapped_column(Text)
    __table_args__ = (CheckConstraint("length(trim(well_number)) > 0", name="number_not_blank"),)

class WellLinked:
    well_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("wells.id", ondelete="RESTRICT"), index=True)

class WellConfigHistory(IdentityMixin, WellLinked, EffectiveMixin, Base):
    __tablename__ = "well_config_histories"
    production_mode: Mapped[str] = mapped_column(String(40))
    configuration: Mapped[dict] = mapped_column(JSON, default=dict)
    __table_args__ = (
        CheckConstraint("effective_end IS NULL OR effective_end > effective_start", name="effective_range"),
        Index("ix_config_well_effective", "well_id", "effective_start", "effective_end"),
    )

class WellTool(IdentityMixin, WellLinked, EffectiveMixin, Base):
    __tablename__ = "well_tools"
    tool_type: Mapped[str] = mapped_column(String(60))
    tool_name: Mapped[str] = mapped_column(String(120))
    depth_m: Mapped[float | None] = mapped_column(Float)
    parameters: Mapped[dict] = mapped_column(JSON, default=dict)
    __table_args__ = (
        CheckConstraint("effective_end IS NULL OR effective_end > effective_start", name="effective_range"),
        CheckConstraint("depth_m IS NULL OR depth_m >= 0", name="nonnegative_depth"),
        Index("ix_tool_well_effective", "well_id", "effective_start", "effective_end"),
    )

class DataImportJob(IdentityMixin, Base):
    __tablename__ = "data_import_jobs"
    source_type: Mapped[str] = mapped_column(String(30))
    filename: Mapped[str | None] = mapped_column(String(255))
    file_sha256: Mapped[str | None] = mapped_column(String(64), index=True)
    mapping: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(30), default="待处理")
    total_rows: Mapped[int] = mapped_column(Integer, default=0)
    success_rows: Mapped[int] = mapped_column(Integer, default=0)
    failed_rows: Mapped[int] = mapped_column(Integer, default=0)
    duplicate_rows: Mapped[int] = mapped_column(Integer, default=0)
    errors: Mapped[list] = mapped_column(JSON, default=list)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (CheckConstraint(
        "total_rows >= 0 AND success_rows >= 0 AND failed_rows >= 0 AND duplicate_rows >= 0 "
        "AND success_rows + failed_rows + duplicate_rows <= total_rows", name="row_counts"),)

class WellMeasurement(IdentityMixin, WellLinked, Base):
    __tablename__ = "well_measurements"
    measured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    tubing_pressure_mpa: Mapped[float | None] = mapped_column(Float)
    casing_pressure_mpa: Mapped[float | None] = mapped_column(Float)
    back_pressure_mpa: Mapped[float | None] = mapped_column(Float)
    instantaneous_flow_m3_h: Mapped[float | None] = mapped_column(Float)
    cumulative_flow_m3: Mapped[float | None] = mapped_column(Float)
    gas_temperature_c: Mapped[float | None] = mapped_column(Float)
    liquid_rate_m3_d: Mapped[float | None] = mapped_column(Float)
    quality_flags: Mapped[list] = mapped_column(JSON, default=list)
    source_type: Mapped[str] = mapped_column(String(30), default="manual")
    is_demo: Mapped[bool] = mapped_column(Boolean, default=True)
    import_job_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("data_import_jobs.id", ondelete="RESTRICT"))
    __table_args__ = (UniqueConstraint("well_id", "measured_at", name="uq_measurement_well_time"),)

class WellMeasureEvent(IdentityMixin, WellLinked, EffectiveMixin, Base):
    __tablename__ = "well_measure_events"
    measure_type: Mapped[str] = mapped_column(String(60))
    parameters: Mapped[dict] = mapped_column(JSON, default=dict)
    notes: Mapped[str | None] = mapped_column(Text)
    __table_args__ = (
        CheckConstraint("effective_end IS NULL OR effective_end > effective_start", name="effective_range"),
        Index("ix_measure_well_effective", "well_id", "effective_start", "effective_end"),
    )

class WellOperationEvent(IdentityMixin, WellLinked, EffectiveMixin, Base):
    __tablename__ = "well_operation_events"
    operation_type: Mapped[str] = mapped_column(String(40))
    planned: Mapped[bool] = mapped_column(Boolean)
    reason: Mapped[str | None] = mapped_column(Text)
    __table_args__ = (
        CheckConstraint("effective_end IS NULL OR effective_end > effective_start", name="effective_range"),
        Index("ix_operation_well_effective", "well_id", "effective_start", "effective_end"),
    )

class WellFaultHistory(IdentityMixin, WellLinked, EffectiveMixin, Base):
    __tablename__ = "well_fault_histories"
    fault_type: Mapped[str] = mapped_column(String(80))
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    evidence: Mapped[dict] = mapped_column(JSON, default=dict)
    notes: Mapped[str | None] = mapped_column(Text)
    __table_args__ = (CheckConstraint("effective_end IS NULL OR effective_end > effective_start", name="effective_range"),)

class AnalysisRule(IdentityMixin, Base):
    __tablename__ = "analysis_rules"
    code: Mapped[str] = mapped_column(String(60))
    name: Mapped[str] = mapped_column(String(120))
    version: Mapped[str] = mapped_column(String(30))
    applicable_states: Mapped[list] = mapped_column(JSON, default=list)
    input_parameters: Mapped[list] = mapped_column(JSON, default=list)
    configuration: Mapped[dict] = mapped_column(JSON, default=dict)
    function_key: Mapped[str] = mapped_column(String(120))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    __table_args__ = (UniqueConstraint("code", "version", name="uq_rule_code_version"),)

class AnalysisRun(IdentityMixin, Base):
    __tablename__ = "analysis_runs"
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(30), default="待执行")
    rule_snapshot: Mapped[list] = mapped_column(JSON, default=list)
    data_cutoff: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    summary: Mapped[dict] = mapped_column(JSON, default=dict)
    error_message: Mapped[str | None] = mapped_column(Text)
    __table_args__ = (CheckConstraint("window_end > window_start", name="window_range"),)

class WellBaseline(IdentityMixin, WellLinked, Base):
    __tablename__ = "well_baselines"
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    production_mode: Mapped[str] = mapped_column(String(40))
    algorithm_version: Mapped[str] = mapped_column(String(30))
    statistics: Mapped[dict] = mapped_column(JSON)
    sample_count: Mapped[int] = mapped_column(Integer)
    analysis_run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("analysis_runs.id", ondelete="RESTRICT"))
    __table_args__ = (
        CheckConstraint("window_end > window_start", name="window_range"),
        CheckConstraint("sample_count > 0", name="positive_samples"),
        Index("ix_baseline_well_window", "well_id", "window_start", "window_end"),
    )

class WellAnomaly(IdentityMixin, WellLinked, Base):
    __tablename__ = "well_anomalies"
    analysis_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("analysis_runs.id", ondelete="RESTRICT"), index=True)
    rule_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("analysis_rules.id", ondelete="RESTRICT"), index=True)
    anomaly_type: Mapped[str] = mapped_column(String(60), index=True)
    severity: Mapped[str] = mapped_column(String(30), default="提示")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    evidence: Mapped[dict] = mapped_column(JSON)
    rule_snapshot: Mapped[dict] = mapped_column(JSON)
    fingerprint: Mapped[str] = mapped_column(String(128))
    __table_args__ = (
        UniqueConstraint("analysis_run_id", "fingerprint", name="uq_anomaly_run_fingerprint"),
        CheckConstraint("ended_at IS NULL OR ended_at > started_at", name="event_range"),
        Index("ix_anomaly_well_start", "well_id", "started_at"),
    )

class AnomalyReview(IdentityMixin, Base):
    __tablename__ = "anomaly_reviews"
    anomaly_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("well_anomalies.id", ondelete="RESTRICT"), index=True)
    reviewer: Mapped[str] = mapped_column(String(80))
    decision: Mapped[str] = mapped_column(String(60))
    comment: Mapped[str] = mapped_column(Text)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

class WellStatusSnapshot(IdentityMixin, WellLinked, Base):
    __tablename__ = "well_status_snapshots"
    analysis_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("analysis_runs.id", ondelete="RESTRICT"), index=True)
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    screening_status: Mapped[str] = mapped_column(String(40), default="数据待核实", index=True)
    production_state: Mapped[str] = mapped_column(String(40), default="工况待核实")
    evidence: Mapped[dict] = mapped_column(JSON, default=dict)
    __table_args__ = (
        UniqueConstraint("well_id", name="uq_snapshot_well"),
        CheckConstraint("screening_status IN ('可信正常', '疑似异常', '措施影响', '数据待核实', '工况待核实')", name="screening_status"),
    )

class WellAnalysisResult(IdentityMixin, WellLinked, Base):
    """每次任务的单井历史结果，与可更新的最新状态快照分离。"""
    __tablename__ = "well_analysis_results"
    analysis_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("analysis_runs.id", ondelete="RESTRICT"), index=True)
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    screening_status: Mapped[str] = mapped_column(String(40), index=True)
    production_state: Mapped[str] = mapped_column(String(40))
    evidence: Mapped[dict] = mapped_column(JSON)
    __table_args__ = (
        UniqueConstraint("analysis_run_id", "well_id", name="uq_analysis_result_run_well"),
        CheckConstraint("screening_status IN ('可信正常', '疑似异常', '措施影响', '数据待核实', '工况待核实')", name="screening_status"),
    )


# 每个依井实体显式双向关联；数据库限制删除父记录，保留历史追溯。
for cls in (WellConfigHistory, WellTool, WellMeasurement, WellMeasureEvent,
            WellOperationEvent, WellFaultHistory, WellBaseline, WellAnomaly, WellStatusSnapshot, WellAnalysisResult):
    attr = cls.__tablename__
    setattr(Well, attr, relationship(cls, back_populates="well", passive_deletes="all"))
    setattr(cls, "well", relationship(Well, back_populates=attr))
WellAnomaly.rule = relationship(AnalysisRule)
WellAnomaly.analysis_run = relationship(AnalysisRun)
WellAnomaly.reviews = relationship(AnomalyReview, back_populates="anomaly", passive_deletes="all")
AnomalyReview.anomaly = relationship(WellAnomaly, back_populates="reviews")
WellMeasurement.import_job = relationship(DataImportJob)
WellBaseline.analysis_run = relationship(AnalysisRun)
WellStatusSnapshot.analysis_run = relationship(AnalysisRun)

WellAnalysisResult.analysis_run = relationship(AnalysisRun)
