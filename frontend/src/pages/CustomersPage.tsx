import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useMemo, useState } from 'react'
import { Plus } from 'lucide-react'
import { api } from '../api/endpoints'
import { shortId, statusLabel } from '../lib/format'
import { useAuth } from '../auth/AuthContext'
import { roleAtLeast } from '../lib/roles'
import { useLocale } from '../i18n/LocaleContext'
import { ConfirmDialog } from '../components/ui/ConfirmDialog'
import { Modal } from '../components/ui/Modal'
import {
  Badge,
  Button,
  EmptyState,
  ErrorBox,
  Input,
  Loading,
  PageHeader,
  Panel,
  Table,
} from '../components/ui/primitives'

type Tab = 'all' | 'segments' | 'blocked'

// Internal identity key patterns: fb:xxx, ig:xxx, wa:xxx, tg:xxx etc.
// These are dedup keys, not real phone numbers — show them as channel labels.
const IDENTITY_RE = /^(fb|ig|wa|tg|cmt|wh|ch):(.+)$/i
const CHANNEL_LABELS: Record<string, string> = {
  fb: 'Facebook',
  ig: 'Instagram',
  wa: 'WhatsApp',
  tg: 'Telegram',
  cmt: 'Comment',
  wh: 'Webhook',
  ch: 'Chat',
}

function parseContact(phone: string | null | undefined, email: string | null | undefined): { real: string | null; channel: string | null } {
  // email field may hold a real phone number (stored there to preserve the identity key in phone)
  const emailIsRealPhone = email && !email.startsWith('page:') && !email.startsWith('comment:')

  if (!phone) return { real: emailIsRealPhone ? email : null, channel: null }
  const m = IDENTITY_RE.exec(phone)
  if (m) return { real: emailIsRealPhone ? email : null, channel: CHANNEL_LABELS[m[1].toLowerCase()] ?? m[1] }
  return { real: phone, channel: null }
}

