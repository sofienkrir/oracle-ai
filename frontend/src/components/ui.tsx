import type { ReactNode } from 'react'
import type { Severity } from '../api/types'
import { SEVERITY_LABELS } from '../lib/labels'
import { Icon } from './Icon'
import type { IconName } from './Icon'

export function Card({
  title,
  icon,
  actions,
  children,
  className = '',
}: {
  title?: ReactNode
  icon?: IconName
  actions?: ReactNode
  children: ReactNode
  className?: string
}) {
  return (
    <section className={`card ${className}`}>
      {(title || actions) && (
        <header className="card-head">
          <h2>
            {icon && <Icon name={icon} size={16} />}
            {title}
          </h2>
          {actions && <div className="card-actions">{actions}</div>}
        </header>
      )}
      {children}
    </section>
  )
}

export function Stat({
  label,
  value,
  hint,
  icon,
  tone,
}: {
  label: string
  value: ReactNode
  hint?: ReactNode
  icon: IconName
  tone?: 'good' | 'warn' | 'bad' | 'accent'
}) {
  return (
    <div className={`stat ${tone ? `tone-${tone}` : ''}`}>
      <div className="stat-label">
        <span className="stat-icon">
          <Icon name={icon} size={15} />
        </span>
        {label}
      </div>
      <div className="stat-value">{value}</div>
      {hint && <div className="stat-hint">{hint}</div>}
    </div>
  )
}

export function SeverityBadge({ severity }: { severity: Severity }) {
  return <span className={`badge sev-${severity}`}>{SEVERITY_LABELS[severity]}</span>
}

export function Bar({ value, tone = 'accent' }: { value: number; tone?: string }) {
  const pct = Math.max(0, Math.min(1, value)) * 100
  return (
    <span className="bar" aria-hidden="true">
      <span className={`bar-fill tone-${tone}`} style={{ width: `${pct}%` }} />
    </span>
  )
}

export function ErrorBox({ error, onRetry }: { error: Error; onRetry?: () => void }) {
  return (
    <div className="alert alert-error" role="alert">
      <Icon name="anomaly" />
      <div>
        <strong>Une erreur est survenue</strong>
        <p>{error.message}</p>
      </div>
      {onRetry && (
        <button className="btn btn-ghost" onClick={onRetry}>
          Réessayer
        </button>
      )}
    </div>
  )
}

export function Loading({ label = 'Chargement…' }: { label?: string }) {
  return (
    <div className="loading" role="status">
      <span className="spinner" aria-hidden="true" />
      {label}
    </div>
  )
}

export function PageHeader({
  title,
  subtitle,
  actions,
}: {
  title: ReactNode
  subtitle?: ReactNode
  actions?: ReactNode
}) {
  return (
    <div className="page-header">
      <div>
        <h1>{title}</h1>
        {subtitle && <p className="subtitle">{subtitle}</p>}
      </div>
      {actions && <div className="page-actions">{actions}</div>}
    </div>
  )
}
