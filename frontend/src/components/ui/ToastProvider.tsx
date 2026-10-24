import { createContext, useCallback, useContext, useRef, useState, type ReactNode } from 'react'

type ToastKind = 'success' | 'error' | 'info'

interface ToastItem {
  id: number
  message: string
  kind: ToastKind
}

interface ToastContextValue {
  showToast: (message: string, kind?: ToastKind) => void
}

const ToastContext = createContext<ToastContextValue | null>(null)

const KIND_STYLES: Record<ToastKind, { background: string; border: string }> = {
  success: { background: '#166534', border: '#22c55e' },
  error: { background: '#991b1b', border: '#ef4444' },
  info: { background: '#1e3a8a', border: '#3b82f6' },
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([])
  const idRef = useRef(0)

  const showToast = useCallback((message: string, kind: ToastKind = 'success') => {
    const id = ++idRef.current
    setToasts((prev) => [...prev, { id, message, kind }])
    window.setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id))
    }, 3500)
  }, [])

  return (
    <ToastContext.Provider value={{ showToast }}>
      {children}
      <div
        style={{
          position: 'fixed',
          bottom: 20,
          right: 20,
          display: 'flex',
          flexDirection: 'column',
          gap: 10,
          zIndex: 9999,
          pointerEvents: 'none',
        }}
      >
        {toasts.map((t) => (
          <div
            key={t.id}
            style={{
              pointerEvents: 'auto',
              minWidth: 240,
              maxWidth: 360,
              padding: '12px 16px',
              borderRadius: 10,
              color: 'white',
              fontSize: 14,
              fontWeight: 500,
              boxShadow: '0 10px 25px rgba(0,0,0,0.2)',
              background: KIND_STYLES[t.kind].background,
              borderLeft: `4px solid ${KIND_STYLES[t.kind].border}`,
              animation: 'toast-slide-in 0.2s ease-out',
            }}
          >
            {t.message}
          </div>
        ))}
      </div>
      <style>
        {`@keyframes toast-slide-in {
          from { opacity: 0; transform: translateY(8px); }
          to { opacity: 1; transform: translateY(0); }
        }`}
      </style>
    </ToastContext.Provider>
  )
}

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext)
  if (!ctx) {
    throw new Error('useToast must be used within a ToastProvider')
  }
  return ctx
}
