<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { getHealth } from '../api'
const route = useRoute()
const health = ref('检查中')
onMounted(async()=>{try{ const data=await getHealth();health.value=data.status==='ok'?'后端已连接':'后端状态待核实'}catch{health.value='后端未连接，请按运行文档启动服务'}})
</script>
<template>
  <el-card shadow="never">
    <template #header><strong>{{ route.name }}</strong></template>
    <el-alert title="生产措施管理独立页面尚未实现，后续联调阶段补齐。" type="info" :closable="false" />
    <p>当前可通过Excel导入加载演示措施，使用单井页面查看措施有效区间；新增、修改措施可使用后端接口文档中的“排采措施”接口。首页、气井列表、异常列表、单井曲线以及分析与规则配置现已可用。</p>
    <el-descriptions :column="1" border>
      <el-descriptions-item label="服务状态">{{ health }}</el-descriptions-item>
      <el-descriptions-item label="数据状态">当前页面尚未接入统计，请通过Excel导入页面生成演示数据</el-descriptions-item>
      <el-descriptions-item label="参数口径">油压、套压、回压、瞬时流量、累计流量、气流温度、产液量（第七项暂定）</el-descriptions-item>
    </el-descriptions>
    <p><a href="http://localhost:8000/docs" target="_blank" rel="noopener">打开后端接口文档</a></p>
  </el-card>
</template>
