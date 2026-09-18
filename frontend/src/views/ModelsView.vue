<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { Search, ArrowUpRight, RefreshCw, Play, Download, Layers3, Sparkles, Upload, LoaderCircle, Check, Clock3 } from 'lucide-vue-next'
import { api, downloadJson } from '../lib/api'
import MessageContent from '../components/MessageContent.vue'

const props = defineProps({ workspace: Object })
const { catalog, loadModels, useModel } = props.workspace
const category = ref('all'), query = ref(''), selectedId = ref('deepseek-ai/DeepSeek-V3.2'), expanded = ref(false)
const loading = ref(false), running = ref(false), polling = ref(false), error = ref(''), result = ref(null)
const prompt = ref('用一个生活中的例子，解释 Agent 与普通聊天机器人的区别。')
const mediaUrl = ref(''), mediaType = ref('image'), mediaName = ref(''), voice = ref('alex'), adapterId = ref('')
const documents = ref('购买后七天内可申请退款。\n退款审核需要一到三个工作日。\n忘记密码可通过绑定邮箱重置。')
const maxTokens = ref(2048)
const job = ref(null), videoResult = ref(null)
let pollTimer, disposed = false, pollCount = 0
const items = computed(() => catalog.value?.items || [])
const groups = computed(() => [...new Map(items.value.map(item => [item.category, { id: item.category, label: item.category_label }])).values()])
const filtered = computed(() => items.value.filter(item => (category.value === 'all' || item.category === category.value) && item.id.toLowerCase().includes(query.value.toLowerCase())))
const visible = computed(() => expanded.value ? filtered.value : filtered.value.slice(0, 9))
const selected = computed(() => items.value.find(item => item.id === selectedId.value))
const cat = computed(() => selected.value?.category)
const canMedia = computed(() => selected.value?.media?.length || selected.value?.requires_image)
const mediaOptions = computed(() => selected.value?.requires_image ? ['image'] : selected.value?.media || [])
const mediaLabels = { image: '图片', audio: '音频', video: '视频' }
const statuses = { listed: '账号已列出', not_listed: '平台未列出', unknown: '待核验', requires_adapter: '需要微调 ID' }
const samples = {
  text: '用一个生活中的例子，解释 Agent 与普通聊天机器人的区别。',
  vision: '请描述画面内容，并列出三个值得关注的细节。',
  omni: '请概括这段素材的主要内容，并提取关键信息。',
  image: '一间宁静的未来学习工作室，鼠尾草绿与温暖米白配色，窗边植物，自然光，精致建筑摄影。',
  video: 'A peaceful learning studio with green plants. Warm sunlight moves slowly across the desk. Cinematic, gentle camera pan.',
  speech: '欢迎来到 EpochFlow。让每一次提问，成为一次发现。',
  embedding: '', rerank: '申请退款后，需要等待多久？', lora: '你好，请简要介绍你的能力。',
}
function safeUrl(value) { return typeof value === 'string' && value.startsWith('https://') ? value : '' }
const imageUrls = computed(() => (result.value?.images || []).map(item => safeUrl(item.url)).filter(Boolean))
const videoUrls = computed(() => (videoResult.value?.results?.videos || []).map(item => safeUrl(item.url)).filter(Boolean))
const statusText = computed(() => ({ Succeed: '生成完成', Failed: '生成失败', InQueue: '正在排队', InProgress: '正在生成' })[videoResult.value?.status] || '已提交，等待查询')
function pick(item) {
  if (running.value) return
  selectedId.value = item.id; prompt.value = samples[item.category]; mediaUrl.value = ''; mediaName.value = ''; mediaType.value = 'image'
  maxTokens.value = item.name.includes('Thinking') || item.name.includes('R1') ? 8192 : 2048
  if (item.requires_image && item.category === 'image') prompt.value = '保持主体与构图不变，将画面调整为温暖的水彩风格。'
  result.value = null; error.value = ''; adapterId.value = ''
}
function filterCategory(id) { category.value = id; expanded.value = false }
async function refresh() {
  loading.value = true; error.value = ''
  try { await loadModels() } catch (e) { error.value = e.message } finally { loading.value = false }
}
async function upload(event) {
  const file = event.target.files?.[0]; event.target.value = ''; if (!file) return
  if (!file.type.startsWith(mediaType.value + '/') || file.size > 700 * 1024) { error.value = '请上传类型匹配且不超过 700KB 的文件；较大的素材请使用公开 HTTPS 地址。'; return }
  const reader = new FileReader()
  reader.onload = () => { mediaUrl.value = reader.result; mediaName.value = file.name; error.value = '' }
  reader.onerror = () => { error.value = '文件读取失败，请重新选择' }
  reader.readAsDataURL(file)
}
async function pollVideo() {
  clearTimeout(pollTimer)
  if (!job.value || polling.value || disposed) return
  polling.value = true
  try {
    videoResult.value = await api('/models/video/status', { method: 'POST', body: { request_id: job.value.requestId } })
    if (['Succeed', 'Failed'].includes(videoResult.value.status)) {
      sessionStorage.removeItem('epochflow.videoJob')
    } else if (++pollCount < 60 && !disposed) pollTimer = setTimeout(pollVideo, 12000)
  } catch (e) { error.value = e.message + ' 可用原任务编号再次查询，不必重新生成。' }
  finally { polling.value = false }
}
async function run() {
  if (!selected.value || running.value) return
  running.value = true; result.value = null; error.value = ''
  try {
    result.value = await api('/models/run', { method: 'POST', body: {
      model: selectedId.value, prompt: prompt.value, media_url: mediaUrl.value, media_type: mediaType.value,
      voice: voice.value, adapter_id: adapterId.value, max_tokens: maxTokens.value,
      documents: ['embedding', 'rerank'].includes(cat.value) ? documents.value.split('\n').map(t => t.trim()).filter(Boolean) : [],
    } })
    if (result.value.requestId) {
      job.value = { requestId: result.value.requestId, model: result.value.model }
      sessionStorage.setItem('epochflow.videoJob', JSON.stringify(job.value)); videoResult.value = null; pollCount = 0
      pollTimer = setTimeout(pollVideo, 12000)
    }
  } catch (e) { error.value = e.message }
  finally { running.value = false }
}
const jobPending = computed(() => job.value && !['Succeed', 'Failed'].includes(videoResult.value?.status))
function exportResult() { downloadJson('epochflow-model-experiment.json', { ...result.value, video: videoResult.value, task: job.value }) }
onMounted(async () => {
  if (!catalog.value) await refresh()
  try { job.value = JSON.parse(sessionStorage.getItem('epochflow.videoJob') || 'null') } catch { /* Optional previous task. */ }
  if (job.value) { selectedId.value = job.value.model; prompt.value = samples.video; pollVideo() }
})
onUnmounted(() => { disposed = true; clearTimeout(pollTimer) })
</script>

