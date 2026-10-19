import type {
  Analysis,
  ColumnRole,
  Dataset,
  DatasetDetail,
  Health,
  Preview,
  Sample,
} from './types'

/** XLSX : première feuille seulement, ou toutes les feuilles empilées. */
export type SheetMode = 'first' | 'all'

const BASE = '/api'

export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly details: Record<string, unknown>

  constructor(status: number, code: string, message: string, details: Record<string, unknown>) {
    super(message)
    this.status = status
    this.code = code
    this.details = details
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(`${BASE}${path}`, init)
  } catch {
    throw new ApiError(0, 'network', 'API injoignable : le backend est-il démarré ?', {})
  }
  if (res.status === 204) return undefined as T
  const text = await res.text()
  let body: unknown = null
  try {
    body = text ? JSON.parse(text) : null
  } catch {
    body = null
  }
  if (!res.ok) {
    const b = (body ?? {}) as { code?: string; message?: string; details?: Record<string, unknown> }
    throw new ApiError(
      res.status,
      b.code ?? 'http_error',
      b.message ?? `Erreur HTTP ${res.status}`,
      b.details ?? {},
    )
  }
  return body as T
}

export const api = {
  health: () => request<Health>('/health'),
  samples: () => request<Sample[]>('/samples'),
  datasets: (loadedOnly = false) =>
    request<Dataset[]>(`/datasets${loadedOnly ? '?loaded_only=true' : ''}`),
  dataset: (id: string) => request<DatasetDetail>(`/datasets/${encodeURIComponent(id)}`),
  preview: (id: string, offset = 0, limit = 50) =>
    request<Preview>(
      `/datasets/${encodeURIComponent(id)}/preview?offset=${offset}&limit=${limit}`,
    ),
  loadSample: (sampleId: string) =>
    request<DatasetDetail>(`/datasets/samples/${encodeURIComponent(sampleId)}`, {
      method: 'POST',
    }),
  upload: (file: File, sheets: SheetMode = 'first') => {
    const form = new FormData()
    form.append('file', file)
    form.append('sheets', sheets)
    return request<DatasetDetail>('/datasets/upload', { method: 'POST', body: form })
  },
  updateRoles: (id: string, roles: Record<string, ColumnRole>) =>
    request<{ roles: Record<string, ColumnRole> }>(`/datasets/${encodeURIComponent(id)}/roles`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ roles }),
    }),
  release: (id: string) =>
    request<void>(`/datasets/${encodeURIComponent(id)}`, { method: 'DELETE' }),
  history: (datasetId?: string) =>
    request<Analysis[]>(
      `/history${datasetId ? `?dataset_id=${encodeURIComponent(datasetId)}` : ''}`,
    ),
  exportUrl: (id: string, format: 'json' | 'csv') =>
    `${BASE}/datasets/${encodeURIComponent(id)}/quality/export?format=${format}`,
}
