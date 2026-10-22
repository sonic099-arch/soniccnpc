<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { request, confirmationPayload, type ImportJob, type StandardField } from '../importApi'
const fields=ref<StandardField[]>([])
const file=ref<File|null>(null), busy=ref(false), loadingDemo=ref(false), error=ref('')
const sheet=ref(''), job=ref<ImportJob|null>(null)
const mapping=ref<Record<string,string>>({}),units=ref<Record<string,string>>({})
const timezone=ref('Asia/Shanghai'),createMissing=ref(false),area=ref('演示导入工区'),isDemo=ref(true),acknowledged=ref(false)
const demoAcknowledged=ref(false),demoResult=ref('')
const preview=computed(()=>job.value?.mapping.preview)
const completed=computed(()=>!!job.value&&['已完成','部分失败','失败'].includes(job.value.status))
const canConfirm=computed(()=>!!job.value&&!completed.value&&acknowledged.value&&!!mapping.value.well_number&&!!mapping.value.measured_at&&fields.value.some(f=>f.unit&&mapping.value[f.key]))
onMounted(async()=>{try{fields.value=await request<StandardField[]>('/excel/fields')}catch(e){error.value=(e as Error).message}})
function choose(event:Event){file.value=(event.target as HTMLInputElement).files?.[0]??null;job.value=null;acknowledged.value=false;error.value=''}
async function upload(){
 if(!file.value)return
 if(file.value.size>25*1024*1024){error.value='文件超过25 MiB，请拆分上传';return}
 busy.value=true;error.value='';job.value=null;acknowledged.value=false
 try{
  const body=new FormData();body.append('file',file.value);if(sheet.value.trim())body.append('sheet',sheet.value.trim())
  job.value=await request<ImportJob>('/excel/preview',{method:'POST',body})
  mapping.value={...job.value.mapping.preview.suggested_mapping};units.value={...job.value.mapping.preview.suggested_units};acknowledged.value=false
 }catch(e){error.value=(e as Error).message}finally{busy.value=false}
}
async function confirm(){
 if(!job.value||!canConfirm.value)return
 busy.value=true;error.value=''
 try{
  job.value=await request<ImportJob>(`/excel/jobs/${job.value.id}/confirm`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(confirmationPayload(mapping.value,units.value,timezone.value,createMissing.value,area.value,isDemo.value))})
  ElMessage.success('导入处理完成，请核对成功、重复和失败数量')
 }catch(e){error.value=(e as Error).message}finally{busy.value=false}
}
async function generate(){
 loadingDemo.value=true;error.value=''
 try{
  const result=await request<{well_count:number;measurement_count:number;already_loaded:boolean;added_wells:number;added_measurements:number}>('/demo/generate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({confirmed:true,count:1000,days:14,seed:20261021})})
  demoResult.value=`${result.already_loaded?'这批演示数据已存在，本次未重复写入':'生成完成'}：${result.well_count}口井，${result.measurement_count}条测量记录；本次新增${result.added_wells}口井、${result.added_measurements}条记录。尚未执行异常分析。`
 }catch(e){error.value=(e as Error).message}finally{loadingDemo.value=false}
}
</script>
<template>
 <div class="import-page">
  <h2>Excel导入与演示数据</h2>
  <el-alert title="所有模拟参数和场景标签仅用于演示，不是现场工艺判定标准。第七参数暂定产液量。" type="warning" :closable="false"/>
  <el-alert v-if="error" :title="error" type="error" :closable="false"/>
  <el-card shadow="never">
   <template #header>1. 上传xlsx并预览（此步骤不写入生产参数）</template>
   <p><a href="/api/v1/excel/template">下载标准模板</a>　<a href="/api/v1/excel/template?example=true">下载三行演示样例</a></p>
   <input type="file" accept=".xlsx" :disabled="busy" aria-label="选择Excel文件" @change="choose"/>
   <el-input v-model="sheet" placeholder="工作表名称，可留空（优先选择“测量数据”）" style="max-width:440px;margin:16px 0" :disabled="busy"/>
   <p><el-button type="primary" :loading="busy" :disabled="!file||loadingDemo" @click="upload">上传并识别字段</el-button></p>
   <p>限制：25 MiB、50万行、100列。当前仅导入测量工作表，事件通过演示生成器或措施接口管理。</p>
  </el-card>
  <el-card v-if="preview" shadow="never">
   <template #header>2. 确认字段映射、单位及关联方式</template>
   <p>工作表：{{preview.sheet}}，有效数据行：{{preview.total_rows}}。自动识别结果仅为建议，请逐项确认。</p>
   <el-alert v-if="preview.ambiguous_fields.length" title="发现多个可能的同类字段，相关映射已清空，请手工选择。" type="warning" :closable="false"/>
   <el-table :data="fields" border>
    <el-table-column label="标准字段" width="170"><template #default="{row}">{{row.label}}{{row.required?'（必选）':''}}</template></el-table-column>
    <el-table-column label="Excel源列"><template #default="{row}"><el-select v-model="mapping[row.key]" clearable placeholder="不导入此项" :disabled="completed||busy"><el-option v-for="header in preview.headers" :key="header" :label="header" :value="header"/></el-select></template></el-table-column>
    <el-table-column label="源数据单位（确认后统一转换）"><template #default="{row}"><el-select v-if="row.unit" v-model="units[row.key]" placeholder="请选择单位" :disabled="completed||busy||!mapping[row.key]"><el-option v-for="unit in row.allowed_units" :key="unit" :label="unit" :value="unit"/></el-select><span v-else>—</span></template></el-table-column>
   </el-table>
   <p>前五行原始预览：</p>
   <el-table :data="preview.samples" max-height="240" border><el-table-column prop="row" label="Excel行号" width="110"/><el-table-column v-for="header in preview.headers" :key="header" :label="header" min-width="160"><template #default="{row}">{{row.values[header]??'（空）'}}</template></el-table-column></el-table>
   <el-form label-width="170px" style="margin-top:20px" :disabled="completed||busy">
    <el-form-item label="无时区时间的解释"><el-select v-model="timezone"><el-option label="中国时间 Asia/Shanghai" value="Asia/Shanghai"/><el-option label="UTC" value="UTC"/></el-select></el-form-item>
    <el-form-item label="数据性质"><el-checkbox v-model="isDemo">本次导入为演示数据</el-checkbox></el-form-item>
    <el-form-item label="井号不存在时"><el-checkbox v-model="createMissing">允许创建新井</el-checkbox></el-form-item>
    <el-form-item v-if="createMissing" label="新建井所属工区"><el-input v-model="area" maxlength="80" style="max-width:360px"/></el-form-item>
    <el-form-item><el-checkbox v-model="acknowledged">我已确认映射、源单位、时区和数据性质</el-checkbox></el-form-item>
   </el-form>
   <el-button type="primary" :loading="busy" :disabled="!canConfirm||loadingDemo" @click="confirm">确认并导入</el-button>
  </el-card>
  <el-card v-if="completed&&job" shadow="never">
   <template #header>3. 导入结果：{{job.status}}</template>
   <el-descriptions :column="4" border><el-descriptions-item label="总行数">{{job.total_rows}}</el-descriptions-item><el-descriptions-item label="成功">{{job.success_rows}}</el-descriptions-item><el-descriptions-item label="重复跳过">{{job.duplicate_rows}}</el-descriptions-item><el-descriptions-item label="失败">{{job.failed_rows}}</el-descriptions-item></el-descriptions>
   <p>任务ID：{{job.id}}　<a :href="job.report_url">下载完整导入报告</a></p>
   <p>同井同时间的相同数值会跳过；不同数值报告冲突并保留原记录。失败行可修正后重新上传。</p>
   <el-table v-if="job.errors.length" :data="job.errors" max-height="320" border><el-table-column prop="row" label="Excel行号" width="110"/><el-table-column prop="reason" label="失败原因"/></el-table>
   <p v-if="job.error_count>100">此处展示前100条错误，完整错误见下载报告。</p>
  </el-card>
  <el-card shadow="never">
   <template #header>生成1000口气井演示数据</template>
   <p>固定随机种子，14天逐小时记录，覆盖13类场景。同时保存配置、井筒工具、措施和操作事件。生成或大文件导入可能需要几分钟，请勿关闭页面。</p>
   <el-checkbox v-model="demoAcknowledged" :disabled="loadingDemo">确认向当前开发数据库写入演示数据</el-checkbox>
   <p><el-button :loading="loadingDemo" :disabled="!demoAcknowledged||busy" @click="generate">生成并加载1000口演示井</el-button></p>
   <el-alert v-if="demoResult" :title="demoResult" type="success" :closable="false"/>
   <p>同一批数据重复生成不会重复写入；相同配置的600口演示井可直接扩容到1000口，保留原记录；配置不同会拒绝写入。异常分析将在任务3实现。</p>
  </el-card>
 </div>
</template>
<style scoped>
.import-page{max-width:1200px}.import-page>.el-card,.import-page>.el-alert{margin-bottom:20px}.import-page h2{padding:0;margin-top:0}a{color:#17776d}.el-select{min-width:220px;max-width:100%}
</style>
