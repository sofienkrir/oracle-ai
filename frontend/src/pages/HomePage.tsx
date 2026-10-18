import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import { Icon } from '../components/Icon'
import { Card, ErrorBox, Loading, PageHeader, Stat } from '../components/ui'
import { DOMAIN_LABELS } from '../lib/labels'
import { formatInt } from '../lib/format'
import { useAsync } from '../lib/useAsync'
import { useWorkspace } from '../state/workspace'

const MODULES: { key: string; label: string; detail: string }[] = [
  { key: 'import_quality', label: 'Import & qualité', detail: 'CSV/XLSX, profilage, rôles, rapport' },
  { key: 'history', label: 'Historique', detail: 'Métadonnées persistantes (SQLite)' },
  { key: 'explorer_kpi', label: 'Explorer & KPI', detail: 'Distributions, KPI Retail/Maintenance' },
  { key: 'anomalies', label: 'Anomalies', detail: 'Médiane/MAD, IQR, Isolation Forest' },
  { key: 'forecasting', label: 'Prévision', detail: 'Split chronologique, baselines, MAE/RMSE' },
  { key: 'root_cause', label: 'Hypothèses de causes', detail: 'Facteurs associés, DoWhy si identifiable' },
  { key: 'scenario_lab', label: 'Scenario Lab', detail: 'Formules visibles, coûts, contraintes' },
  { key: 'decision_report', label: 'Decision Report', detail: 'Recommandations traçables, export' },
]

const EVIDENCE = [
  { tone: 'fact', label: 'Fait observé', text: 'Calculé directement sur les données importées.' },
  { tone: 'assoc', label: 'Association', text: 'Lien statistique, sans implication causale.' },
  { tone: 'pred', label: 'Prédiction', text: 'Sortie de modèle, avec métrique et incertitude.' },
  { tone: 'hyp', label: 'Hypothèse causale', text: 'À vérifier ; jamais présentée comme un fait.' },
]

export function HomePage() {
  const { health, healthError, datasets, select, refresh } = useWorkspace()
  const samples = useAsync(() => api.samples(), [])
  const navigate = useNavigate()
  const [loadingId, setLoadingId] = useState<string>()
  const [loadError, setLoadError] = useState<Error>()

  const loadedCount = datasets.filter((d) => d.loaded).length

  async function loadSample(id: string) {
    setLoadingId(id)
    setLoadError(undefined)
    try {
      const ds = await api.loadSample(id)
      select(ds.id)
      await refresh()
      navigate(`/datasets/${ds.id}`)
    } catch (e) {
      setLoadError(e as Error)
    } finally {
      setLoadingId(undefined)
    }
  }

  return (
    <>
      <PageHeader
        title="Vue d'ensemble"
        subtitle="Transformez des données tabulaires en analyses explicables : chaque résultat expose sa méthode, ses hypothèses et ses limites."
        actions={
          <Link to="/import" className="btn btn-primary">
            <Icon name="upload" size={16} /> Importer un fichier
          </Link>
        }
      />

      <div className="stats">
        <Stat
          icon="database"
          label="API & base locale"
          value={healthError ? 'Hors ligne' : health?.database ? 'Opérationnelles' : '…'}
          hint={healthError ?? (health ? `Moteur v${health.engine_version}` : undefined)}
          tone={healthError ? 'bad' : health?.database ? 'good' : undefined}
        />
        <Stat
          icon="file"
          label="Datasets en mémoire"
          value={`${loadedCount} / ${health?.limits.workspace_max_datasets ?? '—'}`}
          hint={`Expiration après ${health?.limits.workspace_ttl_minutes ?? '—'} min d'inactivité`}
        />
        <Stat
          icon="upload"
          label="Limites d'import"
          value={`${health?.limits.max_upload_mb ?? '—'} Mo`}
          hint={`${formatInt(health?.limits.max_rows)} lignes · ${health?.limits.max_columns ?? '—'} colonnes`}
        />
        <Stat
          icon="spark"
          label="Explications IA"
          value={health?.llm_enabled ? 'LLM activé' : 'Déterministe'}
          hint="Le LLM est optionnel et n'invente aucun chiffre"
          tone="accent"
        />
      </div>

      <Card title="Démarrer avec un dataset de démonstration" icon="database">
        <p className="muted small">
          Ces fichiers sont <strong>100 % synthétiques</strong>, générés par{' '}
          <code>scripts/generate_samples.py</code>. Ils reprennent seulement les noms de colonnes
          des jeux UCI Online Retail et AI4I 2020 et ne représentent aucune entreprise réelle.
        </p>
        {samples.loading && <Loading />}
        {samples.error && <ErrorBox error={samples.error} onRetry={samples.reload} />}
        {loadError && <ErrorBox error={loadError} />}
        <div className="sample-grid">
          {samples.data?.map((s) => (
            <article key={s.id} className="sample">
              <div className="sample-tags">
                <span className={`badge dom-${s.domain}`}>{DOMAIN_LABELS[s.domain]}</span>
                {s.synthetic && <span className="badge">Synthétique</span>}
                <span className="badge">{s.file.split('.').pop()?.toUpperCase()}</span>
              </div>
              <h3>{s.title}</h3>
              <p>{s.description}</p>
              <div className="sample-foot">
                <span className="muted small">{formatInt(s.rows)} lignes</span>
                <button
                  className="btn btn-secondary"
                  disabled={loadingId !== undefined}
                  onClick={() => loadSample(s.id)}
                >
                  {loadingId === s.id ? 'Chargement…' : 'Analyser'}
                  <Icon name="arrow" size={15} />
                </button>
              </div>
            </article>
          ))}
        </div>
      </Card>

      <div className="grid-2">
        <Card title="État des modules" icon="spark">
          <ul className="module-list">
            {MODULES.map((m) => {
              const status = health?.modules[m.key]
              const available = status === 'available'
              return (
                <li key={m.key}>
                  <span className={`dot ${available ? 'good' : 'idle'}`} />
                  <div>
                    <strong>{m.label}</strong>
                    <span className="muted small">{m.detail}</span>
                  </div>
                  <span className={`badge ${available ? 'sev-ok' : ''}`}>
                    {available ? 'Disponible' : status ? `Étape ${status.split(':')[1]}` : '…'}
                  </span>
                </li>
              )
            })}
          </ul>
        </Card>
        <Card title="Niveaux de preuve affichés" icon="info">
          <p className="muted small">
            Les rapports d'ORACLE AI séparent toujours ces quatre natures de résultat.
          </p>
          <ul className="evidence-list">
            {EVIDENCE.map((e) => (
              <li key={e.tone}>
                <span className={`evidence ev-${e.tone}`}>{e.label}</span>
                <span>{e.text}</span>
              </li>
            ))}
          </ul>
        </Card>
      </div>
    </>
  )
}
