<script setup lang="ts">
import {computed} from 'vue'
import {displayTime} from '../analysisApi'
const props=defineProps<{detail:Record<string,unknown>|null}>()
function object(value:unknown):Record<string,any>{return value&&typeof value==='object'&&!Array.isArray(value)?value as Record<string,any>:{}}
const evidence=computed(()=>object(props.detail?.evidence))
const provenance=computed(()=>object(evidence.value.provenance))
const rule=computed(()=>object(props.detail?.rule_snapshot))
const parameters=[['tubing_pressure_mpa','油压（MPa）'],['casing_pressure_mpa','套压（MPa）'],['back_pressure_mpa','回压（MPa）'],['instantaneous_flow_m3_h','瞬时流量（m³/h）'],['cumulative_flow_m3','累计流量（m³）'],['gas_temperature_c','气流温度（℃）'],['liquid_rate_m3_d','产液量（m³/d）']]
const samples=computed(()=>Array.isArray(evidence.value.recent_points)?evidence.value.recent_points:[])
const reviews=computed(()=>Array.isArray(props.detail?.reviews)?props.detail.reviews:[])
function number(value:unknown){return typeof value==='number'?Number(value.toFixed(3)).toLocaleString('zh-CN'):'—'}
</script>
<template>
 <div v-if="detail">
  <el-descriptions :column="1" border>
   <el-descriptions-item label="井号">{{provenance.well_number??'—'}}</el-descriptions-item>
   <el-descriptions-item label="事件类型">{{detail.anomaly_type??'—'}}</el-descriptions-item>
   <el-descriptions-item label="判断规则">{{rule.name??'—'}}（{{rule.code??'—'}} / {{rule.version??'—'}}）</el-descriptions-item>
   <el-descriptions-item label="数据窗口（北京时间）">{{displayTime(provenance.window_start)}} 至 {{displayTime(provenance.window_end)}}</el-descriptions-item>
   <el-descriptions-item label="样本数量">{{provenance.sample_count??'—'}}</el-descriptions-item>
   <el-descriptions-item label="数据性质">{{provenance.is_demo?'演示数据':'需核实来源与现场口径'}}</el-descriptions-item>
  </el-descriptions>
  <h3>判断窗口内的代表性采样</h3><p>下列为部分原始采样，完整规则指标、措施关联和输入摘要见技术追溯记录。</p>
  <el-table :data="samples" border empty-text="无可展示采样" style="width:100%">
   <el-table-column label="采样时间（北京时间）" width="185"><template #default="{row}">{{displayTime(row.measured_at)}}</template></el-table-column>
   <el-table-column v-for="[key,label] in parameters" :key="key" :label="label" min-width="140"><template #default="{row}">{{number(row[key])}}</template></el-table-column>
   <el-table-column prop="measurement_id" label="采样ID" min-width="300"/>
  </el-table>
  <h3>人工复核记录</h3><el-table :data="reviews" border empty-text="暂无人工复核记录"><el-table-column prop="reviewer" label="复核人"/><el-table-column prop="decision" label="复核结论"/><el-table-column prop="comment" label="说明"/></el-table>
  <el-collapse><el-collapse-item title="技术追溯记录（规则配置、指标、事件ID与输入摘要）"><pre>{{JSON.stringify(detail,null,2)}}</pre></el-collapse-item></el-collapse>
 </div>
</template>
<style scoped>h3{margin-top:24px}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:13px;line-height:1.6}.el-collapse{margin-top:20px}</style>
