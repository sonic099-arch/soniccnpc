<script setup lang="ts">
import ReportFilters from '../components/ReportFilters.vue'
import ReportWindow from '../components/ReportWindow.vue'
import {type Page,type WellRow,statusType} from '../screeningApi'
import {displayTime} from '../analysisApi'
import {useReport} from '../useReport'
const {filters,options,data,error,loading,page,load,apply,paginate,wellLink}=useReport<Page<WellRow>>('/wells')
</script>
<template>
 <div class="page" v-loading="loading">
  <div class="page-heading"><div><p class="eyebrow">生产监测 / 气井台账</p><h1>气井列表</h1><p class="muted">查看全部登记井及本次筛查状态，点击井号进入单井分析。</p></div><el-button @click="load">刷新列表</el-button></div>
  <el-alert v-if="error" :title="error" type="error" :closable="false"/>
  <ReportFilters :filters="filters" :options="options" :busy="loading" events @apply="apply"/>
  <ReportWindow :run="data?.run"/>
  <el-card v-if="data" shadow="never"><template #header><strong>气井台账</strong><span class="muted count-label">共 {{data.total}} 口</span></template>
   <el-table :data="data.items" stripe row-key="well_id" empty-text="没有符合筛选条件的气井">
    <el-table-column label="井号" min-width="190"><template #default="{row}"><router-link :to="wellLink(row.well_id)" class="well-link">{{row.well_number}}</router-link><el-tag v-if="row.is_demo" size="small" type="info" class="demo-tag">演示</el-tag></template></el-table-column>
    <el-table-column prop="area" label="工区" min-width="130"/>
    <el-table-column label="筛查状态" width="140"><template #default="{row}"><el-tag :type="statusType(row.screening_status)">{{row.screening_status}}</el-tag></template></el-table-column>
    <el-table-column label="生产状态" min-width="160"><template #default="{row}">{{row.production_state??'尚未分析'}}</template></el-table-column>
    <el-table-column label="异常或影响类型" min-width="250"><template #default="{row}"><span class="muted">{{row.anomaly_types.join('、')||'—'}}</span></template></el-table-column>
    <el-table-column label="分析窗口终点（北京时间）" width="210"><template #default="{row}">{{displayTime(row.as_of)}}</template></el-table-column>
    <el-table-column label="操作" width="100" fixed="right"><template #default="{row}"><router-link :to="wellLink(row.well_id)">查看曲线</router-link></template></el-table-column>
   </el-table>
   <el-pagination :current-page="page" :page-size="50" :total="data.total" layout="total,prev,pager,next" @current-change="paginate"/>
  </el-card>
 </div>
</template>
