import { API_BASE } from '../api/client'

/** Resolve a stored media reference (absolute URL, blob/data URI, or a relative API path) to a usable <img src>. */
export function resolveMediaUrl(url: string | null | undefined): string {
  if (!url) return ''
  if (url.startsWith('blob:') || url.startsWith('data:') || url.startsWith('http://') || url.startsWith('https://')) {
    return url
  }
  const origin = API_BASE.replace(/\/api\/v1\/?$/, '')
  return `${origin}${url.startsWith('/') ? url : `/${url}`}`
}
