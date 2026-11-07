import { afterEach, describe, expect, it, vi } from 'vitest'
import { api, ApiError, setCsrf } from './api'

afterEach(() => { vi.unstubAllGlobals(); setCsrf('') })
describe('authenticated API boundary', () => {
  it('sends CSRF and credentials on mutation', async () => { const fetch = vi.fn().mockResolvedValue(new Response('{"status":"queued"}', { status: 202, headers: { 'Content-Type': 'application/json' } })); vi.stubGlobal('fetch', fetch); setCsrf('test-csrf'); await api('/projects', 'POST', { name: 'Owned' }); expect(fetch.mock.calls[0][1].credentials).toBe('include'); expect(fetch.mock.calls[0][1].headers['X-CSRF-Token']).toBe('test-csrf') })
  it('propagates failed operations without inventing success', async () => { vi.stubGlobal('fetch', vi.fn().mockImplementation(async () => new Response('{"detail":"GitHub authorization required"}', { status: 409 }))); await expect(api('/repositories', 'POST')).rejects.toBeInstanceOf(ApiError); await expect(api('/repositories', 'POST')).rejects.toThrow('GitHub authorization required') })
})
