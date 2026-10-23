import {request} from './importApi'
import {type Run,displayTime,screeningStatuses} from './analysisApi'
export {screeningStatuses}
export const statuses=[...screeningStatuses,'未分析']
export const colors:Record<string,string>={'可信正常':'#159880','疑似异常':'#df744f','措施影响':'#3a86b8','数据待核实':'#d5a137','工况待核实':'#8b74b1','未分析':'#9baab5'}
export interface Options {areas:string[];runs:Run[];selected_run:Run|null;anomaly_types:string[];statuses:string[]}
export interface WellRow {well_id:string;well_number:string;area:string;is_demo:boolean;result_id:string|null;production_state:string|null;screening_status:string;as_of:string|null;anomaly_types:string[]}
export interface EventRow {id:string;well_id:string;well_number:string;area:string;screening_status:string;anomaly_type:string;started_at:string;ended_at:string|null;severity:string;rule_code:string;rule_version:string}
export interface Page<T>{items:T[];total:number;offset:number;limit:number;run:Run|null}
export interface DashboardData {run:Run|null;total_wells:number;analyzed_wells:number;demo_wells:number;status_counts:Record<string,number>;areas:{area:string;screening_status:string;count:number}[];reference:string}
export interface RuleResult {code:string;name:string;version:string;outcome:string;message:string;coverage:boolean;event_count:number}
export interface WellDetailData {well:{id:string;well_number:string;area:string;name:string|null;is_demo:boolean;description:string|null};run:Run|null;latest_measurement_at:string|null;result:{id:string;screening_status:string;production_state:string;as_of:string;evidence:{rule_results:RuleResult[];baseline:Record<string,unknown>}}|null}
export const parameters=[{key:'tubing_pressure_mpa',name:'油压',unit:'MPa'},{key:'casing_pressure_mpa',name:'套压',unit:'MPa'},{key:'back_pressure_mpa',name:'井口回压',unit:'MPa'},{key:'instantaneous_flow_m3_h',name:'瞬时流量',unit:'m³/h'},{key:'cumulative_flow_m3',name:'累计流量',unit:'m³'},{key:'gas_temperature_c',name:'气流温度',unit:'℃'},{key:'liquid_rate_m3_d',name:'产液量',unit:'m³/d'}] as const
export type ParameterKey=typeof parameters[number]['key']
export type Measurement={measurement_id:string;measured_at:string;quality_flags:string[];is_demo:boolean}&Record<ParameterKey,number|null>
export interface MeasureMark {id:string;measure_type:string;effective_start:string;effective_end:string|null;notes:string|null}
export interface OperationMark {id:string;operation_type:string;effective_start:string;effective_end:string|null;planned:boolean}
export interface AnomalyMark {id:string;anomaly_type:string;started_at:string;ended_at:string|null;rule_code:string;rule_version:string}
export interface SeriesData {well_id:string;window_start:string;window_end:string;sample_minutes:number|null;total:number;measurements:Measurement[];measures:MeasureMark[];operations:OperationMark[];anomalies:AnomalyMark[];contains_demo:boolean;source_note:string}
export interface ReportFilters {run_id:string;search:string;area:string;screening_status:string;anomaly_type:string;event_start:string;event_end:string}
export const emptyFilters=():ReportFilters=>({run_id:'',search:'',area:'',screening_status:'',anomaly_type:'',event_start:'',event_end:''})
export function queryString(values:Record<string,string|number|boolean|undefined>){const p=new URLSearchParams();for(const [k,v]of Object.entries(values))if(v!==''&&v!==undefined)p.set(k,String(v));return p.toString()}
export function screening<T>(path:string,params:Record<string,string|number|boolean|undefined>={}){return request<T>('/screening'+path+'?'+queryString(params))}
export function runLabel(run:Run){return `${displayTime(run.window_start)} — ${displayTime(run.window_end)} · ${run.id.slice(0,8)}`}
export function statusType(status:string):'success'|'warning'|'danger'|'info'|'primary'{return status==='可信正常'?'success':status==='疑似异常'?'danger':status==='措施影响'?'primary':status.includes('待核实')?'warning':'info'}
