export interface Well { id: string; well_number: string; area: string; is_demo: boolean }
export interface Page<T> {items: T[]; total: number; offset: number; limit: number}
export async function getHealth(): Promise<{ status: string; stage: string }> {
  const response = await fetch('/health', { signal: AbortSignal.timeout(5000) })
  if (!response.ok) throw new Error('后端服务暂不可用')
  return response.json()
}
