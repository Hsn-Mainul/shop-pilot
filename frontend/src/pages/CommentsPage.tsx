import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useMemo, useState } from 'react'
import { api } from '../api/endpoints'
import { shortId, statusLabel } from '../lib/format'
import { usePollingQuery } from '../hooks/usePollingQuery'
import {
  Badge,
  Button,
  EmptyState,
  ErrorBox,
  Input,
  Loading,
  PageHeader,
  Panel,
} from '../components/ui/primitives'

export function CommentsPage() {
  const qc = useQueryClient()
  const [selected, setSelected] = useState<string | null>(null)
  const [draft, setDraft] = useState('')

  const shop = useQuery({ queryKey: ['shop'], queryFn: api.shop.me })
  const list = usePollingQuery(
    ['conversations', 'comment'],
    () => api.conversations.list(undefined, 'comment'),
    10000,
  )
  const messages = useQuery({
    queryKey: ['messages', selected],
    queryFn: () => api.conversations.messages(selected!),
    enabled: Boolean(selected),
  })
  const customers = useQuery({ queryKey: ['customers'], queryFn: () => api.customers.list() })
  const customerMap = useMemo(
    () => Object.fromEntries((customers.data ?? []).map((c) => [c.id, c])),
    [customers.data],
  )

  const saveMods = useMutation({
    mutationFn: (body: Partial<{
      auto_hide_spam_comments: boolean
      auto_hide_phone_numbers_in_comments: boolean
      ai_auto_reply_comments: boolean
    }>) => api.shop.update(body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['shop'] }),
  })

  const send = useMutation({
    mutationFn: () =>
      api.conversations.send(selected!, { direction: 'outbound', type: 'text', text: draft }),
    onSuccess: () => {
      setDraft('')
      qc.invalidateQueries({ queryKey: ['messages', selected] })
    },
  })

  return (
    <>
      <PageHeader
        title="Comments"
        subtitle="Public comment threads with spam/phone auto-hide and AI auto-reply (FR-CHAT-05)."
      />

      <Panel title="Moderation">
        <div className="toggle-row">
          <div>
            <strong>Auto-hide spam comments</strong>
          </div>
          <button
            type="button"
            className={`switch ${shop.data?.auto_hide_spam_comments ? 'on' : ''}`}
            onClick={() =>
              saveMods.mutate({ auto_hide_spam_comments: !shop.data?.auto_hide_spam_comments })
            }
          />
        </div>
        <div className="toggle-row">
          <div>
            <strong>Auto-hide phone numbers in comments</strong>
          </div>
          <button
            type="button"
            className={`switch ${shop.data?.auto_hide_phone_numbers_in_comments ? 'on' : ''}`}
            onClick={() =>
              saveMods.mutate({
                auto_hide_phone_numbers_in_comments: !shop.data?.auto_hide_phone_numbers_in_comments,
              })
            }
          />
        </div>
        <div className="toggle-row">
          <div>
            <strong>AI auto-reply on comments</strong>
          </div>
          <button
            type="button"
            className={`switch ${shop.data?.ai_auto_reply_comments ? 'on' : ''}`}
            onClick={() =>
              saveMods.mutate({ ai_auto_reply_comments: !shop.data?.ai_auto_reply_comments })
            }
          />
        </div>
      </Panel>

      <div className="inbox-layout">
        <div className="thread-list">
          {list.isLoading ? (
            <Loading />
          ) : !list.data?.length ? (
            <EmptyState title="No comment threads" hint="Comments from connected pages appear here." />
          ) : (
            list.data.map((c) => (
              <button
                key={c.id}
                type="button"
                className={`thread-item ${selected === c.id ? 'active' : ''}`}
                onClick={() => setSelected(c.id)}
              >
                <strong>{customerMap[c.customer_id]?.name || shortId(c.customer_id)}</strong>
                <div className="muted">{statusLabel(c.status)}</div>
              </button>
            ))
          )}
        </div>
        <div className="chat-pane">
          {!selected ? (
            <EmptyState title="Select a comment thread" />
          ) : (
            <>
              <div className="messages">
                {(messages.data ?? []).map((m) => (
                  <div key={m.id} className={`bubble ${m.direction}`}>
                    {m.text || m.type}
                    {m.sent_by_ai ? <Badge tone="info">AI</Badge> : null}
                  </div>
                ))}
              </div>
              <form
                className="chat-compose"
                onSubmit={(e) => {
                  e.preventDefault()
                  if (draft.trim()) send.mutate()
                }}
              >
                <Input value={draft} onChange={(e) => setDraft(e.target.value)} placeholder="Public reply…" />
                <Button type="submit" disabled={!draft.trim() || send.isPending}>
                  Reply
                </Button>
              </form>
              {send.isError ? <ErrorBox error={send.error} /> : null}
            </>
          )}
        </div>
      </div>
    </>
  )
}
