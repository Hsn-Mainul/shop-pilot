import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Plus, Upload } from 'lucide-react'
import { api } from '../api/endpoints'
import { money, shortId, statusLabel } from '../lib/format'
import { useLocale } from '../i18n/LocaleContext'
import { useAuth } from '../auth/AuthContext'
import { roleAtLeast } from '../lib/roles'
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
  Select,
  Table,
  Textarea,
} from '../components/ui/primitives'

const STATUSES = ['new', 'confirmed', 'packed', 'shipped', 'delivered', 'returned', 'on_hold']

const NEXT: Record<string, string[]> = {
  new: ['confirmed', 'on_hold'],
  confirmed: ['packed', 'on_hold', 'returned'],
  packed: ['shipped', 'on_hold'],
  shipped: ['delivered', 'returned'],
  delivered: ['returned'],
  on_hold: ['confirmed', 'returned'],
  returned: [],
}

function parseOrderCsv(text: string) {
  return text
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
    .filter((line) => !line.toLowerCase().startsWith('customer_phone'))
    .map((line) => {
      const [phone, name, item, qty, price, channel] = line.split(',').map((s) => s.trim())
      return {
        customer_phone: phone || undefined,
        customer_name: name || undefined,
        item_name: item || 'Item',
        quantity: Number(qty) || 1,
        unit_price: Number(price) || 0,
        source_channel: channel || 'spreadsheet',
      }
    })
}

