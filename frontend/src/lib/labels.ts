import type { ColumnRole, Domain, SemanticType, Severity } from '../api/types'

export const ROLE_LABELS: Record<ColumnRole, string> = {
  identifier: 'Identifiant',
  datetime: 'Date / temps',
  numeric: 'Numérique',
  categorical: 'Catégorie',
  target: 'Cible / label',
  measure: 'Mesure métier',
  text: 'Texte libre',
  ignore: 'Ignorer',
}

export const ROLE_ORDER: ColumnRole[] = [
  'identifier',
  'datetime',
  'numeric',
  'measure',
  'categorical',
  'target',
  'text',
  'ignore',
]

export const TYPE_LABELS: Record<SemanticType, string> = {
  numeric: 'Numérique',
  boolean: 'Booléen',
  datetime: 'Date',
  categorical: 'Catégoriel',
  text: 'Texte',
  empty: 'Vide',
}

export const DOMAIN_LABELS: Record<Domain, string> = {
  retail: 'Retail',
  maintenance: 'Maintenance',
  generic: 'Générique',
}

export const SEVERITY_LABELS: Record<Severity, string> = {
  error: 'Erreur',
  warning: 'Attention',
  info: 'Info',
}

export const ANALYSIS_LABELS: Record<string, string> = {
  quality_profile: 'Profil qualité',
  roles_update: 'Rôles modifiés',
}

export const SCORE_LABELS: Record<string, string> = {
  completeness: 'Complétude',
  uniqueness: 'Unicité',
  consistency: 'Cohérence',
  usefulness: 'Utilité',
}
