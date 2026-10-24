import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api } from '../api/endpoints'
import { usePollingQuery } from '../hooks/usePollingQuery'
import { useLocale } from '../i18n/LocaleContext'
import { money, relativeSeconds, shortId, statusLabel } from '../lib/format'
import {
  Badge,
  Button,
  EmptyState,
  ErrorBox,
  Loading,
  PageHeader,
  Panel,
  StatTile,
  Table,
} from '../components/ui/primitives'

export function OverviewPage() {
  const { t } = useLocale()
  const stats = usePollingQuery(['inbox-stats'], api.conversations.stats, 8000)
  const orders = usePollingQuery(['orders'], () => api.orders.list(), 12000)
  const payments = usePollingQuery(
    ['payments', 'pending'],
    () => api.payments.list('pending'),
    12000,
  )
  const parcels = usePollingQuery(['parcels'], () => api.delivery.parcels(), 15000)
  const products = useQuery({ queryKey: ['products'], queryFn: () => api.products.list() })
  const checklist = useQuery({ queryKey: ['checklist'], queryFn: api.shop.checklist })
  const shop = useQuery({ queryKey: ['shop'], queryFn: api.shop.me })

  const lowStock =
    products.data?.flatMap((p) =>
      p.variants
        .filter((v) => v.stock_qty <= v.reorder_point)
        .map((v) => ({ product: p, variant: v })),
    ) ?? []
  const soldOut = lowStock.filter((x) => x.variant.stock_qty <= 0)
  const onHold = orders.data?.filter((o) => o.status === 'on_hold') ?? []
  const toPack = orders.data?.filter((o) => o.status === 'confirmed') ?? []
  const failedDeliveries =
    parcels.data?.filter((p) => p.status === 'returned' || p.status === 'on_hold') ?? []
  const latest = [...(orders.data ?? [])].slice(0, 8)
  const currency = shop.data?.currency ?? 'BDT'

  const revenueByChannel = useMemo(() => {
    const map = new Map<string, number>()
    for (const o of orders.data ?? []) {
      if (o.status === 'returned') continue
      const key = o.source_channel || 'manual'
      map.set(key, (map.get(key) ?? 0) + Number(o.total_amount || 0))
    }
    return [...map.entries()].sort((a, b) => b[1] - a[1])
  }, [orders.data])

  const bestDays = useMemo(() => {
    const map = new Map<string, number>()
    const dayNames = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
    for (const o of orders.data ?? []) {
      if (o.status === 'returned' || !o.created_at) continue
      const day = dayNames[new Date(o.created_at).getDay()]
      map.set(day, (map.get(day) ?? 0) + Number(o.total_amount || 0))
    }
    return dayNames
      .filter((d) => map.has(d))
      .map((d) => [d, map.get(d) ?? 0] as [string, number])
      .sort((a, b) => b[1] - a[1])
  }, [orders.data])

  const channelMix = useMemo(() => {
    const map = new Map<string, number>()
    for (const o of orders.data ?? []) {
      const ch = o.source_channel || 'manual'
      map.set(ch, (map.get(ch) ?? 0) + 1)
    }
    return [...map.entries()].sort((a, b) => b[1] - a[1])
  }, [orders.data])

  const totalRevenue = (orders.data ?? [])
    .filter((o) => o.status !== 'returned')
    .reduce((s, o) => s + Number(o.total_amount || 0), 0)

  const fulfilment = useMemo(() => {
    const counts: Record<string, number> = {}
    for (const p of parcels.data ?? []) {
      counts[p.status] = (counts[p.status] ?? 0) + 1
    }
    return counts
  }, [parcels.data])

  const maxChannel = Math.max(
    1,
    ...revenueByChannel.map(([, v]) => v),
    ...channelMix.map(([, v]) => v),
    ...bestDays.map(([, v]) => v),
  )

  return (
    <>
      <PageHeader
        title={t('overview')}
        subtitle="Needs attention, revenue, channels, and fulfilment snapshot."
        actions={
          <Link to="/setup">
            <Button variant="secondary">Setup checklist</Button>
          </Link>
        }
      />

      {(stats.isError || orders.isError) && <ErrorBox error={stats.error ?? orders.error} />}

      <div className="stat-grid">
        <StatTile
          label="Chats waiting"
          value={stats.data?.conversations_waiting_for_reply ?? '—'}
          tone="warn"
          hint={`Avg reply ${relativeSeconds(stats.data?.average_reply_time_seconds)}`}
        />
        <StatTile
          label="Payment checks"
          value={payments.data?.length ?? '—'}
          tone={(payments.data?.length ?? 0) > 0 ? 'warn' : 'default'}
        />
        <StatTile label="Orders to pack" value={toPack.length} />
        <StatTile
          label="Failed deliveries"
          value={failedDeliveries.length}
          tone={failedDeliveries.length ? 'danger' : 'default'}
        />
        <StatTile label="On hold" value={onHold.length} tone={onHold.length ? 'danger' : 'default'} />
        <StatTile label="Low stock" value={lowStock.length} tone={lowStock.length ? 'warn' : 'good'} />
        <StatTile label="Sold out" value={soldOut.length} tone={soldOut.length ? 'danger' : 'default'} />
        <StatTile label="Revenue (orders)" value={money(totalRevenue, currency)} tone="good" />
      </div>

      <div className="grid-2">
        <Panel title="Revenue by channel">
          {!revenueByChannel.length ? (
            <EmptyState title="No sales yet" />
          ) : (
            <div className="bar-chart">
              {revenueByChannel.map(([ch, amt]) => (
                <div className="bar-row" key={ch}>
                  <span>{ch}</span>
                  <div className="bar-track">
                    <span style={{ width: `${(amt / maxChannel) * 100}%` }} />
                  </div>
                  <span>{money(amt, currency)}</span>
                </div>
              ))}
            </div>
          )}
        </Panel>

        <Panel title={t('bestSalesDays')}>
          {!bestDays.length ? (
            <EmptyState title="No dated orders yet" hint="Orders need created_at to rank weekdays." />
          ) : (
            <div className="bar-chart">
              {bestDays.map(([day, amt]) => (
                <div className="bar-row" key={day}>
                  <span>{day}</span>
                  <div className="bar-track">
                    <span style={{ width: `${(amt / maxChannel) * 100}%` }} />
                  </div>
                  <span>{money(amt, currency)}</span>
                </div>
              ))}
            </div>
          )}
        </Panel>
      </div>

      <Panel title="Sales channels">
        {!channelMix.length ? (
          <EmptyState title="No channel mix" />
        ) : (
          <div className="bar-chart">
            {channelMix.map(([ch, count]) => (
              <div className="bar-row" key={ch}>
                <span>{ch}</span>
                <div className="bar-track">
                  <span style={{ width: `${(count / maxChannel) * 100}%` }} />
                </div>
                <span>{count}</span>
              </div>
            ))}
          </div>
        )}
      </Panel>

      <div className="grid-2">
        <Panel title="Latest orders">
          {orders.isLoading ? (
            <Loading />
          ) : !latest.length ? (
            <EmptyState title="No orders yet" />
          ) : (
            <Table>
              <thead>
                <tr>
                  <th>Order</th>
                  <th>Status</th>
                  <th>Channel</th>
                  <th>Total</th>
                </tr>
              </thead>
              <tbody>
                {latest.map((o) => (
                  <tr key={o.id}>
                    <td>{shortId(o.id)}</td>
                    <td>
                      <Badge
                        tone={
                          o.status === 'delivered'
                            ? 'good'
                            : o.status === 'on_hold'
                              ? 'danger'
                              : 'info'
                        }
                      >
                        {statusLabel(o.status)}
                      </Badge>
                    </td>
                    <td>{o.source_channel}</td>
                    <td>{money(o.total_amount, currency)}</td>
                  </tr>
                ))}
              </tbody>
            </Table>
          )}
        </Panel>

        <Panel title="Fulfilment snapshot">
          {parcels.isLoading ? (
            <Loading />
          ) : !parcels.data?.length ? (
            <EmptyState title="No parcels" hint="Book deliveries to see the pipeline." />
          ) : (
            <div className="stat-grid">
              {Object.entries(fulfilment).map(([status, count]) => (
                <StatTile key={status} label={statusLabel(status)} value={count} />
              ))}
            </div>
          )}
        </Panel>
      </div>

      <Panel title="Order pipeline">
        {orders.isLoading ? (
          <Loading />
        ) : (
          <div className="stat-grid">
            {['new', 'confirmed', 'packed', 'shipped', 'delivered', 'returned', 'on_hold'].map(
              (s) => (
                <StatTile
                  key={s}
                  label={statusLabel(s)}
                  value={orders.data?.filter((o) => o.status === s).length ?? 0}
                />
              ),
            )}
          </div>
        )}
      </Panel>

      <Panel title="Setup progress">
        {checklist.isLoading ? (
          <Loading />
        ) : checklist.data ? (
          <div className="stack">
            <div className="row" style={{ justifyContent: 'space-between' }}>
              <strong>{checklist.data.percent_complete}% complete</strong>
              <span className="muted">
                {checklist.data.steps_done}/{checklist.data.steps_total} steps
              </span>
            </div>
            <div className="progress-bar">
              <span style={{ width: `${checklist.data.percent_complete}%` }} />
            </div>
            <Link to="/setup">
              <Button size="sm" variant="secondary">
                Open setup
              </Button>
            </Link>
          </div>
        ) : (
          <EmptyState title="Checklist unavailable" />
        )}
      </Panel>
    </>
  )
}
