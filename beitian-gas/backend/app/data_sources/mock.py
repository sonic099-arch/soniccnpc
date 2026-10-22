"""确定性、相关联的演示曲线；所有参数均非现场工艺判定标准。"""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import NAMESPACE_URL, uuid5
import numpy as np
import pandas as pd
from app.data_sources.base import MeasurementRecord

DISCLAIMER = "仅为演示数据；曲线、参数及预期标签不构成现场工艺判定标准或自动诊断。"
SCENARIOS = [
    ("stable", "稳定自喷井", "正常生产", "可信正常", []),
    ("natural_decline", "自然递减井", "自然递减生产", "可信正常", []),
    ("abnormal_decline", "异常减产井", "生产下降待核实", "疑似异常", ["持续减产"]),
    ("liquid_hint", "疑似积液井", "工况待核实", "疑似异常", ["压力流量关联异常", "疑似积液辅助提示"]),
    ("freeze_hint", "疑似冻堵井", "工况待核实", "疑似异常", ["低温及压力流量关联异常", "疑似冻堵辅助提示"]),
    ("foam_normal", "正常泡排措施井", "泡排措施期间", "措施影响", ["措施影响"]),
    ("foam_poor", "泡排后生产效果不佳井", "措施效果待核实", "疑似异常", ["措施后未恢复"]),
    ("cyclic", "周期性生产井", "按计划周期生产", "可信正常", []),
    ("planned_stop", "计划停井", "计划关井", "可信正常", []),
    ("unplanned_stop", "非计划停井", "非计划关井", "疑似异常", ["非计划停井"]),
    ("frozen_data", "数据冻结井", "数据待核实", "数据待核实", ["数据冻结"]),
    ("missing_data", "数据缺失井", "数据待核实", "数据待核实", ["数据缺失"]),
    ("counter_reset", "累计流量复位井", "计量待核实", "数据待核实", ["累计量复位"]),
]
PARAMETERS = ["tubing_pressure_mpa", "casing_pressure_mpa", "back_pressure_mpa",
              "instantaneous_flow_m3_h", "cumulative_flow_m3", "gas_temperature_c", "liquid_rate_m3_d"]

@dataclass
class MockDataset:
    wells: list[dict]
    configurations: list[dict]
    tools: list[dict]
    measures: list[dict]
    operations: list[dict]
    expected: list[dict]
    measurements: pd.DataFrame
    seed: int

