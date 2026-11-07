import { defineConfig } from '@playwright/test'
export default defineConfig({ testDir: './e2e', timeout: 60000, use: { baseURL: process.env.KYRO_TEST_URL ?? 'http://127.0.0.1:8788', channel: 'chrome', trace: 'retain-on-failure', screenshot: 'only-on-failure' }, workers: 1, reporter: [['list'], ['json', { outputFile: '../docs/evidence/browser-test-results.json' }]] })
