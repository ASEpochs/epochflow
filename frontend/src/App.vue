<script setup>
import { ref, computed } from 'vue'
import { Plus, PanelLeftOpen, MessageSquare, Library, FlaskConical, Activity, Settings2, Layers3, ChevronRight, CircleHelp, X } from 'lucide-vue-next'
import { useWorkspace } from './composables/useWorkspace'
import ChatView from './views/ChatView.vue'
import KnowledgeView from './views/KnowledgeView.vue'
import EvaluationView from './views/EvaluationView.vue'
import OverviewView from './views/OverviewView.vue'
import SettingsView from './views/SettingsView.vue'
import ModelsView from './views/ModelsView.vue'
const workspace = useWorkspace()
const { view, conversations, activeId, health, notice, createConversation, selectConversation, refresh, connectionError } = workspace
const mobileMenu = ref(false)
const navigation = [
  { id: 'chat', label: '对话实验室', icon: MessageSquare, hint: '01' },
  { id: 'knowledge', label: '知识空间', icon: Library, hint: '02' },
  { id: 'evaluation', label: '评测实验', icon: FlaskConical, hint: '03' },
  { id: 'overview', label: '运行概览', icon: Activity, hint: '04' },
  { id: 'models', label: '模型中心', icon: Layers3, hint: '05' },
]
const title = computed(() => navigation.find(item => item.id === view.value)?.label || '工作台设置')
function navigate(id) { view.value = id; mobileMenu.value = false }
</script>
<template>
  <div class="app-layout">
    <button v-if="mobileMenu" class="mobile-scrim" aria-label="关闭菜单" @click="mobileMenu = false"></button>
    <aside class="sidebar" :class="{ 'is-open': mobileMenu }">
      <a class="brand" href="#chat" @click.prevent="navigate('chat')"><span class="brand-icon"><Layers3 :size="23" /></span><span>Epoch<span class="brand-light">Flow</span><small>AGENT ENGINEERING STUDIO</small></span></a>
      <button class="new-session" @click="createConversation(); mobileMenu = false"><Plus :size="17" /> 新建对话 <kbd>＋</kbd></button>
      <div class="nav-caption">工作空间</div>
      <nav aria-label="主导航"><button v-for="item in navigation" :key="item.id" :class="['nav-item', { selected: view === item.id }]" @click="navigate(item.id)"><component :is="item.icon" :size="18" /><span>{{ item.label }}</span><small>{{ item.hint }}</small></button></nav>
      <div class="history-heading"><span class="nav-caption">最近会话</span><span>{{ conversations.length }}</span></div>
      <div class="session-history"><button v-for="conversation in conversations" :key="conversation.id" :class="['history-item', { selected: activeId === conversation.id && view === 'chat' }]" @click="selectConversation(conversation.id); mobileMenu = false"><MessageSquare :size="14" /><span>{{ conversation.title }}</span></button></div>
      <div class="sidebar-bottom"><div class="learning-note"><span class="tiny-label">BUILD. OBSERVE. UNDERSTAND.</span><p>让每一次对话，<br>成为一次 Agent 实验。</p><span class="note-line"></span></div><button class="nav-item" :class="{ selected: view === 'settings' }" @click="navigate('settings')"><Settings2 :size="18" /><span>工作台设置</span><ChevronRight :size="14" /></button><div class="profile"><span class="avatar">A</span><div><strong>ASEpochs</strong><small>Agent 工程作品集</small></div><span class="free-badge">FREE</span></div></div>
    </aside>
    <div class="main-shell">
      <header class="topbar"><div class="breadcrumb"><button class="icon-button menu-toggle" aria-label="打开菜单" @click="mobileMenu = !mobileMenu"><PanelLeftOpen :size="20" /></button><span class="muted">工作空间</span><ChevronRight :size="14" /><strong>{{ title }}</strong></div><div class="topbar-right"><button class="connection" @click="navigate('settings')"><i :class="{ online: health?.status === 'ok' }"></i>{{ health?.status === 'ok' ? (health.model_configured ? '模型已配置' : '模型待配置') : '等待连接' }}</button><span class="separator"></span><button class="quiet small" @click="navigate('overview')"><CircleHelp :size="15" /> 使用指南</button></div></header>
      <main>
        <div v-if="connectionError" class="connection-alert" role="status">{{ connectionError }} <button @click="refresh">重新连接</button><button @click="navigate('settings')">打开设置</button></div>
        <ChatView v-if="view === 'chat'" :workspace="workspace" />
        <KnowledgeView v-else-if="view === 'knowledge'" :workspace="workspace" />
        <EvaluationView v-else-if="view === 'evaluation'" :workspace="workspace" />
        <OverviewView v-else-if="view === 'overview'" :workspace="workspace" />
        <ModelsView v-else-if="view === 'models'" :workspace="workspace" />
        <SettingsView v-else :workspace="workspace" />
      </main>
      <footer class="app-footer"><span><i class="tiny-dot"></i> EpochFlow · 纪流</span><span>公开作品集演示 <span class="footer-dot">·</span> 云端临时数据在休眠或重启后清除</span><span class="footer-version">v1.1 / MODEL STUDIO</span></footer>
    </div>
    <div v-if="notice" class="toast" role="status">{{ notice }}<button class="icon-button" aria-label="关闭通知" @click="notice = ''"><X :size="15" /></button></div>
  </div>
</template>
