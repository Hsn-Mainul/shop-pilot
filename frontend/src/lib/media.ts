import { API_BASE, getAccessToken } from '../api/client'

const FB_CDN_PATTERNS = ['fbcdn.net', 'scontent', 'fbsbx.com']

function isFacebookCdnUrl(url: string): boolean {
  return FB_CDN_PATTERNS.some((p) => url.includes(p))
}

/** Our own uploaded media, served from wherever PUBLIC_BASE_URL points (often an
 * ngrok tunnel so Facebook/Meta can fetch it) — that host's free-tier interstitial
 * page blocks direct browser loads the same way Facebook's CDN does, so this needs
 * the same backend-proxy treatment, not just Facebook URLs. */
function isOwnUploadUrl(url: string): boolean {
  return url.includes('/api/v1/media/files/')
}

/** Resolve a stored media reference (absolute URL, blob/data URI, or a relative API path) to a usable <img src>. */
export function resolveMediaUrl(url: string | null | undefined): string {
  if (!url) return ''
  if (url.startsWith('blob:') || url.startsWith('data:')) return url

  // Facebook CDN URLs, and our own tunnel-hosted uploads, can't be loaded directly
  // by the browser (CORS/Referer policy, or the tunnel host's own warning page).
  // Route them through our backend proxy so they load like normal images.
  if (url.startsWith('https://') || url.startsWith('http://')) {
    if (isFacebookCdnUrl(url) || isOwnUploadUrl(url)) {
      const origin = API_BASE.replace(/\/api\/v1\/?$/, '')
      const token = getAccessToken()
      const tokenParam = token ? `&token=${encodeURIComponent(token)}` : ''
      return `${origin}/api/v1/media/proxy?url=${encodeURIComponent(url)}${tokenParam}`
    }
    return url
  }

  const origin = API_BASE.replace(/\/api\/v1\/?$/, '')
  return `${origin}${url.startsWith('/') ? url : `/${url}`}`
}
