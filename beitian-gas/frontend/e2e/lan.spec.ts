import {test,expect} from '@playwright/test'
import {readFileSync} from 'node:fs'

test('构建网页与离线接口文档不加载外网资源',async({page,baseURL})=>{
 const external:string[]=[],errors:string[]=[]
 page.on('pageerror',e=>errors.push(e.message))
 await page.route('**/*',route=>{const url=route.request().url();if(new URL(url).origin!==new URL(baseURL!).origin){external.push(url);return route.abort()}return route.continue()})
 await page.goto('/docs')
 await expect(page.locator('.swagger-ui .title')).toContainText('北田公司气井智能分析系统')
 await expect(page.locator('.swagger-ui .opblock').first()).toBeVisible()
 await page.goto('/wells')
 await expect(page.getByRole('heading',{name:'气井列表'})).toBeVisible()
 await expect(page.locator('.count-label')).toContainText('1001')
 expect(external).toEqual([]);expect(errors).toEqual([])
})

test('生产静态页面深链接刷新和浏览器跳转不暴露源文件',async({page,request})=>{
 await page.goto('/anomalies');await page.reload()
 await expect(page.getByRole('heading',{name:'异常井列表'})).toBeVisible()
 expect((await request.get('/.env')).status()).toBe(404)
 expect((await request.get('/src/main.ts')).status()).toBe(404)
 expect((await request.get('/api/v1/unknown')).status()).toBe(404)
 const redoc=await request.get('/redoc',{maxRedirects:0});expect(redoc.headers()['location']).toBe('/docs')
})

test('同源入口可下载Excel并上传预览，分析记录数量不受预览影响',async({request})=>{
 const download=await request.get('/api/v1/excel/template?example=true')
 expect(download.ok()).toBe(true);expect(download.headers()['content-disposition']).toContain('attachment')
 expect((await download.body()).subarray(0,2).toString()).toBe('PK')
 const upload=await request.post('/api/v1/excel/preview',{multipart:{file:{name:'example.xlsx',mimeType:'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',buffer:readFileSync('../examples/example.xlsx')}}})
 expect(upload.status()).toBe(201)
 const data=await upload.json();expect(data.mapping.preview.total_rows).toBe(3)
 const dashboard=await(await request.get('/api/v1/screening/dashboard')).json()
 expect(dashboard.total_wells).toBe(1001)
})
