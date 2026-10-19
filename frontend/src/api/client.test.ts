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

  it("envoie le mode de lecture des feuilles Excel avec le fichier", async () => {
    const fetchMock = vi
      .fn()
      .mockImplementation(() =>
        Promise.resolve(new Response(JSON.stringify({ id: 'x' }), { status: 201 })),
      )
    vi.stubGlobal('fetch', fetchMock)
    await api.upload(new File(['a'], 'f.xlsx'), 'all')
    const body = fetchMock.mock.calls[0][1].body as FormData
    expect(body.get('sheets')).toBe('all')
    expect((body.get('file') as File).name).toBe('f.xlsx')

    await api.upload(new File(['a'], 'f.csv'))
    expect((fetchMock.mock.calls[1][1].body as FormData).get('sheets')).toBe('first')
  })
})
