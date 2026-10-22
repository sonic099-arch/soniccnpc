// @vitest-environment happy-dom
import {afterEach,beforeEach,expect,it,vi} from 'vitest'
import {mount,flushPromises,type VueWrapper} from '@vue/test-utils'
import ElementPlus from 'element-plus'
import DataImport from './DataImport.vue'
let wrapper:VueWrapper|undefined
const fields=[
 {key:'well_number',label:'井号',unit:null,allowed_units:[],required:true},
 {key:'measured_at',label:'采样时间',unit:null,allowed_units:[],required:true},
 {key:'instantaneous_flow_m3_h',label:'瞬时流量',unit:'m³/h',allowed_units:['m³/h','m³/d'],required:false},
]
const preview={headers:['井号','时间','流量'],sheets:['测量数据'],sheet:'测量数据',suggested_mapping:{well_number:'井号',measured_at:'时间',instantaneous_flow_m3_h:'流量'},suggested_units:{instantaneous_flow_m3_h:'m³/h'},ambiguous_fields:[],total_rows:1,samples:[{row:2,values:{井号:'演示X',时间:'2026-10-01',流量:100}}]}
const job={id:'job-id',filename:'sample.xlsx',status:'待确认',total_rows:1,success_rows:0,duplicate_rows:0,failed_rows:0,errors:[],error_count:0,mapping:{preview},report_url:'/api/v1/excel/jobs/job-id/report'}
let fetchMock:ReturnType<typeof vi.fn>
beforeEach(()=>{
 fetchMock=vi.fn(async(path:string)=>({ok:true,json:async()=>path.endsWith('/fields')?fields:path.endsWith('/confirm')?{...job,status:'已完成',success_rows:1}:job}))
 vi.stubGlobal('fetch',fetchMock)
})
afterEach(()=>{wrapper?.unmount();wrapper=undefined;vi.unstubAllGlobals()})
async function setupPreview(){
 wrapper=mount(DataImport,{global:{plugins:[ElementPlus]}})
 await flushPromises()
 const input=wrapper.find('input[type="file"]')
 Object.defineProperty(input.element,'files',{value:[new File(['demo'],'sample.xlsx')],configurable:true})
 await input.trigger('change')
 const upload=wrapper.findAll('button').find(b=>b.text().includes('上传并识别字段'))!
 await upload.trigger('click');await flushPromises()
 return wrapper
}
it('预览不会写入，只有勾选确认后才能执行导入并显示结果',async()=>{
 const view=await setupPreview()
 const confirm=view.findAll('button').find(b=>b.text()==='确认并导入')!
 expect(confirm.attributes('disabled')).toBeDefined()
 expect(fetchMock.mock.calls.filter(([path])=>String(path).endsWith('/confirm'))).toHaveLength(0)
 const acknowledgement=view.findAll('label.el-checkbox').find(label=>label.text().includes('我已确认'))!
 await acknowledgement.find('input').setValue(true)
 expect(confirm.attributes('disabled')).toBeUndefined()
 await confirm.trigger('click');await flushPromises()
 expect(fetchMock.mock.calls.filter(([path])=>String(path).endsWith('/confirm'))).toHaveLength(1)
 expect(view.text()).toContain('导入结果：已完成')
 expect(view.find('a[href="/api/v1/excel/jobs/job-id/report"]').exists()).toBe(true)
})
it('重新选择文件会清除旧预览和确认状态',async()=>{
 const view=await setupPreview()
 const acknowledgement=view.findAll('label.el-checkbox').find(label=>label.text().includes('我已确认'))!
 await acknowledgement.find('input').setValue(true)
 const input=view.find('input[type="file"]')
 Object.defineProperty(input.element,'files',{value:[new File(['other'],'new.xlsx')],configurable:true})
 await input.trigger('change')
 expect(view.findAll('button').some(b=>b.text()==='确认并导入')).toBe(false)
 expect(fetchMock.mock.calls.filter(([path])=>String(path).endsWith('/confirm'))).toHaveLength(0)
})
