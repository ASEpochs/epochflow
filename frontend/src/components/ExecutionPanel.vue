<script setup>
import { computed } from 'vue'
import { Workflow, Check, ScanLine } from 'lucide-vue-next'
const props = defineProps({ message: Object })
const result = computed(() => props.message?.result)
const names = { general: '通用咨询', technical: '技术支持', billing: '账单与退款', escalation: '人工交接' }
const pretty = value => JSON.stringify(value ?? {}, null, 2)
</script>
<template>
  <aside class="execution-panel"><div class="panel-heading"><span><Workflow :size="17" /> 执行观察</span><span class="tag neutral">TRACE</span></div>
    <div class="execution-intro"><span class="eyebrow">从问题到答案</span><h3>看见 Agent 的每一步</h3><p>发送消息后，在这里查看实际路由、工具调用与检索结果。</p></div>
    <div class="pipeline"><div v-for="(step, index) in ['读取会话上下文', '识别请求意图', '路由到专业 Agent', '执行工具与生成回复']" :key="step" class="pipeline-step"><div class="step-track"><span :class="['step-number', { done: result }] "><Check v-if="result" :size="13" /><template v-else>{{ String(index + 1).padStart(2, '0') }}</template></span><div v-if="index < 3" class="step-connector"></div></div><div><strong>{{ step }}</strong><small v-if="result && index === 1">{{ result.intent }} · {{ Math.round(result.intent_confidence * 100) }}%</small><small v-else-if="result && index === 2">{{ names[result.primary_agent] || result.primary_agent }}</small><small v-else-if="result && index === 3">{{ result.tools_used?.length || 0 }} 个工具 · {{ (result.latency_ms / 1000).toFixed(1) }} 秒</small><small v-else>{{ ['当前会话最近消息', '结合规则与模型判断', '匹配问题所需能力', '按需检索与调用工具'][index] }}</small></div></div></div>
    <template v-if="result"><div class="execution-detail"><span class="eyebrow">路由决策</span><p>{{ result.routing_reason || '后端未提供路由说明' }}</p><div class="tag-row"><span v-for="agent in result.agent_types" :key="agent" class="tag">{{ names[agent] || agent }}</span></div></div><div class="execution-detail"><span class="eyebrow">工具调用</span><p v-if="!message.trace?.tool_calls?.length" class="muted small">{{ message.traceError ? '调用详情暂时无法加载。' : '此次请求没有工具调用。' }}</p><details v-for="(call, index) in message.trace?.tool_calls || []" :key="index" class="tool-call"><summary><span>{{ call.tool_name || call.name || '工具' }}</span><span :class="['tag', call.success ? '' : 'warning']">{{ call.success ? '成功' : '失败' }}</span></summary><pre>{{ pretty(call) }}</pre></details></div><div class="trace-id">REQUEST ID<code>{{ result.request_id }}</code></div></template>
    <div v-else class="trace-placeholder"><ScanLine :size="26" /><span>{{ message?.pending ? 'Agent 正在执行，完成后显示真实记录' : '等待第一条执行记录' }}</span></div>
    <div class="panel-footnote">仅展示执行事件与结果，不包含模型内部推理。</div>
  </aside>
</template>
