import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useMemo, useState, type ReactNode } from 'react'
import {
  LayoutGrid,
  Plus,
  Zap,
  MessageSquare,
  ShoppingBag,
  Play,
  Pause,
  AlertTriangle,
  GitBranch,
} from 'lucide-react'
import { api } from '../api/endpoints'
import { statusLabel } from '../lib/format'
import { useLocale } from '../i18n/LocaleContext'
import {
  Button,
  EmptyState,
  ErrorBox,
  Input,
  Loading,
  PageHeader,
  Select,
} from '../components/ui/primitives'
import './AutomationsPage.css'

const KINDS = ['all', 'recipe', 'rule', 'workflow', 'scheduled_job', 'sending_rule'] as const

const TRIGGERS = [
  'message.received',
  'order.confirmed',
  'order.delivered',
  'payment.recorded',
  'stock.low',
  'comment.received',
]

const ACTIONS = [
  'send_saved_reply',
  'assign_team_member',
  'create_task',
  'issue_document',
  'notify_owner',
  'tag_customer',
]

type Step = { trigger: string; action: string }

export function AutomationsPage() {
  const { t } = useLocale()
  const qc = useQueryClient()
  const [name, setName] = useState('')
  const [trigger, setTrigger] = useState('message.received')
  const [action, setAction] = useState('send_saved_reply')
  const [kind, setKind] = useState('rule')
  const [tab, setTab] = useState<(typeof KINDS)[number]>('all')
  const [showCreateModal, setShowCreateModal] = useState(false)
  const steps: Step[] = [
    { trigger: 'order.confirmed', action: 'issue_document' },
    { trigger: 'order.confirmed', action: 'notify_owner' },
  ]

  const rules = useQuery({ queryKey: ['automation-rules'], queryFn: api.automation.rules })
  const recipes = useQuery({ queryKey: ['recipes'], queryFn: api.automation.recipes })

  const filteredRules = useMemo(() => {
    const list = rules.data ?? []
    if (tab === 'all') return list
    if (tab === 'recipe') return []
    return list.filter((r) => r.kind === tab)
  }, [rules.data, tab])

  const install = useMutation({
    mutationFn: (code: string) => api.automation.installRecipe(code),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['recipes'] })
      qc.invalidateQueries({ queryKey: ['automation-rules'] })
    },
  })

  const create = useMutation({
    mutationFn: () =>
      api.automation.createRule({
        kind,
        name,
        trigger: kind === 'workflow' ? steps[0]?.trigger || trigger : trigger,
        action: kind === 'workflow' ? 'run_workflow' : action,
        config: kind === 'workflow' ? { steps } : {},
      }),
    onSuccess: () => {
      setName('')
      setShowCreateModal(false)
      qc.invalidateQueries({ queryKey: ['automation-rules'] })
    },
  })

  const toggle = useMutation({
    mutationFn: ({ id, is_active }: { id: string; is_active: boolean }) =>
      api.automation.toggle(id, is_active),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['automation-rules'] }),
  })

  const runs = (rules.data ?? []).reduce((s, r) => s + (r.run_count || 0), 0)
  const fails = (rules.data ?? []).reduce((s, r) => s + (r.failure_count || 0), 0)
  const activeCount = (rules.data ?? []).filter((r) => r.is_active).length

  const getTriggerIcon = (tr: string): ReactNode => {
    if (tr.includes('message') || tr.includes('comment')) return <MessageSquare size={22} />
    if (tr.includes('order')) return <ShoppingBag size={22} />
    if (tr.includes('payment')) return <Zap size={22} />
    if (tr.includes('stock')) return <AlertTriangle size={22} />
    return <GitBranch size={22} />
  }

  return (
    <>
      <PageHeader
        title={t('automations')}
        subtitle="Pre-built recipe gallery, automated triggers, and multi-step customer workflow automations."
        actions={
          <Button onClick={() => setShowCreateModal(true)}>
            <Plus size={16} />
            <span>Create Automation</span>
          </Button>
        }
      />

      {/* Summary KPI Stats */}
      <div className="automation-kpi-grid">
        <div className="automation-kpi-card gradient-highlight">
          <div className="automation-kpi-title blue">
            Active Automations
          </div>
          <div className="automation-kpi-value">
            {activeCount} Active
          </div>
          <div className="automation-kpi-sub">
            Across all channels & webhooks
          </div>
        </div>

        <div className="automation-kpi-card">
          <div className="automation-kpi-title emerald">
            Automated Executions
          </div>
          <div className="automation-kpi-value">
            {runs.toLocaleString()}
          </div>
          <div className="automation-kpi-sub">
            Total trigger dispatches
          </div>
        </div>

        <div className="automation-kpi-card">
          <div className={`automation-kpi-title ${fails > 0 ? 'red' : 'emerald'}`}>
            Execution Failures
          </div>
          <div className={`automation-kpi-value ${fails > 0 ? 'red' : ''}`}>
            {fails}
          </div>
          <div className="automation-kpi-sub">
            {fails === 0 ? '100% health & reliability' : 'Requires inspection'}
          </div>
        </div>
      </div>

      {/* Sub-navigation Pills */}
      <div className="automation-filter-nav">
        {KINDS.map((k) => (
          <button
            key={k}
            type="button"
            onClick={() => setTab(k)}
            className={`automation-filter-tab ${tab === k ? 'active' : ''}`}
          >
            <span>{statusLabel(k)}</span>
          </button>
        ))}
      </div>

      {/* 1. Pre-Built Recipe Gallery (When tab is 'all' or 'recipe') */}
      {(tab === 'all' || tab === 'recipe') && (
        <div className="channels-section-container automation-section-margin">
          <div className="channels-header-bar">
            <div className="channels-title-row">
              <span className="channels-title-icon">
                <LayoutGrid size={20} strokeWidth={2.4} />
              </span>
              <h2 className="channels-heading-text">1-CLICK PRE-BUILT RECIPE GALLERY</h2>
            </div>
            <div className="live-sync-pill">
              <span className="live-sync-dot" />
              <span>Tested & Ready</span>
            </div>
          </div>

          {recipes.isLoading ? (
            <Loading />
          ) : !recipes.data?.length ? (
            <EmptyState title="No recipes in catalogue" />
          ) : (
            <div className="active-channels-grid">
              {recipes.data.map((r) => {
                const isInstalled = r.installed

                return (
                  <div key={r.code} className="channel-card-modern">
                    <div>
                      <div className="channel-top-row">
                        <div className="channel-brand-group">
                          <div className="channel-brand-icon-wrap automation-recipe-icon">
                            <Zap size={24} />
                          </div>
                          <div className="channel-brand-info">
                            <h3>{r.name}</h3>
                            <p className="channel-brand-sub">Recipe Code: {r.code}</p>
                          </div>
                        </div>

                        {isInstalled ? (
                          <div className="channel-status-pill-active">
                            <span className="channel-status-active-dot" />
                            <span>Active</span>
                          </div>
                        ) : (
                          <span className="channel-status-not-linked">Available</span>
                        )}
                      </div>

                      <div className="channel-usage-counter">
                        Trigger: <code>{r.trigger}</code> &bull; Action: <code>{r.action}</code>
                      </div>

                      <p className="automation-recipe-desc">
                        {r.description}
                      </p>

                      <div className="channel-features-list">
                        <div className="channel-feature-bullet">
                          <svg className="channel-feature-check" viewBox="0 0 24 24" fill="none" stroke="#2563eb" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                            <circle cx="12" cy="12" r="10" stroke="#3b82f6" />
                            <path d="m9 12 2 2 4-4" stroke="#2563eb" />
                          </svg>
                          <span>Automated background worker execution</span>
                        </div>
                        <div className="channel-feature-bullet">
                          <svg className="channel-feature-check" viewBox="0 0 24 24" fill="none" stroke="#2563eb" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                            <circle cx="12" cy="12" r="10" stroke="#3b82f6" />
                            <path d="m9 12 2 2 4-4" stroke="#2563eb" />
                          </svg>
                          <span>Idempotent delivery with automatic retry handling</span>
                        </div>
                        <div className="channel-feature-bullet">
                          <svg className="channel-feature-check" viewBox="0 0 24 24" fill="none" stroke="#2563eb" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                            <circle cx="12" cy="12" r="10" stroke="#3b82f6" />
                            <path d="m9 12 2 2 4-4" stroke="#2563eb" />
                          </svg>
                          <span>Real-time event sync across all connected channels</span>
                        </div>
                      </div>
                    </div>

                    <div className="channel-account-block">
                      {isInstalled ? (
                        <>
                          <button type="button" disabled className="channel-btn-limit-reached">
                            Installed & Running
                          </button>
                          <p className="channel-limit-caption">
                            Recipe is active. You can manage or customize it under Active Rules.
                          </p>
                        </>
                      ) : (
                        <button
                          type="button"
                          className="channel-connect-button"
                          onClick={() => install.mutate(r.code)}
                          disabled={install.isPending}
                        >
                          <Plus size={18} strokeWidth={2.4} />
                          <span>1-Click Enable Recipe</span>
                        </button>
                      )}
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      )}

      {/* 2. Active Automation Rules */}
      {tab !== 'recipe' && (
        <div className="channels-section-container">
          <div className="channels-header-bar">
            <div className="channels-title-row">
              <span className="channels-title-icon">
                <LayoutGrid size={20} strokeWidth={2.4} />
              </span>
              <h2 className="channels-heading-text">ACTIVE AUTOMATION RULES & WORKFLOWS</h2>
            </div>
            <div className="live-sync-pill">
              <span className="live-sync-dot" />
              <span>Real-Time Dispatch</span>
            </div>
          </div>

          {rules.isLoading ? (
            <Loading />
          ) : rules.isError ? (
            <ErrorBox error={rules.error} />
          ) : !filteredRules.length ? (
            <EmptyState
              title="No rules found in this filter"
              hint="Enable a recipe from above or click 'Create Automation' to build custom workflows."
            />
          ) : (
            <div className="active-channels-grid">
              {filteredRules.map((r) => {
                const isActive = r.is_active

                return (
                  <div key={r.id} className="channel-card-modern">
                    <div>
                      <div className="channel-top-row">
                        <div className="channel-brand-group">
                          <div className="channel-brand-icon-wrap automation-recipe-icon">
                            {getTriggerIcon(r.trigger)}
                          </div>
                          <div className="channel-brand-info">
                            <h3>{r.name}</h3>
                            <p className="channel-brand-sub">
                              Kind: <strong>{statusLabel(r.kind)}</strong>
                            </p>
                          </div>
                        </div>

                        {isActive ? (
                          <div className="channel-status-pill-active">
                            <span className="channel-status-active-dot" />
                            <span>Active</span>
                          </div>
                        ) : (
                          <span className="channel-status-not-linked">Paused</span>
                        )}
                      </div>

                      <div className="channel-usage-counter">
                        Executed <strong>{r.run_count || 0} times</strong> &bull; {r.failure_count || 0} failures
                      </div>

                      <div className="channel-features-list">
                        <div className="channel-feature-bullet">
                          <svg className="channel-feature-check" viewBox="0 0 24 24" fill="none" stroke="#2563eb" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                            <circle cx="12" cy="12" r="10" stroke="#3b82f6" />
                            <path d="m9 12 2 2 4-4" stroke="#2563eb" />
                          </svg>
                          <span>Trigger Event: <code>{r.trigger}</code></span>
                        </div>
                        <div className="channel-feature-bullet">
                          <svg className="channel-feature-check" viewBox="0 0 24 24" fill="none" stroke="#2563eb" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                            <circle cx="12" cy="12" r="10" stroke="#3b82f6" />
                            <path d="m9 12 2 2 4-4" stroke="#2563eb" />
                          </svg>
                          <span>Automated Action: <code>{r.action}</code></span>
                        </div>
                        <div className="channel-feature-bullet">
                          <svg className="channel-feature-check" viewBox="0 0 24 24" fill="none" stroke="#2563eb" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                            <circle cx="12" cy="12" r="10" stroke="#3b82f6" />
                            <path d="m9 12 2 2 4-4" stroke="#2563eb" />
                          </svg>
                          <span>Fast event listener with zero queue lag</span>
                        </div>
                      </div>
                    </div>

                    <div className="channel-account-block">
                      <button
                        type="button"
                        className={isActive ? 'channel-btn-limit-reached automation-btn-active-toggle' : 'channel-connect-button'}
                        onClick={() => toggle.mutate({ id: r.id, is_active: !isActive })}
                        disabled={toggle.isPending}
                      >
                        {isActive ? (
                          <span className="automation-inline-flex">
                            <Pause size={15} /> Pause Automation
                          </span>
                        ) : (
                          <span className="automation-inline-flex">
                            <Play size={15} /> Enable Automation
                          </span>
                        )}
                      </button>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      )}

      {/* Create Automation Modal */}
      {showCreateModal && (
        <div className="channel-modal-overlay" onClick={() => setShowCreateModal(false)}>
          <div className="channel-modal-dialog" onClick={(e) => e.stopPropagation()}>
            <div className="automation-modal-header">
              <div className="automation-modal-icon">
                <Plus size={22} strokeWidth={2.4} />
              </div>
              <div>
                <h3 className="automation-modal-title">Create Automation Rule</h3>
                <p className="muted automation-modal-sub">
                  Define an event trigger and automated response action
                </p>
              </div>
            </div>

            <form
              onSubmit={(e) => {
                e.preventDefault()
                create.mutate()
              }}
              className="stack automation-modal-form"
            >
              <label className="field-label automation-field-label-flat">
                Automation Rule Name
                <Input
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g. Auto-Reply to New Message"
                  required
                  autoFocus
                />
              </label>

              <label className="field-label automation-field-label-flat">
                Automation Kind
                <Select
                  value={kind}
                  onChange={(e) => {
                    setKind(e.target.value)
                  }}
                >
                  {['rule', 'workflow', 'scheduled_job', 'sending_rule'].map((k) => (
                    <option key={k} value={k}>
                      {statusLabel(k)}
                    </option>
                  ))}
                </Select>
              </label>

              <div className="automation-modal-grid-2">
                <label className="field-label automation-field-label-flat">
                  Event Trigger
                  <Select value={trigger} onChange={(e) => setTrigger(e.target.value)}>
                    {TRIGGERS.map((tr) => (
                      <option key={tr} value={tr}>
                        {tr}
                      </option>
                    ))}
                  </Select>
                </label>

                <label className="field-label automation-field-label-flat">
                  Automated Action
                  <Select value={action} onChange={(e) => setAction(e.target.value)}>
                    {ACTIONS.map((a) => (
                      <option key={a} value={a}>
                        {a}
                      </option>
                    ))}
                  </Select>
                </label>
              </div>

              {create.isError ? <ErrorBox error={create.error} /> : null}

              <div className="automation-modal-actions">
                <Button type="button" variant="secondary" onClick={() => setShowCreateModal(false)}>
                  Cancel
                </Button>
                <Button type="submit" disabled={!name || create.isPending}>
                  {create.isPending ? 'Saving…' : 'Create & Activate Rule'}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </>
  )
}
