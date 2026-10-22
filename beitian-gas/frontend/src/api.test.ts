import { afterEach, expect, it, vi } from 'vitest'
import { getHealth } from './api'
afterEach(()=>vi.unstubAllGlobals())
it('读取后端健康状态',async()=>{
 vi.stubGlobal('fetch',vi.fn().mockResolvedValue({ok:true,json:async()=>({status:'ok',stage:'任务1'})}))
 expect(await getHealth()).toEqual({status:'ok',stage:'任务1'})
})
it('后端错误显示中文提示',async()=>{
 vi.stubGlobal('fetch',vi.fn().mockResolvedValue({ok:false}))
 await expect(getHealth()).rejects.toThrow('后端服务暂不可用')
})
