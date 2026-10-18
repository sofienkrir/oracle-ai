import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { api } from '../api/client'
import type { Dataset, Health } from '../api/types'

interface WorkspaceValue {
  health: Health | undefined
  healthError: string | undefined
  datasets: Dataset[]
  currentId: string | undefined
  current: Dataset | undefined
  select: (id: string | undefined) => void
  refresh: () => Promise<void>
}

const WorkspaceContext = createContext<WorkspaceValue | null>(null)
const STORAGE_KEY = 'oracle.currentDataset'

function readStored(): string | undefined {
  try {
    return localStorage.getItem(STORAGE_KEY) ?? undefined
  } catch {
    return undefined
  }
}

function writeStored(id: string | undefined) {
  try {
    if (id) localStorage.setItem(STORAGE_KEY, id)
    else localStorage.removeItem(STORAGE_KEY)
  } catch {
    /* stockage indisponible : préférence non mémorisée */
  }
}

export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const [health, setHealth] = useState<Health>()
  const [healthError, setHealthError] = useState<string>()
  const [datasets, setDatasets] = useState<Dataset[]>([])
  const [currentId, setCurrentId] = useState<string | undefined>(readStored)

  const refresh = useCallback(
    () =>
      Promise.all([api.health(), api.datasets()]).then(
        ([h, ds]) => {
          setHealth(h)
          setHealthError(undefined)
          setDatasets(ds)
        },
        (e: unknown) => setHealthError(e instanceof Error ? e.message : String(e)),
      ),
    [],
  )

  useEffect(() => {
    refresh().catch(() => undefined)
  }, [refresh])

  const select = useCallback((id: string | undefined) => {
    setCurrentId(id)
    writeStored(id)
  }, [])

  const current = useMemo(() => datasets.find((d) => d.id === currentId), [datasets, currentId])

  const value = useMemo(
    () => ({ health, healthError, datasets, currentId, current, select, refresh }),
    [health, healthError, datasets, currentId, current, select, refresh],
  )
  return <WorkspaceContext.Provider value={value}>{children}</WorkspaceContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useWorkspace(): WorkspaceValue {
  const ctx = useContext(WorkspaceContext)
  if (!ctx) throw new Error('useWorkspace doit être utilisé dans <WorkspaceProvider>')
  return ctx
}
