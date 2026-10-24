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

  return (
    <>
      <PageHeader
        title={t('customers')}
        subtitle="CRM with segments, blocked list, and loyalty-ready records (FR-CUST)."
        actions={
          <div className="row" style={{ gap: '0.5rem' }}>
            {roleAtLeast(role, 'admin') ? (
              <Button variant="secondary" onClick={() => recompute.mutate()} disabled={recompute.isPending}>
                Recompute segments
              </Button>
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
                  <th>Segment</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {filtered.map((c) => (
                  <tr key={c.id}>
                    <td>
                      <strong>{c.name || shortId(c.id)}</strong>
                      {c.is_blocked ? <Badge tone="danger">blocked</Badge> : null}
                    </td>
                    <td>
                      {c.phone || '—'}
                      <div className="muted">{c.email}</div>
                    </td>
                    <td>{c.source || '—'}</td>
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
                ))}
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
