import { useState } from 'react'
import type { FormEvent } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { Button, ErrorBox, Input } from '../components/ui/primitives'

export function LoginPage() {
  const { login, isAuthenticated } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [email, setEmail] = useState('owner@demo-shop.test')
  const [password, setPassword] = useState('ChangeMe123!')
  const [error, setError] = useState<unknown>(null)
  const [busy, setBusy] = useState(false)

  if (isAuthenticated) {
    const to = (location.state as { from?: string } | null)?.from ?? '/'
    return <Navigate to={to} replace />
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await login(email, password)
      navigate('/', { replace: true })
    } catch (err) {
      setError(err)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="login-page">
      <div className="login-card">
        <div className="brand-mark">
          <div className="logo">S</div>
          <div>
            <strong>ShopPilot</strong>
            <div className="muted">Merchant operations console</div>
          </div>
        </div>
        <form onSubmit={onSubmit}>
          <label className="field-label">
            Email
            <Input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoComplete="username"
            />
          </label>
          <label className="field-label">
            Password
            <Input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              autoComplete="current-password"
            />
          </label>
          {error ? <ErrorBox error={error} /> : null}
          <Button type="submit" disabled={busy} style={{ width: '100%' }}>
            {busy ? 'Signing in…' : 'Sign in'}
          </Button>
        </form>
        <div className="demo-hint">
          Demo: <code>owner@demo-shop.test</code> / <code>ChangeMe123!</code>
        </div>
      </div>
    </div>
  )
}
