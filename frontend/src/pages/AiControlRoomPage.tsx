import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/endpoints'
import { useLocale } from '../i18n/LocaleContext'
import { Badge, Button, ErrorBox, Loading, PageHeader, Panel, StatTile } from '../components/ui/primitives'

const MODULES = [
  { key: 'conversations', label: 'Conversations', hint: 'DM autopilot replies (opt-in)' },
  { key: 'comments', label: 'Comments', hint: 'Public comment auto-replies' },
  { key: 'studio', label: 'Studio', hint: 'Social captions and scheduling' },
  { key: 'fulfilment', label: 'Fulfilment', hint: 'Packing and courier prompts' },
  { key: 'money', label: 'Money', hint: 'Payment matching drafts' },
  { key: 'customers', label: 'Customers', hint: 'Loyalty and segment suggestions' },
  { key: 'team', label: 'Team', hint: 'Shift drafts and hygiene alerts' },
  { key: 'voice', label: 'Voice / Calling', hint: 'Inbound and outbound AI calls' },
  { key: 'guardian', label: 'Guardian', hint: 'Escalate stuck automations' },
]

const DEFAULT_TOGGLES = Object.fromEntries(
  // DM autopilot off by default; comments on when shop.ai_auto_reply_comments is also on
  MODULES.map((m) => [m.key, m.key !== 'guardian' && m.key !== 'conversations']),
)

