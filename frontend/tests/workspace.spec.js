import { test, expect } from '@playwright/test'
import fs from 'node:fs/promises'

test('desktop navigation, knowledge lifecycle and real connection state', async ({ page }) => {
  const errors = []; page.on('pageerror', error => errors.push(error.message))
  await page.setViewportSize({ width: 1440, height: 1000 })
  await page.goto('/')
  await expect(page.getByRole('heading', { name: '对话实验室.' })).toBeVisible()
  await expect(page.getByRole('heading', { name: '一个问题， 开启一次探索。' })).toBeVisible()
  await expect(page.getByRole('button', { name: '模型已配置' })).toBeVisible()
  await fs.mkdir('../docs/assets', { recursive: true })
  await page.screenshot({ path: '../docs/assets/workspace-desktop.png', fullPage: true })
  await page.getByRole('button', { name: '知识空间 02' }).click()
  await expect(page.getByRole('button', { name: /退款政策/ })).toBeVisible()
  await page.getByRole('button', { name: '添加文档', exact: true }).click()
  await page.getByLabel('文档标题').fill('浏览器验收资料')
  await page.getByLabel('文档内容').fill('木星轨道课程在周三下午开始。')
  await page.getByRole('dialog').getByRole('button', { name: '添加文档', exact: true }).click()
  await expect(page.getByRole('button', { name: /浏览器验收资料/ })).toBeVisible()
  await page.getByLabel('知识检索问题').fill('木星轨道课程')
  await page.getByLabel('知识检索问题').press('Enter')
  await expect(page.locator('.search-result').first()).toContainText('浏览器验收资料')
  await page.getByRole('button', { name: /浏览器验收资料/ }).click()
  await page.getByRole('button', { name: '移除文档', exact: true }).click()
  await page.getByRole('button', { name: '确认从本次运行移除' }).click()
  await expect(page.getByRole('button', { name: /浏览器验收资料/ })).toHaveCount(0)
  await page.getByRole('button', { name: '评测实验 03' }).click()
  await expect(page.getByRole('button', { name: '运行这项实验' })).toBeVisible()
  await page.getByRole('button', { name: '运行概览 04' }).click()
  await expect(page.getByRole('heading', { name: 'Agent 能力' })).toBeVisible()
  await page.getByRole('button', { name: '工作台设置', exact: true }).click()
  await expect(page.getByText('后端已配置 · 不向浏览器公开')).toBeVisible()
  expect(errors).toEqual([])
})

test('chat UI renders structured results and sanitizes model markdown', async ({ page }) => {
  await page.route('**/api/python/chat', route => route.fulfill({ json: {
    conv_id: 'test-session', request_id: 'ui-test-trace', response: '**测试回复**\n\n```python\nprint("hello")\n```\n<script>alert("xss")</script>',
    intent: 'refund', intent_confidence: 0.9, primary_agent: 'billing', agent_types: ['billing'], tools_used: [], latency_ms: 1234, routing_reason: '测试中的账单路由结果',
  } }))
  await page.route('**/api/python/trace/tool/ui-test-trace', route => route.fulfill({ json: { trace: { tool_calls: [] } } }))
  await page.goto('/')
  await page.getByLabel('输入你的问题').fill('测试退款问题')
  await page.getByRole('button', { name: '发送消息' }).click()
  await expect(page.locator('.markdown-body strong')).toHaveText('测试回复')
  await expect(page.locator('.markdown-body pre')).toContainText('print("hello")')
  await expect(page.locator('.markdown-body script')).toHaveCount(0)
  await expect(page.getByText('测试中的账单路由结果')).toBeVisible()
  await page.getByRole('button', { name: '新建对话' }).click()
  await expect(page.getByRole('heading', { name: '一个问题， 开启一次探索。' })).toBeVisible()
})