export function OrdersPage() {
  const { t } = useLocale()
  const { role } = useAuth()
  const qc = useQueryClient()
  const [filter, setFilter] = useState('')
  const [customerId, setCustomerId] = useState('')
  const [itemName, setItemName] = useState('')
  const [qty, setQty] = useState('1')
  const [unitPrice, setUnitPrice] = useState('')
  const [channel, setChannel] = useState('manual')
  const [csv, setCsv] = useState(
    '01700000000,Demo Customer,T-Shirt,1,499,spreadsheet\n01800000000,Another,Mug,2,299,spreadsheet',
  )
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [showImportModal, setShowImportModal] = useState(false)

  const shop = useQuery({ queryKey: ['shop'], queryFn: api.shop.me })
  const customers = useQuery({ queryKey: ['customers'], queryFn: () => api.customers.list() })
  const orders = useQuery({
    queryKey: ['orders', filter],
    queryFn: () => api.orders.list(filter || undefined),
  })

  const setStatus = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) => api.orders.setStatus(id, status),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['orders'] }),
  })

  const create = useMutation({
    mutationFn: () =>
      api.orders.create({
        customer_id: customerId,
        source_channel: channel,
        items: [
          {
            name_snapshot: itemName,
            quantity: Number(qty) || 1,
            unit_price: Number(unitPrice) || 0,
          },
        ],
      }),
    onSuccess: () => {
      setItemName('')
      setUnitPrice('')
      setShowCreateModal(false)
      qc.invalidateQueries({ queryKey: ['orders'] })
    },
  })

  const importCsv = useMutation({
    mutationFn: () => api.orders.importRows(parseOrderCsv(csv)),
    onSuccess: () => {
      setShowImportModal(false)
      qc.invalidateQueries({ queryKey: ['orders'] })
    },
  })

  const exportCsv = useMutation({
    mutationFn: () => api.orders.exportCsv(),
  })

  const currency = shop.data?.currency ?? 'BDT'

  return (
    <>
      <PageHeader
        title={t('orders')}
        subtitle={t('ordersSubtitle')}
        actions={
          roleAtLeast(role, 'sales') ? (
            <div className="row" style={{ gap: '0.5rem' }}>
              <Button
                variant="secondary"
                onClick={() => exportCsv.mutate()}
                disabled={exportCsv.isPending}
              >
                {t('exportCsv')}
              </Button>
              <Button variant="secondary" onClick={() => setShowImportModal(true)}>
                <Upload size={15} style={{ marginRight: 6 }} />
                {t('spreadsheetSync')}
              </Button>
              <Button onClick={() => setShowCreateModal(true)}>
                <Plus size={15} style={{ marginRight: 6 }} />
                {t('createOrder')}
              </Button>
            </div>
          ) : null
        }
      />

      <div className="row tabs">
        {STATUSES.map((s) => (
          <Button
            key={s}
            size="sm"
            variant={filter === s ? 'primary' : 'secondary'}
            onClick={() => setFilter(filter === s ? '' : s)}
          >
            {statusLabel(s)}
          </Button>
        ))}
      </div>

      <Panel title={t('orders')}>
          {orders.isLoading ? (
            <Loading />
          ) : orders.isError ? (
            <ErrorBox error={orders.error} />
          ) : !orders.data?.length ? (
            <EmptyState title={t('noOrders')} />
          ) : (
            <Table>
              <thead>
                <tr>
                  <th>Order</th>
                  <th>Customer</th>
                  <th>Status</th>
                  <th>Channel</th>
                  <th>Created</th>
                  <th>Total</th>
                  <th>Advance</th>
                </tr>
              </thead>
              <tbody>
                {orders.data.map((o) => (
                  <tr key={o.id}>
                    <td>{shortId(o.id)}</td>
                    <td>{shortId(o.customer_id)}</td>
                    <td>
                      <Badge>{statusLabel(o.status)}</Badge>
                    </td>
                    <td>{o.source_channel}</td>
                    <td>
                      {o.created_at ? new Date(o.created_at).toLocaleDateString() : '—'}
                    </td>
                    <td>{money(o.total_amount, currency)}</td>
                    <td>
                      <Select
                        defaultValue=""
                        onChange={(e) => {
                          if (e.target.value) {
                            setStatus.mutate({ id: o.id, status: e.target.value })
                            e.target.value = ''
                          }
                        }}
                        style={{ minWidth: 130 }}
                      >
                        <option value="">Move to…</option>
                        {(NEXT[o.status] ?? []).map((s) => (
                          <option key={s} value={s}>
                            {statusLabel(s)}
                          </option>
                        ))}
                      </Select>
                    </td>
                  </tr>
                ))}
              </tbody>
            </Table>
          )}
          {setStatus.isError ? <ErrorBox error={setStatus.error} /> : null}
      </Panel>

      {roleAtLeast(role, 'sales') ? (
        <Modal open={showCreateModal} title={t('createOrder')} onClose={() => setShowCreateModal(false)}>
          <div className="stack">
            <label className="field-label">
              Customer
              <Select value={customerId} onChange={(e) => setCustomerId(e.target.value)}>
                <option value="">Select…</option>
                {(customers.data ?? []).map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name || c.phone || shortId(c.id)}
                  </option>
                ))}
              </Select>
            </label>
            <label className="field-label">
              Channel
              <Select value={channel} onChange={(e) => setChannel(e.target.value)}>
                {['manual', 'facebook', 'instagram', 'whatsapp', 'comment', 'call'].map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </Select>
            </label>
            <label className="field-label">
              Item name
              <Input value={itemName} onChange={(e) => setItemName(e.target.value)} />
            </label>
            <label className="field-label">
              Qty
              <Input type="number" value={qty} onChange={(e) => setQty(e.target.value)} />
            </label>
            <label className="field-label">
              Unit price
              <Input type="number" value={unitPrice} onChange={(e) => setUnitPrice(e.target.value)} />
            </label>
            {create.isError ? <ErrorBox error={create.error} /> : null}
            <Button
              onClick={() => create.mutate()}
              disabled={!customerId || !itemName || !unitPrice || create.isPending}
            >
              {t('createOrder')}
            </Button>
          </div>
        </Modal>
      ) : null}

      {roleAtLeast(role, 'sales') ? (
        <Modal open={showImportModal} title={t('spreadsheetSync')} onClose={() => setShowImportModal(false)} width={560}>
          <div className="stack">
            <p className="muted">{t('orderCsvHint')}</p>
            <Textarea value={csv} onChange={(e) => setCsv(e.target.value)} rows={5} />
            {importCsv.isError ? <ErrorBox error={importCsv.error} /> : null}
            {importCsv.data ? (
              <div className="muted">Imported {importCsv.data.created} orders.</div>
            ) : null}
            <Button
              onClick={() => importCsv.mutate()}
              disabled={!csv.trim() || importCsv.isPending}
            >
              {t('importCsv')}
            </Button>
          </div>
        </Modal>
      ) : null}
    </>
  )
}
