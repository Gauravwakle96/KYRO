import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { Activity } from './Activity'
import type { Job } from '../types'

// Explicit API fixtures for the UI boundary; live job recovery is checked separately.
const failed: Job = { id: 'original-import', kind: 'ingest', resource_id: 'controlled-repo', status: 'FAILED', error: 'Worker interrupted', created_at: '2026-11-07T14:00:00Z', cancel_requested: false, events: [{ at: '2026-11-07T14:00:00Z', message: 'Original retrieval evidence' }] }
const pending: Job = { ...failed, id: 'retried-analysis', kind: 'analyze', status: 'PENDING', error: null, events: [{ at: '2026-11-07T14:01:00Z', message: 'Starting retry analysis' }] }

class FixtureEventSource {
  onmessage: ((event: MessageEvent) => void) | null = null
  onerror: (() => void) | null = null
  close() { /* No external connection in this unit fixture. */ }
}

beforeEach(() => vi.stubGlobal('EventSource', FixtureEventSource))
afterEach(() => { cleanup(); vi.unstubAllGlobals() })

function show() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 }, mutations: { retry: false } } })
  render(<QueryClientProvider client={client}><MemoryRouter><Activity /></MemoryRouter></QueryClientProvider>)
}

describe('Agent Workspace recovery', () => {
  it('queues a real API retry and switches to its new execution events', async () => {
    let retried = false
    const fetch = vi.fn(async (url: string, options?: RequestInit) => {
      if (url === '/api/jobs/original-import/retry' && options?.method === 'POST') {
        retried = true
        return new Response(JSON.stringify(pending), { status: 202 })
      }
      return new Response(JSON.stringify(retried ? [pending, failed] : [failed]))
    })
    vi.stubGlobal('fetch', fetch)
    show()
    fireEvent.click(await screen.findByRole('button', { name: 'Retry import' }))
    expect(await screen.findByText('Starting retry analysis')).toBeInTheDocument()
    await waitFor(() => expect(fetch).toHaveBeenCalledWith('/api/jobs/original-import/retry', expect.objectContaining({ method: 'POST', credentials: 'include' })))
    expect(screen.getByRole('link', { name: 'Open repository' })).toHaveAttribute('href', '/repositories/controlled-repo')
  })

  it('shows a rejected retry and preserves the original failure', async () => {
    vi.stubGlobal('fetch', vi.fn(async (url: string) => url.endsWith('/retry')
      ? new Response(JSON.stringify({ detail: 'Source retrieval is incomplete' }), { status: 409 })
      : new Response(JSON.stringify([failed]))))
    show()
    fireEvent.click(await screen.findByRole('button', { name: 'Retry import' }))
    expect(await screen.findByText('Source retrieval is incomplete')).toBeInTheDocument()
    expect(screen.getByText('Original retrieval evidence')).toBeInTheDocument()
    expect(screen.getByText('Worker interrupted')).toBeInTheDocument()
  })

  it('keeps consequential agent actions in their remediation review flow', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify([{ ...failed, kind: 'execute' }]))))
    show()
    expect(await screen.findByRole('link', { name: 'Open remediation evidence' })).toHaveAttribute('href', '/remediation/controlled-repo')
    expect(screen.queryByRole('button', { name: /Retry/ })).not.toBeInTheDocument()
  })

  it('explains automatic recovery and lets the user cancel its scheduled attempt', async () => {
    const scheduled: Job = { ...failed, status: 'PENDING', error: null, payload: { automatic_recovery: { attempt: 1, max_attempts: 3, not_before: '2099-01-01T00:00:00Z' } } }
    let cancelled = false
    vi.stubGlobal('fetch', vi.fn(async (url: string) => {
      if (url.endsWith('/cancel')) {
        cancelled = true
        return new Response(JSON.stringify({ status: 'cancellation_requested' }))
      }
      return new Response(JSON.stringify([{ ...scheduled, status: cancelled ? 'CANCELLED' : 'PENDING' }]))
    }))
    show()
    expect(await screen.findByText(/Automatic recovery is scheduled/)).toHaveTextContent('Attempt 2 of 3')
    fireEvent.click(screen.getByRole('button', { name: 'Cancel job' }))
    expect(await screen.findByRole('button', { name: 'Retry import' })).toBeVisible()
    expect(screen.queryByText(/Automatic recovery is scheduled/)).not.toBeInTheDocument()
  })
})
