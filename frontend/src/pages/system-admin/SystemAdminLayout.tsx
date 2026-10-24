import { Outlet } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { Shield, RefreshCw } from 'lucide-react'
import { Button } from '../../components/ui/primitives'

export function SystemAdminLayout() {
  const queryClient = useQueryClient()

  return (
    <div className="page-container" style={{ padding: '24px 32px', maxWidth: '1400px', margin: '0 auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 28 }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
            <span
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 6,
                padding: '4px 10px',
                background: '#e0f2fe',
                color: '#0369a1',
                borderRadius: 20,
                fontSize: 12,
                fontWeight: 700,
                textTransform: 'uppercase',
                letterSpacing: '0.05em',
              }}
            >
              <Shield size={14} /> Product Owner Command Center
            </span>
          </div>
          <h1 style={{ fontSize: 28, fontWeight: 800, color: '#0f172a', margin: 0 }}>System Administration</h1>
          <p style={{ color: '#64748b', fontSize: 14, margin: '6px 0 0' }}>
            Dashboard, users, subscription plans, internal page access, and platform cost economics.
          </p>
        </div>

        <Button
          variant="secondary"
          onClick={() => queryClient.invalidateQueries({ queryKey: ['system-admin'] })}
          style={{ display: 'flex', alignItems: 'center', gap: 6 }}
        >
          <RefreshCw size={14} /> Refresh Data
        </Button>
      </div>

      <Outlet />
    </div>
  )
}
