import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import {
  LayoutGrid,
  Server,
  Store,
  Palette,
  ShoppingBag,
  Share2,
  CreditCard,
  Bot,
  Users,
  ArrowRight,
  ShieldCheck,
} from 'lucide-react'
import { api } from '../api/endpoints'
import { useLocale } from '../i18n/LocaleContext'
import {
  Button,
  EmptyState,
  ErrorBox,
  Loading,
  PageHeader,
} from '../components/ui/primitives'
import './SetupPage.css'

const STEP_LINKS: Record<string, string> = {
  logo_and_shop_name: '/settings',
  address_and_delivery_charges: '/settings',
  add_first_products: '/products',
  connect_facebook_page: '/integrations',
  how_you_get_paid: '/settings',
  teach_ai_how_shop_works: '/ai-training',
  invite_a_teammate: '/team',
}

export function SetupPage() {
  const { t } = useLocale()
  const checklist = useQuery({ queryKey: ['checklist'], queryFn: api.shop.checklist })
  const shop = useQuery({ queryKey: ['shop'], queryFn: api.shop.me })
  const providers = useQuery({ queryKey: ['system-providers'], queryFn: api.system.providers })

  const remainingMinutes =
    checklist.data?.steps.filter((s) => !s.is_done).reduce((sum, s) => sum + s.estimated_minutes, 0) ??
    0

  const providerEntries = Object.entries(providers.data?.providers ?? {})
  const configuredCount = providerEntries.filter(([, p]) => p.configured).length

  const getStepIcon = (key: string) => {
    if (key.includes('logo') || key.includes('shop')) return <Store size={22} />
    if (key.includes('address') || key.includes('delivery')) return <Palette size={22} />
    if (key.includes('product')) return <ShoppingBag size={22} />
    if (key.includes('facebook') || key.includes('channel')) return <Share2 size={22} />
    if (key.includes('paid') || key.includes('payment')) return <CreditCard size={22} />
    if (key.includes('ai') || key.includes('teach')) return <Bot size={22} />
    return <Users size={22} />
  }

  return (
    <>
      <PageHeader
        title={t('setup')}
        subtitle="Guided checklist for profile, catalogue, channels, and external cloud provider credentials."
        actions={
          <Link to="/integrations">
            <Button>
              <Share2 size={16} />
              <span>Connect Channels</span>
            </Button>
          </Link>
        }
      />

      {checklist.isError ? <ErrorBox error={checklist.error} /> : null}

      {/* KPI Status Cards */}
      <div className="setup-kpi-grid">
        <div className="setup-kpi-card gradient-highlight">
          <div className="setup-kpi-title blue">
            Setup Progress
          </div>
          <div className="setup-kpi-value">
            {checklist.data?.percent_complete ?? 0}% Complete
          </div>
          <div className="setup-kpi-sub">
            {checklist.data?.steps_done ?? 0} of {checklist.data?.steps_total ?? 0} milestones finished
          </div>
        </div>

        <div className="setup-kpi-card">
          <div className="setup-kpi-title sky">
            Est. Time Remaining
          </div>
          <div className="setup-kpi-value">
            ~{remainingMinutes} minutes
          </div>
          <div className="setup-kpi-sub">
            To complete initial store launch
          </div>
        </div>

        <div className="setup-kpi-card">
          <div className="setup-kpi-title emerald">
            Shop Account
          </div>
          <div className="setup-kpi-value truncate">
            {shop.data?.name ?? 'Demo Shop'}
          </div>
          <div className="setup-kpi-sub">
            Category: {shop.data?.category || 'general_retail'}
          </div>
        </div>

        <div className="setup-kpi-card">
          <div className="setup-kpi-title purple">
            Cloud Providers Ready
          </div>
          <div className="setup-kpi-value">
            {configuredCount} / {providerEntries.length || 5}
          </div>
          <div className="setup-kpi-sub">
            AI, Voice, Meta & SMTP
          </div>
        </div>
      </div>

      {/* 1. ONBOARDING CHECKLIST MILESTONES (Cards Grid) */}
      <div className="channels-section-container">
        <div className="channels-header-bar">
          <div className="channels-title-row">
            <span className="channels-title-icon">
              <LayoutGrid size={20} strokeWidth={2.4} />
            </span>
            <h2 className="channels-heading-text">LAUNCH CHECKLIST & MILESTONES</h2>
          </div>
          <div className="live-sync-pill">
            <span className="live-sync-dot" />
            <span>Store Guided Setup</span>
          </div>
        </div>

        {checklist.isLoading ? (
          <Loading />
        ) : !checklist.data?.steps.length ? (
          <EmptyState title="No checklist steps available" />
        ) : (
          <div className="active-channels-grid">
            {checklist.data.steps.map((step) => {
              const isDone = step.is_done
              const to = STEP_LINKS[step.key] || '/settings'

              return (
                <div key={step.key} className="channel-card-modern">
                  <div>
                    <div className="channel-top-row">
                      <div className="channel-brand-group">
                        <div
                          className={`channel-brand-icon-wrap ${isDone ? 'channel-brand-icon-primary' : 'channel-brand-icon-slate'}`}
                        >
                          {getStepIcon(step.key)}
                        </div>
                        <div className="channel-brand-info">
                          <h3>{step.label}</h3>
                          <p className="channel-brand-sub">
                            Category: <strong>{step.group}</strong> &bull; ~{step.estimated_minutes} min
                          </p>
                        </div>
                      </div>

                      {isDone ? (
                        <div className="channel-status-pill-active channel-status-pill-emerald">
                          <span className="channel-status-active-dot emerald" />
                          <span>Done</span>
                        </div>
                      ) : (
                        <div className="channel-status-pill-active">
                          <span className="channel-status-active-dot" />
                          <span>Action Needed</span>
                        </div>
                      )}
                    </div>

                    <div className="channel-usage-counter">
                      Est. Time: {step.estimated_minutes} minutes to configure
                    </div>

                    <div className="channel-features-list">
                      <div className="channel-feature-bullet">
                        <svg className="channel-feature-check" viewBox="0 0 24 24" fill="none" stroke="#2563eb" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                          <circle cx="12" cy="12" r="10" stroke="#3b82f6" />
                          <path d="m9 12 2 2 4-4" stroke="#2563eb" />
                        </svg>
                        <span>Automated onboarding milestone for store launch</span>
                      </div>
                      <div className="channel-feature-bullet">
                        <svg className="channel-feature-check" viewBox="0 0 24 24" fill="none" stroke="#2563eb" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                          <circle cx="12" cy="12" r="10" stroke="#3b82f6" />
                          <path d="m9 12 2 2 4-4" stroke="#2563eb" />
                        </svg>
                        <span>Direct integration with AI orchestrator & multichannel hub</span>
                      </div>
                    </div>
                  </div>

                  <div className="channel-account-block">
                    {isDone ? (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem', width: '100%' }}>
                        <Link to={to} className="setup-link-full">
                          <button
                            type="button"
                            className="channel-connect-button"
                            style={{
                              background: '#f8fafc',
                              color: '#0f172a',
                              border: '1.5px solid #cbd5e1',
                              boxShadow: '0 2px 6px rgba(0,0,0,0.04)',
                            }}
                          >
                            <span>Edit / Reconfigure Step</span>
                            <ArrowRight size={16} />
                          </button>
                        </Link>
                        <p className="channel-limit-caption">
                          Milestone completed. Click above anytime to edit or update.
                        </p>
                      </div>
                    ) : (
                      <Link to={to} className="setup-link-full">
                        <button type="button" className="channel-connect-button">
                          <span>Complete Step Now</span>
                          <ArrowRight size={16} />
                        </button>
                      </Link>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* 2. EXTERNAL CLOUD PROVIDERS STATUS (Cards Grid) */}
      <div className="channels-section-container setup-section-top-margin">
        <div className="channels-header-bar">
          <div className="channels-title-row">
            <span className="channels-title-icon">
              <Server size={20} strokeWidth={2.4} />
            </span>
            <h2 className="channels-heading-text">SYSTEM CLOUD & AI PROVIDERS</h2>
          </div>
          <div className="live-sync-pill">
            <span className="live-sync-dot" />
            <span>Infrastructure Health</span>
          </div>
        </div>

        {providers.isLoading ? (
          <Loading />
        ) : (
          <div className="active-channels-grid">
            {providerEntries.map(([key, p]) => (
              <div key={key} className="channel-card-modern setup-provider-card">
                <div>
                  <div className="channel-top-row">
                    <div className="channel-brand-group">
                      <div
                        className={`channel-brand-icon-wrap ${p.configured ? 'channel-brand-icon-primary' : 'channel-brand-icon-slate'}`}
                      >
                        <ShieldCheck size={22} />
                      </div>
                      <div className="channel-brand-info">
                        <h3>{p.label}</h3>
                        <p className="channel-brand-sub">Provider Key: {key}</p>
                      </div>
                    </div>

                    {p.configured ? (
                      <div className="channel-status-pill-active">
                        <span className="channel-status-active-dot" />
                        <span>Configured</span>
                      </div>
                    ) : (
                      <span className="channel-status-not-linked">Optional</span>
                    )}
                  </div>

                  <div className="channel-features-list setup-provider-features">
                    <div className="channel-feature-bullet">
                      <svg className="channel-feature-check" viewBox="0 0 24 24" fill="none" stroke="#2563eb" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                        <circle cx="12" cy="12" r="10" stroke="#3b82f6" />
                        <path d="m9 12 2 2 4-4" stroke="#2563eb" />
                      </svg>
                      <span>
                        {p.configured ? 'Active credentials loaded from backend environment' : 'Core shop functions work without this provider'}
                      </span>
                    </div>
                  </div>
                </div>

                <div className="channel-account-block">
                  <div className="setup-provider-note">
                    {p.configured ? 'Ready for production traffic' : 'Add credentials in backend/.env to activate'}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </>
  )
}
