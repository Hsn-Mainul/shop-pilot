import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Plus } from 'lucide-react'
import { api } from '../api/endpoints'
import { money, shortId, statusLabel } from '../lib/format'
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
} from '../components/ui/primitives'
import { useAuth } from '../auth/AuthContext'
import { roleAtLeast } from '../lib/roles'

export function DeliveryPage() {
  const qc = useQueryClient()
  const { role } = useAuth()
  const [orderIds, setOrderIds] = useState('')
  const [courier, setCourier] = useState('pathao')
  const [showBookModal, setShowBookModal] = useState(false)

  const parcels = useQuery({ queryKey: ['parcels'], queryFn: () => api.delivery.parcels() })
  const cod = useQuery({
    queryKey: ['cod-summary'],
    queryFn: api.delivery.codSummary,
    enabled: roleAtLeast(role, 'admin'),
  })
  const shop = useQuery({ queryKey: ['shop'], queryFn: api.shop.me })

  const book = useMutation({
    mutationFn: () =>
      api.delivery.book(
        orderIds
          .split(/[\s,]+/)
          .map((s) => s.trim())
          .filter(Boolean),
        courier,
      ),
    onSuccess: () => {
      setOrderIds('')
      setShowBookModal(false)
      qc.invalidateQueries({ queryKey: ['parcels'] })
      qc.invalidateQueries({ queryKey: ['cod-summary'] })
    },
  })

  const setStatus = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) =>
      api.delivery.setStatus(id, status),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['parcels'] }),
  })

  const currency = shop.data?.currency ?? 'BDT'

  return (
    <>
      <PageHeader
        title="Delivery"
        subtitle="Courier booking, tracking, and COD outstanding (FR-DEL)."
        actions={
          <Button onClick={() => setShowBookModal(true)}>
            <Plus size={15} style={{ marginRight: 6 }} />
            Book Parcels
          </Button>
        }
      />

      {roleAtLeast(role, 'admin') ? (
        <>
          <div className="stat-grid">
            <StatTile
              label="COD outstanding"
              value={money(cod.data?.total_outstanding, currency)}
              tone="warn"
            />
            {Object.entries(cod.data?.by_courier ?? {}).map(([courierName, amt]) => (
              <StatTile
                key={courierName}
                label={`COD · ${courierName}`}
                value={money(Number(amt), currency)}
              />
            ))}
          </div>
        </>
      ) : null}

      <Panel title="Parcels">
          {parcels.isLoading ? (
            <Loading />
          ) : parcels.isError ? (
            <ErrorBox error={parcels.error} />
          ) : !parcels.data?.length ? (
            <EmptyState title="No parcels booked" />
          ) : (
            <Table>
              <thead>
                <tr>
                  <th>Parcel</th>
                  <th>Order</th>
                  <th>Courier</th>
                  <th>Status</th>
                  <th>COD</th>
                  <th>Update</th>
                </tr>
              </thead>
              <tbody>
                {parcels.data.map((p) => (
                  <tr key={p.id}>
                    <td>{shortId(p.id)}</td>
                    <td>{shortId(p.order_id)}</td>
                    <td>{p.courier}</td>
                    <td>
                      <Badge>{statusLabel(p.status)}</Badge>
                    </td>
                    <td>{money(p.cod_amount, currency)}</td>
                    <td>
                      <Select
                        defaultValue=""
                        onChange={(e) => {
                          if (e.target.value) {
                            setStatus.mutate({ id: p.id, status: e.target.value })
                            e.target.value = ''
                          }
                        }}
                      >
                        <option value="">Status…</option>
                        {[
                          'to_book',
                          'picked_up',
                          'in_transit',
                          'out_for_delivery',
                          'delivered',
                          'returned',
                          'on_hold',
                        ].map((s) => (
                          <option key={s} value={s}>
                            {statusLabel(s)}
                          </option>
                        ))}
                      </Select>
                    </td>
                  </tr>
                ))}
              </tbody>
            </Table>
          )}
      </Panel>

      <Modal open={showBookModal} title="Book parcels" onClose={() => setShowBookModal(false)}>
        <div className="stack">
          <label className="field-label">
            Order IDs (comma or space separated)
            <Input value={orderIds} onChange={(e) => setOrderIds(e.target.value)} />
          </label>
          <label className="field-label">
            Courier
            <Select value={courier} onChange={(e) => setCourier(e.target.value)}>
              {['pathao', 'steadfast', 'redx', 'paperfly', 'other'].map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </Select>
          </label>
          {book.isError ? <ErrorBox error={book.error} /> : null}
          <Button onClick={() => book.mutate()} disabled={!orderIds || book.isPending}>
            Book
          </Button>
        </div>
      </Modal>
    </>
  )
}
