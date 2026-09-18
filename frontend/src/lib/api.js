const publicBase = import.meta.env.PROD ? import.meta.env.VITE_PYTHON_API_URL : '/api/python'
export const apiBase = (publicBase || '/api/python').replace(/\/+$/, '')
export function token() { return sessionStorage.getItem('epochflow.accessToken') || '' }
export function setToken(value) { sessionStorage.setItem('epochflow.accessToken', value.trim()) }
export async function api(path, { method = 'GET', body, signal } = {}) {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), 180000)
  const abort = () => controller.abort()
  signal?.addEventListener('abort', abort, { once: true })
  try {
    const isForm = body instanceof FormData
    const response = await fetch(apiBase + path, {
      method, signal: controller.signal,
      headers: { ...(token() ? { 'X-Access-Token': token() } : {}), ...(body && !isForm ? { 'Content-Type': 'application/json' } : {}) },
      body: body ? (isForm ? body : JSON.stringify(body)) : undefined,
    })
    if (!(response.headers.get('content-type') || '').includes('application/json')) throw new Error('后端正在唤醒或暂时不可用，请稍后重试。')
    const data = await response.json()
    if (!response.ok) {
      const detail = data.detail || data.message
      throw new Error(typeof detail === 'string' ? detail : response.status === 422 ? '输入格式不正确，请检查后再试。' : `请求失败（${response.status}）`)
    }
    return data
  } catch (error) {
    if (error.name === 'AbortError') throw new Error('请求已超时。免费服务唤醒可能需要一分钟，请稍后重试。')
    if (error instanceof TypeError) throw new Error('无法连接后端。请检查网络与服务地址，或等待免费服务唤醒。')
    throw error
  } finally { clearTimeout(timer); signal?.removeEventListener('abort', abort) }
}
export function downloadJson(filename, data) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: 'application/json;charset=utf-8' }))
  const link = document.createElement('a'); link.href = url; link.download = filename; link.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
