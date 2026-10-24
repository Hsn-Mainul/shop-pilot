import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useMemo, useState } from 'react'
import { Boxes } from 'lucide-react'
import { api } from '../api/endpoints'
import { shortId, statusLabel } from '../lib/format'
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

export function InventoryPage() {
  const qc = useQueryClient()
  const [variantId, setVariantId] = useState('')
  const [delta, setDelta] = useState('1')
  const [reason, setReason] = useState('receive_stock')
  const [batch, setBatch] = useState('')
  const [serials, setSerials] = useState('')
  const [note, setNote] = useState('')
  const [showAdjustModal, setShowAdjustModal] = useState(false)

  const products = useQuery({
    queryKey: ['products', 'product'],
    queryFn: () => api.products.list(undefined, 'product'),
  })
  const ledger = useQuery({
    queryKey: ['stock-ledger'],
    queryFn: () => api.products.stockLedger(),
  })

  const variants = useMemo(
    () =>
      (products.data ?? []).flatMap((p) =>
        p.variants.map((v) => ({
          ...v,
          productName: p.name,
          track_serial: p.track_serial,
          track_batch: p.track_batch,
          low: v.stock_qty <= v.reorder_point,
        })),
      ),
    [products.data],
  )

  const adjust = useMutation({
    mutationFn: () =>
      api.products.adjustStock({
        variant_id: variantId,
        delta_qty: Number(delta),
        reason,
        note: note || undefined,
        batch_code: batch || undefined,
        serial_numbers: serials
          ? serials.split(/[\s,]+/).filter(Boolean)
          : undefined,
      }),
    onSuccess: () => {
      setDelta('1')
      setNote('')
      setSerials('')
      setShowAdjustModal(false)
      qc.invalidateQueries({ queryKey: ['products'] })
      qc.invalidateQueries({ queryKey: ['stock-ledger'] })
    },
  })

  return (
    <>
      <PageHeader
        title="Inventory"
        subtitle="Stock by variant, serial/batch, and full adjustment ledger (FR-CAT-05)."
        actions={
          <Button onClick={() => setShowAdjustModal(true)}>
            <Boxes size={15} style={{ marginRight: 6 }} />
            Adjust Stock
          </Button>
        }
      />

      <Panel title="On-hand stock">
          {products.isLoading ? (
            <Loading />
          ) : !variants.length ? (
            <EmptyState title="No product variants" />
          ) : (
            <Table>
              <thead>
                <tr>
                  <th>Product</th>
                  <th>SKU</th>
                  <th>Location</th>
                  <th>Batch</th>
                  <th>Qty</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {variants.map((v) => (
                  <tr key={v.id}>
                    <td>{v.productName}</td>
                    <td>{v.sku || shortId(v.id)}</td>
                    <td>{v.location || '—'}</td>
                    <td>{v.batch_code || '—'}</td>
                    <td>{v.stock_qty}</td>
                    <td>
                      {v.stock_qty <= 0 ? (
                        <Badge tone="danger">sold out</Badge>
                      ) : v.low ? (
                        <Badge tone="warn">low</Badge>
                      ) : (
                        <Badge tone="good">ok</Badge>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </Table>
          )}
      </Panel>

      <Modal open={showAdjustModal} title="Adjust stock" onClose={() => setShowAdjustModal(false)}>
        <div className="stack">
          <label className="field-label">
            Variant
            <Select value={variantId} onChange={(e) => setVariantId(e.target.value)}>
              <option value="">Select…</option>
              {variants.map((v) => (
                <option key={v.id} value={v.id}>
                  {v.productName} ({v.sku || shortId(v.id)}) — {v.stock_qty}
                </option>
              ))}
            </Select>
          </label>
          <label className="field-label">
            Delta (+ receive / − adjust)
            <Input type="number" value={delta} onChange={(e) => setDelta(e.target.value)} />
          </label>
          <label className="field-label">
            Reason
            <Select value={reason} onChange={(e) => setReason(e.target.value)}>
              {['receive_stock', 'stock_count', 'damage', 'return_to_supplier', 'manual_adjust'].map(
                (r) => (
                  <option key={r} value={r}>
                    {statusLabel(r)}
                  </option>
                ),
              )}
            </Select>
          </label>
          <label className="field-label">
            Batch code
            <Input value={batch} onChange={(e) => setBatch(e.target.value)} />
          </label>
          <label className="field-label">
            Serial numbers
            <Input
              value={serials}
              onChange={(e) => setSerials(e.target.value)}
              placeholder="SN1, SN2"
            />
          </label>
          <label className="field-label">
            Note
            <Input value={note} onChange={(e) => setNote(e.target.value)} />
          </label>
          {adjust.isError ? <ErrorBox error={adjust.error} /> : null}
          <Button onClick={() => adjust.mutate()} disabled={!variantId || adjust.isPending}>
            Post adjustment
          </Button>
        </div>
      </Modal>

      <Panel title="Stock ledger">
        {ledger.isLoading ? (
          <Loading />
        ) : ledger.isError ? (
          <ErrorBox error={ledger.error} />
        ) : !ledger.data?.length ? (
          <EmptyState title="No ledger entries yet" />
        ) : (
          <Table>
            <thead>
              <tr>
                <th>When</th>
                <th>Variant</th>
                <th>Delta</th>
                <th>Reason</th>
                <th>Note</th>
              </tr>
            </thead>
            <tbody>
              {ledger.data.map((e) => (
                <tr key={e.id}>
                  <td>{e.created_at ? new Date(e.created_at).toLocaleString() : '—'}</td>
                  <td>{shortId(e.variant_id)}</td>
                  <td style={{ color: e.delta_qty < 0 ? 'var(--danger)' : 'var(--good)' }}>
                    {e.delta_qty > 0 ? `+${e.delta_qty}` : e.delta_qty}
                  </td>
                  <td>{statusLabel(e.reason)}</td>
                  <td>{e.note || '—'}</td>
                </tr>
              ))}
            </tbody>
          </Table>
        )}
      </Panel>
    </>
  )
}
