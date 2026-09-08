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

describe('signIn (PKCE)', () => {
  beforeEach(() => {
    sessionStorage.clear()
    delete window.location
    window.location = { href: '' }
  })

  it('stores a code_verifier and sends a matching S256 code_challenge', async () => {
    const { signIn } = await import('../auth.js')
    await signIn()

    const verifier = sessionStorage.getItem('healthlab_pkce_verifier')
    expect(verifier).toBeTruthy()

    const [, query] = window.location.href.split('?')
    const params = new URLSearchParams(query)
    expect(params.get('code_challenge_method')).toBe('S256')

    const expectedDigest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(verifier))
    const expectedChallenge = btoa(String.fromCharCode(...new Uint8Array(expectedDigest)))
      .replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
    expect(params.get('code_challenge')).toBe(expectedChallenge)
  })
})
