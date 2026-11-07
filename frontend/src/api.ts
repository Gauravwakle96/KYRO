import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

let csrf = ''
export const setCsrf = (value: string) => { csrf = value }
export class ApiError extends Error { status: number; constructor(message: string, status: number) { super(message); this.status = status } }

export async function api<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
  const response = await fetch('/api' + path, { method, credentials: 'include', headers: { 'Content-Type': 'application/json', ...(csrf ? { 'X-CSRF-Token': csrf } : {}) }, ...(body === undefined ? {} : { body: JSON.stringify(body) }) })
  const data: unknown = await response.json()
  if (!response.ok) {
    const detail = typeof data === 'object' && data !== null && 'detail' in data ? data.detail : 'Request failed'
    throw new ApiError(typeof detail === 'string' ? detail : 'Check the form fields and try again', response.status)
  }
  return data as T
}
export function useData<T>(path: string, options?: { poll?: number; enabled?: boolean }) {
  return useQuery<T, Error>({ queryKey: [path], queryFn: () => api<T>(path), retry: false, refetchInterval: options?.poll, enabled: options?.enabled ?? true })
}
export function useAction() {
  const client = useQueryClient()
  return useMutation({ mutationFn: ({ path, method, body }: { path: string; method?: string; body?: unknown }) => api<unknown>(path, method ?? 'POST', body), onSuccess: () => { void client.invalidateQueries() } })
}
