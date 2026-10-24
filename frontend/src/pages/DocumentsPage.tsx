import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Plus } from 'lucide-react'
import { api } from '../api/endpoints'
import { shortId, statusLabel } from '../lib/format'
import { useAuth } from '../auth/AuthContext'
import { roleAtLeast } from '../lib/roles'
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
  Table,
} from '../components/ui/primitives'

const DOC_TYPES = [
  'invoice',
  'money_receipt',
  'quotation',
  'credit_note',
  'delivery_challan',
  'packing_slip',
  'vat_invoice',
]

const TEMPLATE_GALLERY = [
  { type: 'invoice', template_id: 'classic', label: 'Classic invoice' },
  { type: 'invoice', template_id: 'modern', label: 'Modern invoice' },
  { type: 'money_receipt', template_id: 'classic', label: 'Classic receipt' },
  { type: 'delivery_challan', template_id: 'classic', label: 'Delivery challan' },
  { type: 'packing_slip', template_id: 'classic', label: 'Packing slip' },
  { type: 'vat_invoice', template_id: 'vat_bd', label: 'VAT invoice (BD)' },
]

export function DocumentsPage() {
  const { t } = useLocale()
  const qc = useQueryClient()
  const { role } = useAuth()
  const [orderId, setOrderId] = useState('')
  const [type, setType] = useState('invoice')
  const [showIssueModal, setShowIssueModal] = useState(false)

  const templates = useQuery({
    queryKey: ['doc-templates'],
    queryFn: api.documents.templates,
    enabled: roleAtLeast(role, 'admin'),
  })
  const docs = useQuery({ queryKey: ['documents'], queryFn: () => api.documents.list() })
  const autoRules = useQuery({
    queryKey: ['auto-issue'],
    queryFn: api.documents.autoIssue,
    enabled: roleAtLeast(role, 'admin'),
  })

  const issue = useMutation({
    mutationFn: () => api.documents.issue(orderId, type),
    onSuccess: () => {
      setOrderId('')
      setShowIssueModal(false)
      qc.invalidateQueries({ queryKey: ['documents'] })
    },
  })

  const setDefault = useMutation({
    mutationFn: ({ docType, key }: { docType: string; key: string }) =>
      api.documents.setDefault(docType, key),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['doc-templates'] }),
  })

  const toggleRule = useMutation({
    mutationFn: ({ id, is_active }: { id: string; is_active: boolean }) =>
      api.documents.updateAutoIssue(id, { is_active }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['auto-issue'] }),
  })

  const defaults = new Map(
    (templates.data ?? []).map((t) => [t.document_type ?? t.type, t.template_id ?? t.template_key]),
  )

  return (
    <>
      <PageHeader
        title={t('documents')}
        subtitle={t('documentsSubtitle')}
        actions={
          roleAtLeast(role, 'admin') ? (
            <Button onClick={() => setShowIssueModal(true)}>
              <Plus size={15} style={{ marginRight: 6 }} />
              {t('issueDocument')}
            </Button>
          ) : undefined
        }
      />

      {roleAtLeast(role, 'admin') ? (
        <Panel title={t('autoIssueRules')}>
          {autoRules.isLoading ? (
            <Loading />
          ) : autoRules.isError ? (
            <ErrorBox error={autoRules.error} />
          ) : !autoRules.data?.length ? (
            <EmptyState title="No auto-issue rules" />
          ) : (
            <div className="stack">
              {autoRules.data.map((r) => (
                <div className="toggle-row" key={r.id}>
                  <div>
                    <strong>{statusLabel(r.trigger)}</strong>
                    <div className="muted">Issue {statusLabel(r.document_type)} automatically</div>
                  </div>
                  <button
                    type="button"
                    className={`switch ${r.is_active ? 'on' : ''}`}
                    onClick={() => toggleRule.mutate({ id: r.id, is_active: !r.is_active })}
                    aria-label={`Toggle ${r.trigger}`}
                  />
                </div>
              ))}
            </div>
          )}
        </Panel>
      ) : null}

      {roleAtLeast(role, 'admin') ? (
        <Panel title={t('templateGallery')}>
          <div className="stat-grid">
            {TEMPLATE_GALLERY.map((item) => {
              const isDefault = defaults.get(item.type) === item.template_id
              return (
                <div key={`${item.type}-${item.template_id}`} className="stat-tile">
                  <span className="stat-label">{statusLabel(item.type)}</span>
                  <strong className="stat-value" style={{ fontSize: '1rem' }}>
                    {item.label}
                  </strong>
                  <div className="row" style={{ marginTop: 8 }}>
                    {isDefault ? <Badge tone="good">default</Badge> : null}
                    <Button
                      size="sm"
                      variant={isDefault ? 'secondary' : 'primary'}
                      onClick={() => setDefault.mutate({ docType: item.type, key: item.template_id })}
                      disabled={setDefault.isPending}
                    >
                      {isDefault ? 'Current' : 'Set default'}
                    </Button>
                  </div>
                </div>
              )
            })}
          </div>
        </Panel>
      ) : null}

      <Panel title={t('issuedDocuments')}>
          {docs.isLoading ? (
            <Loading />
          ) : docs.isError ? (
            <ErrorBox error={docs.error} />
          ) : !docs.data?.length ? (
            <EmptyState title="No documents issued" />
          ) : (
            <Table>
              <thead>
                <tr>
                  <th>Number</th>
                  <th>Type</th>
                  <th>Order</th>
                  <th>PDF</th>
                </tr>
              </thead>
              <tbody>
                {docs.data.map((d) => (
                  <tr key={d.id}>
                    <td>{d.document_number}</td>
                    <td>{statusLabel(d.type)}</td>
                    <td>{shortId(d.order_id)}</td>
                    <td>
                      {d.pdf_ref ? (
                        <Button
                          size="sm"
                          variant="secondary"
                          onClick={() =>
                            api.documents.download(d.id, `${d.document_number}.pdf`)
                          }
                        >
                          Download
                        </Button>
                      ) : (
                        '—'
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </Table>
          )}
      </Panel>

      {roleAtLeast(role, 'admin') ? (
        <Modal open={showIssueModal} title={t('issueDocument')} onClose={() => setShowIssueModal(false)}>
          <div className="stack">
            <label className="field-label">
              Order ID
              <Input value={orderId} onChange={(e) => setOrderId(e.target.value)} />
            </label>
            <label className="field-label">
              Type
              <Select value={type} onChange={(e) => setType(e.target.value)}>
                {DOC_TYPES.map((t) => (
                  <option key={t} value={t}>
                    {statusLabel(t)}
                  </option>
                ))}
              </Select>
            </label>
            {issue.isError ? <ErrorBox error={issue.error} /> : null}
            <Button onClick={() => issue.mutate()} disabled={!orderId || issue.isPending}>
              Issue PDF
            </Button>
          </div>
        </Modal>
      ) : null}
    </>
  )
}
