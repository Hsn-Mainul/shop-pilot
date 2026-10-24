import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { api } from '../api/endpoints'
import { shortId } from '../lib/format'
import { useAuth } from '../auth/AuthContext'
import { roleAtLeast } from '../lib/roles'
import {
  Badge,
  Button,
  EmptyState,
  ErrorBox,
  Loading,
  PageHeader,
  Panel,
  Select,
  Table,
  Textarea,
} from '../components/ui/primitives'

export function ReviewsPage() {
  const qc = useQueryClient()
  const { role } = useAuth()
  const [customerId, setCustomerId] = useState('')
  const [rating, setRating] = useState('5')
  const [comment, setComment] = useState('')

  const reviews = useQuery({
    queryKey: ['reviews'],
    queryFn: () => api.reviews.list(true),
  })
  const customers = useQuery({ queryKey: ['customers'], queryFn: () => api.customers.list() })

  const hide = useMutation({
    mutationFn: ({ id, hidden }: { id: string; hidden: boolean }) => api.reviews.hide(id, hidden),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['reviews'] }),
  })

  const create = useMutation({
    mutationFn: () =>
      api.reviews.create({
        customer_id: customerId,
        rating: Number(rating),
        comment: comment.trim() || undefined,
      }),
    onSuccess: () => {
      setComment('')
      setCustomerId('')
      qc.invalidateQueries({ queryKey: ['reviews'] })
    },
  })

  return (
    <>
      <PageHeader title="Reviews" subtitle="Customer ratings and moderation (FR-CUST-04)." />

      {roleAtLeast(role, 'support') ? (
        <Panel title="Add review">
          <div className="row" style={{ flexWrap: 'wrap', gap: 8 }}>
            <Select value={customerId} onChange={(e) => setCustomerId(e.target.value)} style={{ maxWidth: 220 }}>
              <option value="">Customer…</option>
              {(customers.data ?? []).map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name || c.phone || shortId(c.id)}
                </option>
              ))}
            </Select>
            <Select value={rating} onChange={(e) => setRating(e.target.value)} style={{ maxWidth: 100 }}>
              {[5, 4, 3, 2, 1].map((n) => (
                <option key={n} value={n}>
                  {n} ★
                </option>
              ))}
            </Select>
            <Textarea
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              placeholder="Comment (optional)"
              rows={2}
              style={{ flex: 1, minWidth: 200 }}
            />
            <Button disabled={!customerId || create.isPending} onClick={() => create.mutate()}>
              Add review
            </Button>
          </div>
          {create.isError ? <ErrorBox error={create.error} /> : null}
        </Panel>
      ) : null}

      <Panel>
        {reviews.isLoading ? (
          <Loading />
        ) : reviews.isError ? (
          <ErrorBox error={reviews.error} />
        ) : !reviews.data?.length ? (
          <EmptyState title="No reviews yet" />
        ) : (
          <Table>
            <thead>
              <tr>
                <th>Customer</th>
                <th>Rating</th>
                <th>Comment</th>
                <th>Status</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {reviews.data.map((r) => (
                <tr key={r.id}>
                  <td>{shortId(r.customer_id)}</td>
                  <td>
                    {'★'.repeat(r.rating)}
                    {'☆'.repeat(5 - r.rating)}
                  </td>
                  <td>{r.comment || '—'}</td>
                  <td>
                    <Badge tone={r.is_hidden ? 'warn' : 'good'}>
                      {r.is_hidden ? 'hidden' : 'visible'}
                    </Badge>
                  </td>
                  <td>
                    {roleAtLeast(role, 'support') ? (
                      <Button
                        size="sm"
                        variant="secondary"
                        onClick={() => hide.mutate({ id: r.id, hidden: !r.is_hidden })}
                      >
                        {r.is_hidden ? 'Unhide' : 'Hide'}
                      </Button>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </Table>
        )}
      </Panel>
    </>
  )
}
