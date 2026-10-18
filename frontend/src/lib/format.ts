const nf = new Intl.NumberFormat('fr-FR')

export function formatInt(n: number | null | undefined): string {
  if (n === null || n === undefined || Number.isNaN(n)) return '—'
  return nf.format(Math.round(n))
}

export function formatNumber(n: number | null | undefined, digits = 2): string {
  if (n === null || n === undefined || Number.isNaN(n)) return '—'
  const abs = Math.abs(n)
  const d = abs >= 1000 ? 0 : abs >= 100 ? 1 : digits
  return new Intl.NumberFormat('fr-FR', { maximumFractionDigits: d }).format(n)
}

/** `share` est une proportion entre 0 et 1. */
export function formatPct(share: number | null | undefined, digits = 1): string {
  if (share === null || share === undefined || Number.isNaN(share)) return '—'
  if (share > 0 && share < 0.001) return '< 0,1 %'
  return new Intl.NumberFormat('fr-FR', {
    style: 'percent',
    minimumFractionDigits: 0,
    maximumFractionDigits: digits,
  }).format(share)
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} o`
  if (bytes < 1024 ** 2) return `${formatNumber(bytes / 1024, 1)} Ko`
  return `${formatNumber(bytes / 1024 ** 2, 1)} Mo`
}

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleString('fr-FR', { dateStyle: 'medium', timeStyle: 'short' })
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleDateString('fr-FR', { dateStyle: 'medium' })
}

export function scoreTone(score: number): 'good' | 'warn' | 'bad' {
  if (score >= 90) return 'good'
  if (score >= 70) return 'warn'
  return 'bad'
}
