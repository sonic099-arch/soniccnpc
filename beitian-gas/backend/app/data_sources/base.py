"""统一接入契约。任务2实现 Excel/模拟适配器；真实数据库实现须单独授权连接。"""
from datetime import datetime
from typing import Protocol, Iterator
from pydantic import BaseModel, AwareDatetime, ConfigDict

class MeasurementRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    well_number: str
    measured_at: AwareDatetime
    tubing_pressure_mpa: float | None = None
    casing_pressure_mpa: float | None = None
    back_pressure_mpa: float | None = None
    instantaneous_flow_m3_h: float | None = None
    cumulative_flow_m3: float | None = None
    gas_temperature_c: float | None = None
    liquid_rate_m3_d: float | None = None
    is_demo: bool = True

class DataSource(Protocol):
    def read_measurements(self, start: datetime, end: datetime) -> Iterator[MeasurementRecord]: ...

class DatabaseDataSource:
    """任务1测试桩：仅读取注入的标准记录，绝不创建外部数据库连接。"""
    def __init__(self, records: tuple[MeasurementRecord, ...] = ()):
        self.records = records

    def read_measurements(self, start: datetime, end: datetime) -> Iterator[MeasurementRecord]:
        return (r for r in self.records if start <= r.measured_at < end)
