import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ArrowLeft } from 'lucide-react'
import { api } from '../../api/endpoints'
import { Badge, ErrorBox } from '../../components/ui/primitives'
import { UsageBarList, GranularityToggle, type Granularity } from './UsageBarList'

export function UserHistoryPage() {
  const { shopId } = useParams<{ shopId: string }>()
  const navigate = useNavigate()
  const [granularity, setGranularity] = useState<Granularity>('daily')

  const { data: history, isLoading, isError, error } = useQuery({
    queryKey: ['system-admin', 'user-usage', shopId],
    queryFn: () => api.systemAdmin.userUsageHistory(shopId as string),
    enabled: Boolean(shopId),
  })

  return (
    <div>
      <button
        onClick={() => navigate('/system-admin/users')}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 6,
          background: 'none',
          border: 'none',
          color: '#0284c7',
          fontWeight: 600,
          fontSize: 14,
          cursor: 'pointer',
          marginBottom: 16,
          padding: 0,
        }}
      >
        <ArrowLeft size={16} /> Back to User List
      </button>

      {isError ? (
        <ErrorBox error={error} />
      ) : isLoading || !history ? (
        <div style={{ padding: 40, textAlign: 'center', color: '#64748b' }}>Loading user history...</div>
      ) : (
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 20, flexWrap: 'wrap', gap: 12 }}>
            <div>
              <h2 style={{ fontSize: 20, fontWeight: 800, color: '#0f172a', margin: 0 }}>{history.shop_name}</h2>
              <p style={{ color: '#64748b', fontSize: 13, margin: '4px 0 0' }}>
                Plan: <Badge tone="neutral">{history.plan_tier.toUpperCase()}</Badge> &bull; Credit balance:{' '}
                <strong style={{ color: history.credits_balance <= 0 ? '#dc2626' : '#16a34a' }}>
                  {history.credits_balance.toLocaleString()}
                </strong>
              </p>
            </div>
            <GranularityToggle value={granularity} onChange={setGranularity} />
          </div>

          <div style={{ background: '#ffffff', borderRadius: 14, padding: 24, border: '1px solid #e2e8f0', marginBottom: 20 }}>
            <h3 style={{ fontSize: 15, fontWeight: 700, color: '#0f172a', margin: '0 0 14px' }}>
              Overall Usage ({granularity})
            </h3>
            <UsageBarList points={history[granularity]} />
          </div>

          <h3 style={{ fontSize: 16, fontWeight: 700, color: '#0f172a', margin: '0 0 14px' }}>
            Usage by Page ({history.pages.length})
          </h3>
          {history.pages.length === 0 ? (
            <p style={{ color: '#94a3b8', fontStyle: 'italic' }}>No page-level usage recorded yet.</p>
          ) : (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))', gap: 16 }}>
              {history.pages.map((page) => (
                <div key={page.page_id} style={{ background: '#ffffff', borderRadius: 14, padding: 20, border: '1px solid #e2e8f0' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                    <h4 style={{ fontSize: 15, fontWeight: 700, color: '#0f172a', margin: 0 }}>{page.page_name}</h4>
                    <Badge tone="info">{page.platform.toUpperCase()}</Badge>
                  </div>
                  <p style={{ fontSize: 12.5, color: '#64748b', margin: '0 0 12px' }}>
                    {page.credits_used_total.toLocaleString()} credits &bull;{' '}
                    {Math.round(page.tokens_used_total).toLocaleString()} tokens total
                  </p>
                  <UsageBarList points={page[granularity]} />
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