export function CustomersPage() {
  const { t } = useLocale()
  const qc = useQueryClient()
  const { role } = useAuth()
  const [q, setQ] = useState('')
  const [tab, setTab] = useState<Tab>('all')
  const [name, setName] = useState('')
  const [phone, setPhone] = useState('')
  const [email, setEmail] = useState('')
  const [blockTarget, setBlockTarget] = useState<{ id: string; blocked: boolean } | null>(null)
  const [showAddModal, setShowAddModal] = useState(false)

  const customers = useQuery({
    queryKey: ['customers', q],
    queryFn: () => api.customers.list(q || undefined),
  })

  const filtered = useMemo(() => {
    const list = customers.data ?? []
    if (tab === 'blocked') return list.filter((c) => c.is_blocked)
    if (tab === 'segments') return list.filter((c) => Boolean(c.segment))
    return list
  }, [customers.data, tab])

  const segmentCounts = useMemo(() => {
    const map = new Map<string, number>()
    for (const c of customers.data ?? []) {
      const s = c.segment || 'unsegmented'
      map.set(s, (map.get(s) ?? 0) + 1)
    }
    return [...map.entries()]
  }, [customers.data])

  const create = useMutation({
    mutationFn: () =>
      api.customers.create({
        name: name || undefined,
        phone: phone || undefined,
        email: email || undefined,
        source: 'manual',
      }),
    onSuccess: () => {
      setName('')
      setPhone('')
      setEmail('')
      setShowAddModal(false)
      qc.invalidateQueries({ queryKey: ['customers'] })
    },
  })

  const block = useMutation({
    mutationFn: ({ id, blocked }: { id: string; blocked: boolean }) =>
      api.customers.block(id, blocked),
    onSuccess: () => {
      setBlockTarget(null)
      qc.invalidateQueries({ queryKey: ['customers'] })
    },
  })

  const recompute = useMutation({
    mutationFn: api.customers.recomputeSegments,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['customers'] }),
  })

  const enrichNames = useMutation({
    mutationFn: api.customers.enrichNames,
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ['customers'] })
      alert(data.message)
    },
  })

  return (
    <>
      <PageHeader
        title={t('customers')}
        subtitle="CRM with segments, blocked list, and loyalty-ready records (FR-CUST)."
        actions={
          <div className="row" style={{ gap: '0.5rem' }}>
            {roleAtLeast(role, 'admin') ? (
              <>
                <Button variant="secondary" onClick={() => recompute.mutate()} disabled={recompute.isPending}>
                  Recompute segments
                </Button>
                <Button variant="secondary" onClick={() => enrichNames.mutate()} disabled={enrichNames.isPending}>
                  {enrichNames.isPending ? 'Resolving names…' : 'Resolve FB names'}
                </Button>
              </>
            ) : null}
            {roleAtLeast(role, 'sales') ? (
              <Button onClick={() => setShowAddModal(true)}>
                <Plus size={15} style={{ marginRight: 6 }} />
                Add Customer
              </Button>
            ) : null}
          </div>
        }
      />

      <div className="row tabs">
        {(
          [
            ['all', 'All'],
            ['segments', 'Segments'],
            ['blocked', 'Blocked'],
          ] as const
        ).map(([key, label]) => (
          <Button
            key={key}
            size="sm"
            variant={tab === key ? 'primary' : 'secondary'}
            onClick={() => setTab(key)}
          >
            {label}
          </Button>
        ))}
      </div>

      {tab === 'segments' ? (
        <Panel title="Segment summary">
          <div className="stat-grid">
            {segmentCounts.map(([seg, count]) => (
              <div className="stat-tile" key={seg}>
                <span className="stat-label">{statusLabel(seg)}</span>
                <strong className="stat-value">{count}</strong>
              </div>
            ))}
          </div>
        </Panel>
      ) : null}

      <div className="row">
        <Input
          placeholder="Search…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          style={{ maxWidth: 280 }}
        />
      </div>

      <Panel title={tab === 'blocked' ? 'Blocked list' : 'Customer list'}>
          {customers.isLoading ? (
            <Loading />
          ) : customers.isError ? (
            <ErrorBox error={customers.error} />
          ) : !filtered.length ? (
            <EmptyState title="No customers in this view" />
          ) : (
            <Table>
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Contact</th>
                  <th>Source</th>
                  <th>Orders</th>
                  <th>Segment</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {filtered.map((c) => {
                  const { real: realPhone, channel } = parseContact(c.phone, c.email)
                  // Name: use the stored name if it looks real (not a raw FB user ID)
                  const displayName =
                    c.name && !/^\d{10,}$/.test(c.name) ? c.name : null
                  return (
                    <tr key={c.id}>
                      <td>
                        <strong>{displayName ?? <span className="muted">{shortId(c.id)}</span>}</strong>
                        {c.is_blocked ? <Badge tone="danger">blocked</Badge> : null}
                        {channel && !displayName ? (
                          <div className="muted" style={{ fontSize: 12 }}>{channel} user</div>
                        ) : null}
                      </td>
                      <td>
                        {realPhone ? (
                          <span>{realPhone}</span>
                        ) : (
                          <span className="muted" style={{ fontSize: 12 }}>
                            {channel ? `via ${channel}` : '—'}
                          </span>
                        )}
                        {c.email && !c.email.startsWith('page:') && !c.email.startsWith('comment:') ? (
                          <div className="muted">{c.email}</div>
                        ) : null}
                      </td>
                      <td>{c.source || '—'}</td>
                      <td>
                        {(c as any).order_count > 0 ? (
                          <Badge tone="good">{(c as any).order_count} order{(c as any).order_count > 1 ? 's' : ''}</Badge>
                        ) : (
                          <span className="muted">—</span>
                        )}
                      </td>
                      <td>{c.segment ? statusLabel(c.segment) : '—'}</td>
                      <td>
                        {roleAtLeast(role, 'support') ? (
                          <Button
                            size="sm"
                            variant="secondary"
                            onClick={() => setBlockTarget({ id: c.id, blocked: !c.is_blocked })}
                          >
                            {c.is_blocked ? 'Unblock' : 'Block'}
                          </Button>
                        ) : null}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </Table>
          )}
        </Panel>

      {roleAtLeast(role, 'sales') ? (
        <Modal open={showAddModal} title="Add customer" onClose={() => setShowAddModal(false)}>
          <div className="stack">
            <label className="field-label">
              Name
              <Input value={name} onChange={(e) => setName(e.target.value)} />
            </label>
            <label className="field-label">
              Phone
              <Input value={phone} onChange={(e) => setPhone(e.target.value)} />
            </label>
            <label className="field-label">
              Email
              <Input value={email} onChange={(e) => setEmail(e.target.value)} />
            </label>
            {create.isError ? <ErrorBox error={create.error} /> : null}
            <Button onClick={() => create.mutate()} disabled={create.isPending}>
              Create
            </Button>
          </div>
        </Modal>
      ) : null}

      <ConfirmDialog
        open={Boolean(blockTarget)}
        title={blockTarget?.blocked ? 'Block customer?' : 'Unblock customer?'}
        message="This affects whether the customer can place new chats and orders."
        danger={blockTarget?.blocked}
        busy={block.isPending}
        confirmLabel={blockTarget?.blocked ? 'Block' : 'Unblock'}
        onCancel={() => setBlockTarget(null)}
        onConfirm={() => blockTarget && block.mutate(blockTarget)}
      />
    </>
  )
}
