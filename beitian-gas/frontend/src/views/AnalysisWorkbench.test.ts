// @vitest-environment happy-dom
import {afterEach,expect,it,vi} from 'vitest'
import {mount,flushPromises,type VueWrapper} from '@vue/test-utils'
import ElementPlus from 'element-plus'
import AnalysisWorkbench from './AnalysisWorkbench.vue'
let wrapper:VueWrapper|undefined
const run={id:'run-1',status:'已完成',window_start:'2026-10-01T00:00:00Z',window_end:'2026-10-15T00:00:00Z',data_cutoff:'2026-10-22T00:00:00Z',error_message:null,rule_snapshot:[],summary:{total_wells:13,status_counts:{可信正常:4,疑似异常:5,措施影响:1,数据待核实:3,工况待核实:0}}}
afterEach(()=>{wrapper?.unmount();wrapper=undefined;vi.unstubAllGlobals()})
it('必须确认才执行，显示真实任务统计并能打开判断证据',async()=>{
 let executed=false
 const fetch=vi.fn(async(path:string)=>({ok:true,json:async()=>path.endsWith('/runs')?{items:executed?[run]:[]}:path.endsWith('/bootstrap')?{added:11}:path.endsWith('/execute')?(executed=true,run):path.includes('/anomalies?')?{items:[{id:'event-1',well_number:'演示井',anomaly_type:'持续减产',rule_code:'FL001',rule_version:'1.0.0',screening_status:'疑似异常',started_at:'2026-10-14T00:00:00Z'}],total:1}:{anomaly_type:'持续减产',evidence:{provenance:{well_number:'演示井',sample_count:336,is_demo:true},recent_points:[{measurement_id:'measurement-1',measured_at:'2026-10-14T00:00:00Z',tubing_pressure_mpa:6.2}]},rule_snapshot:{name:'持续减产',code:'FL001',version:'1.0.0'}}}))
 vi.stubGlobal('fetch',fetch)
 wrapper=mount(AnalysisWorkbench,{global:{plugins:[ElementPlus],stubs:{RouterLink:true,teleport:true}}})
 await flushPromises()
 const execute=wrapper.findAll('button').find(b=>b.text()==='执行分析')!
 expect(execute.attributes('disabled')).toBeDefined()
 expect(fetch.mock.calls.some(([url])=>url.endsWith('/execute'))).toBe(false)
 await wrapper.findAll('button').find(b=>b.text()==='初始化演示规则')!.trigger('click');await flushPromises()
 expect(wrapper.text()).toContain('新增11条')
 await wrapper.find('input[type="checkbox"]').setValue(true)
 await execute.trigger('click');await flushPromises()
 expect(wrapper.text()).toContain('分析结果：已完成')
 expect(wrapper.text()).toContain('演示井')
 await wrapper.findAll('button').find(b=>b.text()==='证据')!.trigger('click');await flushPromises()
 expect(wrapper.text()).toContain('measurement-1')
 expect(wrapper.text()).toContain('油压（MPa）')
 expect(wrapper.text()).toContain('6.2')
})
it('任务失败时显示服务端原因，不伪造统计',async()=>{
 vi.stubGlobal('fetch',vi.fn(async(path:string)=>path.endsWith('/execute')?{ok:false,json:async()=>({detail:'已有分析任务运行中，请稍后重试'})}:{ok:true,json:async()=>({items:[]})}))
 wrapper=mount(AnalysisWorkbench,{global:{plugins:[ElementPlus],stubs:{RouterLink:true,teleport:true}}})
 await flushPromises();await wrapper.find('input[type="checkbox"]').setValue(true)
 await wrapper.findAll('button').find(b=>b.text()==='执行分析')!.trigger('click');await flushPromises()
 expect(wrapper.text()).toContain('已有分析任务运行中')
 expect(wrapper.text()).not.toContain('分析结果：已完成')
})
