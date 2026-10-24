import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Plus } from 'lucide-react'
import { api } from '../api/endpoints'
import { statusLabel } from '../lib/format'
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
  Textarea,
} from '../components/ui/primitives'

export function CampaignsPage() {
  const { t } = useLocale()
  const qc = useQueryClient()
  const [channel, setChannel] = useState('whatsapp')
  const [segment, setSegment] = useState('all')
  const [message, setMessage] = useState(
    'Hi {{first_name}}, thanks for shopping with {{shop_name}}!',
  )
  const [reportId, setReportId] = useState('')
  const [showAddModal, setShowAddModal] = useState(false)

  const history = useQuery({
    queryKey: ['campaigns'],
    queryFn: api.automation.campaigns,
  })

  const create = useMutation({
    mutationFn: () =>
      api.automation.bulkCampaign({
        channel,
        segment,
        message_template: message,
      }),
    onSuccess: (data) => {
      setReportId(data.id)
      setShowAddModal(false)
      qc.invalidateQueries({ queryKey: ['campaigns'] })
    },
  })

  const report = useMutation({
    mutationFn: (id: string) => api.automation.campaignReport(id),
    onSuccess: (data) => {
      setReportId(data.id)
      qc.invalidateQueries({ queryKey: ['campaigns'] })
    },
  })

  return (
    <>
      <PageHeader
        title={t('campaigns')}
        subtitle="Bulk email, SMS, WhatsApp, and voice campaigns (FR-CUST-06/07/08)."
        actions={
          <Button onClick={() => setShowAddModal(true)}>
            <Plus size={15} style={{ marginRight: 6 }} />
            Create Campaign
          </Button>
        }
      />

      <Modal open={showAddModal} title="Create campaign" onClose={() => setShowAddModal(false)}>
        <div className="stack">
          <label className="field-label">
            Channel
            <Select value={channel} onChange={(e) => setChannel(e.target.value)}>
              {['whatsapp', 'sms', 'email', 'voice'].map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </Select>
          </label>
          <label className="field-label">
            Segment
            <Select value={segment} onChange={(e) => setSegment(e.target.value)}>
              {['all', 'vip', 'repeat_customer', 'one_time_customer', 'no_orders_yet'].map((s) => (
                <option key={s} value={s}>
                  {statusLabel(s)}
                </option>
              ))}
            </Select>
          </label>
          <label className="field-label">
            Message template
            <Textarea value={message} onChange={(e) => setMessage(e.target.value)} rows={5} />
          </label>
          {create.isError ? <ErrorBox error={create.error} /> : null}
          <Button onClick={() => create.mutate()} disabled={!message || create.isPending}>
            {create.isPending ? 'Queueing…' : 'Queue campaign'}
          </Button>
          {create.data ? (
            <div className="demo-hint">
              Campaign created · <Badge>{create.data.status}</Badge>
              <div className="muted">ID: {create.data.id}</div>
            </div>
          ) : null}
        </div>
      </Modal>

      <Panel title="Campaign report">
        <div className="stack">
          <label className="field-label">
            Campaign ID
            <Input value={reportId} onChange={(e) => setReportId(e.target.value)} />
          </label>
          <Button
            variant="secondary"
            onClick={() => report.mutate(reportId)}
            disabled={!reportId || report.isPending}
          >
            {report.isPending ? 'Loading…' : 'Load report'}
          </Button>
          {report.isError ? <ErrorBox error={report.error} /> : null}
          {report.data ? (
            <div className="demo-hint">
              Status: {report.data.status}
              <br />
              Sent: {report.data.sent_count} · Delivered: {report.data.delivered_count}
              <br />
              Opt-outs excluded: {report.data.opted_out_excluded_count}
            </div>
          ) : null}
        </div>
      </Panel>

      <Panel title="Campaign history">
        {history.isLoading ? (
          <Loading />
        ) : history.isError ? (
          <ErrorBox error={history.error} />
        ) : !history.data?.length ? (
          <EmptyState title="No campaigns yet" hint="Create one above to track it here." />
        ) : (
          <div className="stack">
            {history.data.map((c) => (
              <div className="row" key={c.id} style={{ justifyContent: 'space-between' }}>
                <div>
                  <strong>{c.channel}</strong> · {statusLabel(c.segment)}
                  <div className="muted">{c.id}</div>
                </div>
                <div className="row">
                  <Badge>{c.status}</Badge>
                  <span className="muted">
                    {c.sent_count}/{c.delivered_count}
                  </span>
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={() => report.mutate(c.id)}
                  >
                    Refresh
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </Panel>
    </>
  )
}
