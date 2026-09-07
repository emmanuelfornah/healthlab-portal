import { describe, it, expect, beforeEach, vi } from 'vitest'

// Provide required env before importing the module under test.
vi.stubGlobal('import.meta.env', {})

describe('isAuthenticated', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('returns false when no token is stored', async () => {
    const { isAuthenticated } = await import('../auth.js')
    expect(isAuthenticated()).toBe(false)
  })

  it('returns false for an expired token', async () => {
    const expired = { exp: Math.floor(Date.now() / 1000) - 60 }
    const token = `h.${btoa(JSON.stringify(expired))}.s`
    localStorage.setItem('healthlab_id_token', token)
    const { isAuthenticated } = await import('../auth.js')
    expect(isAuthenticated()).toBe(false)
  })

  it('returns true for a valid unexpired token', async () => {
    const valid = { exp: Math.floor(Date.now() / 1000) + 3600 }
    const token = `h.${btoa(JSON.stringify(valid))}.s`
    localStorage.setItem('healthlab_id_token', token)
    const { isAuthenticated } = await import('../auth.js')
    expect(isAuthenticated()).toBe(true)
  })
})
