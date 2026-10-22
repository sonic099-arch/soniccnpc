"""配置项全部必填，不从算法内补写阈值。默认值仅来自独立JSON演示配置。"""
import json
import re
from pathlib import Path
from pydantic import BaseModel, ConfigDict, Field, model_validator

class Config(BaseModel):
    model_config = ConfigDict(extra='forbid',allow_inf_nan=False)

class PolicyConfig(Config):
    sample_minutes: float = Field(gt=0,title='采样间隔（分钟）')
    lookback_hours: float = Field(gt=0,title='默认回看窗口（小时）')
    evaluation_hours: float = Field(gt=0,title='近期评估窗口（小时）')
    baseline_hours: float = Field(gt=0,title='基线最大跨度（小时）')
    baseline_guard_hours: float = Field(gt=0,title='基线与窗口末端隔离（小时）')
    minimum_samples: int = Field(ge=2,title='最低分析样本数')
    baseline_min_samples: int = Field(ge=2,title='最低基线样本数')
    zero_flow: float = Field(ge=0,title='近零流量界限（m³/h）')
    max_natural_decline_daily: float = Field(gt=0,lt=1,title='允许自然递减上限（每天比例）')
    natural_decline_min_r2: float = Field(ge=0,le=1,title='自然递减趋势拟合可信度下限（R²）')
    natural_decline_label_daily: float = Field(ge=0,lt=1,title='自然递减状态提示下限（每天比例）')
    valid_modes: list[str] = Field(min_length=1,title='支持的生产方式')
    known_tools: list[str] = Field(min_length=1,title='已识别工具类型')
    known_measures: list[str] = Field(min_length=1,title='已识别措施类型')
    transition_guard_hours: float = Field(ge=0,title='计划操作边界缓冲（小时）')
    merge_gap_hours: float = Field(ge=0,title='同类事件合并间隔（小时）')
    max_window_hours: float = Field(gt=0,title='最大分析窗口（小时）')

    @model_validator(mode='after')
    def ranges(self):
        if not set(self.valid_modes).issubset({'自喷','泡排','间歇','注醇','其他排采'}):
            raise ValueError('不能通过配置声明引擎尚未支持的生产方式')
        if self.evaluation_hours >= self.lookback_hours or self.lookback_hours > self.max_window_hours:
            raise ValueError('窗口大小关系无效')
        if self.natural_decline_label_daily >= self.max_natural_decline_daily:
            raise ValueError('递减提示下限必须小于递减上限')
        return self

class QualityConfig(Config):
    required_fields: list[str] = Field(min_length=1,title='必需动态参数')
    minimum_recent_coverage: float = Field(gt=0,le=1,title='近期有效采样覆盖率下限')
    max_gap_hours: float = Field(gt=0,title='最大允许采样间隔（小时）')
    future_minutes: float = Field(ge=0,title='未来时间容差（分钟）')

    @model_validator(mode='after')
    def required_inputs(self):
        essential={'tubing_pressure_mpa','casing_pressure_mpa','back_pressure_mpa','instantaneous_flow_m3_h','cumulative_flow_m3','gas_temperature_c'}
        if not essential.issubset(self.required_fields):raise ValueError('质量规则不能省略六个核心参数')
        return self

class FreezeConfig(Config):
    freeze_hours: float = Field(gt=0,title='冻结持续时间（小时）')
    value_tolerance: float = Field(ge=0,title='参数恒定比较容差')

class MeterConfig(Config):
    relative_tolerance: float = Field(gt=0,lt=1,title='累计增量相对误差容差')
    absolute_tolerance_m3: float = Field(ge=0,title='累计增量绝对误差容差（m³）')
    reset_tolerance_m3: float = Field(ge=0,title='累计复位负跳变容差（m³）')
    max_interval_hours: float = Field(gt=0,title='积分检查最大采样间隔（小时）')

class OperationConfig(Config):
    stopped_hours: float = Field(gt=0,title='停井判断持续时间（小时）')

class FlowConfig(Config):
    decline_ratio: float = Field(gt=0,lt=1,title='低于趋势基线的减产比例')
    sustain_hours: float = Field(gt=0,title='减产最短持续时间（小时）')

class PressureConfig(Config):
    step_mpa: float = Field(gt=0,title='压力单步变化界限（MPa）')
    range_mpa: float = Field(gt=0,title='近期压力波动范围（MPa）')
    max_step_interval_hours: float = Field(gt=0,title='压力突变比较最大采样间隔（小时）')

class CorrelationConfig(Config):
    flow_ratio: float = Field(gt=0,lt=1,title='流量相对基线比例上限')
    gap_growth_mpa: float = Field(gt=0,title='套油压差扩大界限（MPa）')
    pressure_change_mpa: float = Field(gt=0,title='油压变化界限（MPa）')
    liquid_growth_m3_d: float = Field(ge=0,title='辅助产液量增长界限（m³/d）')

class TemperatureConfig(Config):
    low_temperature_c: float = Field(title='低温界限（℃）')
    temperature_drop_c: float = Field(gt=0,title='相对基线降温界限（℃）')
    temperature_rise_c: float = Field(gt=0,title='相对基线升温界限（℃）')
    flow_ratio: float = Field(gt=0,lt=1,title='减产关联比例上限')
    pressure_growth_mpa: float = Field(gt=0,title='油压关联增量（MPa）')
    sustain_hours: float = Field(gt=0,title='关联低温最短持续时间（小时）')

class MeasurePeriodConfig(Config):
    recovery_hours: float = Field(ge=0,title='措施恢复缓冲（小时）')

class MeasureEffectConfig(Config):
    pre_hours: float = Field(gt=0,title='措施前参照窗口（小时）')
    post_hours: float = Field(gt=0,title='措施后评估窗口（小时）')
    minimum_post_samples: int = Field(ge=2,title='措施后最低样本数')
    effect_horizon_hours: float = Field(gt=0,title='措施效果回看上限（小时）')
    recovery_ratio: float = Field(gt=0,le=1,title='措施后恢复比例下限')

CONFIG_TYPES={'SYS001':PolicyConfig,'DQ001':QualityConfig,'DQ002':FreezeConfig,'DQ003':MeterConfig,
              'OP001':OperationConfig,'FL001':FlowConfig,'PR001':PressureConfig,'PR002':CorrelationConfig,
              'TP001':TemperatureConfig,'ME001':MeasurePeriodConfig,'ME002':MeasureEffectConfig}

def default_profile():
    return json.loads(Path(__file__).with_name('default_rules.json').read_text(encoding='utf8'))

DEFINITIONS={r['code']:r for r in default_profile()['rules']}

def validate_rule(rule):
    if not re.fullmatch(r'\d+\.\d+\.\d+',rule.version):raise ValueError('规则版本必须使用主版本.次版本.修订号')
    if rule.code not in DEFINITIONS: raise ValueError(f'未知规则编号：{rule.code}')
    if rule.function_key != DEFINITIONS[rule.code]['function_key']: raise ValueError(f'{rule.code}分析函数不受支持')
    config=CONFIG_TYPES[rule.code].model_validate(rule.configuration)
    if rule.code=='DQ001':
        from app.analysis.types import PARAMETERS
        if not set(config.required_fields).issubset(PARAMETERS): raise ValueError('质量规则包含未知参数')
    if not rule.applicable_states or not set(rule.applicable_states).issubset({'全部',*DEFINITIONS['SYS001']['configuration']['valid_modes']}):
        raise ValueError(f'{rule.code}适用工况无效')
    return config.model_dump()