test('mobile workspace has no horizontal overflow and menu works', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/')
  await expect(page.getByRole('heading', { name: '对话实验室.' })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.screenshot({ path: '../docs/assets/workspace-mobile.png', fullPage: true })
  await page.getByRole('button', { name: '打开菜单' }).click()
  await page.getByRole('button', { name: '知识空间 02' }).click()
  await expect(page.getByRole('heading', { name: '知识空间.' })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
})

test('model catalogue filters, runs embeddings and validates image input', async ({ page }) => {
  const errors = []; page.on('pageerror', error => errors.push(error.message))
  await page.setViewportSize({ width: 1440, height: 1000 })
  await page.goto('/')
  await page.getByRole('button', { name: '模型中心 05' }).click()
  await expect(page.getByRole('heading', { name: '模型中心.' })).toBeVisible()
  await expect(page.locator('.model-card')).toHaveCount(9)
  await expect(page.locator('.model-hero-stats').first()).toContainText('50')
  await page.screenshot({ path: '../docs/assets/model-studio.png', fullPage: true, animations: 'disabled' })
  await page.getByLabel('搜索模型').fill('Qwen3-Embedding-0.6B')
  await expect(page.locator('.model-card')).toHaveCount(1)
  await page.locator('.model-card').click()
  await page.route('**/api/python/models/run', async route => {
    const payload = route.request().postDataJSON()
    expect(payload.model).toBe('Qwen/Qwen3-Embedding-0.6B')
    expect(payload.documents).toHaveLength(3)
    await route.fulfill({ json: { model: payload.model, category: 'embedding', latency_ms: 600,
      documents: payload.documents, dimensions: [2, 2, 2], vectors: [[1, 0], [1, 0], [0, 1]],
      similarity: [[1, 1, 0], [1, 1, 0], [0, 0, 1]] } })
  })
  await page.getByRole('button', { name: '运行模型实验' }).click()
  await expect(page.getByRole('table', { name: '余弦相似度' })).toBeVisible()
  await page.getByLabel('搜索模型').fill('Qwen-Image-Edit-2509')
  await page.locator('.model-card').click()
  await expect(page.getByLabel('图片素材 （必填）')).toBeVisible()
  await page.getByRole('button', { name: '运行模型实验' }).click()
  expect(await page.getByLabel('图片素材 （必填）').evaluate(el => el.validity.valueMissing)).toBe(true)
  await page.setViewportSize({ width: 390, height: 844 })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.screenshot({ path: '../docs/assets/model-studio-mobile.png', fullPage: true, animations: 'disabled' })
  expect(errors).toEqual([])
})

test('video task can resume after page reload without submitting again', async ({ page }) => {
  let submitted = 0, queried = 0
  await page.route('**/api/python/models/run', route => {
    submitted++
    return route.fulfill({ json: { model: 'Wan-AI/Wan2.2-T2V-A14B', category: 'video', requestId: 'test-video-task', latency_ms: 100 } })
  })
  await page.route('**/api/python/models/video/status', route => {
    queried++
    expect(route.request().postDataJSON().request_id).toBe('test-video-task')
    return route.fulfill({ json: { status: 'InProgress' } })
  })
  await page.goto('/')
  await page.getByRole('button', { name: '模型中心 05' }).click()
  await page.getByLabel('搜索模型').fill('Wan2.2-T2V')
  await page.locator('.model-card').click()
  await page.getByRole('button', { name: '运行模型实验' }).click()
  await expect(page.getByText('test-video-task')).toBeVisible()
  await page.reload()
  await page.getByRole('button', { name: '模型中心 05' }).click()
  await expect(page.getByText('正在生成', { exact: true })).toBeVisible()
  expect(submitted).toBe(1)
  expect(queried).toBeGreaterThan(0)
  await expect(page.getByRole('button', { name: '已有视频任务待完成' })).toBeDisabled()
})

test('public demo settings do not ask visitors for an access code', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 })
  await page.route('**/api/python/health', route => route.fulfill({ json: {
    status: 'ok', model_configured: true, public_demo: true, model: 'deepseek-ai/DeepSeek-V3.2',
    storage_mode: 'memory', persistent: false, retrieval: 'character_ngram', agents: {},
  } }))
  await page.goto('/')
  await page.getByRole('button', { name: '工作台设置', exact: true }).click()
  await expect(page.getByText('公开演示已开启')).toBeVisible()
  await expect(page.getByLabel('工作台访问码')).toHaveCount(0)
  await expect(page.getByText('公开演示 · 无访问码')).toBeVisible()
})
