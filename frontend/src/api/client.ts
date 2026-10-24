const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8001/api/v1'

const ACCESS_KEY = 'shop_access_token'
const REFRESH_KEY = 'shop_refresh_token'

export function getAccessToken(): string | null {
  return localStorage.getItem(ACCESS_KEY)
}

export function getRefreshToken(): string | null {
  return localStorage.getItem(REFRESH_KEY)
}

export function setTokens(access: string, refresh: string) {
  localStorage.setItem(ACCESS_KEY, access)
  localStorage.setItem(REFRESH_KEY, refresh)
}

export function clearTokens() {
  localStorage.removeItem(ACCESS_KEY)
  localStorage.removeItem(REFRESH_KEY)
}

export class ApiError extends Error {
  status: number
  detail: unknown

  constructor(status: number, detail: unknown) {
    super(typeof detail === 'string' ? detail : `Request failed (${status})`)
    this.status = status
    this.detail = detail
  }
}

let refreshInFlight: Promise<boolean> | null = null

export async function tryRefresh(): Promise<boolean> {
  const refresh = getRefreshToken()
  if (!refresh) return false
  try {
    const res = await fetch(`${API_BASE}/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refresh }),
    })
    if (!res.ok) {
      clearTokens()
      return false
    }
    const data = (await res.json()) as { access_token: string; refresh_token: string }
    setTokens(data.access_token, data.refresh_token)
    return true
  } catch {
    clearTokens()
    return false
  }
}

export async function apiFetch<T>(
  path: string,
  options: RequestInit & { auth?: boolean; form?: boolean } = {},
): Promise<T> {
  const { auth = true, form = false, headers, ...rest } = options
  const finalHeaders = new Headers(headers)

  if (!form && rest.body && !finalHeaders.has('Content-Type')) {
    finalHeaders.set('Content-Type', 'application/json')
  }

  if (auth) {
    const token = getAccessToken()
    if (token) finalHeaders.set('Authorization', `Bearer ${token}`)
  }

  let res = await fetch(`${API_BASE}${path}`, { ...rest, headers: finalHeaders })

  if (res.status === 401 && auth) {
    if (!refreshInFlight) refreshInFlight = tryRefresh().finally(() => { refreshInFlight = null })
    const ok = await refreshInFlight
    if (ok) {
      const retryHeaders = new Headers(headers)
      if (!form && rest.body && !retryHeaders.has('Content-Type')) {
        retryHeaders.set('Content-Type', 'application/json')
      }
      const token = getAccessToken()
      if (token) retryHeaders.set('Authorization', `Bearer ${token}`)
      res = await fetch(`${API_BASE}${path}`, { ...rest, headers: retryHeaders })
    }
  }

  if (!res.ok) {
    let detail: unknown = res.statusText
    try {
      const body = await res.json()
      detail = body.detail ?? body
    } catch {
      /* ignore */
    }
    throw new ApiError(res.status, detail)
  }

  if (res.status === 204) return undefined as T

  const contentType = res.headers.get('content-type') ?? ''
  if (contentType.includes('application/json')) {
    return (await res.json()) as T
  }
  return (await res.blob()) as T
}

export async function loginRequest(email: string, password: string) {
  const body = new URLSearchParams()
  body.set('username', email)
  body.set('password', password)
  return apiFetch<{ access_token: string; refresh_token: string; token_type: string }>(
    '/auth/login',
    { method: 'POST', body, auth: false, form: true },
  )
}

export { API_BASE }
