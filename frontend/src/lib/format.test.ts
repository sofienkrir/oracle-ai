import { describe, expect, it } from 'vitest'
import { formatBytes, formatInt, formatPct, scoreTone } from './format'

const nbsp = (s: string) => s.replace(/[  ]/g, ' ')

describe('format', () => {
  it('formate les entiers en français', () => {
    expect(nbsp(formatInt(18337))).toBe('18 337')
    expect(formatInt(null)).toBe('—')
  })
  it('formate les pourcentages à partir de proportions', () => {
    expect(nbsp(formatPct(0.2049))).toBe('20,5 %')
    expect(formatPct(0.0004)).toBe('< 0,1 %')
    expect(nbsp(formatPct(0))).toBe('0 %')
  })
  it('formate les tailles', () => {
    expect(formatBytes(512)).toBe('512 o')
    expect(formatBytes(1_420_055)).toBe('1,4 Mo')
  })
  it('classe le score', () => {
    expect(scoreTone(95.8)).toBe('good')
    expect(scoreTone(80)).toBe('warn')
    expect(scoreTone(40)).toBe('bad')
  })
})
