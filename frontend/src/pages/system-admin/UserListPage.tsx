import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api } from '../../api/endpoints'
import { Button, Badge, ErrorBox } from '../../components/ui/primitives'

export function UserListPage() {
  const navigate = useNavigate()
  const { data: rows, isLoading, isError, error } = useQuery({
    queryKey: ['system-admin', 'dashboard'],
    queryFn: api.systemAdmin.dashboard,
  })

  return (
    <div>
      <div style={{ marginBottom: 20 }}>
        <h2 style={{ fontSize: 18, fontWeight: 700, color: '#0f172a', margin: 0 }}>User List</h2>
        <p style={{ color: '#64748b', fontSize: 13, margin: '4px 0 0' }}>
          Every user, their connected social pages, and AI token usage. Click a user for their full history.
        </p>
      </div>

      {isLoading ? (
        <div style={{ padding: 40, textAlign: 'center', color: '#64748b' }}>Loading users...</div>
      ) : isError ? (
        <ErrorBox error={error} />
      ) : (
        <div style={{ background: '#ffffff', borderRadius: 14, border: '1px solid #e2e8f0', overflow: 'hidden' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: 14 }}>
            <thead>
              <tr style={{ background: '#f8fafc', borderBottom: '1px solid #e2e8f0', color: '#475569' }}>
                <th style={{ padding: '14px 20px', fontWeight: 600 }}>User / Shop</th>
                <th style={{ padding: '14px 20px', fontWeight: 600 }}>Plan</th>
                <th style={{ padding: '14px 20px', fontWeight: 600 }}>Pages</th>
                <th style={{ padding: '14px 20px', fontWeight: 600 }}>Platforms</th>
                <th style={{ padding: '14px 20px', fontWeight: 600 }}>Used Today</th>
                <th style={{ padding: '14px 20px', fontWeight: 600 }}>Used This Month</th>
                <th style={{ padding: '14px 20px', fontWeight: 600 }}>Used All-Time</th>
                <th style={{ padding: '14px 20px', fontWeight: 600, textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {rows?.map((row) => (
                <tr key={row.shop_id} style={{ borderBottom: '1px solid #f1f5f9' }}>
                  <td style={{ padding: '16px 20px', fontWeight: 700, color: '#0f172a' }}>{row.shop_name}</td>
                  <td style={{ padding: '16px 20px' }}>
                    <Badge tone={row.plan_tier === 'enterprise' || row.plan_tier === 'business' ? 'info' : row.plan_tier === 'pro' ? 'good' : 'neutral'}>
                      {row.plan_tier.toUpperCase()}
                    </Badge>
                  </td>
                  <td style={{ padding: '16px 20px', fontWeight: 600 }}>{row.pages_count}</td>
                  <td style={{ padding: '16px 20px' }}>
                    {row.platforms.length === 0 ? (
                      <span style={{ color: '#94a3b8', fontSize: 12.5 }}>No pages</span>
                    ) : (
                      <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                        {row.platforms.map((p) => (
                          <Badge key={p} tone="neutral">{p}</Badge>
                        ))}
                      </div>
                    )}
                  </td>
                  <td style={{ padding: '16px 20px', fontWeight: 600 }}>{row.credits_used_today.toLocaleString()}</td>
                  <td style={{ padding: '16px 20px', fontWeight: 600 }}>{row.credits_used_this_month.toLocaleString()}</td>
                  <td style={{ padding: '16px 20px', fontWeight: 700, color: '#0284c7' }}>{row.credits_used_total.toLocaleString()}</td>
                  <td style={{ padding: '16px 20px', textAlign: 'right' }}>
                    <Button size="sm" variant="secondary" onClick={() => navigate(`/system-admin/users/${row.shop_id}`)}>
                      View History
                    </Button>
                  </td>
                </tr>
              ))}
              {(rows ?? []).length === 0 && (
                <tr>
                  <td colSpan={8} style={{ padding: 30, textAlign: 'center', color: '#94a3b8', fontStyle: 'italic' }}>
                    No users yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
