import { useEffect, useRef } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { getAccessToken, tryRefresh, API_BASE } from '../api/client'

function wsBase(): string {
  const http = API_BASE.replace(/\/api\/v1\/?$/, '')
  return http.replace(/^http/, 'ws')
}

/** Subscribe to shop WebSocket events and invalidate related queries. */
export function useRealtime(enabled = true) {
  const qc = useQueryClient()
  const retryRef = useRef(0)

  useEffect(() => {
    if (!enabled) return

    let closed = false
    let socket: WebSocket | null = null
    let timer: ReturnType<typeof setTimeout> | undefined

    const connect = async () => {
      if (closed) return
      let token = getAccessToken()
      if (!token) return

      socket = new WebSocket(`${wsBase()}/ws?token=${encodeURIComponent(token)}`)

      socket.onopen = () => {
        retryRef.current = 0
      }

      socket.onmessage = (ev) => {
        try {
          const msg = JSON.parse(ev.data) as { event?: string }
          const event = msg.event ?? ''
          if (event === 'message.created' || event === 'pong') {
            if (event === 'message.created') {
              void qc.invalidateQueries({ queryKey: ['conversations'] })
              void qc.invalidateQueries({ queryKey: ['inbox-stats'] })
              void qc.invalidateQueries({ queryKey: ['messages'] })
            }
            return
          }
          if (event.startsWith('call.')) {
            void qc.invalidateQueries({ queryKey: ['calls'] })
            void qc.invalidateQueries({ queryKey: ['call'] })
            if (event === 'call.transcript') {
              void qc.invalidateQueries({ queryKey: ['call'] })
            }
          }
          if (event.startsWith('payment.') || event === 'order.updated') {
            void qc.invalidateQueries({ queryKey: ['payments'] })
            void qc.invalidateQueries({ queryKey: ['orders'] })
          }
          if (event.startsWith('campaign.')) {
            void qc.invalidateQueries({ queryKey: ['campaigns'] })
          }
        } catch {
          /* ignore malformed */
        }
      }

      socket.onclose = async () => {
        if (closed) return
        try {
          await tryRefresh()
        } catch {
          /* ignore */
        }
        const delay = Math.min(30_000, 1000 * 2 ** retryRef.current)
        retryRef.current += 1
        timer = setTimeout(connect, delay)
      }

      socket.onerror = () => {
        socket?.close()
      }
    }

    connect()
    const ping = setInterval(() => {
      if (socket?.readyState === WebSocket.OPEN) socket.send('ping')
    }, 25000)

    return () => {
      closed = true
      clearInterval(ping)
      if (timer) clearTimeout(timer)
      socket?.close()
    }
  }, [enabled, qc])
}
