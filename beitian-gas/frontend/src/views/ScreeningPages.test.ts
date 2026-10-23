// @vitest-environment happy-dom
import {afterEach,it,expect,vi} from 'vitest'
import {mount,flushPromises,type VueWrapper} from '@vue/test-utils'
import {createRouter,createMemoryHistory,type Router} from 'vue-router'
import ElementPlus from 'element-plus'
import Dashboard from './Dashboard.vue'
import WellList from './WellList.vue'
import AnomalyList from './AnomalyList.vue'
import WellDetail from './WellDetail.vue'
import {parameters,type SeriesData} from '../screeningApi'
let wrapper:VueWrapper|undefined,router:Router
const run={id:'run-1',status:'已完成',window_start:'2026-10-01T00:00:00Z',window_end:'2026-10-15T00:00:00Z',summary:{total_wells:1001,status_counts:{可信正常:308,疑似异常:385,措施影响:77,数据待核实:231,工况待核实:0}},rule_snapshot:[]}
const options={areas:['演示工区1','演示工区2'],runs:[run],selected_run:run,anomaly_types:['持续减产'],statuses:['可信正常','疑似异常','措施影响','数据待核实','工况待核实','未分析']}
const well={well_id:'well-1',well_number:'演示-BT-0001',area:'演示工区1',is_demo:true,result_id:'result-1',screening_status:'疑似异常',production_state:'生产下降待核实',as_of:run.window_end,anomaly_types:['持续减产']}
const event={id:'event-1',well_id:'well-1',well_number:well.well_number,area:well.area,screening_status:'疑似异常',anomaly_type:'持续减产',started_at:'2026-10-14T00:00:00Z',ended_at:run.window_end,rule_code:'FL001',rule_version:'1.0.0'}
const series:SeriesData={well_id:'well-1',window_start:run.window_start,window_end:run.window_end,sample_minutes:60,total:1,measurements:[{measurement_id:'sample-1',measured_at:'2026-10-14T00:00:00Z',quality_flags:[],is_demo:true,...Object.fromEntries(parameters.map(p=>[p.key,6.2])) as Record<typeof parameters[number]['key'],number>} as SeriesData['measurements'][0]],measures:[],operations:[],anomalies:[event],contains_demo:true,source_note:'曲线为原始采样'}
function mockFetch(extra?:(path:string)=>unknown){
 const fetch=vi.fn(async(url:string)=>{
  const p=new URL(url,'http://localhost');let data:unknown=extra?.(p.pathname)
  if(data===undefined){
   if(p.pathname.endsWith('/options'))data=options
   else if(p.pathname.endsWith('/dashboard'))data={run,total_wells:1001,analyzed_wells:1001,demo_wells:1001,status_counts:{...run.summary.status_counts,未分析:0},areas:[{area:well.area,screening_status:'疑似异常',count:385}],reference:'历史窗口'}
   else if(p.pathname.endsWith('/series'))data=series
   else if(p.pathname.endsWith('/wells/well-1'))data={well:{id:'well-1',well_number:well.well_number,area:well.area,is_demo:true},run,latest_measurement_at:'2026-10-14T23:00:00Z',result:{screening_status:'疑似异常',production_state:well.production_state,evidence:{rule_results:[{code:'FL001',name:'持续减产',version:'1.0.0',outcome:'命中',message:'连续减产证据',event_count:1}]}}}
   else if(p.pathname.endsWith('/anomalies/event-1'))data={anomaly_type:'持续减产',rule_snapshot:{name:'持续减产',code:'FL001',version:'1.0.0'},evidence:{provenance:{well_number:well.well_number,is_demo:true},recent_points:series.measurements}}
   else if(p.pathname.endsWith('/anomalies'))data={items:[event],total:1,run}
   else data={items:[{...well,...(p.searchParams.get('search')==='未分析'?{screening_status:'未分析',production_state:null,anomaly_types:[]}: {})}],total:1001,run}
  }
  return {ok:true,json:async()=>data}
 });vi.stubGlobal('fetch',fetch);return fetch
}
async function open(component:any,path:string){router=createRouter({history:createMemoryHistory(),routes:[{path:'/wells/:id',component:{template:'<div />'}},{path:'/:pathMatch(.*)*',component:{template:'<div />'}}]});await router.push(path);await router.isReady();wrapper=mount(component,{global:{plugins:[ElementPlus,router],stubs:{EChart:{props:['option','label','group'],template:'<div class="chart-stub" :aria-label="label" />'},teleport:true}}});await flushPromises();await flushPromises()}
afterEach(()=>{wrapper?.unmount();wrapper=undefined;vi.unstubAllGlobals()})
it('首页展示服务端统计，点击状态卡保留所选任务进入井列表',async()=>{
 mockFetch();await open(Dashboard,'/')
 expect(wrapper!.text()).toContain('1,001');expect(wrapper!.text()).toContain('308');expect(wrapper!.text()).toContain('385')
 expect(wrapper!.findAll('.chart-stub')).toHaveLength(2)
 await wrapper!.findAll('.stat-card').find(b=>b.text().includes('疑似异常'))!.trigger('click');await flushPromises()
 expect(router.currentRoute.value.path).toBe('/wells');expect(router.currentRoute.value.query).toMatchObject({run_id:'run-1',screening_status:'疑似异常'})
})
it('空库首页提示先分析，未分析不会伪装成可信正常',async()=>{
 mockFetch(path=>path.endsWith('/options')?{...options,selected_run:null,runs:[]}:path.endsWith('/dashboard')?{run:null,total_wells:1,analyzed_wells:0,demo_wells:1,status_counts:{未分析:1},areas:[],reference:'尚未分析'}:undefined)
 await open(Dashboard,'/');expect(wrapper!.text()).toContain('尚无完成的分析任务');expect(wrapper!.text()).toContain('本次已分析 0 口')
})
it('气井搜索提交到接口，链接始终带分析任务，页码进入URL',async()=>{
 const fetch=mockFetch();await open(WellList,'/wells')
 expect(wrapper!.find('a.well-link').attributes('href')).toContain('/wells/well-1?run_id=run-1')
 await wrapper!.find('input[placeholder="搜索井号"]').setValue('未分析')
 await wrapper!.find('form').trigger('submit');await flushPromises();await flushPromises()
 expect(fetch.mock.calls.some(([url])=>url.includes('/screening/wells?')&&url.includes('search=') )).toBe(true)
 expect(wrapper!.text()).toContain('尚未分析')
 await router.push('/wells?page=2');await flushPromises();await flushPromises()
 expect(fetch.mock.calls.some(([url])=>url.includes('offset=50'))).toBe(true)
})
it('异常列表默认按井去重，切换事件后可追溯原始证据',async()=>{
 const fetch=mockFetch();await open(AnomalyList,'/anomalies')
 expect(wrapper!.text()).toContain('每口井只显示一行')
 expect(fetch.mock.calls.some(([url])=>url.includes('non_normal=true'))).toBe(true)
 await wrapper!.findAll('button').find(b=>b.text()==='切换为逐事件列表')!.trigger('click');await flushPromises();await flushPromises()
 expect(wrapper!.text()).toContain('FL001 / 1.0.0')
 await wrapper!.findAll('button').find(b=>b.text()==='证据')!.trigger('click');await flushPromises()
 expect(wrapper!.text()).toContain('sample-1');expect(wrapper!.text()).toContain('油压（MPa）')
})
it('单井展示七条独立曲线、原规则和演示提示，切换天数传递准确时间',async()=>{
 const fetch=mockFetch();await open(WellDetail,'/wells/well-1?run_id=run-1')
 expect(wrapper!.findAll('.chart-stub')).toHaveLength(7)
 parameters.forEach(p=>expect(wrapper!.text()).toContain(p.name))
 expect(wrapper!.text()).toContain('不构成现场工艺标准');await vi.waitFor(()=>expect(wrapper!.text()).toContain('命中1条事件'))
 const labels=wrapper!.findAll('label.el-radio-button');await labels.find(b=>b.text()==='末7天')!.find('input').setValue(true);await flushPromises()
 const last=fetch.mock.calls.filter(([url])=>url.includes('/series?')).at(-1)![0];const query=new URL(last,'http://localhost').searchParams
 expect(query.get('window_start')).toBe('2026-10-08T00:00:00.000Z');expect(query.get('run_id')).toBe('run-1')
})
it('单井空曲线明确提示缺数据，不创建七张虚构曲线',async()=>{
 mockFetch(path=>path.endsWith('/series')?{...series,total:0,measurements:[]}:undefined)
 await open(WellDetail,'/wells/well-1');expect(wrapper!.text()).toContain('所选时间范围没有测量数据');expect(wrapper!.findAll('.chart-stub')).toHaveLength(0)
})
it('接口错误显示中文且不会保留旧统计',async()=>{
 vi.stubGlobal('fetch',vi.fn(async()=>({ok:false,json:async()=>({detail:'数据库服务暂不可用'})})))
 await open(Dashboard,'/');expect(wrapper!.text()).toContain('数据库服务暂不可用');expect(wrapper!.findAll('.stat-card')).toHaveLength(0)
})
