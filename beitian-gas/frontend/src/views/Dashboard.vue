<script setup lang="ts">
import {computed} from 'vue'
import {useRouter} from 'vue-router'
import EChart from '../components/EChart.vue'
import ReportFilters from '../components/ReportFilters.vue'
import ReportWindow from '../components/ReportWindow.vue'
import {colors,statuses,type DashboardData} from '../screeningApi'
import {useReport} from '../useReport'
const {filters,options,data,error,loading,load,apply}=useReport<DashboardData>('/dashboard')
const router=useRouter()
const chart=computed(()=>({tooltip:{trigger:'item',renderMode:'richText'},legend:{bottom:0},color:statuses.map(s=>colors[s]),aria:{enabled:true},series:[{type:'pie',stillShowZeroSum:false,radius:['43%','68%'],center:['50%','43%'],label:{show:false},data:statuses.map(name=>({name,value:data.value?.status_counts[name]??0}))}]}))
const areas=computed(()=>[...new Set(data.value?.areas.map(a=>a.area)??[])])
const areaChart=computed(()=>({color:statuses.map(s=>colors[s]),tooltip:{trigger:'axis',renderMode:'richText',axisPointer:{type:'shadow'}},legend:{bottom:0},grid:{left:55,right:20,top:35,bottom:85},xAxis:{type:'category',data:areas.value,axisLabel:{interval:0,rotate:areas.value.length>5?25:0}},yAxis:{type:'value',minInterval:1,name:'井数'},series:statuses.map(name=>({type:'bar',name,stack:'井数',barMaxWidth:48,data:areas.value.map(area=>data.value?.areas.find(x=>x.area===area&&x.screening_status===name)?.count??0)}))}))
function go(status=''){router.push({path:'/wells',query:{...(data.value?.run?{run_id:data.value.run.id}:{}),...(filters.area?{area:filters.area}:{}),...(filters.search?{search:filters.search}:{}),...(status?{screening_status:status}:{})}})}
</script>
<template>
 <div class="page dashboard" v-loading="loading">
  <div class="page-heading"><div><p class="eyebrow">生产监测 / 筛查总览</p><h1>气井生产概览</h1><p class="muted">从生产数据中筛除可信正常井，集中查看需要人工分析的气井。</p></div><el-button @click="load">刷新统计</el-button></div>
  <el-alert v-if="error" :title="error" type="error" :closable="false"/>
  <ReportFilters :filters="filters" :options="options" :busy="loading" @apply="apply"/>
  <template v-if="data">
   <ReportWindow :run="data.run"/>
   <div class="stats-grid"><button class="stat-card total-card" @click="go()"><span>{{filters.search||filters.area||filters.screening_status?'筛选范围气井':'全部登记气井'}}</span><strong>{{data.total_wells.toLocaleString()}}</strong><small>本次已分析 {{data.analyzed_wells.toLocaleString()}} 口</small></button><button v-for="status in statuses" :key="status" class="stat-card" :style="{'--status-color':colors[status]}" @click="go(status)"><span><i/>{{status}}</span><strong>{{(data.status_counts[status]??0).toLocaleString()}}</strong><small>查看气井列表 →</small></button></div>
   <div class="overview-charts"><el-card shadow="never"><template #header><strong>筛查状态分布</strong><span class="muted card-subtitle">按井计数</span></template><EChart :option="chart" label="气井筛查状态分布"/></el-card><el-card shadow="never"><template #header><strong>各工区筛查情况</strong><span class="muted card-subtitle">同一分析任务</span></template><EChart :option="areaChart" label="各工区气井状态堆叠统计"/></el-card></div>
   <el-card shadow="never" class="next-actions"><strong>继续分析</strong><p>{{data.reference}}。疑似积液、冻堵均为辅助提示，需人工核实。</p><router-link :to="{path:'/anomalies',query:data.run?{run_id:data.run.id}:{}}"><el-button type="primary">查看异常井与证据</el-button></router-link><router-link to="/analysis"><el-button>运行或重新分析</el-button></router-link><el-tag v-if="data.demo_wells" type="warning">含 {{data.demo_wells}} 口演示井 · 非现场判定标准</el-tag></el-card>
  </template>
 </div>
</template>
<style scoped>.stats-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:16px;margin:20px 0}.stat-card{font:inherit;text-align:left;background:#fff;border:1px solid #e0e9e6;border-radius:10px;padding:20px;cursor:pointer;transition:transform .15s,box-shadow .15s}.stat-card:hover{transform:translateY(-2px);box-shadow:0 6px 18px #183d3610}.stat-card span{display:block;color:#5f7478;font-size:13px}.stat-card i{display:inline-block;height:8px;width:8px;border-radius:50%;background:var(--status-color);margin-right:8px}.stat-card strong{display:block;font-size:34px;font-weight:650;margin:12px 0 8px;color:var(--status-color,#fff)}.stat-card small{font-size:12px;color:#829397}.total-card{background:#174b43;border-color:#174b43}.total-card span,.total-card small{color:#c2d9d2}.overview-charts{display:grid;grid-template-columns:1fr 1.6fr;gap:20px}.card-subtitle{float:right;font-size:12px}.next-actions{margin-top:20px}.next-actions a{margin-right:12px}.next-actions .el-tag{margin-top:12px}@media(max-width:1100px){.stats-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.overview-charts{grid-template-columns:1fr}}@media(max-width:600px){.stats-grid{gap:8px}.stat-card{padding:14px}}</style>
