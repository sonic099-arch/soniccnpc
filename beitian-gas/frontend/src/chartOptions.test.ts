import {it,expect} from 'vitest'
import {curveOption,curvePoints} from './chartOptions'
import {parameters,type SeriesData,type Measurement} from './screeningApi'
function sample(hour:number,value:number|null):Measurement{return {measurement_id:String(hour),measured_at:`2026-10-14T${String(hour).padStart(2,'0')}:00:00Z`,quality_flags:[],is_demo:true,...Object.fromEntries(parameters.map(p=>[p.key,value])) as Record<typeof parameters[number]['key'],number|null>} as Measurement}
export function fixture():SeriesData{return {well_id:'well-1',window_start:'2026-10-14T00:00:00Z',window_end:'2026-10-15T00:00:00Z',sample_minutes:60,total:4,measurements:[sample(0,100),sample(1,null),sample(5,20),sample(6,0)],measures:[{id:'measure-1',measure_type:'泡排',effective_start:'2026-10-13T00:00:00Z',effective_end:'2026-10-14T12:00:00Z',notes:null}],operations:[],anomalies:[{id:'anomaly-1',anomaly_type:'持续减产',started_at:'2026-10-14T05:00:00Z',ended_at:null,rule_code:'FL001',rule_version:'1.0.0'}],contains_demo:true,source_note:'原始采样'}}
it('保留空值和零值，缺口断线且不生成估算值',()=>{
 const points=curvePoints(fixture(),'instantaneous_flow_m3_h')
 expect(points.map(p=>p[1])).toEqual([100,null,null,20,0])
 expect(points[2][0]).toBe(Date.parse('2026-10-14T02:00:00Z'))
})
it('七条曲线独立单位，累计复位不被平滑或强制单调',()=>{
 parameters.forEach((p,i)=>{
  const option=curveOption(fixture(),p.key,i)
  expect(option.yAxis.name).toBe(p.unit)
  expect(option.series[0].connectNulls).toBe(false)
  expect(option.series[0].smooth).toBe(false)
  expect(option.series[0].data.map(v=>v[1])).toEqual([100,null,null,20,0])
 })
})
it('窗口外措施开始不伪造标线，有效期裁剪到窗口，异常开始时刻保持原值',()=>{
 const data=fixture(),line=curveOption(data,'tubing_pressure_mpa',0).series[0]
 expect(line.markLine.data).toHaveLength(1)
 expect(line.markLine.data[0].xAxis).toBe(Date.parse(data.anomalies[0].started_at))
 expect(line.markArea.data[0][0].xAxis).toBe(Date.parse(data.window_start))
})
it('无采样时仍有时间边界与事件标记',()=>{
 const data={...fixture(),measurements:[]}
 expect(curvePoints(data,'gas_temperature_c')).toEqual([])
 expect(curveOption(data,'gas_temperature_c',5).series[0].markLine.data).toHaveLength(1)
})
