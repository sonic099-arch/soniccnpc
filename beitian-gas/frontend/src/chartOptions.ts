import {parameters,type SeriesData,type ParameterKey} from './screeningApi'
// 图表使用原始数据。采样缺口插入null仅用于断线，不生成估算测量值。
export function curvePoints(data:SeriesData,key:ParameterKey):[number,number|null][]{
 const points:[number,number|null][]=[]
 const times=data.measurements.map(m=>Date.parse(m.measured_at))
 const intervals=times.slice(1).map((t,i)=>t-times[i]).filter(t=>t>0).sort((a,b)=>a-b)
 const cadence=data.sample_minutes?data.sample_minutes*60000:intervals[Math.floor(intervals.length/2)]
 data.measurements.forEach((row,i)=>{
  if(i>0&&cadence&&times[i]-times[i-1]>cadence*1.5)points.push([times[i-1]+cadence,null])
  points.push([times[i],Number.isFinite(row[key])?row[key]:null])
 })
 return points
}
function clock(value:number){return new Date(value).toLocaleString('zh-CN',{timeZone:'Etc/GMT-8',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false})}
export function curveOption(data:SeriesData,key:ParameterKey,index:number){
 const parameter=parameters.find(p=>p.key===key)!,start=Date.parse(data.window_start),end=Date.parse(data.window_end)
 const marks=[...data.measures.filter(m=>Date.parse(m.effective_start)>=start&&Date.parse(m.effective_start)<end).map(m=>({name:`措施：${m.measure_type}`,xAxis:Date.parse(m.effective_start),lineStyle:{color:'#3893af',type:'dashed'},label:{formatter:'措施',position:'insideEndTop'}})),...data.anomalies.filter(a=>Date.parse(a.started_at)>=start&&Date.parse(a.started_at)<end).map(a=>({name:a.anomaly_type,xAxis:Date.parse(a.started_at),lineStyle:{color:'#df744f',type:'dashed'},label:{formatter:'异常',position:'insideStartTop'}}))]
 const areas=data.measures.map(m=>[{name:m.measure_type,xAxis:Math.max(start,Date.parse(m.effective_start)),itemStyle:{color:'#3a86b812'}},{xAxis:Math.min(end,m.effective_end?Date.parse(m.effective_end):end)}])
 return {animation:false,useUTC:true,aria:{enabled:true,description:`${parameter.name}原始曲线，横轴北京时间，纵轴${parameter.unit}`},grid:{left:78,right:30,top:40,bottom:65},tooltip:{trigger:'axis',renderMode:'richText',axisPointer:{type:'line',label:{formatter:(p:{value:number})=>clock(Number(p.value))}},formatter:(rows:{value:[number,number|null]}[])=>rows.length?`${clock(rows[0].value[0])}（北京时间）\n${parameter.name}：${rows[0].value[1]??'缺失'} ${parameter.unit}`:'无采样'},xAxis:{type:'time',min:start,max:end,axisLabel:{formatter:clock,hideOverlap:true}},yAxis:{type:'value',name:parameter.unit,scale:true,splitLine:{lineStyle:{color:'#edf1f2'}}},dataZoom:[{type:'inside',filterMode:'none'},{type:'slider',height:18,bottom:8,filterMode:'none'}],series:[{name:parameter.name,type:'line',showSymbol:false,connectNulls:false,smooth:false,lineStyle:{width:1.8,color:['#177e70','#6d85af','#799b4d','#2994b3','#8f78b1','#dc9a43','#bf7684'][index]},data:curvePoints(data,key),markLine:{symbol:['none','none'],silent:false,data:marks},markArea:{silent:false,label:{show:index===0},data:areas}}]}
}
