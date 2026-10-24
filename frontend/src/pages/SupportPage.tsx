import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Plus } from 'lucide-react'
import { api } from '../api/endpoints'
import { statusLabel } from '../lib/format'
import { useAuth } from '../auth/AuthContext'
import { roleAtLeast } from '../lib/roles'
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
  Table,
  Textarea,
} from '../components/ui/primitives'

export function SupportPage() {
  const qc = useQueryClient()
  const { role } = useAuth()
  const [subject, setSubject] = useState('')
  const [body, setBody] = useState('')
  const [showAddModal, setShowAddModal] = useState(false)

  const tickets = useQuery({ queryKey: ['support'], queryFn: () => api.support.list() })

  const create = useMutation({
    mutationFn: () => api.support.create({ subject, body }),
    onSuccess: () => {
      setSubject('')
      setBody('')
      setShowAddModal(false)
      qc.invalidateQueries({ queryKey: ['support'] })
    },
  })

  const close = useMutation({
    mutationFn: (id: string) => api.support.close(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['support'] }),
  })

  return (
    <>
      <PageHeader
        title="Support"
        subtitle="In-app support tickets (FR-SUP-01)."
        actions={
          <Button onClick={() => setShowAddModal(true)}>
            <Plus size={15} style={{ marginRight: 6 }} />
            New Ticket
          </Button>
        }
      />

      <Panel title="Tickets">
          {tickets.isLoading ? (
            <Loading />
          ) : tickets.isError ? (
            <ErrorBox error={tickets.error} />
          ) : !tickets.data?.length ? (
            <EmptyState title="No tickets" />
          ) : (
            <Table>
              <thead>
                <tr>
                  <th>Subject</th>
                  <th>Status</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {tickets.data.map((t) => (
                  <tr key={t.id}>
                    <td>
                      <strong>{t.subject}</strong>
                      <div className="muted">{t.body.slice(0, 100)}</div>
                    </td>
                    <td>
                      <Badge tone={t.status === 'open' ? 'warn' : 'good'}>
                        {statusLabel(t.status)}
                      </Badge>
                    </td>
                    <td>
                      {t.status === 'open' && roleAtLeast(role, 'admin') ? (
                        <Button size="sm" variant="secondary" onClick={() => close.mutate(t.id)}>
                          Close
                        </Button>
                      ) : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </Table>
          )}
      </Panel>

      <Modal open={showAddModal} title="New ticket" onClose={() => setShowAddModal(false)}>
        <div className="stack">
          <label className="field-label">
            Subject
            <Input value={subject} onChange={(e) => setSubject(e.target.value)} />
          </label>
          <label className="field-label">
            Details
            <Textarea value={body} onChange={(e) => setBody(e.target.value)} rows={5} />
          </label>
          {create.isError ? <ErrorBox error={create.error} /> : null}
          <Button
            onClick={() => create.mutate()}
            disabled={!subject || !body || create.isPending}
          >
            Submit
          </Button>
        </div>
      </Modal>
    </>
  )
}
