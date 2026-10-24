import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  Store,
  ArrowRight,
  Sparkles,
  Package,
  Layers,
  Users,
  CheckCircle2,
} from 'lucide-react'
import { api } from '../api/endpoints'
import { useLocale } from '../i18n/LocaleContext'
import {
  Button,
  ErrorBox,
  Input,
  Loading,
  PageHeader,
  Panel,
  Textarea,
  Select,
} from '../components/ui/primitives'

const DAYS = [
  ['mon', 'Monday'],
  ['tue', 'Tuesday'],
  ['wed', 'Wednesday'],
  ['thu', 'Thursday'],
  ['fri', 'Friday'],
  ['sat', 'Saturday'],
  ['sun', 'Sunday'],
] as const

export function SettingsPage() {
  const { t } = useLocale()
  const qc = useQueryClient()
  const shop = useQuery({ queryKey: ['shop'], queryFn: api.shop.me })

  // Core shop profile
  const [name, setName] = useState('')
  const [category, setCategory] = useState('')
  const [address, setAddress] = useState('')
  const [inside, setInside] = useState('')
  const [outside, setOutside] = useState('')
  const [logoUrl, setLogoUrl] = useState('')
  const [uploadingLogo, setUploadingLogo] = useState(false)

  // Payment methods configuration
  const [bkashNumber, setBkashNumber] = useState('')
  const [bkashType, setBkashType] = useState('Personal')
  const [nagadNumber, setNagadNumber] = useState('')
  const [nagadType, setNagadType] = useState('Personal')
  const [rocketNumber, setRocketNumber] = useState('')
  const [bankDetails, setBankDetails] = useState('')
  const [codInstructions, setCodInstructions] = useState('')

  // Toggles & Moderation
  const [autoSpam, setAutoSpam] = useState(true)
  const [autoPhone, setAutoPhone] = useState(true)
  const [autoReplyComments, setAutoReplyComments] = useState(false)

  // Hours
  const [hours, setHours] = useState<Record<string, string>>({
    mon: '10:00-20:00',
    tue: '10:00-20:00',
    wed: '10:00-20:00',
    thu: '10:00-20:00',
    fri: '10:00-20:00',
    sat: '10:00-20:00',
    sun: 'Closed',
  })

  useEffect(() => {
    if (!shop.data) return
    setName(shop.data.name || '')
    setCategory(shop.data.category ?? '')
    setAddress(shop.data.address ?? '')
    setInside(String(shop.data.delivery_charge_inside_city ?? ''))
    setOutside(String(shop.data.delivery_charge_outside_city ?? ''))
    setAutoSpam(shop.data.auto_hide_spam_comments)
    setAutoPhone(shop.data.auto_hide_phone_numbers_in_comments)
    setAutoReplyComments(shop.data.ai_auto_reply_comments ?? false)

    const toggles = (shop.data.ai_module_toggles || {}) as Record<string, any>
    setLogoUrl(toggles.logo_url || '')

    const pm = (toggles.payment_methods || {}) as Record<string, any>
    setBkashNumber(pm.bkash_number || '')
    setBkashType(pm.bkash_type || 'Personal')
    setNagadNumber(pm.nagad_number || '')
    setNagadType(pm.nagadType || pm.nagad_type || 'Personal')
    setRocketNumber(pm.rocket_number || '')
    setBankDetails(pm.bank_details || '')
    setCodInstructions(pm.cod_instructions || '')

    if (shop.data.opening_hours && Object.keys(shop.data.opening_hours).length) {
      setHours((prev) => ({ ...prev, ...shop.data.opening_hours }))
    }
  }, [shop.data])

  const save = useMutation({
    mutationFn: () =>
      api.shop.update({
        name,
        category: category || null,
        address: address || null,
        delivery_charge_inside_city: inside ? Number(inside) : null,
        delivery_charge_outside_city: outside ? Number(outside) : null,
        auto_hide_spam_comments: autoSpam,
        auto_hide_phone_numbers_in_comments: autoPhone,
        ai_auto_reply_comments: autoReplyComments,
        opening_hours: hours,
        ai_module_toggles: {
          ...(shop.data?.ai_module_toggles || {}),
          logo_url: logoUrl || undefined,
          payment_methods: {
            bkash_number: bkashNumber || undefined,
            bkash_type: bkashType,
            nagad_number: nagadNumber || undefined,
            nagad_type: nagadType,
            rocket_number: rocketNumber || undefined,
            bank_details: bankDetails || undefined,
            cod_instructions: codInstructions || undefined,
          },
        },
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['shop'] })
      qc.invalidateQueries({ queryKey: ['checklist'] })
    },
  })

  async function handleLogoUpload(file: File | null) {
    if (!file) return
    setUploadingLogo(true)
    try {
      const res = await api.media.upload(file)
      setLogoUrl(res.url)
    } finally {
      setUploadingLogo(false)
    }
  }

  return (
    <>
      <PageHeader
        title={t('settings')}
        subtitle="Configure store profile, branding, payment methods, delivery zones, opening hours, and AI moderation."
      />

      {/* QUICK ONBOARDING & EDIT HUB */}
      <div
        style={{
          background: '#ffffff',
          borderRadius: 14,
          padding: '1.25rem 1.5rem',
          border: '1px solid #e2e8f0',
          marginBottom: '1.5rem',
          boxShadow: '0 2px 8px rgba(0,0,0,0.03)',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.75rem', marginBottom: '1rem' }}>
          <div>
            <h3 style={{ margin: 0, fontSize: '1.05rem', fontWeight: 600, color: '#0f172a' }}>
              Setup & Configuration Hub
            </h3>
            <p style={{ margin: 0, fontSize: '0.86rem', color: '#64748b' }}>
              Jump directly to edit or reconfigure any component of your storefront anytime:
            </p>
          </div>
          <Link to="/setup" style={{ textDecoration: 'none' }}>
            <span style={{ fontSize: '0.85rem', color: '#2563eb', fontWeight: 600, display: 'flex', alignItems: 'center', gap: 4 }}>
              View Full Launch Checklist <ArrowRight size={14} />
            </span>
          </Link>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '0.75rem' }}>
          <Link to="/setup" style={{ textDecoration: 'none' }}>
            <div style={{ padding: '0.75rem', borderRadius: 8, background: '#f8fafc', border: '1px solid #e2e8f0', display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
              <CheckCircle2 size={18} color="#10b981" />
              <div>
                <strong style={{ fontSize: '0.84rem', color: '#0f172a', display: 'block' }}>Milestones</strong>
                <span style={{ fontSize: '0.75rem', color: '#64748b' }}>Edit Setup Steps</span>
              </div>
            </div>
          </Link>

          <Link to="/ai-training" style={{ textDecoration: 'none' }}>
            <div style={{ padding: '0.75rem', borderRadius: 8, background: '#f8fafc', border: '1px solid #e2e8f0', display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
              <Sparkles size={18} color="#6366f1" />
              <div>
                <strong style={{ fontSize: '0.84rem', color: '#0f172a', display: 'block' }}>AI Knowledge</strong>
                <span style={{ fontSize: '0.75rem', color: '#64748b' }}>Train Model & Rules</span>
              </div>
            </div>
          </Link>

          <Link to="/products" style={{ textDecoration: 'none' }}>
            <div style={{ padding: '0.75rem', borderRadius: 8, background: '#f8fafc', border: '1px solid #e2e8f0', display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
              <Package size={18} color="#f59e0b" />
              <div>
                <strong style={{ fontSize: '0.84rem', color: '#0f172a', display: 'block' }}>Products</strong>
                <span style={{ fontSize: '0.75rem', color: '#64748b' }}>Catalogue & Stock</span>
              </div>
            </div>
          </Link>

          <Link to="/integrations" style={{ textDecoration: 'none' }}>
            <div style={{ padding: '0.75rem', borderRadius: 8, background: '#f8fafc', border: '1px solid #e2e8f0', display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
              <Layers size={18} color="#06b6d4" />
              <div>
                <strong style={{ fontSize: '0.84rem', color: '#0f172a', display: 'block' }}>Channels</strong>
                <span style={{ fontSize: '0.75rem', color: '#64748b' }}>Facebook & Meta Hub</span>
              </div>
            </div>
          </Link>

          <Link to="/team" style={{ textDecoration: 'none' }}>
            <div style={{ padding: '0.75rem', borderRadius: 8, background: '#f8fafc', border: '1px solid #e2e8f0', display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
              <Users size={18} color="#8b5cf6" />
              <div>
                <strong style={{ fontSize: '0.84rem', color: '#0f172a', display: 'block' }}>Team & Roles</strong>
                <span style={{ fontSize: '0.75rem', color: '#64748b' }}>Invite Teammates</span>
              </div>
            </div>
          </Link>
        </div>
      </div>

      {shop.isLoading ? (
        <Loading />
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(420px, 1fr))', gap: '1.5rem' }}>
          {/* SECTION 1: SHOP IDENTITY & BRANDING */}
          <Panel title="Shop Profile & Branding">
            <div className="stack" style={{ gap: '1rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '1.25rem' }}>
                <div
                  style={{
                    width: 72,
                    height: 72,
                    borderRadius: 12,
                    background: '#f1f5f9',
                    border: '1.5px dashed #cbd5e1',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    overflow: 'hidden',
                    flexShrink: 0,
                  }}
                >
                  {logoUrl ? (
                    <img src={logoUrl} alt="Store logo" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                  ) : (
                    <Store size={32} color="#94a3b8" />
                  )}
                </div>
                <div style={{ flex: 1 }}>
                  <label className="field-label" style={{ marginBottom: '0.35rem' }}>
                    Store Logo
                  </label>
                  <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                    <Input
                      placeholder="https://example.com/logo.png"
                      value={logoUrl}
                      onChange={(e) => setLogoUrl(e.target.value)}
                    />
                    <label
                      style={{
                        padding: '0.45rem 0.85rem',
                        background: '#f1f5f9',
                        borderRadius: 8,
                        cursor: 'pointer',
                        fontSize: '0.85rem',
                        fontWeight: 600,
                        color: '#334155',
                        whiteSpace: 'nowrap',
                        border: '1px solid #cbd5e1',
                      }}
                    >
                      {uploadingLogo ? 'Uploading...' : 'Upload'}
                      <input
                        type="file"
                        accept="image/*"
                        style={{ display: 'none' }}
                        onChange={(e) => handleLogoUpload(e.target.files?.[0] ?? null)}
                      />
                    </label>
                  </div>
                </div>
              </div>

              <label className="field-label">
                Shop name
                <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. My Awesome Shop" />
              </label>

              <label className="field-label">
                Business category
                <Input value={category} onChange={(e) => setCategory(e.target.value)} placeholder="e.g. Fashion, Electronics, Political Campaign" />
              </label>

              <label className="field-label">
                Store physical address
                <Input value={address} onChange={(e) => setAddress(e.target.value)} placeholder="House, Road, Area, Dhaka" />
              </label>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                <label className="field-label">
                  Delivery charge (inside city)
                  <Input type="number" value={inside} onChange={(e) => setInside(e.target.value)} placeholder="60" />
                </label>
                <label className="field-label">
                  Delivery charge (outside city)
                  <Input type="number" value={outside} onChange={(e) => setOutside(e.target.value)} placeholder="120" />
                </label>
              </div>
            </div>
          </Panel>

          {/* SECTION 2: HOW YOU GET PAID (PAYMENT METHODS) */}
          <Panel title="How You Get Paid (Payment Accounts)">
            <div className="stack" style={{ gap: '1rem' }}>
              <p style={{ margin: 0, fontSize: '0.86rem', color: '#64748b' }}>
                Configure numbers and accounts provided to customers and used by AI during order confirmations.
              </p>

              <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '0.75rem' }}>
                <label className="field-label">
                  bKash Number
                  <Input
                    placeholder="01700-000000"
                    value={bkashNumber}
                    onChange={(e) => setBkashNumber(e.target.value)}
                  />
                </label>
                <label className="field-label">
                  Account Type
                  <Select value={bkashType} onChange={(e) => setBkashType(e.target.value)}>
                    <option value="Personal">Personal</option>
                    <option value="Merchant">Merchant</option>
                    <option value="Agent">Agent</option>
                  </Select>
                </label>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '0.75rem' }}>
                <label className="field-label">
                  Nagad Number
                  <Input
                    placeholder="01800-000000"
                    value={nagadNumber}
                    onChange={(e) => setNagadNumber(e.target.value)}
                  />
                </label>
                <label className="field-label">
                  Account Type
                  <Select value={nagadType} onChange={(e) => setNagadType(e.target.value)}>
                    <option value="Personal">Personal</option>
                    <option value="Merchant">Merchant</option>
                    <option value="Agent">Agent</option>
                  </Select>
                </label>
              </div>

              <label className="field-label">
                Rocket Number (Optional)
                <Input
                  placeholder="01900-000000-8"
                  value={rocketNumber}
                  onChange={(e) => setRocketNumber(e.target.value)}
                />
              </label>

              <label className="field-label">
                Bank Transfer Details (Optional)
                <Textarea
                  placeholder="Bank: City Bank, Account Name: Store Ltd, A/C: 123456789, Branch: Gulshan"
                  value={bankDetails}
                  onChange={(e) => setBankDetails(e.target.value)}
                  rows={2}
                />
              </label>

              <label className="field-label">
                Cash on Delivery (COD) Instructions
                <Input
                  placeholder="e.g. Available nationwide. Pay courier upon package inspection."
                  value={codInstructions}
                  onChange={(e) => setCodInstructions(e.target.value)}
                />
              </label>
            </div>
          </Panel>

          {/* SECTION 3: OPENING HOURS */}
          <Panel title="Opening & Operating Hours">
            <div className="stack" style={{ gap: '0.65rem' }}>
              <p style={{ margin: 0, fontSize: '0.86rem', color: '#64748b' }}>
                Used by the AI to answer operating schedule queries and schedule delivery orders accurately.
              </p>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem' }}>
                {DAYS.map(([key, label]) => (
                  <label className="field-label" key={key} style={{ fontSize: '0.82rem' }}>
                    {label}
                    <Input
                      value={hours[key] ?? ''}
                      onChange={(e) => setHours((h) => ({ ...h, [key]: e.target.value }))}
                      placeholder="10:00-20:00 or Closed"
                    />
                  </label>
                ))}
              </div>
            </div>
          </Panel>

          {/* SECTION 4: AI COMMENT MODERATION & AUTO-REPLY */}
          <Panel title="Comment Moderation & Auto-Reply">
            <div className="stack" style={{ gap: '1rem' }}>
              <div className="toggle-row">
                <div>
                  <strong>Auto-hide spam comments</strong>
                  <div className="muted" style={{ fontSize: '0.82rem' }}>
                    Instantly hides derogatory comments and repetitive spam across all connected Meta pages.
                  </div>
                </div>
                <button
                  type="button"
                  className={`switch ${autoSpam ? 'on' : ''}`}
                  onClick={() => setAutoSpam((v) => !v)}
                />
              </div>

              <div className="toggle-row">
                <div>
                  <strong>Auto-hide phone numbers in comments</strong>
                  <div className="muted" style={{ fontSize: '0.82rem' }}>
                    Safeguards customer privacy by hiding phone numbers posted publicly on posts.
                  </div>
                </div>
                <button
                  type="button"
                  className={`switch ${autoPhone ? 'on' : ''}`}
                  onClick={() => setAutoPhone((v) => !v)}
                />
              </div>

              <div className="toggle-row">
                <div>
                  <strong>AI auto-reply on public comments</strong>
                  <div className="muted" style={{ fontSize: '0.82rem' }}>
                    Instructs the AI orchestrator to answer public Facebook & Instagram comment queries.
                  </div>
                </div>
                <button
                  type="button"
                  className={`switch ${autoReplyComments ? 'on' : ''}`}
                  onClick={() => setAutoReplyComments((v) => !v)}
                />
              </div>
            </div>
          </Panel>
        </div>
      )}

      {/* SAVE ACTIONS BAR */}
      <div
        style={{
          marginTop: '1.5rem',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          background: '#ffffff',
          padding: '1rem 1.5rem',
          borderRadius: 12,
          border: '1px solid #e2e8f0',
        }}
      >
        <div>
          {save.isError ? <ErrorBox error={save.error} /> : null}
          {save.isSuccess ? (
            <span style={{ color: '#16a34a', fontWeight: 600, display: 'flex', alignItems: 'center', gap: 6 }}>
              <CheckCircle2 size={16} /> All settings saved and synchronized successfully.
            </span>
          ) : (
            <span className="muted">All changes update your live shop profile and AI knowledge base.</span>
          )}
        </div>
        <Button onClick={() => save.mutate()} disabled={!name || save.isPending}>
          {save.isPending ? 'Saving...' : t('save')}
        </Button>
      </div>
    </>
  )
}
