import { useEffect } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api, ApiError } from '../api/client'
import type { DatasetDetail } from '../api/types'
import { Icon } from '../components/Icon'
import {
  ColumnsRoles,
  IssuesPanel,
  MissingPanel,
  ParseInfo,
  PreviewTable,
  ScorePanel,
} from '../components/quality'
import { ErrorBox, Loading, PageHeader, Stat } from '../components/ui'
import { DOMAIN_LABELS } from '../lib/labels'
import { formatBytes, formatInt, formatNumber, formatPct, scoreTone } from '../lib/format'
import { useAsync } from '../lib/useAsync'
import { useWorkspace } from '../state/workspace'

export function DatasetPage() {
  const { id = '' } = useParams()
  const { select, refresh } = useWorkspace()
  const res = useAsync(() => api.dataset(id), [id])
  const loadedId = res.data?.id

  useEffect(() => {
    if (loadedId) select(loadedId)
  }, [loadedId, select])

  const dataset: DatasetDetail | undefined = res.data

  if (res.error) {
    const expired = res.error instanceof ApiError && res.error.code === 'dataset_expired'
    return (
      <>
        <PageHeader title="Dataset indisponible" />
        <ErrorBox error={res.error} />
        {expired && (
          <p>
            <Link className="btn btn-primary" to="/import">
              <Icon name="upload" size={16} /> Réimporter le fichier
            </Link>
          </p>
        )}
      </>
    )
  }
  if (!dataset) return <Loading label="Chargement du rapport de qualité…" />

  const q = dataset.quality
  const nWarnings = q.issues.filter((i) => i.severity !== 'info').length

  function onRolesSaved() {
    // Constats dépendant du rôle et score recalculés côté serveur : on recharge le rapport.
    res.reload()
    void refresh()
  }

  return (
    <>
      <PageHeader
        title={dataset.name}
        subtitle={
          <span className="tags">
            <span className={`badge dom-${dataset.domain}`}>{DOMAIN_LABELS[dataset.domain]}</span>
            <span className="badge">{dataset.file_format.toUpperCase()}</span>
            <span className="badge">{formatBytes(dataset.size_bytes)}</span>
            {dataset.source_kind === 'sample' && (
              <span className="badge badge-warn">Données synthétiques</span>
            )}
          </span>
        }
        actions={
          <>
            <a className="btn btn-secondary" href={api.exportUrl(dataset.id, 'csv')} download>
              <Icon name="download" size={16} /> Rapport CSV
            </a>
            <a className="btn btn-secondary" href={api.exportUrl(dataset.id, 'json')} download>
              <Icon name="download" size={16} /> Rapport JSON
            </a>
          </>
        }
      />

      <div className="stats stats-5">
        <Stat icon="file" label="Lignes" value={formatInt(q.n_rows)} hint="Toutes conservées" />
        <Stat icon="database" label="Colonnes" value={q.n_columns} hint={`Schéma : ${DOMAIN_LABELS[q.domain]}`} />
        <Stat
          icon="explore"
          label="Cellules manquantes"
          value={formatPct(q.pct_cells_missing, 2)}
          hint={`${formatInt(q.n_cells_missing)} cellules`}
          tone={q.pct_cells_missing > 0.1 ? 'warn' : undefined}
        />
        <Stat
          icon="anomaly"
          label="Lignes dupliquées"
          value={formatInt(q.n_duplicate_rows)}
          hint={`${formatPct(q.pct_duplicate_rows, 2)} · non supprimées`}
          tone={q.n_duplicate_rows > 0 ? 'warn' : 'good'}
        />
        <Stat
          icon="check"
          label="Indicateur qualité"
          value={`${formatNumber(q.score, 1)} / 100`}
          hint={`${nWarnings} point(s) d'attention`}
          tone={scoreTone(q.score)}
        />
      </div>

      <div className="grid-main">
        <IssuesPanel issues={q.issues} />
        <div className="stack">
          <ScorePanel report={q} />
          <MissingPanel columns={q.columns} />
        </div>
      </div>

      <ColumnsRoles key={dataset.id} dataset={dataset} onSaved={onRolesSaved} />
      <PreviewTable datasetId={dataset.id} total={q.n_rows} />
      <ParseInfo dataset={dataset} />
    </>
  )
}
