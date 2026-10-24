import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { api } from '../api/endpoints'
import { shortId, statusLabel } from '../lib/format'
import { useLocale } from '../i18n/LocaleContext'
import { ConfirmDialog } from '../components/ui/ConfirmDialog'
import {
  Badge,
  Button,
  EmptyState,
  ErrorBox,
  Loading,
  PageHeader,
  Panel,
  Table,
} from '../components/ui/primitives'

export function LoyaltyPage() {
  const { t } = useLocale()
  const qc = useQueryClient()
  const [status, setStatus] = useState('waiting')
  const [pending, setPending] = useState<{ id: string; approve: boolean } | null>(null)

  const list = useQuery({
    queryKey: ['loyalty', status],
    queryFn: () => api.loyalty.list(status),
  })

  const decide = useMutation({
    mutationFn: ({ id, approve }: { id: string; approve: boolean }) =>
      api.loyalty.decide(id, approve),
    onSuccess: () => {
      setPending(null)
      qc.invalidateQueries({ queryKey: ['loyalty'] })
    },
  })

  return (
    <>
      <PageHeader
        title={t('loyalty')}
        subtitle="Approve AI-drafted thank-you rewards at milestones (FR-CUST-03)."
      />

      <div className="row tabs">
        {['waiting', 'approved', 'set_aside', 'sent'].map((s) => (
          <Button
            key={s}
            size="sm"
            variant={status === s ? 'primary' : 'secondary'}
            onClick={() => setStatus(s)}
          >
            {statusLabel(s)}
          </Button>
        ))}
      </div>

      <Panel title={`${statusLabel(status)} rewards`}>
        {list.isLoading ? (
          <Loading />
        ) : list.isError ? (
          <ErrorBox error={list.error} />
        ) : !list.data?.length ? (
          <EmptyState title={`No ${statusLabel(status)} rewards`} />
        ) : (
          <Table>
            <thead>
              <tr>
                <th>Customer</th>
                <th>Milestone</th>
                <th>Type</th>
                <th>Status</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {list.data.map((r) => (
                <tr key={r.id}>
                  <td>{shortId(r.customer_id)}</td>
                  <td>{r.milestone}</td>
                  <td>{r.reward_type}</td>
                  <td>
                    <Badge tone="warn">{statusLabel(r.status)}</Badge>
                  </td>
                  <td className="row">
                    {r.status === 'waiting' || status === 'waiting' ? (
                      <>
                        <Button size="sm" onClick={() => setPending({ id: r.id, approve: true })}>
                          Approve
                        </Button>
                        <Button
                          size="sm"
                          variant="secondary"
                          onClick={() => setPending({ id: r.id, approve: false })}
                        >
                          Set aside
                        </Button>
                      </>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </Table>
        )}
      </Panel>

      <ConfirmDialog
        open={Boolean(pending)}
        title={pending?.approve ? 'Approve reward?' : 'Set reward aside?'}
        message={
          pending?.approve
            ? 'Approves this loyalty thank-you so it can be sent to the customer.'
            : 'Sets this draft aside without sending.'
        }
        busy={decide.isPending}
        confirmLabel={pending?.approve ? 'Approve' : 'Set aside'}
        onCancel={() => setPending(null)}
        onConfirm={() => pending && decide.mutate(pending)}
      />
    </>
  )
}
