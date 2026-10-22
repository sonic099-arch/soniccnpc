<script setup lang="ts">
import {ref,onMounted} from 'vue'
import AnalysisEvidence from '../components/AnalysisEvidence.vue'
import {request} from '../importApi'
import {runAnalysis,initializeRules,displayTime,screeningStatuses,type Run,type AnalysisEvent} from '../analysisApi'
const busy=ref(false),acknowledged=ref(false),error=ref(''),notice=ref(''),area=ref(''),range=ref<Date[]>([])
const run=ref<Run|null>(null),history=ref<Run[]>([]),events=ref<AnalysisEvent[]>([]),total=ref(0),page=ref(1)
const drawer=ref(false),detail=ref<Record<string,unknown>|null>(null)
async function refreshHistory(){history.value=(await request<{items:Run[]}>('/analysis/runs')).items}
async function loadEvents(){if(!run.value)return;const params=new URLSearchParams({run_id:run.value.id,offset:String((page.value-1)*50),limit:'50'});const data=await request<{items:AnalysisEvent[];total:number}>('/analysis/anomalies?'+params);events.value=data.items;total.value=data.total}
async function selectRun(value:Run){run.value=value;page.value=1;await loadEvents()}
onMounted(async()=>{try{await refreshHistory();if(history.value[0])await selectRun(history.value[0])}catch(e){error.value=(e as Error).message}})
async function bootstrap(){busy.value=true;error.value='';try{const data=await initializeRules();notice.value=`规则初始化完成，新增${data.added}条；已有配置保持原值。`}catch(e){error.value=(e as Error).message}finally{busy.value=false}}
async function execute(){if(!acknowledged.value)return;busy.value=true;error.value='';try{await selectRun(await runAnalysis(range.value??[],area.value));await refreshHistory()}catch(e){error.value=(e as Error).message;try{await refreshHistory()}catch{/* 保留原始错误提示 */}}finally{busy.value=false}}
async function showEvidence(event:AnalysisEvent){error.value='';try{detail.value=await request<Record<string,unknown>>('/analysis/anomalies/'+event.id);drawer.value=true}catch(e){error.value=(e as Error).message}}
</script>
<template>
 <div class="workbench">
  <h2>运行分析与证据追溯</h2>
  <el-alert title="当前使用演示规则，阈值未经现场标定。疑似积液、冻堵仅辅助提示，须人工复核。" type="warning" :closable="false"/>
  <el-alert v-if="error" :title="error" type="error" :closable="false"/>
  <el-alert v-if="notice" :title="notice" type="success" :closable="false"/>
  <el-card shadow="never">
   <template #header>1. 初始化规则并执行筛查</template>
   <p><el-button :disabled="busy" @click="bootstrap">初始化演示规则</el-button>　<router-link to="/rules">查看与修改规则</router-link></p>
   <el-form label-width="170px" :disabled="busy">
    <el-form-item label="分析工区"><el-input v-model="area" clearable placeholder="留空分析全部工区" style="max-width:360px"/></el-form-item>
    <el-form-item label="数据窗口"><el-date-picker v-model="range" type="datetimerange" start-placeholder="开始时间（本地时间）" end-placeholder="结束时间（不含）" clearable/></el-form-item>
    <el-form-item><span>留空时按最新采样确定终点，默认回看14天；历史数据结果不表示当前实时井况。</span></el-form-item>
    <el-form-item><el-checkbox v-model="acknowledged">确认按所选范围运行筛查</el-checkbox></el-form-item>
   </el-form>
   <el-button type="primary" :disabled="!acknowledged" :loading="busy" @click="execute">执行分析</el-button>
   <p>修改规则后需重新执行。缺少数据、配置或规则覆盖的井会列为待核实。</p>
  </el-card>
  <el-card v-if="run" shadow="never">
   <template #header>2. 分析结果：{{run.status}}</template>
   <p>任务ID：{{run.id}}</p><p>数据窗口（北京时间）：{{displayTime(run.window_start)}} 至 {{displayTime(run.window_end)}}（结束不含）</p>
   <el-alert v-if="run.error_message" :title="run.error_message" type="error" :closable="false"/>
   <el-descriptions v-if="run.summary.status_counts" :column="3" border>
    <el-descriptions-item label="分析井数">{{run.summary.total_wells}}</el-descriptions-item>
    <el-descriptions-item v-for="status in screeningStatuses" :key="status" :label="status">{{run.summary.status_counts[status]??0}}</el-descriptions-item>
   </el-descriptions>
   <p>可信正常表示在本次窗口和已执行规则下未发现异常；下表只展示异常、措施影响及待核实事件。</p>
   <el-table :data="events" border empty-text="本任务没有需复核事件">
    <el-table-column prop="well_number" label="井号" min-width="170"/><el-table-column prop="screening_status" label="筛查状态" width="130"/>
    <el-table-column prop="anomaly_type" label="事件类型" min-width="200"/><el-table-column label="规则版本" width="160"><template #default="{row}">{{row.rule_code}} / {{row.rule_version}}</template></el-table-column>
    <el-table-column label="开始时间（北京时间）" width="190"><template #default="{row}">{{displayTime(row.started_at)}}</template></el-table-column>
    <el-table-column label="追溯" width="90"><template #default="{row}"><el-button link type="primary" @click="showEvidence(row)">证据</el-button></template></el-table-column>
   </el-table>
   <el-pagination v-model:current-page="page" :page-size="50" :total="total" layout="prev,pager,next,total" @current-change="loadEvents"/>
  </el-card>
  <el-card shadow="never"><template #header>3. 历史任务（保留旧版规则与判断）</template>
   <el-table :data="history" empty-text="尚未执行分析"><el-table-column prop="id" label="任务ID" min-width="260"/><el-table-column prop="status" label="状态" width="110"/><el-table-column label="分析井数"><template #default="{row}">{{row.summary.total_wells??'—'}}</template></el-table-column><el-table-column label="查看"><template #default="{row}"><el-button link type="primary" @click="selectRun(row)">查看本次结果</el-button></template></el-table-column></el-table>
  </el-card>
  <el-drawer v-model="drawer" title="规则快照、判断证据与人工复核记录" size="70%"><el-alert title="证据中的数值、采样ID及事件ID可用于技术追溯；辅助提示不能视为现场确诊。" type="info" :closable="false"/><AnalysisEvidence :detail="detail"/></el-drawer>
 </div>
</template>
<style scoped>
.workbench{max-width:1400px}.workbench>h2{padding:0;margin-top:0}.workbench>.el-card,.workbench>.el-alert{margin-bottom:20px}.el-pagination{margin-top:20px}a{color:#17776d}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:13px;line-height:1.6}
</style>
