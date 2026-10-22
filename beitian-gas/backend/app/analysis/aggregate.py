from hashlib import sha256
import json
from datetime import timedelta
from app.analysis.types import clean

class AnomalyAggregator:
    def aggregate(self,well_id,results,rules,gap_hours):
        events=[]
        for result in results:
            for event in result.events:
                events.append({**event,'code':result.code,'rule_id':str(rules[result.code].id),'version':rules[result.code].version})
        events.sort(key=lambda e:(e['code'],e['anomaly_type'],e['started_at']))
        merged=[]
        for event in events:
            if merged and (merged[-1]['code'],merged[-1]['anomaly_type'],merged[-1]['action'])==(event['code'],event['anomaly_type'],event['action']) and event['started_at']<=merged[-1]['ended_at']+timedelta(hours=gap_hours):
                merged[-1]['ended_at']=max(merged[-1]['ended_at'],event['ended_at'])
                merged[-1]['evidence']['merged_evidence'].append(clean(event['evidence']))
            else:
                merged.append({**event,'evidence':{'merged_evidence':[clean(event['evidence'])]}})
        for event in merged:
            key=[well_id,event['code'],event['version'],event['anomaly_type'],event['started_at'].isoformat(),event['ended_at'].isoformat()]
            event['fingerprint']=sha256(json.dumps(key,ensure_ascii=False).encode()).hexdigest()
        return merged

class WellStatusClassifier:
    def classify(self,state,baseline,results):
        actions={e['action'] for result in results for e in result.events}
        kinds={e['anomaly_type'] for result in results for e in result.events}
        if 'verify_data' in actions:
            data_kinds={e['anomaly_type'] for r in results if r.code.startswith('DQ') for e in r.events}
            production='计量待核实' if data_kinds and data_kinds.issubset({'累计量复位','累计与瞬时流量不一致'}) else '数据待核实'
            return '数据待核实',production
        if not state.known or not baseline.valid or 'verify_state' in actions or any(not r.coverage for r in results):
            return '工况待核实','工况待核实'
        if 'abnormal' in actions:
            if '措施后未恢复' in kinds: production='措施效果待核实'
            elif any('辅助提示' in kind for kind in kinds): production='工况待核实'
            elif '非计划停井' in kinds: production='非计划关井'
            elif '持续减产' in kinds: production='生产下降待核实'
            else: production='工况待核实'
            return '疑似异常',production
        if 'measure' in actions:return '措施影响',state.production_state
        return '可信正常',state.production_state
