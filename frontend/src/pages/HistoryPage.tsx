import { Link } from 'react-router-dom'
import { api } from '../api/client'
import type { Analysis } from '../api/types'
import { Icon } from '../components/Icon'
import { Card, ErrorBox, Loading, PageHeader } from '../components/ui'
import { ANALYSIS_LABELS, ROLE_LABELS } from '../lib/labels'
import type { ColumnRole } from '../api/types'
import { formatDateTime, formatInt, formatPct } from '../lib/format'
import { useAsync } from '../lib/useAsync'
import { useWorkspace } from '../state/workspace'

function summarize(a: Analysis): string {
  const s = a.summary as Record<string, number | string>
  if (a.kind === 'quality_profile') {
    return [
      `score ${s.score}`,
      `${formatInt(Number(s.n_rows))} lignes`,
      `${s.n_issues} constats`,
      `${formatPct(Number(s.pct_cells_missing), 2)} manquants`,
      `${s.duration_s} s`,
    ].join(' · ')
  }
  if (a.kind === 'roles_update') {
    const changed = (a.params.changed ?? {}) as Record<string, ColumnRole>
    return Object.entries(changed)
      .map(([col, role]) => `${col} → ${ROLE_LABELS[role] ?? role}`)
      .join(' · ')
  }
  return JSON.stringify(a.summary)
}

function download(name: string, content: string) {
  const url = URL.createObjectURL(new Blob([content], { type: 'application/json' }))
  const a = document.createElement('a')
  a.href = url
  a.download = name
  a.click()
  URL.revokeObjectURL(url)
}

export function HistoryPage() {
  const res = useAsync(() => api.history(), [])
  const { datasets } = useWorkspace()
  const loaded = new Set(datasets.filter((d) => d.loaded).map((d) => d.id))

  return (
    <>
      <PageHeader
        title="Historique des analyses"
        subtitle="Métadonnées, paramètres et résumés enregistrés dans SQLite. Ils persistent après redémarrage ; les fichiers sources ne sont pas conservés."
        actions={
          res.data && res.data.length > 0 ? (
            <button
              className="btn btn-secondary"
              onClick={() => download('oracle_historique.json', JSON.stringify(res.data, null, 2))}
            >
              <Icon name="download" size={16} /> Exporter JSON
            </button>
          ) : null
        }
      />
      <Card>
        {res.loading && <Loading />}
        {res.error && <ErrorBox error={res.error} onRetry={res.reload} />}
        {res.data && res.data.length === 0 && (
          <p className="muted">Aucune analyse enregistrée pour le moment.</p>
        )}
        {res.data && res.data.length > 0 && (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Dataset</th>
                  <th>Analyse</th>
                  <th>Résumé</th>
                  <th>Moteur</th>
                </tr>
              </thead>
              <tbody>
                {res.data.map((a) => (
                  <tr key={a.id}>
                    <td className="nowrap">{formatDateTime(a.created_at)}</td>
                    <td>
                      {loaded.has(a.dataset_id) ? (
                        <Link to={`/datasets/${a.dataset_id}`}>{a.dataset_name}</Link>
                      ) : (
                        <span title="Copie de travail libérée">{a.dataset_name}</span>
                      )}
                    </td>
                    <td>
                      <span className="badge">{ANALYSIS_LABELS[a.kind] ?? a.kind}</span>
                    </td>
                    <td className="small">{summarize(a)}</td>
                    <td className="muted small">v{a.engine_version}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </>
  )
}
