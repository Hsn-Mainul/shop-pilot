import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Plus } from 'lucide-react'
import { api } from '../api/endpoints'
import { money, statusLabel } from '../lib/format'
import { Modal } from '../components/ui/Modal'
import {
  Button,
  EmptyState,
  ErrorBox,
  Input,
  Loading,
  PageHeader,
  Panel,
  Select,
  StatTile,
  Table,
} from '../components/ui/primitives'

export function FinancePage() {
  const qc = useQueryClient()
  const [category, setCategory] = useState('other')
  const [amount, setAmount] = useState('')
  const [paidFrom, setPaidFrom] = useState('cash')
  const [note, setNote] = useState('')
  const [receiptUrl, setReceiptUrl] = useState('')
  const [uploading, setUploading] = useState(false)
  const [exportBusy, setExportBusy] = useState<string | null>(null)
  const [exportError, setExportError] = useState<unknown>(null)
  const [showAddModal, setShowAddModal] = useState(false)
  const [period, setPeriod] = useState(() => {
    const d = new Date()
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
  })

  const shop = useQuery({ queryKey: ['shop'], queryFn: api.shop.me })
  const overview = useQuery({ queryKey: ['finance-overview'], queryFn: api.finance.overview })
  const expenses = useQuery({ queryKey: ['expenses'], queryFn: api.finance.expenses })
  const statement = useQuery({
    queryKey: ['statement', period],
    queryFn: () => api.finance.statement(period),
  })
  const forecast = useQuery({
    queryKey: ['cash-forecast'],
    queryFn: () => api.finance.cashForecast(28),
  })

  const add = useMutation({
    mutationFn: () =>
      api.finance.addExpense({
        category,
        amount: Number(amount),
        paid_from: paidFrom,
        note: note || undefined,
        receipt_photo_url: receiptUrl || undefined,
      }),
    onSuccess: () => {
      setAmount('')
      setNote('')
      setReceiptUrl('')
      setShowAddModal(false)
      qc.invalidateQueries({ queryKey: ['expenses'] })
      qc.invalidateQueries({ queryKey: ['finance-overview'] })
    },
  })

  async function onReceiptFile(file: File | null) {
    if (!file) return
    setUploading(true)
    try {
      const res = await api.media.upload(file)
      setReceiptUrl(res.url)
    } finally {
      setUploading(false)
    }
  }

  const currency = shop.data?.currency ?? 'BDT'
  const o = overview.data

  return (
    <>
      <PageHeader
        title="Finance"
        subtitle="P&L, cash forecast, expenses, statements, and CSV exports (FR-FIN)."
        actions={
          <div className="row">
            <Button onClick={() => setShowAddModal(true)}>
              <Plus size={15} style={{ marginRight: 6 }} />
              Record Expense
            </Button>
            {(['sales_book', 'expenses', 'stock_value'] as const).map((type) => (
              <Button
                key={type}
                size="sm"
                variant="secondary"
                disabled={exportBusy !== null}
                onClick={async () => {
                  setExportBusy(type)
                  setExportError(null)
                  try {
                    await api.finance.exportCsv(type)
                  } catch (err) {
                    setExportError(err)
                  } finally {
                    setExportBusy(null)
                  }
                }}
              >
                {exportBusy === type ? 'Exporting…' : `Export ${type.replace(/_/g, ' ')}`}
              </Button>
            ))}
          </div>
        }
      />
      {exportError ? <ErrorBox error={exportError} /> : null}

      {overview.isLoading ? (
        <Loading />
      ) : overview.isError ? (
        <ErrorBox error={overview.error} />
      ) : (
        <div className="stat-grid">
          <StatTile label="Sales" value={money(o?.sales, currency)} />
          <StatTile label="COGS" value={money(o?.cost_of_goods_sold, currency)} />
          <StatTile label="Gross profit" value={money(o?.gross_profit, currency)} tone="good" />
          <StatTile label="Expenses" value={money(o?.expenses_total, currency)} />
          <StatTile label="Net profit" value={money(o?.net_profit, currency)} tone="good" />
          <StatTile label="Cash on hand" value={money(o?.cash_on_hand, currency)} />
          <StatTile label="COD with couriers" value={money(o?.cod_with_couriers, currency)} tone="warn" />
          <StatTile label="Stock at cost" value={money(o?.stock_value_at_cost, currency)} />
        </div>
      )}

      <Panel title="Cash forecast (4 weeks)">
        {forecast.isLoading ? (
          <Loading />
        ) : forecast.isError ? (
          <ErrorBox error={forecast.error} />
        ) : forecast.data ? (
          <>
            <p className="muted">
              Starting cash {money(forecast.data.starting_cash, currency)} · horizon{' '}
              {forecast.data.horizon_days} days
            </p>
            <Table>
              <thead>
                <tr>
                  <th>Period</th>
                  <th>In</th>
                  <th>Out</th>
                  <th>Net</th>
                  <th>Balance</th>
                </tr>
              </thead>
              <tbody>
                {forecast.data.points.map((p) => (
                  <tr key={p.label}>
                    <td>{p.label}</td>
                    <td>{money(p.projected_in, currency)}</td>
                    <td>{money(p.projected_out, currency)}</td>
                    <td>{money(p.net, currency)}</td>
                    <td>{money(p.running_balance, currency)}</td>
                  </tr>
                ))}
              </tbody>
            </Table>
          </>
        ) : null}
      </Panel>

      <Panel title="Expenses">
          {expenses.isLoading ? (
            <Loading />
          ) : !expenses.data?.length ? (
            <EmptyState title="No expenses recorded" />
          ) : (
            <Table>
              <thead>
                <tr>
                  <th>Category</th>
                  <th>Amount</th>
                  <th>Paid from</th>
                  <th>Note</th>
                  <th>Receipt</th>
                </tr>
              </thead>
              <tbody>
                {expenses.data.map((e) => (
                  <tr key={e.id}>
                    <td>{statusLabel(e.category)}</td>
                    <td>{money(e.amount, currency)}</td>
                    <td>{e.paid_from}</td>
                    <td>{e.note || '—'}</td>
                    <td>
                      {e.receipt_photo_url ? (
                        <Button
                          size="sm"
                          variant="secondary"
                          onClick={() => api.media.open(e.receipt_photo_url!)}
                        >
                          View
                        </Button>
                      ) : (
                        '—'
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </Table>
          )}
      </Panel>

      <Panel title="Statement">
        <div className="stack">
          <label className="field-label">
            Period (YYYY-MM / YYYY-Qn / YYYY)
            <Input value={period} onChange={(e) => setPeriod(e.target.value)} />
          </label>
          {statement.isLoading ? (
            <Loading />
          ) : statement.data ? (
            <div className="demo-hint">
              Sales: {money(Number(statement.data.sales), currency)}
              <br />
              Expenses: {money(Number(statement.data.expenses), currency)}
              <br />
              Net: {money(Number(statement.data.net_profit), currency)}
            </div>
          ) : null}
        </div>
      </Panel>

      <Modal open={showAddModal} title="Record expense" onClose={() => setShowAddModal(false)}>
        <div className="stack">
          <label className="field-label">
            Category
            <Select value={category} onChange={(e) => setCategory(e.target.value)}>
              {[
                'inventory_purchase',
                'rent',
                'salaries',
                'delivery_courier',
                'marketing',
                'utilities',
                'payment_gateway_fees',
                'telephony',
                'other',
              ].map((c) => (
                <option key={c} value={c}>
                  {statusLabel(c)}
                </option>
              ))}
            </Select>
          </label>
          <label className="field-label">
            Amount
            <Input type="number" value={amount} onChange={(e) => setAmount(e.target.value)} />
          </label>
          <label className="field-label">
            Paid from
            <Select value={paidFrom} onChange={(e) => setPaidFrom(e.target.value)}>
              {['cash', 'bank', 'wallet'].map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </Select>
          </label>
          <label className="field-label">
            Note
            <Input value={note} onChange={(e) => setNote(e.target.value)} />
          </label>
          <label className="field-label">
            Receipt photo
            <Input
              type="file"
              accept="image/*,.pdf"
              onChange={(e) => onReceiptFile(e.target.files?.[0] ?? null)}
            />
          </label>
          {uploading ? <div className="muted">Uploading…</div> : null}
          {receiptUrl ? <div className="muted">Attached: {receiptUrl}</div> : null}
          {add.isError ? <ErrorBox error={add.error} /> : null}
          <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.25rem' }}>
            <Button onClick={() => add.mutate()} disabled={!amount || add.isPending}>
              Save expense
            </Button>
            <Button variant="secondary" onClick={() => setShowAddModal(false)}>
              Cancel
            </Button>
          </div>
        </div>
      </Modal>
    </>
  )
}
