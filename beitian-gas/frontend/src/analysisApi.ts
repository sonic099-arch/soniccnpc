import { request } from './importApi'
export interface Run {id:string;status:string;window_start:string;window_end:string;data_cutoff:string;error_message:string|null;summary:{total_wells?:number;status_counts?:Record<string,number>;anomaly_events?:number;reference?:string;warning?:string};rule_snapshot:Record<string,unknown>[]}
export interface AnalysisEvent {id:string;well_id:string;well_number:string;anomaly_type:string;rule_code:string;rule_version:string;started_at:string;screening_status:string}
export interface ConfigProperty {type:string;title:string;minimum?:number;maximum?:number;exclusiveMinimum?:number;exclusiveMaximum?:number}
export interface ConfigRule {id:string;code:string;name:string;version:string;enabled:boolean;configuration:Record<string,number|string[]>;applicable_states:string[];input_parameters:string[];config_schema:{properties:Record<string,ConfigProperty>};warning:string}
export const screeningStatuses=['可信正常','疑似异常','措施影响','数据待核实','工况待核实']
export function nextVersion(version:string){const parts=version.split('.').map(Number);return `${parts[0]}.${parts[1]}.${parts[2]+1}`}
export function runAnalysis(range:Date[],area:string){
 const body={confirmed:true,...(range.length===2?{window_start:range[0].toISOString(),window_end:range[1].toISOString()}:{}),...(area.trim()?{area:area.trim()}:{})}
 return request<Run>('/analysis/execute',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})
}
export function initializeRules(){return request<{added:number;warning:string}>('/analysis/rules/bootstrap',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({confirmed:true})})}
export function displayTime(value:string|undefined){if(!value||!Number.isFinite(Date.parse(value)))return '—';return new Date(value).toLocaleString('zh-CN',{timeZone:'Etc/GMT-8',hour12:false})}
