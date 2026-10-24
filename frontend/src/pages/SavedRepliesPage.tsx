import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Plus } from 'lucide-react'
import { api } from '../api/endpoints'
import { useAuth } from '../auth/AuthContext'
import { roleAtLeast } from '../lib/roles'
import { ConfirmDialog } from '../components/ui/ConfirmDialog'
import { Modal } from '../components/ui/Modal'
import {
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
import type { SavedReply } from '../types/api'

export function SavedRepliesPage() {
  const qc = useQueryClient()
  const { role } = useAuth()
  const canEdit = roleAtLeast(role, 'admin')

  // Create state
  const [shortcut, setShortcut] = useState('')
  const [title, setTitle] = useState('')
  const [body, setBody] = useState('')
  const [language, setLanguage] = useState('en')
  const [deleteId, setDeleteId] = useState<string | null>(null)

  // Edit state
  const [editingReply, setEditingReply] = useState<SavedReply | null>(null)
  const [editShortcut, setEditShortcut] = useState('')
  const [editTitle, setEditTitle] = useState('')
  const [editBody, setEditBody] = useState('')
  const [editLanguage, setEditLanguage] = useState('en')
  const [showAddModal, setShowAddModal] = useState(false)

  const list = useQuery({ queryKey: ['saved-replies'], queryFn: api.savedReplies.list })

  const create = useMutation({
    mutationFn: () => api.savedReplies.create({ shortcut, title, body, language }),
    onSuccess: () => {
      setShortcut('')
      setTitle('')
      setBody('')
      setShowAddModal(false)
      qc.invalidateQueries({ queryKey: ['saved-replies'] })
    },
  })

  const update = useMutation({
    mutationFn: async () => {
      if (!editingReply) return
      await api.savedReplies.update(editingReply.id, {
        shortcut: editShortcut,
        title: editTitle,
        body: editBody,
        language: editLanguage,
      })
    },
    onSuccess: () => {
      setEditingReply(null)
      qc.invalidateQueries({ queryKey: ['saved-replies'] })
    },
  })

  const remove = useMutation({
    mutationFn: (id: string) => api.savedReplies.remove(id),
    onSuccess: () => {
      setDeleteId(null)
      qc.invalidateQueries({ queryKey: ['saved-replies'] })
    },
  })

  function handleStartEdit(r: SavedReply) {
    setEditingReply(r)
    setEditShortcut(r.shortcut)
    setEditTitle(r.title)
    setEditBody(r.body)
    setEditLanguage(r.language)
  }

  return (
    <>
      <PageHeader
        title="Saved replies"
        subtitle="Shortcut-tagged templates with merge variables (FR-CHAT-03). Include {{shop_name}}."
        actions={
          canEdit ? (
            <Button onClick={() => setShowAddModal(true)}>
              <Plus size={15} style={{ marginRight: 6 }} />
              Add Reply
            </Button>
          ) : undefined
        }
      />

      <Panel title="Library">
          {list.isLoading ? (
            <Loading />
          ) : list.isError ? (
            <ErrorBox error={list.error} />
          ) : !list.data?.length ? (
            <EmptyState title="No saved replies" />
          ) : (
            <Table>
              <thead>
                <tr>
                  <th>Shortcut</th>
                  <th>Title & Body</th>
                  <th>Language</th>
                  <th>Uses</th>
                  <th style={{ textAlign: 'right' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {list.data.map((r) => {
                  const isBeingEdited = editingReply?.id === r.id
                  return (
                    <tr
                      key={r.id}
                      style={{
                        background: isBeingEdited ? '#f8fafc' : undefined,
                        borderLeft: isBeingEdited ? '3px solid #2563eb' : undefined,
                      }}
                    >
                      <td>
                        <code>/{r.shortcut}</code>
                      </td>
                      <td>
                        <strong>{r.title}</strong>
                        <div className="muted">{r.body.slice(0, 80)}</div>
                      </td>
                      <td>{r.language}</td>
                      <td>{r.usage_count}</td>
                      <td>
                        {canEdit ? (
                          <div style={{ display: 'flex', gap: '0.4rem', justifyContent: 'flex-end' }}>
                            <Button
                              size="sm"
                              variant={isBeingEdited ? 'primary' : 'secondary'}
                              onClick={() => handleStartEdit(r)}
                            >
                              Edit
                            </Button>
                            <Button size="sm" variant="danger" onClick={() => setDeleteId(r.id)}>
                              Delete
                            </Button>
                          </div>
                        ) : null}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </Table>
          )}
        </Panel>

        {canEdit ? (
          <>
            <Modal
              open={Boolean(editingReply)}
              title={`Edit reply: /${editingReply?.shortcut ?? ''}`}
              onClose={() => setEditingReply(null)}
            >
                <div className="stack">
                  <label className="field-label">
                    Shortcut
                    <Input
                      value={editShortcut}
                      onChange={(e) => setEditShortcut(e.target.value)}
                      placeholder="thanks"
                    />
                  </label>
                  <label className="field-label">
                    Title
                    <Input value={editTitle} onChange={(e) => setEditTitle(e.target.value)} />
                  </label>
                  <label className="field-label">
                    Body
                    <Textarea
                      value={editBody}
                      onChange={(e) => setEditBody(e.target.value)}
                      placeholder="Hi {{first_name}}, thanks for ordering from {{shop_name}}!"
                    />
                  </label>
                  <label className="field-label">
                    Language
                    <Input value={editLanguage} onChange={(e) => setEditLanguage(e.target.value)} />
                  </label>
                  {update.isError ? <ErrorBox error={update.error} /> : null}
                  <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.5rem' }}>
                    <Button
                      onClick={() => update.mutate()}
                      disabled={!editShortcut || !editTitle || !editBody || update.isPending}
                    >
                      {update.isPending ? 'Saving...' : 'Save Changes'}
                    </Button>
                    <Button variant="secondary" onClick={() => setEditingReply(null)}>
                      Cancel
                    </Button>
                  </div>
                </div>
            </Modal>

            <Modal open={showAddModal} title="Add reply" onClose={() => setShowAddModal(false)}>
                <div className="stack">
                  <label className="field-label">
                    Shortcut
                    <Input value={shortcut} onChange={(e) => setShortcut(e.target.value)} placeholder="thanks" />
                  </label>
                  <label className="field-label">
                    Title
                    <Input value={title} onChange={(e) => setTitle(e.target.value)} />
                  </label>
                  <label className="field-label">
                    Body
                    <Textarea
                      value={body}
                      onChange={(e) => setBody(e.target.value)}
                      placeholder="Hi {{first_name}}, thanks for ordering from {{shop_name}}!"
                    />
                  </label>
                  <label className="field-label">
                    Language
                    <Input value={language} onChange={(e) => setLanguage(e.target.value)} />
                  </label>
                  {create.isError ? <ErrorBox error={create.error} /> : null}
                  <Button
                    onClick={() => create.mutate()}
                    disabled={!shortcut || !title || !body || create.isPending}
                  >
                    Save
                  </Button>
                </div>
            </Modal>
          </>
        ) : null}

      <ConfirmDialog
        open={Boolean(deleteId)}
        title="Delete saved reply?"
        message="Shortcuts using this template will no longer expand."
        danger
        busy={remove.isPending}
        confirmLabel="Delete"
        onCancel={() => setDeleteId(null)}
        onConfirm={() => deleteId && remove.mutate(deleteId)}
      />
    </>
  )
}
