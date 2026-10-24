import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { Plus } from 'lucide-react'
import { api } from '../api/endpoints'
import { shortId, statusLabel } from '../lib/format'
import { useAuth } from '../auth/AuthContext'
import { roleAtLeast } from '../lib/roles'
import { usePollingQuery } from '../hooks/usePollingQuery'
import { useLocale } from '../i18n/LocaleContext'
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
  StatTile,
  Table,
  Textarea,
} from '../components/ui/primitives'

export function CallsPage() {
  const { t } = useLocale()
  const qc = useQueryClient()
  const { role } = useAuth()
  const isAdmin = roleAtLeast(role, 'admin')
  const [customerId, setCustomerId] = useState('')
  const [script, setScript] = useState('')
  const [monitorId, setMonitorId] = useState<string | null>(null)
  const [opening, setOpening] = useState('')
  const [voiceName, setVoiceName] = useState('')
  const [forbidden, setForbidden] = useState('')
  const [overflow, setOverflow] = useState('human_queue')
  const [hoursStart, setHoursStart] = useState('09:00')
  const [hoursEnd, setHoursEnd] = useState('21:00')
  const [maxLines, setMaxLines] = useState('3')
  const [prioritizeRepeat, setPrioritizeRepeat] = useState(true)
  const [showAddModal, setShowAddModal] = useState(false)

  const customers = useQuery({ queryKey: ['customers'], queryFn: () => api.customers.list() })
  const calls = usePollingQuery(['calls'], api.calls.list, 5000)
  const persona = useQuery({
    queryKey: ['voice-persona'],
    queryFn: api.calls.voicePersona,
    enabled: isAdmin,
  })
  const routing = useQuery({
    queryKey: ['call-routing'],
    queryFn: api.calls.routing,
    enabled: isAdmin,
  })
  const metrics = useQuery({
    queryKey: ['call-metrics'],
    queryFn: api.calls.metrics,
    enabled: isAdmin,
  })
  const dialects = useQuery({
    queryKey: ['dialects'],
    queryFn: api.dialects.list,
    enabled: isAdmin,
  })
  const monitored = useQuery({
    queryKey: ['call', monitorId],
    queryFn: () => api.calls.get(monitorId!),
    enabled: Boolean(monitorId),
    refetchInterval: monitorId ? 3000 : false,
  })

  useEffect(() => {
    if (!persona.data) return
    setVoiceName(persona.data.voice_name || persona.data.name || '')
    setOpening(persona.data.opening_script || '')
    setForbidden((persona.data.forbidden_topics || []).join(', '))
  }, [persona.data])

  useEffect(() => {
    if (!routing.data) return
    setOverflow(routing.data.overflow_action || 'human_queue')
    setHoursStart(String(routing.data.business_hours_start || '09:00').slice(0, 5))
    setHoursEnd(String(routing.data.business_hours_end || '21:00').slice(0, 5))
    setMaxLines(String(routing.data.max_concurrent_human_lines ?? 3))
    setPrioritizeRepeat(Boolean(routing.data.prioritize_repeat_customers ?? true))
  }, [routing.data])

  const outbound = useMutation({
    mutationFn: () => api.calls.outbound(customerId, script || undefined),
    onSuccess: () => {
      setCustomerId('')
      setScript('')
      setShowAddModal(false)
      qc.invalidateQueries({ queryKey: ['calls'] })
    },
  })
  const monitor = useMutation({
    mutationFn: (id: string) => api.calls.monitor(id),
    onSuccess: (data) => setMonitorId(data.id),
  })
  const handover = useMutation({
    mutationFn: (id: string) => api.calls.handover(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['calls'] })
      if (monitorId) qc.invalidateQueries({ queryKey: ['call', monitorId] })
    },
  })
  const savePersona = useMutation({
    mutationFn: () =>
      api.calls.updateVoicePersona({
        voice_name: voiceName || undefined,
        opening_script: opening || undefined,
        forbidden_topics: forbidden
          .split(',')
          .map((s) => s.trim())
          .filter(Boolean),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['voice-persona'] }),
  })
  const saveRouting = useMutation({
    mutationFn: () =>
      api.calls.updateRouting({
        overflow_action: overflow,
        business_hours_start: hoursStart,
        business_hours_end: hoursEnd,
        max_concurrent_human_lines: Number(maxLines) || 3,
        prioritize_repeat_customers: prioritizeRepeat,
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['call-routing'] }),
  })
  const toggleDialect = useMutation({
    mutationFn: ({ id, enabled }: { id: string; enabled: boolean }) =>
      api.dialects.toggle(id, enabled),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['dialects'] }),
  })
  const simulate = useMutation({
    mutationFn: () => api.ai.simulateCall({ opening_message: opening || undefined }),
  })

  return (
    <>
      <PageHeader
        title={t('calls')}
        subtitle="Outbound, monitor, persona, routing rules, dialects, and metrics (FR-CALL / FR-VPER)."
        actions={
          <Button onClick={() => setShowAddModal(true)}>
            <Plus size={15} style={{ marginRight: 6 }} />
            Outbound Call
          </Button>
        }
      />

      {isAdmin && metrics.data ? (
        <div className="stat-grid">
          {Object.entries(metrics.data)
            .slice(0, 4)
            .map(([k, v]) => (
              <StatTile key={k} label={k.replace(/_/g, ' ')} value={String(v ?? '—')} />
            ))}
        </div>
      ) : null}

      <Panel title="Call list">
          {calls.isLoading ? (
            <Loading />
          ) : !calls.data?.length ? (
            <EmptyState title="No calls yet" />
          ) : (
            <Table>
              <thead>
                <tr>
                  <th>Call</th>
                  <th>Direction</th>
                  <th>Status</th>
                  <th>AI</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {calls.data.map((c) => (
                  <tr key={c.id}>
                    <td>{shortId(c.id)}</td>
                    <td>{c.direction}</td>
                    <td>
                      <Badge>{statusLabel(c.status)}</Badge>
                    </td>
                    <td>{c.handled_by_ai ? 'yes' : 'no'}</td>
                    <td className="row">
                      {isAdmin ? (
                        <Button size="sm" variant="secondary" onClick={() => monitor.mutate(c.id)}>
                          Monitor
                        </Button>
                      ) : null}
                      <Button size="sm" onClick={() => handover.mutate(c.id)}>
                        Handover
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </Table>
          )}
        </Panel>

        <Panel title="Live monitor">
            {!monitorId ? (
              <EmptyState title="No call selected" hint="Click Monitor on a call." />
            ) : monitored.isLoading ? (
              <Loading label="Joining…" />
            ) : (
              <div className="stack">
                <div className="row" style={{ justifyContent: 'space-between' }}>
                  <strong>{shortId(monitorId)}</strong>
                  <Badge tone="info">{statusLabel(monitored.data?.status ?? '—')}</Badge>
                </div>
                <p className="muted">
                  Live dialect ASR transcript updates over WebSocket when media
                  streaming is active. Provider call SID is in recording_ref.
                </p>
                <div className="demo-hint">
                  {monitored.data?.transcript || 'Waiting for transcript segments…'}
                </div>
                <Button size="sm" variant="secondary" onClick={() => setMonitorId(null)}>
                  Leave monitor
                </Button>
              </div>
            )}
          </Panel>

      <Modal open={showAddModal} title="Outbound call" onClose={() => setShowAddModal(false)}>
        <div className="stack">
          <label className="field-label">
            Customer
            <Select value={customerId} onChange={(e) => setCustomerId(e.target.value)}>
              <option value="">Select customer…</option>
              {(customers.data ?? []).map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name || c.phone || shortId(c.id)}
                </option>
              ))}
            </Select>
          </label>
          <label className="field-label">
            Script note
            <Textarea value={script} onChange={(e) => setScript(e.target.value)} />
          </label>
          {outbound.isError ? <ErrorBox error={outbound.error} /> : null}
          <Button onClick={() => outbound.mutate()} disabled={!customerId || outbound.isPending}>
            Place call
          </Button>
        </div>
      </Modal>

      {isAdmin ? (
        <>
          <div className="grid-2">
            <Panel title="Voice persona">
              <div className="stack">
                <label className="field-label">
                  Voice name
                  <Input value={voiceName} onChange={(e) => setVoiceName(e.target.value)} />
                </label>
                <label className="field-label">
                  Opening script
                  <Textarea value={opening} onChange={(e) => setOpening(e.target.value)} />
                </label>
                <label className="field-label">
                  Forbidden topics (comma-separated)
                  <Input value={forbidden} onChange={(e) => setForbidden(e.target.value)} />
                </label>
                <Button onClick={() => savePersona.mutate()} disabled={savePersona.isPending}>
                  Save persona
                </Button>
                <Button variant="secondary" onClick={() => simulate.mutate()} disabled={simulate.isPending}>
                  Simulate call
                </Button>
                {simulate.data ? (
                  <div className="demo-hint">
                    <div className="muted">{simulate.data.dialect_used}</div>
                    <p>{simulate.data.transcript_preview}</p>
                  </div>
                ) : null}
              </div>
            </Panel>

            <Panel title="Routing rules">
              <div className="stack">
                <label className="field-label">
                  Business hours start
                  <Input type="time" value={hoursStart} onChange={(e) => setHoursStart(e.target.value)} />
                </label>
                <label className="field-label">
                  Business hours end
                  <Input type="time" value={hoursEnd} onChange={(e) => setHoursEnd(e.target.value)} />
                </label>
                <label className="field-label">
                  Overflow action
                  <Select value={overflow} onChange={(e) => setOverflow(e.target.value)}>
                    <option value="human_queue">Human queue</option>
                    <option value="voicemail">Voicemail</option>
                    <option value="callback">Callback</option>
                    <option value="ai_continue">AI continue</option>
                  </Select>
                </label>
                <label className="field-label">
                  Max concurrent human lines
                  <Input type="number" value={maxLines} onChange={(e) => setMaxLines(e.target.value)} />
                </label>
                <div className="toggle-row">
                  <strong>Prioritize repeat customers</strong>
                  <button
                    type="button"
                    className={`switch ${prioritizeRepeat ? 'on' : ''}`}
                    onClick={() => setPrioritizeRepeat((v) => !v)}
                  />
                </div>
                {saveRouting.isError ? <ErrorBox error={saveRouting.error} /> : null}
                <Button onClick={() => saveRouting.mutate()} disabled={saveRouting.isPending}>
                  Save routing
                </Button>
              </div>
            </Panel>
          </div>

          <Panel title="Dialect packs">
            {!dialects.data?.length ? (
              <EmptyState title="No dialect packs" />
            ) : (
              <Table>
                <thead>
                  <tr>
                    <th>Region</th>
                    <th>Code</th>
                    <th>Accuracy</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {dialects.data.map((d) => (
                    <tr key={d.id}>
                      <td>{d.region_label}</td>
                      <td>{d.language_code}</td>
                      <td>
                        <Badge tone={d.accuracy_status === 'production' ? 'good' : 'warn'}>
                          {d.accuracy_status}
                        </Badge>
                      </td>
                      <td>
                        <Button
                          size="sm"
                          variant="secondary"
                          onClick={() =>
                            toggleDialect.mutate({ id: d.id, enabled: !(d.is_enabled ?? true) })
                          }
                        >
                          Toggle
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            )}
          </Panel>
        </>
      ) : null}
    </>
  )
}
