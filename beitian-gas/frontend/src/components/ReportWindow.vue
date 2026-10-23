<script setup lang="ts">
import {type Run,displayTime} from '../analysisApi'
defineProps<{run:Run|null|undefined}>()
</script>
<template>
 <div v-if="run" class="report-window"><span class="window-dot"/>数据窗口（北京时间）：<strong>{{displayTime(run.window_start)}}</strong> 至 <strong>{{displayTime(run.window_end)}}</strong>（结束不含）<span class="muted"> · 任务 {{run.id.slice(0,8)}}</span></div>
 <el-alert v-else title="尚无完成的分析任务。请先导入数据并到“运行分析”执行筛查；登记井暂列为未分析。" type="info" :closable="false"/>
</template>
<style scoped>.report-window{padding:13px 16px;background:#eaf3f1;border:1px solid #d6e8e2;border-radius:8px;font-size:13px;line-height:1.8;margin-bottom:20px}.window-dot{display:inline-block;width:7px;height:7px;border-radius:50%;background:#159880;margin-right:8px}</style>
