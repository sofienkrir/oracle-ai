// Miroir des schémas Pydantic du backend (backend/app/api/schemas.py, app/data/schemas.py).

export type Severity = 'info' | 'warning' | 'error'
export type SemanticType = 'numeric' | 'boolean' | 'datetime' | 'categorical' | 'text' | 'empty'
export type ColumnRole =
  | 'identifier'
  | 'datetime'
  | 'numeric'
  | 'categorical'
  | 'target'
  | 'measure'
  | 'text'
  | 'ignore'
export type Domain = 'retail' | 'maintenance' | 'generic'

export interface Health {
  status: 'ok' | 'degraded'
  app: string
  engine_version: string
  environment: string
  database: boolean
  llm_enabled: boolean
  limits: Record<string, number>
  modules: Record<string, string>
}

export interface Sample {
  id: string
  file: string
  title: string
  domain: Domain
  description: string
  synthetic: boolean
  provenance: string
  rows: number | null
}

export interface NumericStats {
  min: number | null
  max: number | null
  mean: number | null
  std: number | null
  median: number | null
  q1: number | null
  q3: number | null
  n_zero: number
  n_negative: number
}

export interface DatetimeStats {
  min: string | null
  max: string | null
  parse_share: number
  native: boolean
  format: string | null
  ambiguous: boolean
}

export interface ColumnProfile {
  name: string
  dtype: string
  semantic_type: SemanticType
  n_missing: number
  pct_missing: number
  n_unique: number
  unique_ratio: number
  numeric_parse_share: number | null
  numeric: NumericStats | null
  datetime: DatetimeStats | null
  top_values: { value: string; count: number }[]
  suggested_role: ColumnRole
  role_reason: string
  issues: string[]
}

export interface QualityIssue {
  code: string
  severity: Severity
  column: string | null
  count: number | null
  message: string
}

export interface QualityReport {
  n_rows: number
  n_columns: number
  n_cells_missing: number
  pct_cells_missing: number
  n_duplicate_rows: number
  pct_duplicate_rows: number
  domain: Domain
  domain_reason: string
  columns: ColumnProfile[]
  issues: QualityIssue[]
  score: number
  score_breakdown: Record<string, number>
  parameters: Record<string, number>
}

export interface Dataset {
  id: string
  name: string
  source_kind: 'upload' | 'sample'
  file_format: 'csv' | 'xlsx'
  sha256: string
  size_bytes: number
  n_rows: number
  n_columns: number
  domain: Domain
  roles: Record<string, ColumnRole>
  created_at: string
  released_at: string | null
  loaded: boolean
}

export interface Transformation {
  column: string | null
  action: string
  detail: string
}

export interface DatasetDetail extends Dataset {
  parse_info: Record<string, unknown>
  transformations: Transformation[]
  quality: QualityReport
}

export interface Preview {
  columns: string[]
  rows: (string | number | boolean | null)[][]
  offset: number
  limit: number
  total: number
}

export interface Analysis {
  id: number
  dataset_id: string
  dataset_name: string
  kind: string
  params: Record<string, unknown>
  summary: Record<string, unknown>
  engine_version: string
  created_at: string
}