export function AiControlRoomPage() {
  const { t } = useLocale()
  const qc = useQueryClient()
  const [toggles, setToggles] = useState<Record<string, boolean>>(DEFAULT_TOGGLES)

  const shop = useQuery({ queryKey: ['shop'], queryFn: api.shop.me })
  const plan = useQuery({ queryKey: ['plan'], queryFn: api.plan.current })
  const catalogue = useQuery({ queryKey: ['plan-catalogue'], queryFn: api.plan.catalogue })
  const rules = useQuery({ queryKey: ['automation-rules'], queryFn: api.automation.rules })
  const pending = useQuery({ queryKey: ['ai-pending'], queryFn: api.ai.pending })
  const loyalty = useQuery({
    queryKey: ['loyalty', 'waiting'],
    queryFn: () => api.loyalty.list('waiting'),
  })
  const payments = useQuery({
    queryKey: ['payments', 'pending'],
    queryFn: () => api.payments.list('pending'),
  })
  const products = useQuery({ queryKey: ['products'], queryFn: () => api.products.list() })
  const ragStatus = useQuery({ queryKey: ['ai-rag-status'], queryFn: api.ai.ragStatus })

  useEffect(() => {
    if (shop.data?.ai_module_toggles && Object.keys(shop.data.ai_module_toggles).length) {
      setToggles({ ...DEFAULT_TOGGLES, ...shop.data.ai_module_toggles })
    }
  }, [shop.data])

  const saveToggles = useMutation({
    mutationFn: (next: Record<string, boolean>) =>
      api.shop.update({ ai_module_toggles: next }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['shop'] }),
  })

  const toggleRule = useMutation({
    mutationFn: ({ id, is_active }: { id: string; is_active: boolean }) =>
      api.automation.toggle(id, is_active),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['automation-rules'] }),
  })

  function flip(key: string) {
    const next = { ...toggles, [key]: !toggles[key] }
    setToggles(next)
    saveToggles.mutate(next)
  }

  const failed = rules.data?.filter((r) => r.failure_count > 0) ?? []
  const lowStockCount =
    products.data?.flatMap((p) => p.variants.filter((v) => v.stock_qty <= v.reorder_point)).length ??
    0

  const tasks = useMemo(() => {
    const items: { id: string; title: string; to: string; tone: 'warn' | 'danger' | 'info' }[] = []
    for (const p of payments.data ?? []) {
      items.push({
        id: `pay-${p.id}`,
        title: `Review payment ${p.method} · ${p.amount}`,
        to: '/payments',
        tone: 'warn',
      })
    }
    for (const k of pending.data ?? []) {
      items.push({
        id: `know-${k.id}`,
        title: `Approve knowledge: ${k.title}`,
        to: '/ai-training',
        tone: 'info',
      })
    }
    for (const l of loyalty.data ?? []) {
      items.push({
        id: `loy-${l.id}`,
        title: `Loyalty draft: ${l.milestone}`,
        to: '/loyalty',
        tone: 'warn',
      })
    }
    for (const r of failed) {
      items.push({
        id: `rule-${r.id}`,
        title: `Fix automation: ${r.name}`,
        to: '/automations',
        tone: 'danger',
      })
    }
    if (lowStockCount > 0) {
      items.push({
        id: 'stock',
        title: `${lowStockCount} low-stock variants need attention`,
        to: '/inventory',
        tone: 'warn',
      })
    }
    return items.slice(0, 12)
  }, [payments.data, pending.data, loyalty.data, failed, lowStockCount])

  const planMeta = catalogue.data?.find((p) => p.code === plan.data?.plan_code)
  const creditLimit = planMeta?.monthly_ai_credits ?? 0
  const used = plan.data?.ai_credits_used_this_month ?? 0
  const remaining = plan.data?.ai_credits_remaining ?? 0
  const creditPct =
    creditLimit > 0 ? Math.min(100, Math.round((remaining / creditLimit) * 100)) : 0

  return (
    <>
      <PageHeader
        title={t('aiControl')}
        subtitle="Daily tasks, module switches, AI credit meter, and escalations."
        actions={
          <div className="row" style={{ gap: '8px' }}>
            <Badge tone={ragStatus.data?.ollama_online ? 'good' : 'neutral'}>
              Ollama: {ragStatus.data?.chat_model ?? 'Local'} ({ragStatus.data?.embed_model ?? 'RAG'})
            </Badge>
            <Link to="/ai/train">
              <Button size="sm" variant="secondary">
                RAG Studio
              </Button>
            </Link>
          </div>
        }
      />

      <div className="stat-grid">
        <StatTile label="Credits left" value={remaining} tone="good" />
        <StatTile label="Used this month" value={used} />
        <StatTile
          label="Local RAG Vector Store"
          value={`${ragStatus.data?.knowledge_indexed ?? 0} facts / ${ragStatus.data?.products_indexed ?? 0} prods`}
          hint={ragStatus.data?.ollama_online ? 'Ollama vector search active' : 'Offline'}
          tone={ragStatus.data?.ollama_online ? 'good' : 'default'}
        />
        <StatTile
          label="Open tasks"
          value={tasks.length}
          tone={tasks.length ? 'warn' : 'default'}
        />
      </div>

      <Panel title="AI credit meter">
        <div className="row" style={{ justifyContent: 'space-between' }}>
          <strong>
            {remaining} / {creditLimit || '—'} credits remaining
          </strong>
          <span className="muted">{plan.data?.plan_code ?? '—'}</span>
        </div>
        <div className="credit-meter">
          <span style={{ width: `${creditPct}%` }} />
        </div>
      </Panel>

      <div className="grid-2">
        <Panel title="Daily task list">
          {!tasks.length ? (
            <p className="muted">Nothing queued for today. Escalations will appear here.</p>
          ) : (
            <div className="stack">
              {tasks.map((task) => (
                <div className="row" key={task.id} style={{ justifyContent: 'space-between' }}>
                  <div>
                    <strong>{task.title}</strong>
                  </div>
                  <div className="row">
                    <Badge tone={task.tone}>todo</Badge>
                    <Link to={task.to}>
                      <Button size="sm" variant="secondary">
                        Open
                      </Button>
                    </Link>
                  </div>
                </div>
              ))}
            </div>
          )}
        </Panel>

        <Panel title="Module switches (saved)">
          {MODULES.map((m) => (
            <div className="toggle-row" key={m.key}>
              <div>
                <strong>{m.label}</strong>
                <div className="muted">{m.hint}</div>
              </div>
              <button
                type="button"
                className={`switch ${toggles[m.key] ? 'on' : ''}`}
                aria-pressed={toggles[m.key]}
                onClick={() => flip(m.key)}
              />
            </div>
          ))}
          {saveToggles.isError ? <ErrorBox error={saveToggles.error} /> : null}
        </Panel>
      </div>

      <Panel title="Escalation feed">
        {rules.isLoading ? (
          <Loading />
        ) : rules.isError ? (
          <ErrorBox error={rules.error} />
        ) : !failed.length && !(pending.data?.length || loyalty.data?.length) ? (
          <p className="muted">All clear — no failed automations or review queues.</p>
        ) : (
          <div className="stack">
            {failed.map((r) => (
              <div className="row" key={r.id} style={{ justifyContent: 'space-between' }}>
                <div>
                  <strong>{r.name}</strong>
                  <div className="muted">
                    {r.failure_count} failures · {r.trigger}
                  </div>
                </div>
                <div className="row">
                  <Badge tone="danger">needs attention</Badge>
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={() => toggleRule.mutate({ id: r.id, is_active: !r.is_active })}
                  >
                    {r.is_active ? 'Pause' : 'Resume'}
                  </Button>
                  <Link to="/automations">
                    <Button size="sm" variant="ghost">
                      Open
                    </Button>
                  </Link>
                </div>
              </div>
            ))}
            {(pending.data ?? []).slice(0, 5).map((k) => (
              <div key={k.id} className="row" style={{ justifyContent: 'space-between' }}>
                <div>
                  <strong>{k.title}</strong>
                  <div className="muted">Knowledge awaiting approval</div>
                </div>
                <Link to="/ai-training">
                  <Badge tone="warn">review</Badge>
                </Link>
              </div>
            ))}
            {(loyalty.data ?? []).slice(0, 5).map((l) => (
              <div key={l.id} className="row" style={{ justifyContent: 'space-between' }}>
                <div>
                  <strong>{l.milestone}</strong>
                  <div className="muted">Loyalty reward draft</div>
                </div>
                <Link to="/loyalty">
                  <Badge tone="warn">approve</Badge>
                </Link>
              </div>
            ))}
          </div>
        )}
      </Panel>
    </>
  )
}
