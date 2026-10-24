import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useMemo, useState } from 'react'
import { api } from '../api/endpoints'
import { usePollingQuery } from '../hooks/usePollingQuery'
import { useLocale } from '../i18n/LocaleContext'
import { Sparkles } from 'lucide-react'
import { shortId, statusLabel } from '../lib/format'
import { useAuth } from '../auth/AuthContext'
import { roleAtLeast } from '../lib/roles'
import './InboxPage.css'
import {
  Badge,
  Button,
  EmptyState,
  ErrorBox,
  Input,
  Loading,
  PageHeader,
  Select,
  StatTile,
} from '../components/ui/primitives'

export function InboxPage() {
  const { t } = useLocale()
  const { role } = useAuth()
  const qc = useQueryClient()
  const [status, setStatus] = useState('')
  const [channel, setChannel] = useState('')
  const [selected, setSelected] = useState<string | null>(null)
  const [draft, setDraft] = useState('')
  const [assignee, setAssignee] = useState('')
  const [uploading, setUploading] = useState(false)
  const [newCustomerId, setNewCustomerId] = useState('')
  const [newChannel, setNewChannel] = useState('facebook')

  const stats = usePollingQuery(['inbox-stats'], api.conversations.stats, 8000)
  const list = usePollingQuery(
    ['conversations', status, channel],
    () => api.conversations.list(status || undefined, channel || undefined),
    8000,
  )
  const messages = useQuery({
    queryKey: ['messages', selected],
    queryFn: () => api.conversations.messages(selected!),
    enabled: Boolean(selected),
  })
  const customers = useQuery({ queryKey: ['customers'], queryFn: () => api.customers.list() })
  const replies = useQuery({ queryKey: ['saved-replies'], queryFn: api.savedReplies.list })
  const team = useQuery({
    queryKey: ['team'],
    queryFn: api.team.list,
    enabled: roleAtLeast(role, 'admin'),
  })

  const customerMap = useMemo(
    () => Object.fromEntries((customers.data ?? []).map((c) => [c.id, c])),
    [customers.data],
  )

  const send = useMutation({
    mutationFn: (body?: { type?: string; text?: string; audio_ref?: string }) =>
      api.conversations.send(selected!, {
        direction: 'outbound',
        type: body?.type ?? 'text',
        text: body?.text ?? draft,
        audio_ref: body?.audio_ref,
      }),
    onSuccess: () => {
      setDraft('')
      qc.invalidateQueries({ queryKey: ['messages', selected] })
      qc.invalidateQueries({ queryKey: ['inbox-stats'] })
    },
  })

  async function onAttachImage(file: File | null) {
    if (!file || !selected) return
    setUploading(true)
    try {
      const res = await api.media.upload(file)
      await send.mutateAsync({
        type: 'image',
        text: draft || file.name,
        audio_ref: res.url,
      })
    } finally {
      setUploading(false)
    }
  }

  const handover = useMutation({
    mutationFn: () =>
      api.conversations.handover(selected!, {
        assigned_team_member_id: assignee,
        summary_note: 'Handed over from inbox',
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['conversations'] })
      qc.invalidateQueries({ queryKey: ['messages', selected] })
    },
  })

  const transcribe = useMutation({
    mutationFn: (messageId: string) => api.conversations.transcribe(selected!, messageId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['messages', selected] }),
  })

  const startThread = useMutation({
    mutationFn: () =>
      api.conversations.create({
        customer_id: newCustomerId,
        channel: newChannel,
        initial_message: draft.trim() || undefined,
      }),
    onSuccess: (conv) => {
      setSelected(conv.id)
      setDraft('')
      setNewCustomerId('')
      qc.invalidateQueries({ queryKey: ['conversations'] })
      qc.invalidateQueries({ queryKey: ['messages', conv.id] })
    },
  })

  const aiDraft = useMutation({
    mutationFn: async () => {
      const msgList = messages.data ?? []
      const latestInbound = [...msgList].reverse().find((m) => m.direction === 'inbound')
      const question =
        latestInbound?.text ||
        draft ||
        'Please introduce our store, current popular products, sizes, prices and delivery charges.'
      return api.ai.ask(question)
    },
    onSuccess: (data) => {
      setDraft(data.answer)
    },
  })

  return (
    <>
      <PageHeader
        title={t('inbox')}
        subtitle="Unified inbox with channel filters, saved replies, and handover (FR-CHAT)."
      />

      <div className="stat-grid">
        <StatTile label="Waiting" value={stats.data?.conversations_waiting_for_reply ?? '—'} tone="warn" />
        <StatTile label="Price requests" value={stats.data?.price_request_messages ?? '—'} />
        <StatTile label="Orders from comments" value={stats.data?.orders_from_comments ?? '—'} />
      </div>

      <div className="row">
        <Select value={status} onChange={(e) => setStatus(e.target.value)} className="inbox-status-select">
          <option value="">All statuses</option>
          <option value="open">Open</option>
          <option value="waiting_on_customer">Waiting on customer</option>
          <option value="handed_over">Handed over</option>
          <option value="closed">Closed</option>
        </Select>
        <Select value={channel} onChange={(e) => setChannel(e.target.value)} className="inbox-channel-select">
          <option value="">All channels</option>
          <option value="facebook">Facebook</option>
          <option value="instagram">Instagram</option>
          <option value="tiktok">TikTok</option>
          <option value="whatsapp">WhatsApp</option>
          <option value="telegram">Telegram</option>
          <option value="comment">Comment</option>
          <option value="webhook">Webhook</option>
        </Select>
        <Select
          value={newCustomerId}
          onChange={(e) => setNewCustomerId(e.target.value)}
          className="inbox-customer-select"
        >
          <option value="">Start with customer…</option>
          {(customers.data ?? []).map((c) => (
            <option key={c.id} value={c.id}>
              {c.name || c.phone || c.id.slice(0, 8)}
            </option>
          ))}
        </Select>
        <Select value={newChannel} onChange={(e) => setNewChannel(e.target.value)} className="inbox-channel-select">
          <option value="facebook">Facebook</option>
          <option value="instagram">Instagram</option>
          <option value="whatsapp">WhatsApp</option>
          <option value="telegram">Telegram</option>
        </Select>
        <Button
          size="sm"
          variant="secondary"
          disabled={!newCustomerId || startThread.isPending}
          onClick={() => startThread.mutate()}
        >
          Start thread
        </Button>
      </div>
      {startThread.isError ? <ErrorBox error={startThread.error} /> : null}

      {list.isError ? <ErrorBox error={list.error} /> : null}

      <div className="inbox-layout">
        <div className="thread-list">
          {list.isLoading ? (
            <Loading />
          ) : !list.data?.length ? (
            <EmptyState title="No conversations" />
          ) : (
            list.data.map((c) => {
              const customer = customerMap[c.customer_id]
              return (
                <button
                  key={c.id}
                  type="button"
                  className={`thread-item ${selected === c.id ? 'active' : ''}`}
                  onClick={() => setSelected(c.id)}
                >
                  <div className="inbox-header-row">
                    <strong>{customer?.name || customer?.phone || shortId(c.customer_id)}</strong>
                    <Badge tone="info">{c.channel}</Badge>
                  </div>
                  <div className="muted">{statusLabel(c.status)}</div>
                </button>
              )
            })
          )}
        </div>

        <div className="chat-pane">
          {!selected ? (
            <EmptyState title="Select a conversation" />
          ) : messages.isLoading ? (
            <Loading />
          ) : (
            <>
              <div className="messages">
                {(messages.data ?? []).map((m) => (
                  <div key={m.id} className={`bubble ${m.direction}`}>
                    <div>{m.text || (m.type === 'voice_note' ? 'Voice note' : m.type)}</div>
                    {m.type === 'image' && m.audio_ref ? (
                      <div className="inbox-media-wrap">
                        <img
                          src={m.audio_ref.startsWith('http') ? m.audio_ref : m.audio_ref}
                          alt=""
                          className="inbox-media-img"
                          onError={(e) => {
                            ;(e.target as HTMLImageElement).style.display = 'none'
                          }}
                        />
                        <Button
                          size="sm"
                          variant="secondary"
                          className="inbox-media-audio"
                          onClick={() => api.media.open(m.audio_ref!)}
                        >
                          Open image
                        </Button>
                      </div>
                    ) : null}
                    {m.type === 'voice_note' && !m.text ? (
                      <Button
                        size="sm"
                        variant="secondary"
                        className="inbox-transcribe-btn"
                        onClick={() => transcribe.mutate(m.id)}
                        disabled={transcribe.isPending}
                      >
                        Transcribe
                      </Button>
                    ) : null}
                    <div className="muted inbox-meta-note">
                      {m.detected_language ? `${m.detected_language}` : null}
                      {m.sent_by_ai ? `${m.detected_language ? ' · ' : ''}AI` : null}
                      {m.direction === 'outbound' && m.delivery_status ? (
                        <>
                          {(m.detected_language || m.sent_by_ai) ? ' · ' : ''}
                          <span
                            title={m.delivery_detail || undefined}
                            className={
                              m.delivery_status === 'sent'
                                ? 'inbox-status-sent'
                                : m.delivery_status === 'failed'
                                  ? 'inbox-status-failed'
                                  : undefined
                            }
                          >
                            {m.delivery_status}
                            {m.delivery_detail && m.delivery_status === 'failed'
                              ? `: ${m.delivery_detail}`
                              : ''}
                          </span>
                        </>
                      ) : null}
                    </div>
                  </div>
                ))}
              </div>

              <div className="inbox-reply-toolbar">
                <Select
                  value=""
                  onChange={(e) => {
                    if (e.target.value) {
                      setDraft(e.target.value)
                      e.target.value = ''
                    }
                  }}
                  className="inbox-saved-reply-select"
                >
                  <option value="">Insert saved reply…</option>
                  {(replies.data ?? []).map((r) => (
                    <option key={r.id} value={r.body}>
                      /{r.shortcut} — {r.title}
                    </option>
                  ))}
                </Select>
                <Button
                  size="sm"
                  variant="secondary"
                  type="button"
                  disabled={aiDraft.isPending || !selected}
                  onClick={() => aiDraft.mutate()}
                  className="ai-suggest-draft-btn"
                  title="Generate an AI response draft to review before sending"
                >
                  <Sparkles size={14} />
                  <span>{aiDraft.isPending ? 'Drafting…' : 'AI Suggest Draft'}</span>
                </Button>
                {roleAtLeast(role, 'support') ? (
                  <>
                    <Select
                      value={assignee}
                      onChange={(e) => setAssignee(e.target.value)}
                      className="inbox-assignee-select"
                    >
                      <option value="">Handover to…</option>
                      {(team.data ?? []).map((m) => (
                        <option key={m.id} value={m.id}>
                          {m.first_name || m.email}
                        </option>
                      ))}
                    </Select>
                    <Button
                      size="sm"
                      variant="secondary"
                      disabled={!assignee || handover.isPending}
                      onClick={() => handover.mutate()}
                    >
                      Handover
                    </Button>
                  </>
                ) : null}
              </div>

              <form
                className="chat-compose"
                onSubmit={(e) => {
                  e.preventDefault()
                  if (draft.trim()) send.mutate(undefined)
                }}
              >
                <Input
                  value={draft}
                  onChange={(e) => setDraft(e.target.value)}
                  placeholder="Write a reply…"
                />
                <label className="inbox-attach-label">
                  <Input
                    type="file"
                    accept="image/*"
                    className="inbox-file-input"
                    onChange={(e) => onAttachImage(e.target.files?.[0] ?? null)}
                  />
                </label>
                <Button type="submit" disabled={send.isPending || uploading || !draft.trim()}>
                  {uploading ? 'Uploading…' : 'Send'}
                </Button>
              </form>
              {send.isError ? <ErrorBox error={send.error} /> : null}
              {handover.isError ? <ErrorBox error={handover.error} /> : null}
            </>
          )}
        </div>
      </div>
    </>
  )
}
