import type { AdminUsagePoint, AdminCostPoint } from '../../types/api'

export type Granularity = 'daily' | 'monthly' | 'yearly'

export function UsageBarList({
  points,
  unit = 'credits',
}: {
  points: AdminUsagePoint[] | AdminCostPoint[]
  unit?: 'credits' | 'cost'
}) {
  if (points.length === 0) {
    return (
      <p style={{ color: '#94a3b8', fontSize: 13, fontStyle: 'italic', margin: 0 }}>
        No usage recorded for this period yet.
      </p>
    )
  }
  const recent = points.slice(-12)
  const max = Math.max(...recent.map((p) => (unit === 'cost' ? (p as AdminCostPoint).cost_usd : p.credits_used)), 1)
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      {recent.map((p) => {
        const value = unit === 'cost' ? (p as AdminCostPoint).cost_usd : p.credits_used
        return (
          <div key={p.period}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12.5, marginBottom: 3 }}>
              <span style={{ fontWeight: 600, color: '#0f172a' }}>{p.period}</span>
              <span style={{ color: '#64748b' }}>
                {unit === 'cost'
                  ? `$${value.toFixed(4)}`
                  : `${value.toLocaleString()} credits (${Math.round(p.tokens_used).toLocaleString()} tokens)`}
              </span>
            </div>
            <div style={{ width: '100%', height: 6, background: '#f1f5f9', borderRadius: 3, overflow: 'hidden' }}>
              <div style={{ width: `${(value / max) * 100}%`, height: '100%', background: '#0284c7' }} />
            </div>
          </div>
        )
      })}
    </div>
  )
}

export function GranularityToggle({
  value,
  onChange,
  size = 'md',
}: {
  value: Granularity
  onChange: (g: Granularity) => void
  size?: 'sm' | 'md'
}) {
  const options: Granularity[] = ['daily', 'monthly', 'yearly']
  return (
    <div style={{ display: 'flex', gap: 6 }}>
      {options.map((g) => (
        <button
          key={g}
          onClick={() => onChange(g)}
          style={{
            padding: size === 'sm' ? '5px 12px' : '6px 14px',
            borderRadius: 8,
            border: '1px solid #e2e8f0',
            background: value === g ? '#0284c7' : '#ffffff',
            color: value === g ? '#ffffff' : '#475569',
            fontWeight: 600,
            fontSize: size === 'sm' ? 12 : 12.5,
            cursor: 'pointer',
            textTransform: 'capitalize',
          }}
        >
          {g}
        </button>
      ))}
    </div>
  )
}
