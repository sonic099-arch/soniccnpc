<script setup lang="ts">
import {computed} from 'vue'
import {runLabel,type Options,type ReportFilters} from '../screeningApi'
const props=defineProps<{filters:ReportFilters;options:Options|null;busy:boolean;events?:boolean}>()
const emit=defineEmits<{apply:[]}>()
const range=computed({get:()=>props.filters.event_start&&props.filters.event_end?[props.filters.event_start,props.filters.event_end]:[],set:(v:string[]|null)=>{props.filters.event_start=v?.[0]??'';props.filters.event_end=v?.[1]??''}})
function clear(){props.filters.search='';props.filters.area='';props.filters.screening_status='';props.filters.anomaly_type='';range.value=[];emit('apply')}
</script>
<template>
 <el-card class="filter-panel" shadow="never">
  <el-form :inline="true" @submit.prevent="emit('apply')" :disabled="busy">
   <el-form-item label="分析任务"><select v-model="filters.run_id" class="report-select run-select" aria-label="分析任务" :disabled="busy"><option value="">最近完成的任务</option><option v-for="run in options?.runs??[]" :key="run.id" :value="run.id">{{runLabel(run)}}</option></select></el-form-item>
   <el-form-item label="井号"><el-input v-model="filters.search" clearable placeholder="搜索井号" style="width:175px" @keyup.enter="emit('apply')"/></el-form-item>
   <el-form-item label="工区"><select v-model="filters.area" class="report-select" aria-label="工区" :disabled="busy"><option value="">全部工区</option><option v-for="area in options?.areas??[]" :key="area" :value="area">{{area}}</option></select></el-form-item>
   <el-form-item label="筛查状态"><select v-model="filters.screening_status" class="report-select" aria-label="筛查状态" :disabled="busy"><option value="">全部状态</option><option v-for="s in options?.statuses??[]" :key="s" :value="s">{{s}}</option></select></el-form-item>
   <template v-if="events">
    <el-form-item label="异常类型"><select v-model="filters.anomaly_type" class="report-select type-select" aria-label="异常类型" :disabled="busy"><option value="">全部事件类型</option><option v-for="kind in options?.anomaly_types??[]" :key="kind" :value="kind">{{kind}}</option></select></el-form-item>
    <el-form-item label="事件时间"><el-date-picker v-model="range" type="datetimerange" value-format="YYYY-MM-DDTHH:mm:ssZ" start-placeholder="开始（本地时间）" end-placeholder="结束（不含）"/></el-form-item>
   </template>
   <el-form-item><el-button type="primary" native-type="submit">查询</el-button><el-button @click="clear">清空筛选</el-button></el-form-item>
  </el-form>
  <p class="muted filter-hint">按同一次分析任务查看结果，切换任务可查看不同分析窗口。{{events?'事件时间按区间重叠筛选，不会重新计算规则。':''}}</p>
 </el-card>
</template>
<style scoped>.filter-panel .el-form-item{margin-bottom:14px}.filter-hint{margin:0;font-size:12px}.filter-panel{margin-bottom:20px}</style>
