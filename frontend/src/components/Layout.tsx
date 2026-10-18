import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useWorkspace } from '../state/workspace'
import { DOMAIN_LABELS } from '../lib/labels'
import { Icon } from './Icon'
import type { IconName } from './Icon'

interface NavItem {
  to: string
  label: string
  icon: IconName
  module?: string
}

const SECTIONS: { title: string; items: NavItem[] }[] = [
  {
    title: 'Données',
    items: [
      { to: '/', label: 'Accueil', icon: 'home' },
      { to: '/import', label: 'Import & Qualité', icon: 'upload', module: 'import_quality' },
      { to: '/explorer', label: 'Explorer', icon: 'explore', module: 'explorer_kpi' },
    ],
  },
  {
    title: 'IA & analyses',
    items: [
      { to: '/anomalies', label: 'Anomalies', icon: 'anomaly', module: 'anomalies' },
      { to: '/forecasting', label: 'Prévision', icon: 'forecast', module: 'forecasting' },
      { to: '/root-cause', label: 'Hypothèses de causes', icon: 'cause', module: 'root_cause' },
    ],
  },
  {
    title: 'Décision',
    items: [
      { to: '/scenarios', label: 'Scenario Lab', icon: 'scenario', module: 'scenario_lab' },
      { to: '/report', label: 'Decision Report', icon: 'report', module: 'decision_report' },
      { to: '/history', label: 'Historique', icon: 'history', module: 'history' },
    ],
  },
]

function stepTag(status: string | undefined): string | null {
  if (!status || status === 'available') return null
  const step = status.split(':')[1]
  return step ? `Étape ${step}` : 'Bientôt'
}

export function Layout() {
  const { health, healthError, datasets, currentId, select } = useWorkspace()
  const navigate = useNavigate()
  const loaded = datasets.filter((d) => d.loaded)

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true">
            <span />
          </span>
          <span className="brand-name">
            ORACLE <b>AI</b>
          </span>
        </div>
        <nav aria-label="Navigation principale">
          {SECTIONS.map((section) => (
            <div key={section.title} className="nav-section">
              <div className="nav-title">{section.title}</div>
              {section.items.map((item) => {
                const tag = item.module ? stepTag(health?.modules[item.module]) : null
                return (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    end={item.to === '/'}
                    className={({ isActive }) =>
                      `nav-link${isActive ? ' active' : ''}${tag ? ' planned' : ''}`
                    }
                  >
                    <Icon name={item.icon} />
                    <span>{item.label}</span>
                    {tag && <span className="nav-tag">{tag}</span>}
                  </NavLink>
                )
              })}
            </div>
          ))}
        </nav>
        <div className="sidebar-foot">
          <div className="status-line">
            <span className={`dot ${healthError ? 'bad' : health?.status === 'ok' ? 'good' : 'warn'}`} />
            {healthError ? 'API injoignable' : health ? `API v${health.engine_version}` : 'Connexion…'}
          </div>
          <div className="status-line muted">
            <Icon name="lock" size={14} /> Traitement 100 % local
          </div>
        </div>
      </aside>

      <div className="main">
        <header className="topbar">
          <label className="dataset-picker">
            <Icon name="database" size={16} />
            <select
              aria-label="Dataset actif"
              value={currentId && loaded.some((d) => d.id === currentId) ? currentId : ''}
              onChange={(e) => {
                const id = e.target.value || undefined
                select(id)
                if (id) navigate(`/datasets/${id}`)
              }}
            >
              <option value="">Aucun dataset actif</option>
              {loaded.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name} · {DOMAIN_LABELS[d.domain]}
                </option>
              ))}
            </select>
          </label>
          <div className="topbar-right">
            <span className={`chip ${health?.llm_enabled ? 'chip-accent' : ''}`}>
              <Icon name="spark" size={14} />
              {health?.llm_enabled ? 'Explications LLM activées' : 'Mode déterministe (sans LLM)'}
            </span>
          </div>
        </header>
        <main className="content">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
