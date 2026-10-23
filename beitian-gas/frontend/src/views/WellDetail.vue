<script setup lang="ts">
import {computed,ref,watch,onBeforeUnmount} from 'vue'
import {useRoute,useRouter} from 'vue-router'
import {connect,disconnect} from 'echarts/core'
import {screening,parameters,runLabel,statusType,type Options,type WellDetailData,type SeriesData} from '../screeningApi'
import {displayTime} from '../analysisApi'
import {request} from '../importApi'
import {curveOption} from '../chartOptions'
import EChart from '../components/EChart.vue'
import ReportWindow from '../components/ReportWindow.vue'
import AnalysisEvidence from '../components/AnalysisEvidence.vue'
const route=useRoute(),router=useRouter(),detail=ref<WellDetailData|null>(null),options=ref<Options|null>(null),series=ref<SeriesData|null>(null)
const loading=ref(false),curveLoading=ref(false),error=ref(''),curveError=ref(''),range=ref<Date[]>([]),selectedRun=ref(''),preset=ref('window'),drawer=ref(false),evidence=ref<Record<string,unknown>|null>(null),evidenceError=ref('')
const group=`well-curves-${Math.random().toString(36).slice(2)}`
let loadSequence=0,curveSequence=0
const chartOptions=computed(()=>series.value?parameters.map((p,i)=>curveOption(series.value!,p.key,i)):[])
async function load(){
 const seq=++loadSequence;++curveSequence;loading.value=true;error.value='';series.value=null;detail.value=null
 try{
  const run_id=typeof route.query.run_id==='string'?route.query.run_id:''
  const o=await screening<Options>('/options',{run_id});if(seq!==loadSequence)return
  const d=await screening<WellDetailData>('/wells/'+route.params.id,{run_id:o.selected_run?.id});if(seq!==loadSequence)return
  options.value=o;selectedRun.value=o.selected_run?.id??'';detail.value=d;preset.value='window'
  if(d.run)range.value=[new Date(d.run.window_start),new Date(d.run.window_end)]
  else if(d.latest_measurement_at){const end=new Date(Date.parse(d.latest_measurement_at)+1);range.value=[new Date(end.getTime()-14*86400000),end]}
  else range.value=[]
  await loadCurves()
 }catch(e){if(seq===loadSequence)error.value=(e as Error).message}
 finally{if(seq===loadSequence)loading.value=false}
}
async function loadCurves(){
 const seq=++curveSequence;curveLoading.value=true;curveError.value=''
 try{
  const d=await screening<SeriesData>('/wells/'+route.params.id+'/series',{run_id:selectedRun.value,...(range.value?.length===2?{window_start:range.value[0].toISOString(),window_end:range.value[1].toISOString()}:{})})
  if(seq===curveSequence){series.value=d;connect(group)}
 }catch(e){if(seq===curveSequence){series.value=null;curveError.value=(e as Error).message}}
 finally{if(seq===curveSequence)curveLoading.value=false}
}
function changeRun(){router.push({query:{run_id:selectedRun.value||undefined}})}
async function selectPreset(value:string|number|boolean|undefined){
 preset.value=String(value)
 const d=detail.value;if(!d)return
 const end=new Date(d.run?.window_end??(d.latest_measurement_at?Date.parse(d.latest_measurement_at)+1:Date.now()))
 if(value==='window'&&d.run)range.value=[new Date(d.run.window_start),end]
 else range.value=[new Date(end.getTime()-Number(value==='window'?14:value)*86400000),end]
 await loadCurves()
}
async function showEvidence(id:string){drawer.value=true;evidence.value=null;evidenceError.value='';try{evidence.value=await request<Record<string,unknown>>('/analysis/anomalies/'+id)}catch(e){evidenceError.value=(e as Error).message}}
watch(()=>route.fullPath,load,{immediate:true});onBeforeUnmount(()=>{loadSequence++;curveSequence++;disconnect(group)})
</script>
<template>
 <div class="page well-detail" v-loading="loading">
  <div class="page-heading"><div><p class="eyebrow"><router-link :to="{path:'/wells',query:selectedRun?{run_id:selectedRun}:{}}">气井列表</router-link> / 单井分析</p><h1>{{detail?.well.well_number??'单井分析'}}</h1><p class="muted">{{detail?.well.area??'加载井信息'}} · 七参数联动曲线与规则证据</p></div><el-button @click="load">刷新单井</el-button></div>
  <el-alert v-if="error" :title="error" type="error" :closable="false"/>
  <template v-if="detail">
   <el-alert v-if="detail.well.is_demo||series?.contains_demo" title="演示数据：曲线、参数和规则阈值不构成现场工艺标准；疑似积液、冻堵仅提供辅助提示。" type="warning" :closable="false"/>
   <el-card shadow="never" class="well-summary"><div class="summary-row"><div><el-tag :type="statusType(detail.result?.screening_status??'未分析')" size="large">{{detail.result?.screening_status??'未分析'}}</el-tag><span>{{detail.result?.production_state??'未参与本次任务，请先运行分析'}}</span></div><select v-model="selectedRun" class="report-select run-select" aria-label="单井分析任务" :disabled="loading" @change="changeRun"><option v-if="!options?.runs.length" value="">暂无分析任务</option><option v-for="run in options?.runs??[]" :key="run.id" :value="run.id">{{runLabel(run)}}</option></select></div><p class="muted small-copy">气井ID：{{detail.well.id}}　最新原始采样：{{displayTime(detail.latest_measurement_at)}}</p><ReportWindow :run="detail.run"/></el-card>
   <el-card shadow="never" class="curve-controls"><template #header><strong>动态参数曲线</strong><span class="muted count-label">7项 · 统一时间轴 · 图内滚轮缩放</span></template>
    <div class="range-row"><el-radio-group v-model="preset" @change="selectPreset"><el-radio-button value="window">分析窗口</el-radio-button><el-radio-button value="7">末7天</el-radio-button><el-radio-button value="14">末14天</el-radio-button><el-radio-button value="30">末30天</el-radio-button></el-radio-group><el-date-picker v-model="range" type="datetimerange" start-placeholder="开始（本地时间）" end-placeholder="结束（不含）" :clearable="false"/><el-button type="primary" :loading="curveLoading" @click="preset='custom';loadCurves()">更新曲线</el-button></div>
    <p class="muted small-copy">天数以所选分析窗口终点为参考。曲线时间范围变化不会重新计算规则。横轴及下方事件表显示北京时间。</p><p class="mark-legend"><span class="measure-marker"/>蓝色虚线：措施开始 / 浅蓝区域：有效期　<span class="anomaly-marker"/>橙色虚线：异常开始</p>
   </el-card>
   <el-alert v-if="curveError" :title="curveError" type="error" :closable="false"/>
   <div v-if="series" v-loading="curveLoading">
    <p class="muted small-copy">{{series.source_note}}。当前窗口 {{series.total}} 个采样；第七参数暂定产液量。</p>
    <el-empty v-if="!series.total" description="所选时间范围没有测量数据，请调整窗口"/>
    <div class="curve-grid" v-else><el-card v-for="(parameter,index) in parameters" :key="parameter.key" shadow="never" :class="{'wide-curve':index===3}"><template #header><strong>{{parameter.name}}</strong><span class="muted count-label">{{parameter.unit}}</span></template><EChart :option="chartOptions[index]" :label="parameter.name+'原始曲线'" :group="group" height="285px"/></el-card></div>
    <el-card shadow="never" class="event-card"><template #header><strong>措施与操作时间</strong><span class="muted count-label">包含与窗口重叠的有效区间</span></template><el-table :data="series.measures" empty-text="窗口内无措施记录"><el-table-column prop="measure_type" label="措施类型"/><el-table-column label="开始（北京时间）"><template #default="{row}">{{displayTime(row.effective_start)}}</template></el-table-column><el-table-column label="结束（北京时间）"><template #default="{row}">{{row.effective_end?displayTime(row.effective_end):'持续有效'}}</template></el-table-column><el-table-column prop="notes" label="备注"/></el-table><el-collapse><el-collapse-item title="开关井等操作记录"><el-table :data="series.operations" empty-text="窗口内无操作记录"><el-table-column prop="operation_type" label="操作"/><el-table-column label="计划情况"><template #default="{row}">{{row.planned?'计划操作':'非计划操作'}}</template></el-table-column><el-table-column label="开始（北京时间）"><template #default="{row}">{{displayTime(row.effective_start)}}</template></el-table-column><el-table-column label="结束（北京时间）"><template #default="{row}">{{row.effective_end?displayTime(row.effective_end):'持续有效'}}</template></el-table-column></el-table></el-collapse-item></el-collapse></el-card>
    <el-card shadow="never" class="event-card"><template #header><strong>异常与影响事件</strong></template><el-table :data="series.anomalies" empty-text="本窗口无分析事件"><el-table-column prop="anomaly_type" label="事件类型" min-width="230"/><el-table-column label="规则版本"><template #default="{row}">{{row.rule_code}} / {{row.rule_version}}</template></el-table-column><el-table-column label="开始（北京时间）"><template #default="{row}">{{displayTime(row.started_at)}}</template></el-table-column><el-table-column label="结束（北京时间）"><template #default="{row}">{{displayTime(row.ended_at)}}</template></el-table-column><el-table-column label="判断依据" width="100"><template #default="{row}"><el-button link type="primary" @click="showEvidence(row.id)">查看证据</el-button></template></el-table-column></el-table></el-card>
   </div>
   <el-card v-if="detail.result" shadow="never" class="event-card"><template #header><strong>本次规则执行结果</strong><span class="muted count-label">规则结果不随曲线窗口变化</span></template><el-table :data="detail.result.evidence.rule_results" empty-text="暂无规则结果"><el-table-column prop="code" label="编号" width="100"/><el-table-column prop="name" label="规则名称" min-width="210"/><el-table-column prop="version" label="版本" width="100"/><el-table-column prop="outcome" label="执行结果" width="110"/><el-table-column label="判断说明" min-width="300"><template #default="{row}">{{row.outcome==='命中'?`命中${row.event_count}条事件，请结合上方事件证据复核`:row.message}}</template></el-table-column><el-table-column prop="event_count" label="事件数" width="90"/></el-table></el-card>
  </template>
  <el-drawer v-model="drawer" title="单井异常判断证据" size="75%"><el-alert v-if="evidenceError" :title="evidenceError" type="error" :closable="false"/><AnalysisEvidence :detail="evidence"/></el-drawer>
 </div>
</template>
<style scoped>.well-summary,.curve-controls,.event-card{margin:20px 0}.summary-row,.range-row{display:flex;align-items:center;justify-content:space-between;gap:16px;flex-wrap:wrap}.summary-row .el-tag{margin-right:12px}.small-copy{font-size:12px}.curve-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:20px}.curve-grid .el-card{min-width:0}.wide-curve{grid-column:1/-1;grid-row:1}.mark-legend{font-size:12px;color:#6b8087}.measure-marker,.anomaly-marker{display:inline-block;width:20px;border-top:2px dashed #3893af;vertical-align:middle}.anomaly-marker{border-color:#df744f}@media(max-width:1000px){.curve-grid{grid-template-columns:1fr}}@media(max-width:600px){.summary-row{align-items:stretch}.range-row .el-date-editor{max-width:100%}}</style>
