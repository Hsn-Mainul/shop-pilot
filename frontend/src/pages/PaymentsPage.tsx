import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type ReactNode } from 'react'
import {
  LayoutGrid,
  Plus,
  CheckCircle2,
  ExternalLink,
  Copy,
  Zap,
} from 'lucide-react'
import { api } from '../api/endpoints'
import { money, shortId } from '../lib/format'
import { extractProofUrl, proofLabel } from '../lib/proof'
import { useLocale } from '../i18n/LocaleContext'
import { ConfirmDialog } from '../components/ui/ConfirmDialog'
import {
  Button,
  EmptyState,
  ErrorBox,
  Input,
  Loading,
  PageHeader,
  Select,
} from '../components/ui/primitives'
import './PaymentsPage.css'

export function PaymentsPage() {
  const { t } = useLocale()
  const qc = useQueryClient()
  const [filter, setFilter] = useState('')
  const [orderId, setOrderId] = useState('')
  const [amount, setAmount] = useState('')
  const [method, setMethod] = useState('bkash')
  const [trx, setTrx] = useState('')
  const [proofNote, setProofNote] = useState('')
  const [proofUrl, setProofUrl] = useState('')
  const [sender, setSender] = useState('')
  const [uploading, setUploading] = useState(false)
  const [confirmId, setConfirmId] = useState<string | null>(null)
  const [showRecordModal, setShowRecordModal] = useState(false)
  const [copiedId, setCopiedId] = useState<string | null>(null)

  const shop = useQuery({ queryKey: ['shop'], queryFn: api.shop.me })
  const payments = useQuery({
    queryKey: ['payments', filter],
    queryFn: () => api.payments.list(filter || undefined),
  })

  const autoConfirm = Boolean(shop.data?.ai_module_toggles?.money)

  const toggleAuto = useMutation({
    mutationFn: () =>
      api.shop.update({
        ai_module_toggles: {
          ...(shop.data?.ai_module_toggles ?? {}),
          money: !autoConfirm,
        },
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['shop'] }),
  })

  const create = useMutation({
    mutationFn: () =>
      api.payments.create({
        order_id: orderId,
        method,
        amount: Number(amount),
        trx_ref: trx || undefined,
        sender_number: sender || undefined,
        note: [proofNote, proofUrl].filter(Boolean).join(' | ') || undefined,
      }),
    onSuccess: () => {
      setOrderId('')
      setAmount('')
      setTrx('')
      setProofNote('')
      setProofUrl('')
      setSender('')
      setShowRecordModal(false)
      qc.invalidateQueries({ queryKey: ['payments'] })
    },
  })

  async function onProofFile(file: File | null) {
    if (!file) return
    setUploading(true)
    try {
      const res = await api.media.upload(file)
      setProofUrl(res.url)
      if (!proofNote) setProofNote(`Proof: ${file.name}`)
    } finally {
      setUploading(false)
    }
  }

  const confirm = useMutation({
    mutationFn: (id: string) => api.payments.confirm(id),
    onSuccess: () => {
      setConfirmId(null)
      qc.invalidateQueries({ queryKey: ['payments'] })
    },
  })

  const currency = shop.data?.currency ?? 'BDT'

  const methodIcons: Record<string, () => ReactNode> = {
    bkash: () => (
      <svg width="40" height="40" viewBox="0 0 40 40" fill="none">
        <rect x="2" y="2" width="36" height="36" rx="10" fill="#E2136E" />
        <path
          d="M11 20L20 11L29 20L24 29H16L11 20Z"
          stroke="white"
          strokeWidth="2.4"
          fill="none"
          strokeLinejoin="round"
        />
        <circle cx="20" cy="20" r="3" fill="white" />
      </svg>
    ),
    nagad: () => (
      <svg width="40" height="40" viewBox="0 0 40 40" fill="none">
        <defs>
          <linearGradient id="nagadPayGrad" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="#F7941D" />
            <stop offset="100%" stopColor="#D8232A" />
          </linearGradient>
        </defs>
        <rect x="2" y="2" width="36" height="36" rx="10" fill="url(#nagadPayGrad)" />
        <path
          d="M13 27V13L27 27V13"
          stroke="white"
          strokeWidth="2.8"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    ),
    card: () => (
      <svg width="40" height="40" viewBox="0 0 40 40" fill="none">
        <rect x="2" y="2" width="36" height="36" rx="10" fill="#635BFF" />
        <rect x="8" y="13" width="24" height="15" rx="3" stroke="white" strokeWidth="2.2" fill="none" />
        <line x1="8" y1="18" x2="32" y2="18" stroke="white" strokeWidth="2.2" />
        <circle cx="13" cy="23" r="1.5" fill="white" />
      </svg>
    ),
    stripe: () => (
      <svg width="40" height="40" viewBox="0 0 40 40" fill="none">
        <rect x="2" y="2" width="36" height="36" rx="10" fill="#635BFF" />
        <path
          d="M23.5 16.5C23.5 14.8 22 13.8 20 13.8C17.5 13.8 15.5 15 15.5 15L14.5 12C14.5 12 17 10.8 20.5 10.8C24.5 10.8 27.2 13 27.2 16.8C27.2 21.8 20.2 21.5 20.2 23.5C20.2 24.5 21.2 25 22.8 25C25.2 25 27 24 27 24L28 27C28 27 25.5 28.2 22.2 28.2C18.2 28.2 16.5 26 16.5 23C16.5 18.2 23.5 18.5 23.5 16.5Z"
          fill="white"
        />
      </svg>
    ),
    bank: () => (
      <svg width="40" height="40" viewBox="0 0 40 40" fill="none">
        <rect x="2" y="2" width="36" height="36" rx="10" fill="#0284c7" />
        <path d="M12 26H28M13 22V17M18 22V17M22 22V17M27 22V17M11 15L20 10L29 15H11Z" stroke="white" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    ),
    cod: () => (
      <svg width="40" height="40" viewBox="0 0 40 40" fill="none">
        <rect x="2" y="2" width="36" height="36" rx="10" fill="#059669" />
        <rect x="8" y="12" width="24" height="16" rx="3" stroke="white" strokeWidth="2.2" />
        <circle cx="20" cy="20" r="3.5" stroke="white" strokeWidth="2" />
      </svg>
    ),
    cash: () => (
      <svg width="40" height="40" viewBox="0 0 40 40" fill="none">
        <rect x="2" y="2" width="36" height="36" rx="10" fill="#059669" />
        <rect x="8" y="12" width="24" height="16" rx="3" stroke="white" strokeWidth="2.2" />
        <circle cx="20" cy="20" r="3.5" stroke="white" strokeWidth="2" />
      </svg>
    ),
  }

  const copyToClipboard = (text: string, id: string) => {
    navigator.clipboard.writeText(text)
    setCopiedId(id)
    setTimeout(() => setCopiedId(null), 2000)
  }

  const paymentList = payments.data ?? []
  const totalAmount = paymentList.reduce((acc, p) => acc + (p.amount || 0), 0)
  const pendingCount = paymentList.filter((p) => p.status === 'pending').length
  const needsReviewCount = paymentList.filter((p) => p.status === 'needs_review').length
  const confirmedCount = paymentList.filter((p) => p.status === 'confirmed').length

  return (
    <>
      <PageHeader
        title={t('payments')}
        subtitle="Automated matching queue, payment proof verification, and AI double-entry ledger reconciliation."
        actions={
          <div className="payments-header-actions">
            <button
              type="button"
              onClick={() => toggleAuto.mutate()}
              className={`ai-auto-toggle-btn ${autoConfirm ? 'active' : ''}`}
            >
              <Zap size={14} className={autoConfirm ? 'text-blue-600' : 'text-gray-400'} />
              <span>AI Auto-Confirm: {autoConfirm ? 'Active' : 'Off'}</span>
            </button>

            <Button onClick={() => setShowRecordModal(true)}>
              <Plus size={16} />
              <span>Record Payment</span>
            </Button>
          </div>
        }
      />

      {/* Summary KPI Counters (Exact match aesthetic) */}
      <div className="payment-kpi-grid">
        <div className="payment-kpi-card gradient-highlight">
          <div className="payment-kpi-title blue">
            Total Payment Volume
          </div>
          <div className="payment-kpi-value">
            {money(totalAmount, currency)}
          </div>
          <div className="payment-kpi-sub">
            {paymentList.length} transactions recorded
          </div>
        </div>

        <div className="payment-kpi-card">
          <div className="payment-kpi-title sky">
            Pending Verification
          </div>
          <div className="payment-kpi-value">
            {pendingCount}
          </div>
          <div className="payment-kpi-sub">
            Awaiting TrxID match
          </div>
        </div>

        <div className="payment-kpi-card">
          <div className="payment-kpi-title amber">
            Needs Human Review
          </div>
          <div className="payment-kpi-value">
            {needsReviewCount}
          </div>
          <div className="payment-kpi-sub">
            Manual screenshot check
          </div>
        </div>

        <div className="payment-kpi-card">
          <div className="payment-kpi-title emerald">
            Confirmed & Reconciled
          </div>
          <div className="payment-kpi-value">
            {confirmedCount}
          </div>
          <div className="payment-kpi-sub">
            Settled to general ledger
          </div>
        </div>
      </div>

      {/* Filter Navigation Tabs */}
      <div className="payment-filter-nav">
        {[
          { key: '', label: 'All Transactions', count: paymentList.length },
          { key: 'pending', label: 'Pending', count: pendingCount },
          { key: 'needs_review', label: 'Needs Review', count: needsReviewCount },
          { key: 'confirmed', label: 'Confirmed', count: confirmedCount },
          { key: 'rejected', label: 'Rejected', count: 0 },
        ].map((f) => (
          <button
            key={f.key || 'all'}
            type="button"
            onClick={() => setFilter(f.key)}
            className={`payment-filter-tab ${filter === f.key ? 'active' : ''}`}
          >
            <span>{f.label}</span>
            <span className="payment-tab-badge">
              {f.count}
            </span>
          </button>
        ))}
      </div>

      {/* Payment Queue Cards Section */}
      <div className="channels-section-container">
        <div className="channels-header-bar">
          <div className="channels-title-row">
            <span className="channels-title-icon">
              <LayoutGrid size={20} strokeWidth={2.4} />
            </span>
            <h2 className="channels-heading-text">PAYMENT PROOF & MATCHING QUEUE</h2>
          </div>
          <div className="live-sync-pill">
            <span className="live-sync-dot" />
            <span>Live IPN Sync</span>
          </div>
        </div>

        {payments.isLoading ? (
          <Loading />
        ) : payments.isError ? (
          <ErrorBox error={payments.error} />
        ) : !paymentList.length ? (
          <EmptyState
            title="No matching payments"
            hint="Record manual payments or connect bKash/Nagad/Stripe in Integrations to auto-receive webhook proofs."
          />
        ) : (
          <div className="active-channels-grid">
            {paymentList.map((p) => {
              const proof = extractProofUrl(p.note)
              const iconFn = methodIcons[p.method.toLowerCase()] || methodIcons.bkash
              const isConfirmed = p.status === 'confirmed'
              const isNeedsReview = p.status === 'needs_review'

              return (
                <div key={p.id} className="channel-card-modern">
                  <div>
                    {/* Top Row: Method Icon + Brand Details + Status */}
                    <div className="channel-top-row">
                      <div className="channel-brand-group">
                        <div className="channel-brand-icon-wrap">{iconFn()}</div>
                        <div className="channel-brand-info">
                          <h3 className="payment-method-heading">{p.method} Payment</h3>
                          <p className="channel-brand-sub">
                            Order Ref: <strong>#{shortId(p.order_id)}</strong> &bull; ID: {shortId(p.id)}
                          </p>
                        </div>
                      </div>

                      {isConfirmed ? (
                        <div className="channel-status-pill-active channel-status-pill-emerald">
                          <span className="channel-status-active-dot emerald" />
                          <span>Confirmed</span>
                        </div>
                      ) : isNeedsReview ? (
                        <div className="channel-status-pill-active channel-status-pill-amber">
                          <span className="channel-status-active-dot amber" />
                          <span>Needs Review</span>
                        </div>
                      ) : (
                        <div className="channel-status-pill-active">
                          <span className="channel-status-active-dot" />
                          <span>Pending Match</span>
                        </div>
                      )}
                    </div>

                    {/* Prominent Amount Display */}
                    <div className="payment-amount-box">
                      <div className="payment-amount-label">
                        Payment Amount
                      </div>
                      <div className="payment-amount-num">
                        {money(p.amount, currency)}
                      </div>
                    </div>

                    {/* Metadata Checklist */}
                    <div className="channel-features-list">
                      <div className="channel-feature-bullet">
                        <svg className="channel-feature-check" viewBox="0 0 24 24" fill="none" stroke="#2563eb" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                          <circle cx="12" cy="12" r="10" stroke="#3b82f6" />
                          <path d="m9 12 2 2 4-4" stroke="#2563eb" />
                        </svg>
                        <span>
                          Trx Ref: <strong>{p.trx_ref || 'Awaiting TrxID'}</strong>
                        </span>
                        {p.trx_ref ? (
                          <button
                            type="button"
                            onClick={() => copyToClipboard(p.trx_ref!, p.id)}
                            className="payment-copy-btn"
                            title="Copy TrxID"
                          >
                            {copiedId === p.id ? <CheckCircle2 size={14} color="#16a34a" /> : <Copy size={14} />}
                          </button>
                        ) : null}
                      </div>

                      <div className="channel-feature-bullet">
                        <svg className="channel-feature-check" viewBox="0 0 24 24" fill="none" stroke="#2563eb" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                          <circle cx="12" cy="12" r="10" stroke="#3b82f6" />
                          <path d="m9 12 2 2 4-4" stroke="#2563eb" />
                        </svg>
                        <span>
                          Sender Mobile / Account: <strong>{p.sender_number || 'Direct API checkout'}</strong>
                        </span>
                      </div>

                      <div className="channel-feature-bullet">
                        <svg className="channel-feature-check" viewBox="0 0 24 24" fill="none" stroke="#2563eb" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                          <circle cx="12" cy="12" r="10" stroke="#3b82f6" />
                          <path d="m9 12 2 2 4-4" stroke="#2563eb" />
                        </svg>
                        <span>Proof Details: {proofLabel(p.note) || 'Electronic ledger entry'}</span>
                      </div>
                    </div>
                  </div>

                  {/* Bottom Action & Proof Preview Block */}
                  <div className="channel-account-block">
                    {proof ? (
                      <div className="payment-proof-bar">
                        <div className="payment-proof-meta">
                          <span className="payment-proof-label">
                            Attachment: {proofLabel(p.note)}
                          </span>
                        </div>
                        <button
                          type="button"
                          onClick={() => api.media.open(proof)}
                          className="payment-view-proof-btn"
                        >
                          <ExternalLink size={13} />
                          <span>View Proof</span>
                        </button>
                      </div>
                    ) : null}

                    {isConfirmed ? (
                      <>
                        <button type="button" disabled className="channel-btn-limit-reached">
                          Settled & Posted to Ledger
                        </button>
                        <p className="channel-limit-caption">
                          Payment has been validated and synced with general account balance.
                        </p>
                      </>
                    ) : (
                      <button
                        type="button"
                        className="channel-connect-button"
                        onClick={() => setConfirmId(p.id)}
                        disabled={confirm.isPending}
                      >
                        <CheckCircle2 size={18} strokeWidth={2.4} />
                        <span>Confirm & Reconcile Payment</span>
                      </button>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* Confirmation Dialog */}
      <ConfirmDialog
        open={Boolean(confirmId)}
        title="Confirm & Reconcile Payment?"
        message="This validates the payment proof and immediately posts an entry to the financial ledger for this order."
        busy={confirm.isPending}
        confirmLabel="Confirm Payment"
        onCancel={() => setConfirmId(null)}
        onConfirm={() => confirmId && confirm.mutate(confirmId)}
      />

      {/* Record Payment Modal */}
      {showRecordModal ? (
        <div className="channel-modal-overlay" onClick={() => setShowRecordModal(false)}>
          <div className="channel-modal-dialog" onClick={(e) => e.stopPropagation()}>
            <div className="payment-modal-header">
              <div className="payment-modal-icon">
                <Plus size={22} strokeWidth={2.4} />
              </div>
              <div>
                <h3 className="payment-modal-title">Record Manual Payment</h3>
                <p className="muted payment-modal-sub">
                  Link a customer payment proof to an order
                </p>
              </div>
            </div>

            <form
              onSubmit={(e) => {
                e.preventDefault()
                create.mutate()
              }}
              className="stack payment-modal-form"
            >
              <label className="field-label payment-field-label-flat">
                Order ID
                <Input
                  value={orderId}
                  onChange={(e) => setOrderId(e.target.value)}
                  placeholder="Order UUID or Short ID"
                  required
                />
              </label>

              <div className="payment-modal-grid-2">
                <label className="field-label payment-field-label-flat">
                  Method
                  <Select value={method} onChange={(e) => setMethod(e.target.value)}>
                    {['bkash', 'nagad', 'card', 'bank', 'cash', 'cod'].map((m) => (
                      <option key={m} value={m}>
                        {m.toUpperCase()}
                      </option>
                    ))}
                  </Select>
                </label>

                <label className="field-label payment-field-label-flat">
                  Amount ({currency})
                  <Input
                    type="number"
                    step="0.01"
                    value={amount}
                    onChange={(e) => setAmount(e.target.value)}
                    placeholder="0.00"
                    required
                  />
                </label>
              </div>

              <div className="payment-modal-grid-2">
                <label className="field-label payment-field-label-flat">
                  Trx Reference (Optional)
                  <Input
                    value={trx}
                    onChange={(e) => setTrx(e.target.value)}
                    placeholder="e.g. 9J3K81LZ"
                  />
                </label>

                <label className="field-label payment-field-label-flat">
                  Sender Number (Optional)
                  <Input
                    value={sender}
                    onChange={(e) => setSender(e.target.value)}
                    placeholder="e.g. 01700-000000"
                  />
                </label>
              </div>

              <label className="field-label payment-field-label-flat">
                Proof Screenshot / Receipt
                <Input
                  type="file"
                  accept="image/*"
                  onChange={(e) => onProofFile(e.target.files?.[0] ?? null)}
                  disabled={uploading}
                />
              </label>
              {uploading ? <div className="muted">Uploading screenshot proof…</div> : null}
              {proofUrl ? <div className="muted payment-proof-success">Attachment uploaded successfully.</div> : null}

              <div className="payment-modal-actions">
                <Button type="button" variant="secondary" onClick={() => setShowRecordModal(false)}>
                  Cancel
                </Button>
                <Button type="submit" disabled={create.isPending || uploading}>
                  {create.isPending ? 'Recording…' : 'Record & Match Payment'}
                </Button>
              </div>
            </form>
          </div>
        </div>
      ) : null}
    </>
  )
}
