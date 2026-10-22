// @vitest-environment happy-dom
import {afterEach,expect,it,vi} from 'vitest'
import {mount,flushPromises,type VueWrapper} from '@vue/test-utils'
import ElementPlus,{ElInputNumber} from 'element-plus'
import RuleConfiguration from './RuleConfiguration.vue'
let wrapper:VueWrapper|undefined
const original={id:'rule-1',code:'FL001',name:'持续减产',version:'1.0.0',enabled:true,configuration:{decline_ratio:.25,sustain_hours:12},applicable_states:['全部'],input_parameters:['瞬时流量','基线'],config_schema:{properties:{decline_ratio:{title:'减产比例',type:'number',minimum:0,maximum:1},sustain_hours:{title:'持续时间（小时）',type:'number',minimum:0}}},warning:'演示'}
afterEach(()=>{wrapper?.unmount();wrapper=undefined;vi.unstubAllGlobals()})
async function edit(){
 wrapper=mount(RuleConfiguration,{global:{plugins:[ElementPlus],stubs:{RouterLink:true,teleport:true}}})
 await flushPromises();await wrapper.findAll('button').find(b=>b.text()==='查看并发布新版本')!.trigger('click');await flushPromises()
 const numeric=wrapper.findAllComponents(ElInputNumber)[0]
 await numeric.find('input').setValue('0.95');await numeric.find('input').trigger('change');await flushPromises()
}
it('发布新版本携带完整配置，编辑过程不改写旧版',async()=>{
 let current=JSON.parse(JSON.stringify(original));let published:Record<string,any>|null=null
 vi.stubGlobal('fetch',vi.fn(async(path:string,init?:RequestInit)=>{
  if(path.endsWith('/versions')){published=JSON.parse(init?.body as string);current={...current,...published};return {ok:true,json:async()=>current}}
  return {ok:true,json:async()=>({items:[current]})}
 }))
 await edit()
 expect(original.configuration.decline_ratio).toBe(.25)
 await wrapper!.findAll('button').find(b=>b.text()==='发布新版本')!.trigger('click');await flushPromises()
 expect(published).toMatchObject({version:'1.0.1',configuration:{decline_ratio:.95,sustain_hours:12},enabled:true,applicable_states:['全部']})
 expect(wrapper!.text()).toContain('新版本已发布')
})
it('发布失败保留旧版并展示中文原因',async()=>{
 vi.stubGlobal('fetch',vi.fn(async(path:string)=>path.endsWith('/versions')?{ok:false,json:async()=>({detail:'规则配置无效'})}:{ok:true,json:async()=>({items:[original]})}))
 await edit();await wrapper!.findAll('button').find(b=>b.text()==='发布新版本')!.trigger('click');await flushPromises()
 expect(wrapper!.text()).toContain('规则配置无效')
 expect(original.configuration.decline_ratio).toBe(.25)
 expect(wrapper!.text()).not.toContain('新版本已发布')
})
