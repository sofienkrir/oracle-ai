import { useRef, useState } from 'react'
import type { DragEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api, ApiError } from '../api/client'
import type { SheetMode } from '../api/client'
import { Icon } from '../components/Icon'
import { Card, PageHeader } from '../components/ui'
import { DOMAIN_LABELS } from '../lib/labels'
import { formatBytes, formatDateTime, formatInt } from '../lib/format'
import { useWorkspace } from '../state/workspace'

const ACCEPT = '.csv,.xlsx'

export function ImportPage() {
  const { health, datasets, select, refresh } = useWorkspace()
  const navigate = useNavigate()
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)
  const [busy, setBusy] = useState<string>()
  const [error, setError] = useState<ApiError | Error>()
  const [sheets, setSheets] = useState<SheetMode>('first')

  const loaded = datasets.filter((d) => d.loaded)

  async function handleFile(file: File) {
    setError(undefined)
    setBusy(file.name)
    try {
      const ds = await api.upload(file, sheets)
      select(ds.id)
      await refresh()
      navigate(`/datasets/${ds.id}`)
    } catch (e) {
      setError(e as Error)
    } finally {
      setBusy(undefined)
      if (inputRef.current) inputRef.current.value = ''
    }
  }

  function onDrop(e: DragEvent) {
    e.preventDefault()
    setDragging(false)
    const file = e.dataTransfer.files[0]
    if (file) void handleFile(file)
  }

  async function release(id: string) {
    await api.release(id)
    await refresh()
  }

  return (
    <>
      <PageHeader
        title="Import & qualité des données"
        subtitle="Le fichier est lu localement, validé puis profilé. Aucune ligne n'est supprimée ni modifiée silencieusement."
      />

      <div
        className={`dropzone${dragging ? ' dragging' : ''}${busy ? ' busy' : ''}`}
        onDragOver={(e) => {
          e.preventDefault()
          setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
      >
        <div className="dropzone-icon">
          <Icon name="upload" size={26} />
        </div>
        {busy ? (
          <>
            <strong>Analyse de « {busy} » en cours…</strong>
            <span className="muted">Validation, lecture et profilage qualité.</span>
            <span className="spinner" aria-hidden="true" />
          </>
        ) : (
          <>
            <strong>Glissez un fichier ici</strong>
            <span className="muted">
              ou{' '}
              <button className="link-btn" onClick={() => inputRef.current?.click()}>
                parcourez votre ordinateur
              </button>
            </span>
            <span className="muted small">
              Formats : .csv, .xlsx (feuilles : voir l'option ci-dessous) · max {health?.limits.max_upload_mb ?? '—'} Mo ·{' '}
              {formatInt(health?.limits.max_rows)} lignes · {health?.limits.max_columns ?? '—'}{' '}
              colonnes · macros refusées
            </span>
          </>
        )}
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPT}
          hidden
          data-testid="file-input"
          onChange={(e) => {
            const f = e.target.files?.[0]
            if (f) void handleFile(f)
          }}
        />
      </div>

      <fieldset className="sheet-mode" disabled={!!busy}>
        <legend>Classeurs Excel (.xlsx) avec plusieurs feuilles</legend>
        <label>
          <input
            type="radio"
            name="sheets"
            value="first"
            checked={sheets === 'first'}
            onChange={() => setSheets('first')}
          />
          <span>
            <strong>Première feuille seulement</strong>
            <span className="muted small">Comportement par défaut.</span>
          </span>
        </label>
        <label>
          <input
            type="radio"
            name="sheets"
            value="all"
            checked={sheets === 'all'}
            onChange={() => setSheets('all')}
          />
          <span>
            <strong>Toutes les feuilles, empilées</strong>
            <span className="muted small">
              Ex. une feuille par année. Les feuilles doivent avoir exactement les mêmes colonnes ;
              les lignes identiques d'une feuille à l'autre sont signalées, pas supprimées.
            </span>
          </span>
        </label>
      </fieldset>

      {error && (
        <div className="alert alert-error" role="alert">
          <Icon name="anomaly" />
          <div>
            <strong>Import refusé</strong>
            <p>{error.message}</p>
          </div>
        </div>
      )}

      <Card title="Datasets en mémoire" icon="database">
        {loaded.length === 0 ? (
          <p className="muted">
            Aucun dataset chargé. Importez un fichier ou partez d'un{' '}
            <Link to="/">dataset de démonstration</Link>.
          </p>
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Fichier</th>
                  <th>Domaine</th>
                  <th className="num">Lignes</th>
                  <th className="num">Colonnes</th>
                  <th className="num">Taille</th>
                  <th>Importé le</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {loaded.map((d) => (
                  <tr key={d.id}>
                    <td>
                      <Link to={`/datasets/${d.id}`} onClick={() => select(d.id)}>
                        {d.name}
                      </Link>
                      {d.source_kind === 'sample' && <span className="badge ml">Synthétique</span>}
                    </td>
                    <td>
                      <span className={`badge dom-${d.domain}`}>{DOMAIN_LABELS[d.domain]}</span>
                    </td>
                    <td className="num">{formatInt(d.n_rows)}</td>
                    <td className="num">{d.n_columns}</td>
                    <td className="num">{formatBytes(d.size_bytes)}</td>
                    <td>{formatDateTime(d.created_at)}</td>
                    <td className="row-actions">
                      <button
                        className="icon-btn"
                        title="Libérer la mémoire (les métadonnées restent dans l'historique)"
                        onClick={() => release(d.id)}
                      >
                        <Icon name="trash" size={16} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <p className="muted small">
          Les copies de travail vivent uniquement en mémoire du backend. Après redémarrage ou
          expiration, seules les métadonnées restent (voir Historique) : il faut réimporter le
          fichier.
        </p>
      </Card>
    </>
  )
}