class MockDataSource:
    def __init__(self, count=1000, days=14, seed=20261021,
                 start=datetime(2026, 10, 1, tzinfo=timezone.utc)):
        if not 13 <= count <= 5000 or not 4 <= days <= 90:
            raise ValueError("演示井数须为13至5000，天数须为4至90")
        if start.tzinfo is None or start.utcoffset() is None:
            raise ValueError("起始时间必须包含时区")
        if count * days * 24 > 1_000_000:
            raise ValueError("单次生成最多100万条演示记录，请分批生成")
        if not 0 <= seed <= 2**32-1:
            raise ValueError("随机种子须为0至2³²-1")
        self.count, self.days, self.seed = count, days, seed
        self.start = start.astimezone(timezone.utc)
        self._dataset = None

    def generate(self) -> MockDataset:
        if self._dataset is not None:
            return self._dataset
        n = self.days * 24
        x = np.arange(n)
        times = [self.start + timedelta(hours=int(i)) for i in x]
        wells, configs, tools, measures, operations, expected, frames = ([] for _ in range(7))
        for i in range(self.count):
            rng = np.random.default_rng(np.random.SeedSequence([self.seed, i]))
            key, title, state, screening, labels = SCENARIOS[i % len(SCENARIOS)]
            number = f"演示-BT-{i+1:04d}"
            well_id = uuid5(NAMESPACE_URL, "beitian/demo/" + number)
            wells.append(dict(id=well_id, well_number=number, area=f"演示工区{i%4+1}", is_demo=True,
                              description=f"{DISCLAIMER} 场景：{title}"))
            mode = "泡排" if key.startswith("foam") else "间歇" if key == "cyclic" else "自喷"
            if key == "stable" and i % 3 == 0:
                mode = "注醇"
            if key == "stable" and i % 3 == 1:
                mode = "其他排采"
            config = {"is_demo": True, "demo_scenario": key, "warning": DISCLAIMER}
            if key == "cyclic":
                config["cycle"] = {"period_hours": 24, "open_hours": 8, "anchor": self.start.isoformat()}
            configs.append(dict(well_id=well_id, production_mode=mode, configuration=config,
                                effective_start=self.start, effective_end=None))
            tools.append(dict(well_id=well_id, tool_type="速度管柱" if mode == "泡排" else "井下节流器",
                              tool_name="演示井筒工具", depth_m=float(1500+i%30*25),
                              parameters={"is_demo": True, "warning": DISCLAIMER},
                              effective_start=self.start, effective_end=None))
            base = rng.uniform(450, 1300)
            # 共同低频扰动联动流量、背压、温度；压力由简化阻力关系驱动。
            latent = np.convolve(rng.normal(0, 0.012, n+4), np.ones(5)/5, mode="valid")
            factor = np.ones(n)
            onset = n - 48
            if key == "natural_decline": factor = np.exp(-x / (n * 10))
            if key in ("abnormal_decline", "liquid_hint", "freeze_hint"):
                factor[onset:] = np.linspace(1, 0.24, n-onset)
            if key == "liquid_hint": factor[onset:] *= 0.8 + 0.2*np.sin(x[onset:]*0.8)
            if key == "foam_normal":
                onset = n-18
                factor[onset:] = 1 - 0.5*np.exp(-(x[onset:]-onset)/5)
            if key == "foam_poor":
                onset = n-72
                factor[onset:] = 0.42 + 0.12*np.exp(-(x[onset:]-onset)/6)
            if key == "cyclic": factor[(x % 24) >= 8] = 0
            if key in ("planned_stop", "unplanned_stop"):
                onset = n-24
                factor[onset:] = 0
            flow = np.maximum(0, base*factor*(1+latent))
            back = 2.0 + 0.25*flow/base + latent*2
            tubing = 8.0 + (i%8)*0.3 - 1.2*(flow/base)**2 + latent*2
            casing = tubing + 0.8 + 0.1*np.cos(x/24)
            temperature = 15 + 4*flow/base + latent*8
            liquid = 0.2 + 0.4*flow/base
            if key == "liquid_hint":
                obstruction = 1-factor[onset:]
                tubing[onset:] -= 3*obstruction
                casing[onset:] += 1.3*obstruction
                liquid[onset:] += 2*obstruction
            if key == "freeze_hint":
                temperature[onset:] -= np.linspace(0, 28, n-onset)
                tubing[onset:] += (1-factor[onset:])*1.5
                back[onset:] -= (1-factor[onset:])*0.4
            cumulative = 10000 + np.r_[0, np.cumsum((flow[:-1]+flow[1:])/2)]
            if key == "counter_reset": cumulative[onset:] -= cumulative[onset]
            values = np.column_stack([tubing, casing, back, flow, cumulative, temperature, liquid])
            if key == "frozen_data":
                onset = n-24
                values[onset:] = values[onset-1]
            if key == "missing_data":
                onset = n-24
                values[onset:, [0, 3, 5]] = np.nan
            values = np.round(values, 6)
            frame = pd.DataFrame(values, columns=PARAMETERS)
            frame.insert(0, "measured_at", times)
            frame.insert(0, "well_number", number)
            frame["is_demo"] = True
            if key == "missing_data": frame = frame.iloc[:-6]  # 同时包含字段缺失和采样间断
            frames.append(frame)
            if key.startswith("foam"):
                measures.append(dict(well_id=well_id, measure_type="泡排", effective_start=times[onset],
                                     effective_end=self.start+timedelta(hours=onset+24),
                                     parameters={"is_demo": True, "warning": DISCLAIMER}, notes="演示泡排事件"))
            if mode in ("注醇", "其他排采"):
                measures.append(dict(well_id=well_id, measure_type="注醇" if mode == "注醇" else "机械排液",
                                     effective_start=times[24], effective_end=times[36],
                                     parameters={"is_demo": True, "warning": DISCLAIMER}, notes="演示排采事件"))
            if key in ("planned_stop", "unplanned_stop"):
                operations.append(dict(well_id=well_id, operation_type="关井", planned=key=="planned_stop",
                                       effective_start=times[onset], effective_end=None, reason=f"演示：{title}"))
            if key == "cyclic":
                for d in range(self.days):
                    for offset, kind, duration in ((0,"开井",8),(8,"关井",16)):
                        t = self.start + timedelta(hours=d*24+offset)
                        operations.append(dict(well_id=well_id, operation_type=kind, planned=True,
                                               effective_start=t, effective_end=t+timedelta(hours=duration), reason="演示周期计划"))
            expected.append(dict(well_number=number, scenario=key, scenario_name=title,
                                 expected_production_state=state, expected_screening_status=screening,
                                 expected_labels=list(labels), onset=times[onset].isoformat() if labels or key == "planned_stop" else None,
                                 is_demo=True, warning=DISCLAIMER))
        self._dataset = MockDataset(wells, configs, tools, measures, operations, expected,
                                     pd.concat(frames, ignore_index=True), self.seed)
        return self._dataset

    def read_measurements(self, start, end):
        frame = self.generate().measurements
        frame = frame.loc[(frame.measured_at >= start) & (frame.measured_at < end)]
        frame = frame.astype(object).where(pd.notna(frame), None)
        for row in frame.to_dict("records"):
            yield MeasurementRecord(**row)
