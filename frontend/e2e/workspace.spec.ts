import { test, expect } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'
import fs from 'node:fs'
import path from 'node:path'

const credentials = JSON.parse(fs.readFileSync(process.env.KYRO_TEST_CREDENTIALS ?? '../data/acceptance/test-login.json', 'utf8')) as { email: string; password: string }
const evidence = path.resolve('../docs/evidence/browser')
fs.mkdirSync(evidence, { recursive: true })
fs.mkdirSync(path.join(evidence, 'screens'), { recursive: true })

test.beforeEach(async ({ page }) => {
  await page.goto('/')
  await page.getByLabel('Email', { exact: true }).fill(credentials.email)
  await page.getByLabel('Password', { exact: true }).fill(credentials.password)
  await page.getByRole('button', { name: 'Sign in', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'A clearer path to secure code.' })).toBeVisible({ timeout: 30000 })
  await expect(page.locator('.state.loading')).toHaveCount(0, { timeout: 30000 })
})

for (const viewport of [{ width: 390, height: 844 }, { width: 768, height: 1024 }, { width: 1440, height: 900 }]) {
  test(`responsive and accessible workspace ${viewport.width}x${viewport.height}`, async ({ page }) => {
    await page.setViewportSize(viewport)
    await page.emulateMedia({ reducedMotion: 'reduce' })
    await expect(page.getByText('Repositories', { exact: true }).last()).toBeVisible()
    await page.screenshot({ path: path.join(evidence, `${viewport.width}x${viewport.height}.png`), fullPage: true })
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth)
    expect(overflow).toBe(false)
    const result = await new AxeBuilder({ page }).analyze()
    fs.writeFileSync(path.join(evidence, `axe-${viewport.width}.json`), JSON.stringify(result.violations, null, 2))
    expect(result.violations).toEqual([])
    if (viewport.width < 960) {
      await page.getByRole('button', { name: 'Open navigation' }).click()
      await expect(page.getByRole('navigation').getByRole('link', { name: 'Projects', exact: true })).toBeVisible()
      await page.keyboard.press('Escape')
      await expect(page.getByRole('button', { name: 'Open navigation' })).toBeFocused()
    }
  })
}

test('all primary screens load real data without console errors', async ({ page }) => {
  const errors: string[] = []
  page.on('pageerror', error => errors.push(error.message))
  const screens = [{ url: '/projects', title: 'Projects' }, { url: '/repositories', title: 'Repositories' }, { url: '/security', title: 'Security' }, { url: '/findings', title: 'Findings' }, { url: '/dependencies', title: 'Dependencies' }, { url: '/remediation', title: 'Remediation' }, { url: '/agent-workspace', title: 'Agent workspace' }, { url: '/verification', title: 'Verification center' }, { url: '/pull-requests', title: 'Pull requests' }, { url: '/analytics', title: 'Analytics' }, { url: '/models', title: 'AI models' }, { url: '/settings', title: 'Settings' }, { url: '/onboarding', title: 'Make KYRO your workspace.' }]
  for (const screen of screens) {
    await page.goto(screen.url)
    await expect(page.getByRole('heading', { name: screen.title, exact: true, level: 1 })).toBeVisible()
    await expect(page.getByText('Loading workspace…', { exact: true })).toHaveCount(0, { timeout: 30000 })
    await expect(page.locator('.state.loading')).toHaveCount(0, { timeout: 30000 })
    expect(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth)).toBe(false)
    await page.screenshot({ path: path.join(evidence, 'screens', screen.url.slice(1) + '.png'), fullPage: true })
  }
  expect(errors).toEqual([])
})

test('project form persists and requires deletion confirmation', async ({ page }) => {
  await page.goto('/projects')
  const name = `Browser test ${Date.now()}`
  await page.getByLabel('Project name').fill(name)
  await page.getByLabel('Description').fill('Controlled browser acceptance record')
  await page.getByRole('button', { name: 'Create project', exact: true }).click()
  await expect(page.getByRole('link', { name, exact: true })).toBeVisible()
  await expect(page.getByText('Project changes saved.')).toBeVisible()
  await page.screenshot({ path: path.join(evidence, 'success-state.png') })
  await page.getByRole('button', { name: 'Delete ' + name, exact: true }).click()
  await expect(page.getByText('Delete this project, its repositories and stored evidence?')).toBeVisible()
  await page.getByRole('button', { name: 'Delete project', exact: true }).click()
  await expect(page.getByRole('link', { name, exact: true })).not.toBeVisible()
})

test('finding evidence and remediation views are connected', async ({ page }) => {
  await page.goto('/findings')
  const link = page.locator('tbody a').first()
  await expect(link).toBeVisible()
  await link.click()
  await expect(page.getByRole('heading', { name: 'Scanner provenance' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Reachability evidence' })).toBeVisible()
  const axe = await new AxeBuilder({ page }).analyze()
  expect(axe.violations).toEqual([])
})

test('failure and permission states provide recovery', async ({ page }) => {
  await page.route('**/api/findings', route => route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'Controlled API outage for browser test' }) }))
  await page.goto('/findings')
  await expect(page.getByRole('alert')).toContainText('Controlled API outage for browser test')
  await expect(page.getByRole('button', { name: 'Try again' })).toBeVisible()
  await page.screenshot({ path: path.join(evidence, 'error-state.png') })
  await page.unroute('**/api/findings')
  await page.getByRole('button', { name: 'Try again' }).click()
  await expect(page.locator('tbody a').first()).toBeVisible()
  await page.goto('/pull-requests')
  await expect(page.getByText('No pull requests created', { exact: true })).toBeVisible()
  await page.screenshot({ path: path.join(evidence, 'empty-state.png') })
  await page.goto('/onboarding')
  await expect(page.getByText('See README for least-privilege GitHub App configuration or OAuth client setup.')).toBeVisible()
  await page.screenshot({ path: path.join(evidence, 'permission-state.png') })
})