<template>
  <div class="standard-page model-page">
    <div class="page-heading"><div><div class="eyebrow">ONE STUDIO. MANY POSSIBILITIES.</div><h1>模型中心<span class="heading-dot">.</span></h1><p>从文字到声音与画面，把好奇变成一次具体的实验。</p></div><button class="quiet" :disabled="loading" @click="refresh"><RefreshCw :size="16" :class="{ spin: loading }" /> 刷新状态</button></div>
    <section class="model-hero"><div><span class="eyebrow">SILICONFLOW × EPOCHFLOW</span><h2>不止于对话。<br><span>探索模型的更多可能。</span></h2><p>理解一张图，生成一段声音，或看见文字之间的语义距离。<br>所有实验通过你的硅基流动账号完成。</p></div><div class="model-hero-art" aria-hidden="true"><div class="orbit orbit-one"></div><div class="orbit orbit-two"></div><span class="orbit-core"><Layers3 :size="34" :stroke-width="1.3" /></span><span class="orbit-tag tag-text">Aa</span><span class="orbit-tag tag-sound">∿</span><span class="orbit-tag tag-image"><Sparkles :size="19" /></span></div><div class="model-hero-stats"><div><strong>{{ items.length || '—' }}</strong><span>清单模型</span></div><div><strong>{{ catalog?.listed_count ?? '—' }}</strong><span>账号已列出</span></div><div><strong>{{ groups.length || '—' }}</strong><span>实验方向</span></div></div></section>
    <div v-if="error && !selected" class="error-box" role="alert">{{ error }}</div>
    <div v-if="catalog?.error" class="info-banner">{{ catalog.error }}；模型清单仍可浏览。</div>
    <section class="model-browser" aria-label="模型目录">
      <div class="model-browser-heading"><div><span class="eyebrow">MODEL COLLECTION</span><h2>选择你的实验伙伴</h2></div><div class="input-with-icon model-search"><Search :size="16" /><input v-model="query" aria-label="搜索模型" placeholder="搜索模型名称…" @input="expanded = false" /></div></div>
      <div class="model-filters" aria-label="模型分类"><button :class="{ active: category === 'all' }" @click="filterCategory('all')">全部 <small>{{ items.length }}</small></button><button v-for="group in groups" :key="group.id" :class="{ active: category === group.id }" @click="filterCategory(group.id)">{{ group.label }} <small>{{ items.filter(item => item.category === group.id).length }}</small></button></div>
      <div v-if="loading && !items.length" class="empty-small">正在读取账号模型清单…</div>
      <div class="model-cards"><button v-for="item in visible" :key="item.id" :disabled="running" :class="['model-card', { chosen: selectedId === item.id }]" @click="pick(item)"><div class="model-card-top"><span class="model-vendor">{{ item.provider }}</span><Check v-if="selectedId === item.id" :size="15" /><ArrowUpRight v-else :size="15" /></div><h3>{{ item.name }}</h3><p>{{ item.category_label }}<span v-if="item.agent"> · Agent 工具调用</span><span v-else-if="item.requires_image"> · 需要原图</span></p><span :class="['model-availability', { listed: item.availability === 'listed' }]"><i></i>{{ statuses[item.availability] }}</span></button></div>
      <div v-if="!filtered.length && !loading" class="empty-small">没有找到对应模型，换个关键词试试。</div>
      <button v-if="filtered.length > 9" class="quiet model-expand" @click="expanded = !expanded">{{ expanded ? '收起清单' : `展开全部 ${filtered.length} 个模型` }}</button>
      <p class="panel-footnote">{{ catalog?.note }} 状态缓存 5 分钟；代金券清单来源：你提供的 2026-06-12 版本。</p>
    </section>

    <section v-if="selected" class="model-playground" aria-label="模型体验">
      <div class="surface model-input"><div class="section-heading"><div><span class="eyebrow">PLAYGROUND</span><h2>开始一次实验</h2></div><Play :size="19" /></div><div class="selected-model"><span class="tag">{{ selected.category_label }}</span><h3>{{ selected.name }}</h3><code>{{ selected.id }}</code></div>
        <button v-if="selected.agent" class="quiet agent-use" :disabled="running" @click="useModel(selected.id)">用于多 Agent 对话 <ArrowUpRight :size="15" /></button>
        <form @submit.prevent="run"><fieldset :disabled="running">
          <div v-if="cat === 'lora'" class="subtle-note">这是微调系列入口。请先在硅基流动完成训练，再填写该账号可见的实际模型 ID。此处不会发起训练任务。<a href="https://docs.siliconflow.cn/docs/userguide/guides/fine-tune" target="_blank" rel="noopener noreferrer">查看微调说明 ↗</a></div>
          <label v-if="cat === 'lora'" class="field">训练后的模型 ID<input v-model="adapterId" required maxlength="200" placeholder="从平台复制实际模型标识" /></label>
          <label v-if="cat !== 'embedding'" class="field">{{ cat === 'rerank' ? '检索问题' : cat === 'speech' ? '朗读文本' : '提示词' }}<textarea v-model="prompt" :maxlength="cat === 'speech' ? 1500 : 8000" rows="5" required></textarea></label>
          <label v-if="['embedding', 'rerank'].includes(cat)" class="field">{{ cat === 'embedding' ? '待比较文本' : '候选资料' }}<textarea v-model="documents" rows="6" maxlength="48000" required placeholder="每行一条，最多 12 条，每条最多 4000 字符"></textarea><small>每行一条，最多 12 条。{{ cat === 'embedding' ? '返回真实向量与余弦相似度。' : '按与问题的相关度重新排序。' }}</small></label>
          <div v-if="canMedia" class="media-input"><label v-if="mediaOptions.length > 1" class="field">素材类型<select v-model="mediaType" @change="mediaUrl = ''; mediaName = ''"><option v-for="type in mediaOptions" :key="type" :value="type">{{ mediaLabels[type] }}</option></select></label><label class="field">{{ mediaLabels[mediaType] }}素材 {{ selected.requires_image ? '（必填）' : '（可选）' }}<input v-if="!mediaName" v-model="mediaUrl" type="url" placeholder="https://… 公开素材地址" :required="selected.requires_image && !mediaUrl" /><span v-else class="uploaded-file">{{ mediaName }} <button type="button" class="quiet" @click="mediaUrl = ''; mediaName = ''">移除</button></span></label><label class="quiet upload-label"><Upload :size="15" /> 选择文件 · ≤700KB<input type="file" :accept="mediaType + '/*'" @change="upload" /></label></div>
          <label v-if="cat === 'speech'" class="field">预设音色<select v-model="voice"><option v-for="name in ['alex', 'anna', 'bella', 'benjamin', 'charles', 'claire', 'david', 'diana']" :key="name">{{ name }}</option></select></label>
          <label v-if="['text', 'vision', 'omni', 'lora'].includes(cat)" class="field">输出上限<select v-model.number="maxTokens"><option :value="1024">1024 tokens · 简短回答</option><option :value="2048">2048 tokens · 标准回答</option><option :value="4096">4096 tokens · 较长回答</option><option :value="8192">8192 tokens · 推理任务</option></select><small>推理模型需要预留思考与最终回答的输出空间。</small></label>
          <p class="experiment-note">点击运行会调用硅基流动 API，可能消耗代金券或余额。Render 免费托管不代表模型调用免费。</p>
          <div v-if="error" class="error-box" role="alert">{{ error }}</div>
          <button class="primary model-run" :disabled="running || (cat === 'video' && jobPending)"><LoaderCircle v-if="running" :size="16" class="spin" /><Play v-else :size="15" />{{ running ? '模型正在执行…' : cat === 'video' && jobPending ? '已有视频任务待完成' : '运行模型实验' }}</button>
        </fieldset></form>
      </div>
      <div class="surface model-output"><div class="section-heading"><div><span class="eyebrow">OBSERVE & LEARN</span><h2>实验结果</h2></div><button class="quiet" :disabled="!result && !videoResult" @click="exportResult"><Download :size="15" /> 导出</button></div>
        <div v-if="running" class="model-result-empty" role="status"><LoaderCircle :size="32" class="spin" /><h3>等待模型的回应</h3><p>图片和推理模型可能需要更长时间。<br>请保持当前页面，避免重复提交。</p></div>
        <template v-else-if="result"><div class="experiment-meta"><span class="tag">{{ result.model.split('/').at(-1) }}</span><span>{{ (result.latency_ms / 1000).toFixed(1) }}s</span><span v-if="result.usage?.total_tokens">{{ result.usage.total_tokens }} tokens</span></div><MessageContent v-if="result.text" :content="result.text" />
          <div v-if="imageUrls.length" class="media-results"><figure v-for="url in imageUrls" :key="url"><img :src="url" alt="模型生成的图片" /><figcaption><a :href="url" target="_blank" rel="noopener noreferrer">打开原图并保存 ↗</a></figcaption></figure></div>
          <div v-if="result.audio?.startsWith('data:audio/mpeg;base64,')" class="audio-result"><span class="eyebrow">GENERATED VOICE</span><audio controls :src="result.audio"></audio><a :href="result.audio" download="epochflow-voice.mp3">下载 MP3 ↓</a></div>
          <div v-if="result.similarity" class="similarity-result"><p class="muted small">{{ result.documents.length }} 条文本 · {{ result.dimensions[0] }} 维向量。越接近 1，方向越相似。</p><div class="table-scroll"><table><caption>余弦相似度</caption><thead><tr><th>文本</th><th v-for="(_, i) in result.documents" :key="i">{{ i + 1 }}</th></tr></thead><tbody><tr v-for="(row, i) in result.similarity" :key="i"><th>{{ i + 1 }}</th><td v-for="(score, j) in row" :key="j" :style="{ background: `rgba(113, 150, 98, ${Math.max(0, score) * .25})` }">{{ score.toFixed(3) }}</td></tr></tbody></table></div><ol><li v-for="(text, i) in result.documents" :key="i">{{ text }}</li></ol><p class="panel-footnote">完整向量包含在导出的 JSON 中；本次实验不会改变知识空间的默认检索方式。</p></div>
          <div v-if="result.results" class="rerank-results"><article v-for="(row, i) in result.results" :key="row.index"><div><span class="tag">#{{ i + 1 }}</span><small>原始位置 {{ row.index + 1 }} · {{ row.score.toFixed(4) }}</small></div><p>{{ row.text }}</p><meter min="0" max="1" :value="row.score" :aria-label="`资料 ${row.index + 1} 相关度`"></meter></article></div>
        </template>
        <div v-else-if="!job || cat !== 'video'" class="model-result-empty"><span class="result-emblem"><Sparkles :size="29" :stroke-width="1.3" /></span><h3>想法，从这里变得具体。</h3><p>选择模型，调整输入，再运行实验。<br>这里会展示模型真实返回的内容。</p></div>
        <div v-if="job && cat === 'video'" class="video-job"><div class="section-heading"><strong><Clock3 :size="15" /> {{ statusText }}</strong><button class="quiet" :disabled="polling" @click="pollCount = 0; pollVideo()">{{ polling ? '查询中…' : '查询状态' }}</button></div><p class="small muted">{{ job.model }}</p><code>{{ job.requestId }}</code><p v-if="videoResult?.reason">{{ videoResult.reason }}</p><video v-for="url in videoUrls" :key="url" controls :src="url"></video><a v-for="url in videoUrls" :key="url" :href="url" target="_blank" rel="noopener noreferrer">打开视频并保存 ↗</a><p class="panel-footnote">任务编号保留在当前浏览器会话，可刷新后继续查询。生成链接会过期，请及时保存。</p></div>
      </div>
    </section>
  </div>
</template>
