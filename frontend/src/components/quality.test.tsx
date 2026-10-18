import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { QualityIssue } from '../api/types'
import { IssuesPanel } from './quality'

const issues: QualityIssue[] = [
  { code: 'duplicate_rows', severity: 'warning', column: null, count: 3, message: '3 doublons' },
  { code: 'missing_values', severity: 'info', column: 'a', count: 1, message: '1 manquant' },
]

describe('IssuesPanel', () => {
  it('filtre par gravité', () => {
    render(<IssuesPanel issues={issues} />)
    expect(screen.getByText('3 doublons')).toBeInTheDocument()
    expect(screen.getByText('1 manquant')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /Infos/ }))
    expect(screen.queryByText('3 doublons')).not.toBeInTheDocument()
    expect(screen.getByText('1 manquant')).toBeInTheDocument()
  })
})
