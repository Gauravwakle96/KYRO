import { afterEach, describe, expect, it } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import '@testing-library/jest-dom/vitest'
import { MemoryRouter } from 'react-router-dom'
import { Badge, Empty, ErrorState } from './ui'

afterEach(cleanup)
describe('evidence states', () => {
  it('renders partial results explicitly', () => { render(<Badge value="PARTIALLY_VERIFIED" />); expect(screen.getByText('PARTIALLY VERIFIED')).toBeInTheDocument() })
  it('announces actual errors and supports retry', () => { let count = 0; render(<ErrorState error={new Error('Scanner timed out')} retry={() => count++} />); screen.getByRole('button').click(); expect(count).toBe(1); expect(screen.getByRole('alert')).toHaveTextContent('Scanner timed out') })
  it('gives an actionable empty state', () => { render(<MemoryRouter><Empty title="No findings" detail="Run a scan" href="/security" action="Open security" /></MemoryRouter>); expect(screen.getByRole('link')).toHaveAttribute('href', '/security') })
})
