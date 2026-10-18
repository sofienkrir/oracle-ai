import { afterEach, describe, expect, it, vi } from 'vitest'
import { api, ApiError } from './client'

afterEach(() => vi.unstubAllGlobals())

describe('client API', () => {
  it('transforme une erreur backend en ApiError lisible', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({ code: 'unsupported_file_type', message: 'Macros refusées', details: {} }),
          { status: 415 },
        ),
      ),
    )
    const err = await api.health().catch((e: unknown) => e)
    expect(err).toBeInstanceOf(ApiError)
    expect((err as ApiError).status).toBe(415)
    expect((err as ApiError).code).toBe('unsupported_file_type')
    expect((err as ApiError).message).toBe('Macros refusées')
  })

  it('signale un backend injoignable', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('fetch failed')))
    const err = (await api.samples().catch((e: unknown) => e)) as ApiError
    expect(err.code).toBe('network')
  })
})