test('loading state announces actual pending API response', async ({ page }) => {
  await page.route('**/api/projects', async route => {
    await new Promise(resolve => setTimeout(resolve, 2500))
    await route.continue()
  })
  await page.goto('/projects')
  await expect(page.getByText('Loading workspace…', { exact: true })).toBeVisible()
  await page.screenshot({ path: path.join(evidence, 'loading-state.png') })
  await expect(page.getByText('Loading workspace…', { exact: true })).toHaveCount(0)
})

test('partial scan status is distinct from successful coverage (labelled browser fixture)', async ({ page }) => {
  await page.route('**/api/scans', async route => {
    const response = await route.fetch()
    const scans = await response.json() as { status: string; id: string }[]
    expect(scans.length).toBeGreaterThan(0)
    scans[0].status = 'PARTIAL'
    await route.fulfill({ response, json: scans })
  })
  await page.goto('/security')
  await expect(page.getByText('PARTIAL', { exact: true }).first()).toBeVisible()
  await page.screenshot({ path: path.join(evidence, 'partial-state-browser-fixture.png') })
})

test('API reference loads with self-hosted assets under the application CSP', async ({ page }) => {
  const errors: string[] = []
  page.on('pageerror', error => errors.push(error.message))
  await page.goto('/docs')
  await expect(page.locator('.swagger-ui .info .title')).toContainText('KYRO')
  await expect(page.locator('.opblock').first()).toBeVisible()
  expect(errors).toEqual([])
})

test('redesigned access screen works at every target width and password visibility stays under user control', async ({ page }) => {
  await page.getByRole('button', { name: 'Sign out', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Welcome back.', exact: true })).toBeVisible()
  for (const viewport of [{ width: 390, height: 844 }, { width: 768, height: 1024 }, { width: 1440, height: 900 }]) {
    await page.setViewportSize(viewport)
    await page.emulateMedia({ reducedMotion: 'reduce' })
    expect(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth)).toBe(false)
    await page.screenshot({ path: path.join(evidence, `auth-${viewport.width}x${viewport.height}.png`), fullPage: true })
    const accessibility = await new AxeBuilder({ page }).analyze()
    expect(accessibility.violations).toEqual([])
  }
  const password = page.getByLabel('Password', { exact: true })
  await password.fill('controlled-display-check')
  await expect(password).toHaveAttribute('type', 'password')
  await page.getByRole('button', { name: 'Show password', exact: true }).click()
  await expect(password).toHaveAttribute('type', 'text')
  await page.getByRole('button', { name: 'Hide password', exact: true }).click()
  await expect(password).toHaveAttribute('type', 'password')
  await password.fill('')
  await page.getByLabel('Email', { exact: true }).focus()
  await page.keyboard.press('Tab')
  await expect(password).toBeFocused()
  await page.keyboard.press('Tab')
  await expect(page.getByRole('button', { name: 'Show password', exact: true })).toBeFocused()
})

test('overview workflow guide navigates to actual product screens', async ({ page }) => {
  const steps = [{ name: 'Understand', title: 'Repositories' }, { name: 'Investigate', title: 'Findings' }, { name: 'Engineer', title: 'Remediation' }, { name: 'Verify', title: 'Verification center' }]
  for (const step of steps) {
    await page.goto('/')
    await page.locator('.workflow-guide').getByRole('link', { name: new RegExp(step.name) }).click()
    await expect(page.getByRole('heading', { name: step.title, level: 1, exact: true })).toBeVisible()
  }
})

test('recovered indexing job keeps its actual recovery history available', async ({ page }) => {
  const recoveryFile = path.resolve('../data/deployment-acceptance/recovery-ids.json')
  test.skip(!fs.existsSync(recoveryFile), 'Run the actual recovery acceptance harness on the isolated deployment first')
  const record = JSON.parse(fs.readFileSync(recoveryFile, 'utf8')) as { analysis_job_id: string; repository_id: string }
  await page.goto('/agent-workspace')
  await page.locator(`[data-job-id="${record.analysis_job_id}"]`).click()
  const history = page.getByText('Recovery history · 1 attempt(s)', { exact: true })
  await expect(history).toBeVisible()
  await history.click()
  await expect(page.getByText('Worker interrupted during a read operation', { exact: true })).toBeVisible()
  await expect(page.getByRole('link', { name: 'Open repository' })).toHaveAttribute('href', '/repositories/' + record.repository_id)
})

test('settings exposes the actual bounded automatic recovery policy', async ({ page }) => {
  await page.goto('/settings')
  await expect(page.getByRole('heading', { name: 'Automatic recovery', exact: true })).toBeVisible()
  await expect(page.getByText(/Safe operations retry temporary failures for up to 3 attempts/)).toBeVisible()
})
