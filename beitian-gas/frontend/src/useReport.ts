import {ref,reactive,watch,onBeforeUnmount} from 'vue'
import {useRoute,useRouter} from 'vue-router'
import {screening,emptyFilters,type ReportFilters,type Options} from './screeningApi'
export function useReport<T>(endpoint:string|(()=>string),extra:Record<string,string|boolean>={}){
 const route=useRoute(),router=useRouter(),filters=reactive(emptyFilters())
 const options=ref<Options|null>(null),data=ref<T|null>(null),error=ref(''),loading=ref(false),page=ref(1)
 let sequence=0
 async function load(){
  const seq=++sequence;loading.value=true;error.value=''
  for(const key of Object.keys(filters) as (keyof ReportFilters)[])filters[key]=typeof route.query[key]==='string'?route.query[key] as string:''
  const n=Number(route.query.page);page.value=Number.isInteger(n)&&n>0?n:1
  try{
   const o=await screening<Options>('/options',{run_id:filters.run_id});if(seq!==sequence)return
   options.value=o
   const result=await screening<T>(typeof endpoint==='function'?endpoint():endpoint,{...filters,run_id:o.selected_run?.id,offset:(page.value-1)*50,limit:50,...extra})
   if(seq===sequence)data.value=result
  }catch(e){if(seq===sequence){data.value=null;error.value=(e as Error).message}}
  finally{if(seq===sequence)loading.value=false}
 }
 function apply(){const query:Record<string,string>=typeof route.query.view==='string'?{view:route.query.view}:{};for(const[k,v]of Object.entries(filters))if(v)query[k]=v;router.push({path:route.path,query})}
 function paginate(value:number){router.push({query:{...route.query,page:String(value)}})}
 function wellLink(id:string){return {path:'/wells/'+id,query:options.value?.selected_run?{run_id:options.value.selected_run.id}:{}}}
 watch(()=>route.fullPath,load,{immediate:true});onBeforeUnmount(()=>sequence++)
 return {filters,options,data,error,loading,page,load,apply,paginate,wellLink}
}
