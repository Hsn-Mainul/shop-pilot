import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Plus } from 'lucide-react'
import { api } from '../api/endpoints'
import { money, statusLabel } from '../lib/format'
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
  Textarea,
} from '../components/ui/primitives'
import type { Product } from '../types/api'

export function ServicesPage() {
  const qc = useQueryClient()

  // Create state
  const [name, setName] = useState('')
  const [pricingMode, setPricingMode] = useState('fixed')
  const [price, setPrice] = useState('')
  const [scheduleMode, setScheduleMode] = useState('time_slot')
  const [duration, setDuration] = useState('60')
  const [recurrence, setRecurrence] = useState('')
  const [location, setLocation] = useState('')
  const [description, setDescription] = useState('')

  // Edit state
  const [editingService, setEditingService] = useState<Product | null>(null)
  const [editName, setEditName] = useState('')
  const [editPricingMode, setEditPricingMode] = useState('fixed')
  const [editPrice, setEditPrice] = useState('')
  const [editScheduleMode, setEditScheduleMode] = useState('time_slot')
  const [editDuration, setEditDuration] = useState('60')
  const [editRecurrence, setEditRecurrence] = useState('')
  const [editLocation, setEditLocation] = useState('')
  const [editDescription, setEditDescription] = useState('')
  const [deleteId, setDeleteId] = useState<string | null>(null)
  const [showAddModal, setShowAddModal] = useState(false)

  const shop = useQuery({ queryKey: ['shop'], queryFn: api.shop.me })
  const services = useQuery({
    queryKey: ['products', 'service'],
    queryFn: () => api.products.list(undefined, 'service'),
  })

  const create = useMutation({
    mutationFn: () =>
      api.products.create({
        name,
        price: Number(price) || 0,
        kind: 'service',
        pricing_mode: pricingMode,
        description: description || undefined,
        scheduling: {
          mode: scheduleMode,
          duration_minutes: Number(duration) || 60,
          recurrence: recurrence || null,
          delivery_location: location || null,
        },
        variants: [{ attributes: { type: 'service' }, stock_qty: 999, reorder_point: 0 }],
      }),
    onSuccess: () => {
      setName('')
      setPrice('')
      setDescription('')
      setLocation('')
      setRecurrence('')
      setShowAddModal(false)
      qc.invalidateQueries({ queryKey: ['products', 'service'] })
    },
  })

  const update = useMutation({
    mutationFn: async () => {
      if (!editingService) return
      await api.products.update(editingService.id, {
        name: editName,
        price: Number(editPrice) || 0,
        pricing_mode: editPricingMode,
        description: editDescription || null,
        scheduling: {
          mode: editScheduleMode,
          duration_minutes: Number(editDuration) || 60,
          recurrence: editRecurrence || null,
          delivery_location: editLocation || null,
        },
      })
    },
    onSuccess: () => {
      setEditingService(null)
      qc.invalidateQueries({ queryKey: ['products', 'service'] })
    },
  })

  const remove = useMutation({
    mutationFn: (id: string) => api.products.remove(id),
    onSuccess: () => {
      setDeleteId(null)
      qc.invalidateQueries({ queryKey: ['products', 'service'] })
    },
  })

  function handleStartEdit(s: Product) {
    setEditingService(s)
    setEditName(s.name)
    setEditPricingMode(s.pricing_mode || 'fixed')
    setEditPrice(String(s.price || 0))
    const sched = (s.scheduling || {}) as Record<string, any>
    setEditScheduleMode(sched.mode || 'time_slot')
    setEditDuration(String(sched.duration_minutes || 60))
    setEditRecurrence(sched.recurrence || '')
    setEditLocation(sched.delivery_location || '')
    setEditDescription(s.description || '')
  }

  const currency = shop.data?.currency ?? 'BDT'

  return (
    <>
      <PageHeader
        title="Services"
        subtitle="Bookable/quotable services with Fixed / From / On Quote pricing (FR-CAT)."
        actions={
          <Button onClick={() => setShowAddModal(true)}>
            <Plus size={15} style={{ marginRight: 6 }} />
            Add Service
          </Button>
        }
      />

      <Panel title="Service catalogue">
          {services.isLoading ? (
            <Loading />
          ) : services.isError ? (
            <ErrorBox error={services.error} />
          ) : !services.data?.length ? (
            <EmptyState title="No services yet" />
          ) : (
            <Table>
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Pricing</th>
                  <th>Schedule</th>
                  <th>Price</th>
                  <th style={{ textAlign: 'right' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {services.data.map((s) => {
                  const isBeingEdited = editingService?.id === s.id
                  return (
                    <tr
                      key={s.id}
                      style={{
                        background: isBeingEdited ? '#f8fafc' : undefined,
                        borderLeft: isBeingEdited ? '3px solid #2563eb' : undefined,
                      }}
                    >
                      <td>
                        <strong>{s.name}</strong>
                        <div className="muted">{s.description?.slice(0, 60)}</div>
                      </td>
                      <td>
                        <Badge tone="info">{statusLabel(s.pricing_mode)}</Badge>
                      </td>
                      <td>
                        {String(s.scheduling?.mode ?? '—')}
                        {s.scheduling?.duration_minutes
                          ? ` · ${s.scheduling.duration_minutes}m`
                          : ''}
                      </td>
                      <td>
                        {s.pricing_mode === 'on_quote'
                          ? 'On quote'
                          : s.pricing_mode === 'from'
                            ? `From ${money(s.price, currency)}`
                            : money(s.price, currency)}
                      </td>
                      <td>
                        <div style={{ display: 'flex', gap: '0.4rem', justifyContent: 'flex-end' }}>
                          <Button
                            size="sm"
                            variant={isBeingEdited ? 'primary' : 'secondary'}
                            onClick={() => handleStartEdit(s)}
                          >
                            Edit
                          </Button>
                          <Button size="sm" variant="danger" onClick={() => setDeleteId(s.id)}>
                            Delete
                          </Button>
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </Table>
          )}
        </Panel>

        <Modal
          open={Boolean(editingService)}
          title={`Edit service: ${editingService?.name ?? ''}`}
          onClose={() => setEditingService(null)}
        >
              <div className="stack">
                <label className="field-label">
                  Name
                  <Input value={editName} onChange={(e) => setEditName(e.target.value)} />
                </label>
                <label className="field-label">
                  Pricing mode
                  <Select value={editPricingMode} onChange={(e) => setEditPricingMode(e.target.value)}>
                    <option value="fixed">Fixed</option>
                    <option value="from">From</option>
                    <option value="on_quote">On quote</option>
                  </Select>
                </label>
                <label className="field-label">
                  Price
                  <Input type="number" value={editPrice} onChange={(e) => setEditPrice(e.target.value)} />
                </label>
                <label className="field-label">
                  Scheduling
                  <Select value={editScheduleMode} onChange={(e) => setEditScheduleMode(e.target.value)}>
                    <option value="time_slot">Time slot</option>
                    <option value="due_date">Due date</option>
                  </Select>
                </label>
                <label className="field-label">
                  Duration (minutes)
                  <Input type="number" value={editDuration} onChange={(e) => setEditDuration(e.target.value)} />
                </label>
                <label className="field-label">
                  Recurrence
                  <Select value={editRecurrence} onChange={(e) => setEditRecurrence(e.target.value)}>
                    <option value="">None</option>
                    <option value="weekly">Weekly</option>
                    <option value="monthly">Monthly</option>
                  </Select>
                </label>
                <label className="field-label">
                  Delivery / service location
                  <Input value={editLocation} onChange={(e) => setEditLocation(e.target.value)} />
                </label>
                <label className="field-label">
                  Description
                  <Textarea value={editDescription} onChange={(e) => setEditDescription(e.target.value)} />
                </label>
                {update.isError ? <ErrorBox error={update.error} /> : null}
                <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.5rem' }}>
                  <Button onClick={() => update.mutate()} disabled={!editName || update.isPending}>
                    {update.isPending ? 'Saving...' : 'Save Changes'}
                  </Button>
                  <Button variant="secondary" onClick={() => setEditingService(null)}>
                    Cancel
                  </Button>
                </div>
              </div>
        </Modal>

        <Modal open={showAddModal} title="Add service" onClose={() => setShowAddModal(false)}>
              <div className="stack">
                <label className="field-label">
                  Name
                  <Input value={name} onChange={(e) => setName(e.target.value)} />
                </label>
                <label className="field-label">
                  Pricing mode
                  <Select value={pricingMode} onChange={(e) => setPricingMode(e.target.value)}>
                    <option value="fixed">Fixed</option>
                    <option value="from">From</option>
                    <option value="on_quote">On quote</option>
                  </Select>
                </label>
                <label className="field-label">
                  Price
                  <Input type="number" value={price} onChange={(e) => setPrice(e.target.value)} />
                </label>
                <label className="field-label">
                  Scheduling
                  <Select value={scheduleMode} onChange={(e) => setScheduleMode(e.target.value)}>
                    <option value="time_slot">Time slot</option>
                    <option value="due_date">Due date</option>
                  </Select>
                </label>
                <label className="field-label">
                  Duration (minutes)
                  <Input type="number" value={duration} onChange={(e) => setDuration(e.target.value)} />
                </label>
                <label className="field-label">
                  Recurrence
                  <Select value={recurrence} onChange={(e) => setRecurrence(e.target.value)}>
                    <option value="">None</option>
                    <option value="weekly">Weekly</option>
                    <option value="monthly">Monthly</option>
                  </Select>
                </label>
                <label className="field-label">
                  Delivery / service location
                  <Input value={location} onChange={(e) => setLocation(e.target.value)} />
                </label>
                <label className="field-label">
                  Description
                  <Textarea value={description} onChange={(e) => setDescription(e.target.value)} />
                </label>
                {create.isError ? <ErrorBox error={create.error} /> : null}
                <Button onClick={() => create.mutate()} disabled={!name || create.isPending}>
                  Create service
                </Button>
              </div>
        </Modal>

      <ConfirmDialog
        open={Boolean(deleteId)}
        title="Delete service?"
        message="This removes the service from your catalogue."
        danger
        confirmLabel="Delete"
        onConfirm={() => (deleteId ? remove.mutate(deleteId) : undefined)}
        onCancel={() => setDeleteId(null)}
      />
    </>
  )
}
