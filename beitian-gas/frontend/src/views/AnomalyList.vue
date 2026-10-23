<script setup lang="ts">
import {computed,ref} from 'vue'
import {useRoute,useRouter} from 'vue-router'
import ReportFilters from '../components/ReportFilters.vue'
import ReportWindow from '../components/ReportWindow.vue'
import AnalysisEvidence from '../components/AnalysisEvidence.vue'
import {request} from '../importApi'
import {type Page,type WellRow,type EventRow,statusType} from '../screeningApi'
import {displayTime} from '../analysisApi'
import {useReport} from '../useReport'
const route=useRoute(),router=useRouter(),eventView=computed(()=>route.query.view==='events')
const {filters,options,data,error,loading,page,load,apply,paginate,wellLink}=useReport<Page<WellRow|EventRow>>(()=>eventView.value?'/anomalies':'/wells',{non_normal:true})
const drawer=ref(false),evidence=ref<Record<string,unknown>|null>(null),evidenceLoading=ref(false),evidenceError=ref('')
async function showEvidence(id:string){drawer.value=true;evidence.value=null;evidenceError.value='';evidenceLoading.value=true;try{evidence.value=await request<Record<string,unknown>>('/analysis/anomalies/'+id)}catch(e){evidenceError.value=(e as Error).message}finally{evidenceLoading.value=false}}
function switchView(){router.push({query:{...route.query,view:eventView.value?'wells':'events',page:undefined}})}
</script>
<template>
 <div class="page" v-loading="loading">
  <div class="page-heading"><div><p class="eyebrow">生产监测 / 人工复核</p><h1>异常井列表</h1><p class="muted">默认排除可信正常井。措施影响与待核实井也在此保留，方便人工筛查。</p></div><el-button @click="load">刷新列表</el-button></div>
  <el-alert v-if="error" :title="error" type="error" :closable="false"/>
  <ReportFilters :filters="filters" :options="options" :busy="loading" events @apply="apply"/>
  <ReportWindow :run="data?.run"/>
  <el-card v-if="data" shadow="never">
   <template #header><div class="table-heading"><strong>{{eventView?'异常与影响事件':'需复核气井'}} <span class="muted">{{data.total}} {{eventView?'条事件':'口井'}}</span></strong><el-button @click="switchView">{{eventView?'切换为按井汇总':'切换为逐事件列表'}}</el-button></div></template>
   <p class="muted small-copy">{{eventView?'一口井可能命中多条规则，事件数不等于异常井数。':'每口井只显示一行。未分析井需先运行分析；疑似积液、冻堵均为辅助提示。'}}</p>
   <el-table :data="data.items" stripe :row-key="eventView?'id':'well_id'" empty-text="没有符合条件的异常或待核实记录">
    <el-table-column label="井号" min-width="185"><template #default="{row}"><router-link :to="wellLink(row.well_id)" class="well-link">{{row.well_number}}</router-link></template></el-table-column>
    <el-table-column prop="area" label="工区" width="130"/>
    <el-table-column label="筛查状态" width="140"><template #default="{row}"><el-tag :type="statusType(row.screening_status)">{{row.screening_status}}</el-tag></template></el-table-column>
    <template v-if="eventView">
     <el-table-column prop="anomaly_type" label="事件类型" min-width="230"/>
     <el-table-column label="规则版本" width="165"><template #default="{row}">{{row.rule_code}} / {{row.rule_version}}</template></el-table-column>
     <el-table-column label="异常开始（北京时间）" width="200"><template #default="{row}">{{displayTime(row.started_at)}}</template></el-table-column>
     <el-table-column label="追溯" width="90" fixed="right"><template #default="{row}"><el-button link type="primary" @click="showEvidence(row.id)">证据</el-button></template></el-table-column>
    </template>
    <template v-else>
     <el-table-column label="生产状态" min-width="160"><template #default="{row}">{{row.production_state??'尚未分析'}}</template></el-table-column>
     <el-table-column label="命中事件" min-width="300"><template #default="{row}">{{row.anomaly_types.join('、')||'尚无分析事件'}}</template></el-table-column>
     <el-table-column label="操作" width="110" fixed="right"><template #default="{row}"><router-link :to="wellLink(row.well_id)">单井分析</router-link></template></el-table-column>
    </template>
   </el-table>
   <el-pagination :current-page="page" :page-size="50" :total="data.total" layout="total,prev,pager,next" @current-change="paginate"/>
  </el-card>
  <el-drawer v-model="drawer" title="异常判断证据" size="75%"><div v-loading="evidenceLoading"><el-alert v-if="evidenceError" :title="evidenceError" type="error" :closable="false"/><AnalysisEvidence :detail="evidence"/></div></el-drawer>
 </div>
</template>
<style scoped>.table-heading{display:flex;align-items:center;justify-content:space-between;gap:12px}.table-heading strong>span{font-size:13px;font-weight:400;margin-left:12px}.small-copy{font-size:13px;margin-top:0}</style>
