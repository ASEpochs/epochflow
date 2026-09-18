import { ref, computed, watch, onMounted } from 'vue'
import { api, downloadJson } from '../lib/api'
const STORAGE_KEY = 'epochflow.sessions.v1'
function restore() { try { return JSON.parse(sessionStorage.getItem(STORAGE_KEY) || '[]').slice(0, 30) } catch { return [] } }
export function useWorkspace() {
  const view = ref('chat'), conversations = ref(restore()), activeId = ref(conversations.value[0]?.id || '')
  const active = computed(() => conversations.value.find(item => item.id === activeId.value))
  const health = ref(null), monitor = ref(null), skills = ref(null), notice = ref(''), busy = ref(false), connectionError = ref('')
  const catalog = ref(null), selectedModel = ref(sessionStorage.getItem('epochflow.agentModel') || '')
  watch(selectedModel, value => sessionStorage.setItem('epochflow.agentModel', value))
  const agentModels = computed(() => (catalog.value?.items || []).filter(item => item.agent))
  async function loadModels() { catalog.value = await api('/models'); return catalog.value }
  function useModel(id) { selectedModel.value = id; createConversation(); notify('新会话已选择 ' + id.split('/').at(-1)) }
  let noticeTimer
  const userId = sessionStorage.getItem('epochflow.user') || crypto.randomUUID()
  sessionStorage.setItem('epochflow.user', userId)
  watch(conversations, value => { try { sessionStorage.setItem(STORAGE_KEY, JSON.stringify(value.slice(0, 30))) } catch { /* Quota must not prevent chat. */ } }, { deep: true })
  function notify(message) { notice.value = message; clearTimeout(noticeTimer); noticeTimer = setTimeout(() => { notice.value = '' }, 5500) }
  function createConversation() {
    const conversation = { id: crypto.randomUUID(), title: '新的 Agent 实验', serverId: '', messages: [], createdAt: new Date().toISOString() }
    conversations.value.unshift(conversation); conversations.value = conversations.value.slice(0, 30); activeId.value = conversation.id; view.value = 'chat'
    return conversation
  }
  function selectConversation(id) { activeId.value = id; view.value = 'chat' }
  function deleteConversation() {
    if (busy.value) return
    conversations.value = conversations.value.filter(item => item.id !== activeId.value)
    activeId.value = conversations.value[0]?.id || ''; if (!activeId.value) createConversation()
    notify('已移除此浏览器中的会话记录')
  }
  async function refresh() {
    connectionError.value = ''
    try {
      health.value = await api('/health')
      const results = await Promise.allSettled([api('/monitor'), api('/skills'), loadModels()])
      if (results[0].status === 'fulfilled') monitor.value = results[0].value
      else connectionError.value = results[0].reason.message
      if (results[1].status === 'fulfilled') skills.value = results[1].value
    } catch (error) { health.value = null; connectionError.value = error.message }
  }
  async function send(text, retry = false) {
    if (!text.trim() || busy.value) return
    const conversation = active.value || createConversation()
    if (!retry) conversation.messages.push({ id: crypto.randomUUID(), role: 'user', content: text.trim() })
    if (conversation.messages.filter(item => item.role === 'user').length === 1) conversation.title = text.trim().slice(0, 24)
    conversation.messages.push({ id: crypto.randomUUID(), role: 'assistant', content: '', pending: true, prompt: text })
    const message = conversation.messages[conversation.messages.length - 1]
    busy.value = true
    try {
      const response = await api('/chat', { method: 'POST', body: { message: text, user_id: userId, conv_id: conversation.serverId || undefined, model: selectedModel.value || undefined } })
      conversation.serverId = response.conv_id; message.content = response.response; message.result = response
      try { message.trace = (await api(`/trace/tool/${encodeURIComponent(response.request_id)}`)).trace } catch { message.traceError = true }
      await refresh()
    } catch (error) { message.error = error.message }
    finally { message.pending = false; busy.value = false }
  }
  function exportConversation() { if (active.value) downloadJson(`epochflow-conversation-${active.value.id.slice(0, 8)}.json`, active.value) }
  onMounted(() => { if (!activeId.value) createConversation(); refresh() })
  return { view, conversations, activeId, active, health, monitor, skills, notice, busy, connectionError, notify, refresh, createConversation, selectConversation, deleteConversation, send, exportConversation, catalog, loadModels, selectedModel, agentModels, useModel }
}
