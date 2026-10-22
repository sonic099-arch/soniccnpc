<script setup lang="ts">
import {onMounted,ref} from 'vue'
import {request} from '../importApi'
import {initializeRules,nextVersion,type ConfigRule} from '../analysisApi'
const rules=ref<ConfigRule[]>([]),busy=ref(false),error=ref(''),notice=ref(''),dialog=ref(false)
const selected=ref<ConfigRule|null>(null),configuration=ref<Record<string,number|string[]>>({}),version=ref(''),enabled=ref(true),states=ref<string[]>([])
const modes=['全部','自喷','泡排','间歇','注醇','其他排采']
const parameterLabels:Record<string,string>={tubing_pressure_mpa:'油压',casing_pressure_mpa:'套压',back_pressure_mpa:'井口回压',instantaneous_flow_m3_h:'瞬时流量',cumulative_flow_m3:'累计流量',gas_temperature_c:'气流温度',liquid_rate_m3_d:'产液量'}
function readable(value:number|string[]){return Array.isArray(value)?value.map(v=>parameterLabels[v]??v).join('、'):String(value)}
async function load(){try{rules.value=(await request<{items:ConfigRule[]}>('/analysis/rules')).items;error.value=''}catch(e){error.value=(e as Error).message}}
onMounted(load)
async function bootstrap(){busy.value=true;try{await initializeRules();await load()}catch(e){error.value=(e as Error).message}finally{busy.value=false}}
function edit(rule:ConfigRule){selected.value=rule;configuration.value=JSON.parse(JSON.stringify(rule.configuration));version.value=nextVersion(rule.version);enabled.value=rule.enabled;states.value=[...rule.applicable_states];dialog.value=true}
function changeStates(values:string[]){const next=values.includes('全部')&&values.length>1?(values.at(-1)==='全部'?['全部']:values.filter(v=>v!=='全部')):values;if(JSON.stringify(next)!==JSON.stringify(states.value))states.value=next}
function setNumber(key:string,value:number|undefined){if(value!==undefined)configuration.value[key]=value}
async function save(){if(!selected.value)return;busy.value=true;error.value='';try{await request(`/analysis/rules/${selected.value.code}/versions`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({version:version.value,configuration:configuration.value,enabled:enabled.value,applicable_states:states.value})});dialog.value=false;notice.value='新版本已发布，请到运行分析页面重新计算；历史任务保留原规则与证据。';await load()}catch(e){error.value=(e as Error).message}finally{busy.value=false}}
</script>
<template>
 <div class="rules-page"><h2>规则配置与版本管理</h2>
  <el-alert title="以下为演示阈值，未经现场标定。发布新版本后需重新分析，历史结果保持原判断。" type="warning" :closable="false"/>
  <el-alert v-if="error" :title="error" type="error" :closable="false"/><el-alert v-if="notice" :title="notice" type="success" :closable="false"/>
  <p><el-button :loading="busy" @click="bootstrap">初始化演示规则</el-button>　<router-link to="/analysis">进入运行分析</router-link></p>
  <el-table :data="rules" border empty-text="请先初始化规则"><el-table-column prop="code" label="编号" width="110"/><el-table-column prop="name" label="中文名称" min-width="230"/><el-table-column prop="version" label="版本" width="100"/><el-table-column label="启用状态" width="100"><template #default="{row}">{{row.enabled?'启用':'停用'}}</template></el-table-column><el-table-column label="适用工况"><template #default="{row}">{{row.applicable_states.join('、')}}</template></el-table-column><el-table-column label="操作" width="160"><template #default="{row}"><el-button link type="primary" @click="edit(row)">查看并发布新版本</el-button></template></el-table-column></el-table>
  <el-dialog v-model="dialog" :title="selected?.name" width="800px">
   <template v-if="selected">
    <el-alert v-if="error" :title="error" type="error" :closable="false"/>
    <p>输入参数：{{selected.input_parameters.join('、')}}</p>
    <el-form label-width="290px" :disabled="busy">
     <el-form-item label="新版本号"><el-input v-model="version" placeholder="例如1.0.1"/></el-form-item>
     <el-form-item label="启用本规则"><el-checkbox v-model="enabled">启用（停用后相关井不能筛为可信正常）</el-checkbox></el-form-item>
     <el-form-item label="适用工况"><el-checkbox-group v-model="states" @change="changeStates"><el-checkbox v-for="mode in modes" :key="mode" :value="mode">{{mode}}</el-checkbox></el-checkbox-group></el-form-item>
     <el-form-item v-for="(value,key) in configuration" :key="key" :label="selected.config_schema.properties[key]?.title??key">
      <el-input-number v-if="typeof value==='number'" :model-value="value" :step="selected.config_schema.properties[key]?.type==='integer'?1:.01" :min="selected.config_schema.properties[key]?.minimum" :max="selected.config_schema.properties[key]?.maximum" @update:model-value="(v: number | undefined)=>setNumber(String(key),v)"/>
      <span v-else>{{readable(value)}}（策略列表可通过版本接口调整）</span>
     </el-form-item>
    </el-form>
   </template>
   <template #footer><el-button @click="dialog=false">取消</el-button><el-button type="primary" :loading="busy" @click="save">发布新版本</el-button></template>
  </el-dialog>
 </div>
</template>
<style scoped>.rules-page>h2{padding:0;margin-top:0}.rules-page>.el-alert{margin-bottom:16px}.rules-page .el-table{max-width:1400px}.el-select{width:100%}a{color:#17776d}</style>
