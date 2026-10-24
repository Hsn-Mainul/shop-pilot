import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../../api/endpoints'
import { Badge, ErrorBox } from '../../components/ui/primitives'
import { UsageBarList, GranularityToggle, type Granularity } from './UsageBarList'

export function CostAnalysisPage() {
  const [granularity, setGranularity] = useState<Granularity>('daily')

  const { data: costAnalysis, isLoading, isError, error } = useQuery({
    queryKey: ['system-admin', 'cost-analysis'],
    queryFn: api.systemAdmin.costAnalysis,
  })

  return (
    <div>
      <div style={{ marginBottom: 20 }}>
        <h2 style={{ fontSize: 18, fontWeight: 700, color: '#0f172a', margin: 0 }}>Cost Analysis</h2>
        <p style={{ color: '#64748b', fontSize: 13, margin: '4px 0 0' }}>
          Wholesale LLM cost vs subscriber revenue, tracked by day, month, and year, plus the pages driving the most spend.
        </p>
      </div>

      {isError ? (
        <ErrorBox error={error} />
      ) : isLoading || !costAnalysis ? (
        <div style={{ padding: 40, textAlign: 'center', color: '#64748b' }}>Calculating cost analysis...</div>
      ) : (
        <>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 16, marginBottom: 24 }}>
            <div style={{ background: '#ffffff', borderRadius: 12, padding: 20, border: '1px solid #e2e8f0' }}>
              <div style={{ fontSize: 13, fontWeight: 600, color: '#64748b', marginBottom: 4 }}>Total Tokens Consumed</div>
              <div style={{ fontSize: 24, fontWeight: 800, color: '#0f172a' }}>
                {Math.round(costAnalysis.total_tokens_consumed).toLocaleString()}
              </div>
            </div>
            <div style={{ background: '#ffffff', borderRadius: 12, padding: 20, border: '1px solid #e2e8f0' }}>
              <div style={{ fontSize: 13, fontWeight: 600, color: '#64748b', marginBottom: 4 }}>Wholesale LLM Cost</div>
              <div style={{ fontSize: 24, fontWeight: 800, color: '#dc2626' }}>${costAnalysis.total_wholesale_cost_usd}</div>
            </div>
            <div style={{ background: '#ffffff', borderRadius: 12, padding: 20, border: '1px solid #e2e8f0' }}>
              <div style={{ fontSize: 13, fontWeight: 600, color: '#64748b', marginBottom: 4 }}>Subscriber Revenue</div>
              <div style={{ fontSize: 24, fontWeight: 800, color: '#16a34a' }}>${costAnalysis.total_subscriber_revenue_usd}</div>
            </div>
            <div style={{ background: '#ffffff', borderRadius: 12, padding: 20, border: '1px solid #e2e8f0' }}>
              <div style={{ fontSize: 13, fontWeight: 600, color: '#64748b', marginBottom: 4 }}>Net Margin</div>
              <div style={{ fontSize: 24, fontWeight: 800, color: '#0284c7' }}>{costAnalysis.net_margin_percentage}%</div>
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(420px, 1fr))', gap: 20 }}>
            <div style={{ background: '#ffffff', borderRadius: 14, padding: 24, border: '1px solid #e2e8f0' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
                <h3 style={{ fontSize: 16, fontWeight: 700, color: '#0f172a', margin: 0 }}>
                  Cost Over Time ({granularity})
                </h3>
                <GranularityToggle value={granularity} onChange={setGranularity} size="sm" />
              </div>
              <UsageBarList points={costAnalysis[granularity]} unit="cost" />
            </div>

            <div style={{ background: '#ffffff', borderRadius: 14, padding: 24, border: '1px solid #e2e8f0' }}>
              <h3 style={{ fontSize: 16, fontWeight: 700, color: '#0f172a', margin: '0 0 16px' }}>Top Pages by Cost</h3>
              {costAnalysis.top_pages_by_cost.length === 0 ? (
                <p style={{ color: '#94a3b8', fontStyle: 'italic' }}>No cost recorded yet.</p>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                  {costAnalysis.top_pages_by_cost.map((p, idx) => (
                    <div
                      key={p.page_id}
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
                          #{idx + 1} {p.page_name}
                        </span>
                        <span style={{ marginLeft: 8 }}>
                          <Badge tone="info">{p.platform}</Badge>
                        </span>
                      </div>
                      <span style={{ fontWeight: 700, color: '#dc2626' }}>${p.cost_usd.toFixed(4)}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  )
}
