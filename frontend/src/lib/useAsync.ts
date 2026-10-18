import { useCallback, useEffect, useRef, useState } from 'react'

export interface AsyncState<T> {
  data: T | undefined
  error: Error | undefined
  loading: boolean
  reload: () => void
}

/** Charge une ressource asynchrone ; ignore les réponses obsolètes. */
export function useAsync<T>(fn: () => Promise<T>, deps: unknown[]): AsyncState<T> {
  const [data, setData] = useState<T>()
  const [error, setError] = useState<Error>()
  const [loading, setLoading] = useState(true)
  const [tick, setTick] = useState(0)
  const callId = useRef(0)

  useEffect(() => {
    const id = ++callId.current
    setLoading(true)
    setError(undefined)
    fn()
      .then((d) => {
        if (id === callId.current) setData(d)
      })
      .catch((e: unknown) => {
        if (id === callId.current) setError(e instanceof Error ? e : new Error(String(e)))
      })
      .finally(() => {
        if (id === callId.current) setLoading(false)
      })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick])

  const reload = useCallback(() => setTick((t) => t + 1), [])
  return { data, error, loading, reload }
}
