import { defineConfig } from '@playwright/test'
export default defineConfig({
  testDir: './tests', timeout: 30000, retries: 0, workers: 1,
  use: { baseURL: process.env.PREVIEW_URL || 'http://127.0.0.1:5174', channel: process.env.CI ? undefined : 'chrome', headless: true, screenshot: 'only-on-failure' },
  reporter: 'list',
})
