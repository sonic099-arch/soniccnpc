export interface StandardField { key: string; label: string; unit: string|null; allowed_units: string[]; required: boolean }
export interface Preview { headers: string[]; sheets: string[]; sheet: string; suggested_mapping: Record<string,string>; suggested_units: Record<string,string>; ambiguous_fields:string[]; total_rows:number; samples:{row:number;values:Record<string,unknown>}[] }
export interface ImportJob { id:string; filename:string; status:string; total_rows:number; success_rows:number; failed_rows:number; duplicate_rows:number; errors:{row:number;reason:string;values:Record<string,unknown>}[]; error_count:number; mapping:{preview:Preview}; report_url:string }
export async function request<T>(path:string,init:RequestInit={}):Promise<T>{
 let response:Response
 try{response=await fetch('/api/v1'+path,{...init,signal:AbortSignal.timeout(600000)})}catch(e){
  const name=(e as Error).name
  throw new Error(name==='TimeoutError'||name==='AbortError'?'请求超时，请稍后在任务记录中核对结果':'无法连接后端服务，请检查服务是否已启动')
 }
 if(!response.ok){
  let message='请求失败，请检查服务状态'
  try{const body=await response.json();if(typeof body.detail==='string')message=body.detail}catch{/* 使用中文默认提示 */}
  throw new Error(message)
 }
 return response.json()
}
export function confirmationPayload(mapping:Record<string,string>,units:Record<string,string>,timezone:string,createMissing:boolean,area:string,isDemo:boolean){
 return {confirmed:true,mapping:Object.fromEntries(Object.entries(mapping).filter(([,v])=>v)),units,timezone,is_demo:isDemo,create_missing_wells:createMissing,default_area:area}
}
