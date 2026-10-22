import {afterEach,expect,it,vi} from 'vitest'
import {request,confirmationPayload} from './importApi'
afterEach(()=>vi.unstubAllGlobals())
it('上传预览保留FormData，不错误设置JSON头',async()=>{
 const fetch=vi.fn().mockResolvedValue({ok:true,json:async()=>({id:'job'})});vi.stubGlobal('fetch',fetch)
 const form=new FormData();form.append('file','演示')
 expect(await request('/excel/preview',{method:'POST',body:form})).toEqual({id:'job'})
 expect(fetch.mock.calls[0][0]).toBe('/api/v1/excel/preview')
 expect(fetch.mock.calls[0][1].body).toBe(form)
})
it('确认配置保留单位和时区，移除未选字段',()=>{
 expect(confirmationPayload({well_number:'井号',measured_at:'时间',gas_temperature_c:''},{},'Asia/Shanghai',true,'演示',true)).toEqual({confirmed:true,mapping:{well_number:'井号',measured_at:'时间'},units:{},timezone:'Asia/Shanghai',is_demo:true,create_missing_wells:true,default_area:'演示'})
})
it('接口错误显示服务端中文原因',async()=>{
 vi.stubGlobal('fetch',vi.fn().mockResolvedValue({ok:false,json:async()=>({detail:'井号不存在'})}))
 await expect(request('/excel/preview')).rejects.toThrow('井号不存在')
})
it('非JSON错误回退中文提示',async()=>{
 vi.stubGlobal('fetch',vi.fn().mockResolvedValue({ok:false,json:async()=>{throw Error()}}))
 await expect(request('/excel/preview')).rejects.toThrow('请求失败，请检查服务状态')
})
it('网络不可用时给出中文错误',async()=>{
 vi.stubGlobal('fetch',vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
 await expect(request('/analysis/runs')).rejects.toThrow('无法连接后端服务')
})
it('超时提示先核对任务结果，避免误以为已取消',async()=>{
 vi.stubGlobal('fetch',vi.fn().mockRejectedValue(new DOMException('timeout','TimeoutError')))
 await expect(request('/analysis/execute')).rejects.toThrow('请求超时，请稍后在任务记录中核对结果')
})
