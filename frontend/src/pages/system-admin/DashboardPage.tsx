import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api } from '../../api/endpoints'
import { Button, Badge, ErrorBox } from '../../components/ui/primitives'

export function DashboardPage() {
  const navigate = useNavigate()
  const { data: rows, isLoading, isError, error } = useQuery({
    queryKey: ['system-admin', 'dashboard'],
    queryFn: api.systemAdmin.dashboard,
  })

  return (
    <div>
      <div style={{ marginBottom: 20 }}>
        <h2 style={{ fontSize: 18, fontWeight: 700, color: '#0f172a', margin: 0 }}>Platform Dashboard</h2>
        <p style={{ color: '#64748b', fontSize: 13, margin: '4px 0 0' }}>
          Every user's connected social pages and AI token usage, at a glance.
        </p>
      </div>

      {isLoading ? (
        <div style={{ padding: 40, textAlign: 'center', color: '#64748b' }}>Loading dashboard...</div>
      ) : isError ? (
        <ErrorBox error={error} />
      ) : (
        <>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 16, marginBottom: 24 }}>
            <div style={{ background: '#ffffff', borderRadius: 12, padding: 20, border: '1px solid #e2e8f0' }}>
              <div style={{ fontSize: 13, fontWeight: 600, color: '#64748b', marginBottom: 4 }}>Total Users</div>
              <div style={{ fontSize: 26, fontWeight: 800, color: '#0f172a' }}>{rows?.length ?? 0}</div>
            </div>
            <div style={{ background: '#ffffff', borderRadius: 12, padding: 20, border: '1px solid #e2e8f0' }}>
              <div style={{ fontSize: 13, fontWeight: 600, color: '#64748b', marginBottom: 4 }}>Total Connected Pages</div>
              <div style={{ fontSize: 26, fontWeight: 800, color: '#0f172a' }}>
                {rows?.reduce((sum, r) => sum + r.pages_count, 0) ?? 0}
              </div>
            </div>
            <div style={{ background: '#ffffff', borderRadius: 12, padding: 20, border: '1px solid #e2e8f0' }}>
              <div style={{ fontSize: 13, fontWeight: 600, color: '#64748b', marginBottom: 4 }}>Credits Used Today</div>
              <div style={{ fontSize: 26, fontWeight: 800, color: '#0284c7' }}>
                {(rows?.reduce((sum, r) => sum + r.credits_used_today, 0) ?? 0).toLocaleString()}
              </div>
            </div>
            <div style={{ background: '#ffffff', borderRadius: 12, padding: 20, border: '1px solid #e2e8f0' }}>
              <div style={{ fontSize: 13, fontWeight: 600, color: '#64748b', marginBottom: 4 }}>Credits Used This Month</div>
              <div style={{ fontSize: 26, fontWeight: 800, color: '#16a34a' }}>
                {(rows?.reduce((sum, r) => sum + r.credits_used_this_month, 0) ?? 0).toLocaleString()}
              </div>
            </div>
          </div>

          <div style={{ background: '#ffffff', borderRadius: 14, padding: 24, border: '1px solid #e2e8f0' }}>
            <h3 style={{ fontSize: 16, fontWeight: 700, color: '#0f172a', margin: '0 0 16px' }}>
              Top Users by All-Time Usage
            </h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {[...(rows ?? [])]
                .sort((a, b) => b.credits_used_total - a.credits_used_total)
                .slice(0, 8)
                .map((row, idx) => (
                  <div
                    key={row.shop_id}
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      padding: '10px 14px',
                      background: '#f8fafc',
                      borderRadius: 8,
                    }}
                  >
                    <div>
                      <span style={{ fontWeight: 700, color: '#0f172a' }}>
                        #{idx + 1} {row.shop_name}
                      </span>
                      <span style={{ marginLeft: 8 }}>
                        <Badge tone="neutral">{row.pages_count} pages</Badge>
                      </span>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                      <span style={{ fontWeight: 700, color: '#0284c7' }}>
                        {row.credits_used_total.toLocaleString()} credits
                      </span>
                      <Button
                        size="sm"
                        variant="secondary"
                        onClick={() => navigate(`/system-admin/users/${row.shop_id}`)}
                      >
                        View History
                      </Button>
                    </div>
                  </div>
                ))}
              {(rows ?? []).length === 0 && (
                <p style={{ color: '#94a3b8', fontStyle: 'italic', margin: 0 }}>No usage recorded yet.</p>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  )
}
