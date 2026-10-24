import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { UserPlus } from 'lucide-react'
import { api } from '../api/endpoints'
import { shortId, statusLabel } from '../lib/format'
import { roleLabel } from '../lib/roles'
import { useLocale } from '../i18n/LocaleContext'
import { ConfirmDialog } from '../components/ui/ConfirmDialog'
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
  Table,
} from '../components/ui/primitives'
import type { Role } from '../types/api'

export function TeamPage() {
  const { t } = useLocale()
  const qc = useQueryClient()
  const [email, setEmail] = useState('')
  const [role, setRole] = useState<Role>('sales')
  const [firstName, setFirstName] = useState('')
  const [start, setStart] = useState('')
  const [end, setEnd] = useState('')
  const [reason, setReason] = useState('')
  const [leaveDecision, setLeaveDecision] = useState<{ id: string; status: string } | null>(null)
  const [showInviteModal, setShowInviteModal] = useState(false)

  const team = useQuery({ queryKey: ['team'], queryFn: api.team.list })
  const shifts = useQuery({ queryKey: ['shifts'], queryFn: api.teamOps.shifts })
  const leave = useQuery({ queryKey: ['leave'], queryFn: api.teamOps.leaveList })

  const draftShifts = useMutation({
    mutationFn: () => api.teamOps.draftShifts(7),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['shifts'] }),
  })

  const confirmShift = useMutation({
    mutationFn: (id: string) => api.teamOps.confirmShift(id, true),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['shifts'] }),
  })

  const invite = useMutation({
    mutationFn: () =>
      api.team.invite({
        email,
        role,
        first_name: firstName || undefined,
      }),
    onSuccess: () => {
      setEmail('')
      setFirstName('')
      setShowInviteModal(false)
      qc.invalidateQueries({ queryKey: ['team'] })
    },
  })

  const requestLeave = useMutation({
    mutationFn: () => api.teamOps.requestLeave({ start_date: start, end_date: end, reason }),
    onSuccess: () => {
      setStart('')
      setEnd('')
      setReason('')
      qc.invalidateQueries({ queryKey: ['leave'] })
    },
  })

  const decideLeave = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) =>
      api.teamOps.decideLeave(id, status),
    onSuccess: () => {
      setLeaveDecision(null)
      qc.invalidateQueries({ queryKey: ['leave'] })
    },
  })

  return (
    <>
      <PageHeader
        title={t('team')}
        subtitle={t('teamSubtitle')}
        actions={
          <Button onClick={() => setShowInviteModal(true)}>
            <UserPlus size={15} style={{ marginRight: 6 }} />
            Invite Teammate
          </Button>
        }
      />

      <Panel title="Team members">
          {team.isLoading ? (
            <Loading />
          ) : team.isError ? (
            <ErrorBox error={team.error} />
          ) : !team.data?.length ? (
            <EmptyState title="No team members" />
          ) : (
            <Table>
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Email</th>
                  <th>Role</th>
                  <th>Active</th>
                </tr>
              </thead>
              <tbody>
                {team.data.map((m) => (
                  <tr key={m.id}>
                    <td>
                      {[m.first_name, m.last_name].filter(Boolean).join(' ') || shortId(m.id)}
                    </td>
                    <td>{m.email}</td>
                    <td>{roleLabel(m.role)}</td>
                    <td>
                      <Badge tone={m.is_active ? 'good' : 'neutral'}>
                        {m.is_active ? 'yes' : 'no'}
                      </Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </Table>
          )}
        </Panel>

      <div className="grid-2">
        <Panel
          title="Shifts"
          actions={
            <Button size="sm" onClick={() => draftShifts.mutate()} disabled={draftShifts.isPending}>
              AI draft week
            </Button>
          }
        >
          {draftShifts.isError ? <ErrorBox error={draftShifts.error} /> : null}
          {shifts.isLoading ? (
            <Loading />
          ) : !shifts.data?.length ? (
            <EmptyState title="No shifts scheduled" hint="Generate an AI draft from recent order volume." />
          ) : (
            <Table>
              <thead>
                <tr>
                  <th>Member</th>
                  <th>Date</th>
                  <th>Hours</th>
                  <th>Status</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {shifts.data.map((s) => (
                  <tr key={s.id}>
                    <td>{shortId(s.team_member_id)}</td>
                    <td>{s.shift_date}</td>
                    <td>{s.planned_hours}</td>
                    <td>
                      <Badge tone={s.is_confirmed ? 'good' : 'warn'}>
                        {s.is_confirmed ? 'confirmed' : 'draft'}
                      </Badge>
                    </td>
                    <td>
                      {!s.is_confirmed ? (
                        <Button size="sm" onClick={() => confirmShift.mutate(s.id)}>
                          Confirm
                        </Button>
                      ) : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </Table>
          )}
        </Panel>

        <Panel title="Leave">
          <div className="stack">
            <label className="field-label">
              Start
              <Input type="date" value={start} onChange={(e) => setStart(e.target.value)} />
            </label>
            <label className="field-label">
              End
              <Input type="date" value={end} onChange={(e) => setEnd(e.target.value)} />
            </label>
            <label className="field-label">
              Reason
              <Input value={reason} onChange={(e) => setReason(e.target.value)} />
            </label>
            <Button
              onClick={() => requestLeave.mutate()}
              disabled={!start || !end || requestLeave.isPending}
            >
              Request leave
            </Button>
            {leave.data?.length ? (
              <Table>
                <thead>
                  <tr>
                    <th>Member</th>
                    <th>Range</th>
                    <th>Status</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {leave.data.map((l) => (
                    <tr key={l.id}>
                      <td>{shortId(l.team_member_id)}</td>
                      <td>
                        {l.start_date} → {l.end_date}
                      </td>
                      <td>
                        <Badge>{statusLabel(l.status)}</Badge>
                      </td>
                      <td>
                        {l.status === 'pending' ? (
                          <div className="row">
                            <Button
                              size="sm"
                              onClick={() => setLeaveDecision({ id: l.id, status: 'approved' })}
                            >
                              Approve
                            </Button>
                            <Button
                              size="sm"
                              variant="secondary"
                              onClick={() => setLeaveDecision({ id: l.id, status: 'rejected' })}
                            >
                              Reject
                            </Button>
                          </div>
                        ) : null}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            ) : null}
          </div>
        </Panel>
      </div>

      <Modal open={showInviteModal} title="Invite teammate" onClose={() => setShowInviteModal(false)}>
        <div className="stack">
          <label className="field-label">
            Email
            <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
          </label>
          <label className="field-label">
            First name
            <Input value={firstName} onChange={(e) => setFirstName(e.target.value)} />
          </label>
          <label className="field-label">
            Role
            <Select value={role} onChange={(e) => setRole(e.target.value as Role)}>
              {(['admin', 'sales', 'support', 'warehouse'] as Role[]).map((r) => (
                <option key={r} value={r}>
                  {roleLabel(r)}
                </option>
              ))}
            </Select>
          </label>
          {invite.isError ? <ErrorBox error={invite.error} /> : null}
          <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.25rem' }}>
            <Button onClick={() => invite.mutate()} disabled={!email || invite.isPending}>
              Invite
            </Button>
            <Button variant="secondary" onClick={() => setShowInviteModal(false)}>
              Cancel
            </Button>
          </div>
        </div>
      </Modal>

      <ConfirmDialog
        open={Boolean(leaveDecision)}
        title={leaveDecision?.status === 'approved' ? 'Approve leave?' : 'Reject leave?'}
        message="This updates the leave request status for the teammate."
        busy={decideLeave.isPending}
        confirmLabel={leaveDecision?.status === 'approved' ? 'Approve' : 'Reject'}
        onCancel={() => setLeaveDecision(null)}
        onConfirm={() => leaveDecision && decideLeave.mutate(leaveDecision)}
      />
    </>
  )
}
