import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import { clearTokens, getAccessToken, loginRequest, setTokens } from '../api/client'
import type { JwtClaims, Role } from '../types/api'

function decodeJwt(token: string): JwtClaims | null {
  try {
    const payload = token.split('.')[1]
    const json = atob(payload.replace(/-/g, '+').replace(/_/g, '/'))
    return JSON.parse(json) as JwtClaims
  } catch {
    return null
  }
}

interface AuthState {
  token: string | null
  claims: JwtClaims | null
  login: (email: string, password: string) => Promise<void>
  logout: () => void
  role: Role | null
  shopId: string | null
  isAuthenticated: boolean
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(() => getAccessToken())

  const claims = useMemo(() => (token ? decodeJwt(token) : null), [token])

  const login = useCallback(async (email: string, password: string) => {
    const res = await loginRequest(email, password)
    setTokens(res.access_token, res.refresh_token)
    setToken(res.access_token)
  }, [])

  const logout = useCallback(() => {
    clearTokens()
    setToken(null)
  }, [])

  const value: AuthState = {
    token,
    claims,
    login,
    logout,
    role: claims?.role ?? null,
    shopId: claims?.shop_id ?? null,
    isAuthenticated: Boolean(token && claims),
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
