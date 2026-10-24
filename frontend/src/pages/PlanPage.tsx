import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type ReactNode } from 'react'
import {
  LayoutGrid,
  Sparkles,
  Zap,
  Crown,
  Building2,
  CreditCard,
} from 'lucide-react'
import { api } from '../api/endpoints'
import { money, statusLabel } from '../lib/format'
import { useAuth } from '../auth/AuthContext'
import { ConfirmDialog } from '../components/ui/ConfirmDialog'
import {
  ErrorBox,
  Loading,
  PageHeader,
} from '../components/ui/primitives'
import './PlanPage.css'

export function PlanPage() {
  const qc = useQueryClient()
  const { role } = useAuth()
  const [pendingPlan, setPendingPlan] = useState<string | null>(null)
  const catalogue = useQuery({ queryKey: ['plan-catalogue'], queryFn: api.plan.catalogue })
  const current = useQuery({ queryKey: ['plan'], queryFn: api.plan.current })

  const change = useMutation({
    mutationFn: (plan_code: string) => api.plan.change(plan_code),
    onSuccess: () => {
      setPendingPlan(null)
      qc.invalidateQueries({ queryKey: ['plan'] })
      qc.invalidateQueries({ queryKey: ['shop'] })
    },
  })

  const getPlanIcon = (code: string): ReactNode => {
    if (code.includes('business')) return <Crown size={24} />
    if (code.includes('pro')) return <Sparkles size={24} />
    if (code.includes('enterprise')) return <Building2 size={24} />
    return <Zap size={24} />
  }

  const currentPlan = current.data

  return (
    <>
      <PageHeader
        title="Subscription & Plan Limits"
        subtitle="Manage your shop plan tier, multichannel limits, AI credits, and voice telephony quotas."
      />

      {current.isError ? <ErrorBox error={current.error} /> : null}

      {/* KPI Usage Statistics */}
      <div className="plan-kpi-grid">
        <div className="plan-kpi-card gradient-highlight">
          <div className="plan-kpi-title blue">
            Current Active Plan
          </div>
          <div className="plan-kpi-value capitalize">
            {currentPlan?.plan_code ?? 'Free Plan'}
          </div>
          <div className="plan-kpi-sub">
            Status: {statusLabel(currentPlan?.status ?? 'active')}
          </div>
        </div>

        <div className="plan-kpi-card">
          <div className="plan-kpi-title emerald">
            Monthly AI Credits Left
          </div>
          <div className="plan-kpi-value">
            {currentPlan?.ai_credits_remaining ?? 0}
          </div>
          <div className="plan-kpi-sub">
            {currentPlan?.ai_credits_used_this_month ?? 0} credits consumed this billing cycle
          </div>
        </div>

        <div className="plan-kpi-card">
          <div className="plan-kpi-title purple">
            Subscription Renewal
          </div>
          <div className="plan-kpi-value">
            Auto-Renew
          </div>
          <div className="plan-kpi-sub">
            Cancel or change tiers anytime
          </div>
        </div>
      </div>

      {/* Plan Tier Cards Grid matching Active Channels layout */}
      <div className="channels-section-container">
        <div className="channels-header-bar">
          <div className="channels-title-row">
            <span className="channels-title-icon">
              <LayoutGrid size={20} strokeWidth={2.4} />
            </span>
            <h2 className="channels-heading-text">SUBSCRIPTION TIERS & PRICING</h2>
          </div>
          <div className="live-sync-pill">
            <span className="live-sync-dot" />
            <span>Multi-Channel Plans</span>
          </div>
        </div>

        {catalogue.isLoading ? (
          <Loading />
        ) : (
          <div className="active-channels-grid">
            {(catalogue.data ?? []).map((p) => {
              const isCurrent = currentPlan?.plan_code === p.code

              return (
                <div key={p.code} className="channel-card-modern">
                  <div>
                    <div className="channel-top-row">
                      <div className="channel-brand-group">
                        <div
                          className={`channel-brand-icon-wrap ${isCurrent ? 'channel-brand-icon-primary' : 'channel-brand-icon-slate'}`}
                        >
                          {getPlanIcon(p.code)}
                        </div>
                        <div className="channel-brand-info">
                          <h3>{p.name} Plan</h3>
                          <p className="channel-brand-sub">Tier Code: {p.code}</p>
                        </div>
                      </div>

                      {isCurrent ? (
                        <div className="channel-status-pill-active channel-status-pill-emerald">
                          <span className="channel-status-active-dot emerald" />
                          <span>Current Plan</span>
                        </div>
                      ) : (
                        <span className="channel-status-not-linked">Available</span>
                      )}
                    </div>

                    {/* Price Header */}
                    <div className="plan-price-box">
                      <div className="plan-price-label">
                        Monthly Pricing
                      </div>
                      <div className="plan-price-num">
                        {p.monthly_price === 0 ? 'Free' : `${money(p.monthly_price)} / month`}
                      </div>
                    </div>

                    {/* Features list */}
                    <div className="channel-features-list">
                      <div className="channel-feature-bullet">
                        <svg className="channel-feature-check" viewBox="0 0 24 24" fill="none" stroke="#2563eb" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                          <circle cx="12" cy="12" r="10" stroke="#3b82f6" />
                          <path d="m9 12 2 2 4-4" stroke="#2563eb" />
                        </svg>
                        <span>
                          <strong>{p.channel_limit} Active Channel{p.channel_limit > 1 ? 's' : ''}</strong> (Facebook, IG, TikTok, WhatsApp)
                        </span>
                      </div>

                      <div className="channel-feature-bullet">
                        <svg className="channel-feature-check" viewBox="0 0 24 24" fill="none" stroke="#2563eb" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                          <circle cx="12" cy="12" r="10" stroke="#3b82f6" />
                          <path d="m9 12 2 2 4-4" stroke="#2563eb" />
                        </svg>
                        <span>
                          <strong>{p.monthly_ai_credits.toLocaleString()} AI Credits / month</strong> for auto-replies
                        </span>
                      </div>

                      <div className="channel-feature-bullet">
                        <svg className="channel-feature-check" viewBox="0 0 24 24" fill="none" stroke="#2563eb" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                          <circle cx="12" cy="12" r="10" stroke="#3b82f6" />
                          <path d="m9 12 2 2 4-4" stroke="#2563eb" />
                        </svg>
                        <span>
                          <strong>{p.monthly_voice_minutes} Voice Minutes / month</strong> for AI order calling
                        </span>
                      </div>

                      <div className="channel-feature-bullet">
                        <svg className="channel-feature-check" viewBox="0 0 24 24" fill="none" stroke="#2563eb" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                          <circle cx="12" cy="12" r="10" stroke="#3b82f6" />
                          <path d="m9 12 2 2 4-4" stroke="#2563eb" />
                        </svg>
                        <span>
                          <strong>{p.team_seat_limit} Team Seat{p.team_seat_limit > 1 ? 's' : ''}</strong> with role-based access
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Bottom Action Block */}
                  <div className="channel-account-block">
                    {isCurrent ? (
                      <>
                        <button type="button" disabled className="channel-btn-limit-reached">
                          Current Active Plan
                        </button>
                        <p className="channel-limit-caption">
                          Your shop is currently operating on this subscription tier.
                        </p>
                      </>
                    ) : (
                      <button
                        type="button"
                        className="channel-connect-button"
                        onClick={() => setPendingPlan(p.code)}
                        disabled={change.isPending || role !== 'super_admin'}
                      >
                        <CreditCard size={17} />
                        <span>Switch to {p.name} Plan</span>
                      </button>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* Plan Switch Confirmation Dialog */}
      <ConfirmDialog
        open={Boolean(pendingPlan)}
        title="Confirm Plan Switch?"
        message={`Are you sure you want to change your shop subscription to ${pendingPlan?.toUpperCase()}? Quotas and channel limits will adjust immediately.`}
        busy={change.isPending}
        confirmLabel="Confirm Plan Switch"
        onCancel={() => setPendingPlan(null)}
        onConfirm={() => pendingPlan && change.mutate(pendingPlan)}
      />
    </>
  )
}
