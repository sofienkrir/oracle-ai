import { useMemo, useState } from 'react'
import { api, ApiError } from '../api/client'
import type {
  ColumnProfile,
  ColumnRole,
  DatasetDetail,
  QualityIssue,
  QualityReport,
  Severity,
} from '../api/types'
import { formatDate, formatInt, formatNumber, formatPct } from '../lib/format'
import { ROLE_LABELS, ROLE_ORDER, SCORE_LABELS, TYPE_LABELS } from '../lib/labels'
import { useAsync } from '../lib/useAsync'
import { Icon } from './Icon'
import { Bar, Card, ErrorBox, Loading, SeverityBadge } from './ui'

// ----------------------------------------------------------------- problèmes

export function IssuesPanel({ issues }: { issues: QualityIssue[] }) {
  const [filter, setFilter] = useState<Severity | 'all'>('all')
  const counts = useMemo(() => {
    const c: Record<string, number> = { all: issues.length, error: 0, warning: 0, info: 0 }
    issues.forEach((i) => (c[i.severity] += 1))
    return c
  }, [issues])
  const shown = filter === 'all' ? issues : issues.filter((i) => i.severity === filter)

  return (
    <Card
      title="Problèmes détectés"
      icon="anomaly"
      actions={
        <div className="segmented" role="group" aria-label="Filtrer par gravité">
          {(['all', 'error', 'warning', 'info'] as const).map((k) => (
            <button
              key={k}
              className={filter === k ? 'on' : ''}
              onClick={() => setFilter(k)}
              disabled={counts[k] === 0 && k !== 'all'}
            >
              {k === 'all' ? 'Tous' : k === 'error' ? 'Erreurs' : k === 'warning' ? 'Attention' : 'Infos'}{' '}
              <span className="count">{counts[k]}</span>
            </button>
          ))}
        </div>
      }
    >
      {shown.length === 0 ? (
        <p className="empty-ok">
          <Icon name="check" /> Aucun problème de cette catégorie.
        </p>
      ) : (
        <ul className="issues">
          {shown.map((i, idx) => (
            <li key={`${i.code}-${i.column}-${idx}`}>
              <SeverityBadge severity={i.severity} />
              <div>
                <p>{i.message}</p>
                <span className="muted small">
                  <code>{i.code}</code>
                  {i.column && <> · colonne {i.column}</>}
                </span>
              </div>
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}

// ----------------------------------------------------------------- score

export function ScorePanel({ report }: { report: QualityReport }) {
  return (
    <Card title="Indicateur de qualité" icon="check">
      <div className="score-row">
        <div className={`score-ring tone-${report.score >= 90 ? 'good' : report.score >= 70 ? 'warn' : 'bad'}`}>
          <svg viewBox="0 0 36 36" aria-hidden="true">
            <circle cx="18" cy="18" r="15.5" className="ring-bg" />
            <circle
              cx="18"
              cy="18"
              r="15.5"
              className="ring-fg"
              strokeDasharray={`${(report.score / 100) * 97.4} 97.4`}
            />
          </svg>
          <span>{formatNumber(report.score, 1)}</span>
        </div>
        <ul className="breakdown">
          {Object.entries(report.score_breakdown).map(([k, v]) => (
            <li key={k}>
              <span>{SCORE_LABELS[k] ?? k}</span>
              <Bar value={v / 100} tone={v >= 90 ? 'good' : v >= 70 ? 'warn' : 'bad'} />
              <span className="num">{formatNumber(v, 1)}</span>
            </li>
          ))}
        </ul>
      </div>
      <p className="muted small">
        Heuristique documentée : moyenne de 4 composantes égales (cellules renseignées, lignes non
        dupliquées, colonnes sans types incohérents, colonnes ni vides ni constantes). Utile pour
        comparer des versions d'un même fichier, pas comme norme absolue.
      </p>
    </Card>
  )
}

// ----------------------------------------------------------------- manquants

export function MissingPanel({ columns }: { columns: ColumnProfile[] }) {
  const withMissing = [...columns]
    .filter((c) => c.n_missing > 0)
    .sort((a, b) => b.pct_missing - a.pct_missing)
    .slice(0, 8)
  return (
    <Card title="Valeurs manquantes par colonne" icon="explore">
      {withMissing.length === 0 ? (
        <p className="empty-ok">
          <Icon name="check" /> Aucune valeur manquante.
        </p>
      ) : (
        <ul className="hbars">
          {withMissing.map((c) => (
            <li key={c.name}>
              <span className="hbar-label" title={c.name}>
                {c.name}
              </span>
              <Bar value={c.pct_missing} tone={c.pct_missing >= 0.3 ? 'bad' : 'accent'} />
              <span className="num">{formatPct(c.pct_missing)}</span>
              <span className="num muted">{formatInt(c.n_missing)}</span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}

// ----------------------------------------------------------------- colonnes & rôles

function columnSummary(c: ColumnProfile): string {
  if (c.numeric) {
    return `min ${formatNumber(c.numeric.min)} · méd. ${formatNumber(c.numeric.median)} · max ${formatNumber(c.numeric.max)}`
  }
  if (c.datetime) {
    const fmt = c.datetime.native ? 'date native' : `format ${c.datetime.format}`
    return `${formatDate(c.datetime.min)} → ${formatDate(c.datetime.max)} · ${fmt}`
  }
  if (c.top_values.length) {
    return c.top_values
      .slice(0, 3)
      .map((t) => `${t.value} (${formatInt(t.count)})`)
      .join(' · ')
  }
  return '—'
}

export function ColumnsRoles({
  dataset,
  onSaved,
}: {
  dataset: DatasetDetail
  onSaved: (roles: Record<string, ColumnRole>) => void
}) {
  const [draft, setDraft] = useState<Record<string, ColumnRole>>(dataset.roles)
  const [saving, setSaving] = useState(false)
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [message, setMessage] = useState<string>()

  const changed = Object.keys(draft).filter((k) => draft[k] !== dataset.roles[k])

  async function save() {
    setSaving(true)
    setErrors({})
    setMessage(undefined)
    try {
      const res = await api.updateRoles(dataset.id, draft)
      onSaved(res.roles)
      setMessage('Rôles enregistrés et journalisés dans l’historique.')
    } catch (e) {
      if (e instanceof ApiError && e.details.errors) {
        setErrors(e.details.errors as Record<string, string>)
        setMessage(e.message)
      } else {
        setMessage((e as Error).message)
      }
    } finally {
      setSaving(false)
    }
  }

  return (
    <Card
      title="Colonnes et rôles"
      icon="database"
      actions={
        <>
          {changed.length > 0 && (
            <button className="btn btn-ghost" onClick={() => setDraft(dataset.roles)}>
              Annuler
            </button>
          )}
          <button className="btn btn-primary" disabled={changed.length === 0 || saving} onClick={save}>
            {saving ? 'Validation…' : `Confirmer les rôles${changed.length ? ` (${changed.length})` : ''}`}
          </button>
        </>
      }
    >
      <p className="muted small">
        Rôles proposés automatiquement à partir du contenu et du schéma reconnu. Vérifiez-les : ils
        détermineront les analyses possibles (une seule cible autorisée).
      </p>
      {message && (
        <p className={`notice ${Object.keys(errors).length ? 'notice-error' : 'notice-ok'}`}>
          {message}
          {errors.__all__ && <> — {errors.__all__}</>}
        </p>
      )}
      <div className="table-wrap">
        <table className="table columns-table">
          <thead>
            <tr>
              <th>Colonne</th>
              <th>Type détecté</th>
              <th>Manquants</th>
              <th className="num">Distinctes</th>
              <th>Aperçu des valeurs</th>
              <th>Rôle</th>
            </tr>
          </thead>
          <tbody>
            {dataset.quality.columns.map((c) => (
              <tr key={c.name} className={errors[c.name] ? 'row-error' : ''}>
                <td>
                  <strong className="col-name">{c.name}</strong>
                  {c.issues.length > 0 && (
                    <span className="issue-dot" title={c.issues.join(', ')}>
                      {c.issues.length}
                    </span>
                  )}
                </td>
                <td>
                  <span className={`type type-${c.semantic_type}`}>{TYPE_LABELS[c.semantic_type]}</span>
                  <span className="muted small block">{c.dtype}</span>
                </td>
                <td className="missing-cell">
                  <Bar value={c.pct_missing} tone={c.pct_missing >= 0.3 ? 'bad' : 'accent'} />
                  <span className="small">{formatPct(c.pct_missing)}</span>
                </td>
                <td className="num">{formatInt(c.n_unique)}</td>
                <td className="small muted values-cell">{columnSummary(c)}</td>
                <td>
                  <select
                    aria-label={`Rôle de ${c.name}`}
                    className={draft[c.name] !== dataset.roles[c.name] ? 'changed' : ''}
                    value={draft[c.name]}
                    onChange={(e) => setDraft({ ...draft, [c.name]: e.target.value as ColumnRole })}
                  >
                    {ROLE_ORDER.map((r) => (
                      <option key={r} value={r}>
                        {ROLE_LABELS[r]}
                      </option>
                    ))}
                  </select>
                  <span className="muted small block" title={c.role_reason}>
                    {errors[c.name] ?? c.role_reason}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  )
}

// ----------------------------------------------------------------- aperçu

const PAGE = 25

export function PreviewTable({ datasetId, total }: { datasetId: string; total: number }) {
  const [offset, setOffset] = useState(0)
  const page = useAsync(() => api.preview(datasetId, offset, PAGE), [datasetId, offset])
  return (
    <Card
      title="Aperçu des données brutes"
      icon="file"
      actions={
        <div className="pager">
          <button className="btn btn-ghost" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE))}>
            Précédent
          </button>
          <span className="muted small">
            {formatInt(offset + 1)}–{formatInt(Math.min(offset + PAGE, total))} sur {formatInt(total)}
          </span>
          <button className="btn btn-ghost" disabled={offset + PAGE >= total} onClick={() => setOffset(offset + PAGE)}>
            Suivant
          </button>
        </div>
      }
    >
      {page.error && <ErrorBox error={page.error} onRetry={page.reload} />}
      {page.loading && !page.data && <Loading />}
      {page.data && (
        <div className="table-wrap preview">
          <table className="table dense">
            <thead>
              <tr>
                <th className="num muted">#</th>
                {page.data.columns.map((c) => (
                  <th key={c}>{c}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {page.data.rows.map((row, i) => (
                <tr key={page.data!.offset + i}>
                  <td className="num muted">{page.data!.offset + i + 1}</td>
                  {row.map((v, j) => (
                    <td key={j} className={v === null ? 'null' : typeof v === 'number' ? 'num' : ''}>
                      {v === null ? 'vide' : String(v)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  )
}

// ----------------------------------------------------------------- lecture du fichier

const PARSE_LABELS: Record<string, string> = {
  encoding: 'Encodage',
  delimiter: 'Séparateur',
  engine: 'Moteur Excel',
  sheet_mode: 'Mode de lecture Excel',
  sheet: 'Feuille(s) importée(s)',
  sheets_imported: 'Lignes par feuille',
  sheets_skipped: 'Feuilles ignorées',
  sheets_available: 'Feuilles disponibles',
  note: 'Note',
}

function showValue(v: unknown, key?: string): string {
  if (key === 'sheet_mode') return v === 'all' ? 'Toutes les feuilles, empilées' : 'Première feuille seulement'
  if (Array.isArray(v)) return v.join(', ')
  if (v === '\t') return 'tabulation'
  if (v === null || v === undefined) return '—'
  return String(v)
}

export function ParseInfo({ dataset }: { dataset: DatasetDetail }) {
  return (
    <Card title="Lecture du fichier et transformations" icon="info">
      <dl className="kv">
        <div className="kv-row">
          <dt>Empreinte SHA-256</dt>
          <dd>
            <code className="hash">{dataset.sha256}</code>
          </dd>
        </div>
        {Object.entries(dataset.parse_info).map(([k, v]) => (
          <div key={k} className="kv-row">
            <dt>{PARSE_LABELS[k] ?? k}</dt>
            <dd>{showValue(v, k)}</dd>
          </div>
        ))}
        <div className="kv-row">
          <dt>Schéma reconnu</dt>
          <dd>{dataset.quality.domain_reason}</dd>
        </div>
      </dl>
      <h3 className="sub">Transformations appliquées</h3>
      {dataset.transformations.length === 0 ? (
        <p className="muted small">Aucune : les valeurs sont conservées telles que lues.</p>
      ) : (
        <ul className="transforms">
          {dataset.transformations.map((t, i) => (
            <li key={i}>
              <code>{t.action}</code>
              {t.column && <strong> {t.column}</strong>} — {t.detail}
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}
