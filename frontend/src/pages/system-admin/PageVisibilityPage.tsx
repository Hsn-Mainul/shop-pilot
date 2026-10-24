import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Eye, EyeOff, UserPlus, Trash2, Users } from 'lucide-react'
import { api } from '../../api/endpoints'
import { Button, Badge, Select, ErrorBox } from '../../components/ui/primitives'
import { useToast } from '../../components/ui/ToastProvider'

export function PageVisibilityPage() {
  const queryClient = useQueryClient()
  const { showToast } = useToast()
  const [selectedPageForPerm, setSelectedPageForPerm] = useState<string | null>(null)
  const [selectedUserId, setSelectedUserId] = useState<string>('')

  const { data: pages, isLoading, isError, error } = useQuery({
    queryKey: ['system-admin', 'app-pages'],
    queryFn: api.systemAdmin.listAppPages,
  })

  const { data: users } = useQuery({
    queryKey: ['system-admin', 'users'],
    queryFn: api.systemAdmin.listUsers,
  })

  const updateVisibilityMutation = useMutation({
    mutationFn: ({ pageKey, isRestricted }: { pageKey: string; isRestricted: boolean }) =>
      api.systemAdmin.updateAppPageVisibility(pageKey, isRestricted),
    onSuccess: (updated) => {
      queryClient.invalidateQueries({ queryKey: ['system-admin', 'app-pages'] })
      queryClient.invalidateQueries({ queryKey: ['hidden-pages'] })
      showToast(
        `'${updated.label}' is now ${updated.is_restricted ? 'restricted to permitted users' : 'visible to everyone'}.`,
        'success',
      )
    },
    onError: (err: unknown) => {
      showToast(err instanceof Error ? err.message : 'Could not update page visibility.', 'error')
    },
  })

  const grantPermissionMutation = useMutation({
    mutationFn: ({ pageKey, userId }: { pageKey: string; userId: string }) =>
      api.systemAdmin.grantAppPagePermission(pageKey, userId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['system-admin', 'app-pages'] })
      queryClient.invalidateQueries({ queryKey: ['hidden-pages'] })
      setSelectedUserId('')
      showToast('User access granted.', 'success')
    },
    onError: (err: unknown) => {
      showToast(err instanceof Error ? err.message : 'Could not grant access.', 'error')
    },
  })

  const revokePermissionMutation = useMutation({
    mutationFn: ({ pageKey, userId }: { pageKey: string; userId: string }) =>
      api.systemAdmin.revokeAppPagePermission(pageKey, userId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['system-admin', 'app-pages'] })
      queryClient.invalidateQueries({ queryKey: ['hidden-pages'] })
      showToast('User access revoked.', 'success')
    },
    onError: (err: unknown) => {
      showToast(err instanceof Error ? err.message : 'Could not revoke access.', 'error')
    },
  })

  return (
    <div>
      <div style={{ marginBottom: 20 }}>
        <h2 style={{ fontSize: 18, fontWeight: 700, color: '#0f172a', margin: 0 }}>
          Application Page Visibility & Permissions
        </h2>
        <p style={{ color: '#64748b', fontSize: 13, margin: '4px 0 0' }}>
          Control access to OUR OWN app modules — Setup, Integrations, Products, and the rest of the sidebar —
          not social media pages. Keep a module visible to every team member, or restrict it to specific users.
        </p>
      </div>

      {isLoading ? (
        <div style={{ padding: 40, textAlign: 'center', color: '#64748b' }}>Loading application pages...</div>
      ) : isError ? (
        <ErrorBox error={error} />
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {pages?.map((page) => (
            <div
              key={page.page_key}
              style={{
                background: '#ffffff',
                border: page.is_restricted ? '1.5px dashed #cbd5e1' : '1px solid #e2e8f0',
                borderRadius: 14,
                padding: 18,
                boxShadow: '0 2px 8px rgba(0,0,0,0.02)',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <h3 style={{ fontSize: 15.5, fontWeight: 700, color: '#0f172a', margin: 0 }}>{page.label}</h3>
                  <Badge tone={page.is_restricted ? 'danger' : 'good'}>
                    {page.is_restricted ? 'Restricted' : 'Visible to All'}
                  </Badge>
                </div>

                <Button
                  size="sm"
                  variant={page.is_restricted ? 'secondary' : 'danger'}
                  onClick={() =>
                    updateVisibilityMutation.mutate({ pageKey: page.page_key, isRestricted: !page.is_restricted })
                  }
                  disabled={updateVisibilityMutation.isPending}
                  style={{ display: 'flex', alignItems: 'center', gap: 6 }}
                >
                  {page.is_restricted ? (
                    <>
                      <Eye size={14} /> Make Visible to All
                    </>
                  ) : (
                    <>
                      <EyeOff size={14} /> Restrict Access
                    </>
                  )}
                </Button>
              </div>

              {page.is_restricted && (
                <div style={{ marginTop: 14, borderTop: '1px solid #f1f5f9', paddingTop: 12 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
                    <span style={{ fontSize: 13, fontWeight: 600, color: '#334155', display: 'flex', alignItems: 'center', gap: 6 }}>
                      <Users size={14} /> Permitted Users ({page.permitted_users.length}):
                    </span>

                    {selectedPageForPerm !== page.page_key && (
                      <button
                        onClick={() => setSelectedPageForPerm(page.page_key)}
                        style={{
                          background: 'none',
                          border: 'none',
                          color: '#0284c7',
                          fontSize: 13,
                          fontWeight: 600,
                          cursor: 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          gap: 4,
                        }}
                      >
                        <UserPlus size={14} /> Add User
                      </button>
                    )}
                  </div>

                  {selectedPageForPerm === page.page_key && (
                    <div
                      style={{
                        background: '#f8fafc',
                        padding: 12,
                        borderRadius: 8,
                        border: '1px solid #e2e8f0',
                        display: 'flex',
                        alignItems: 'center',
                        gap: 10,
                        marginBottom: 12,
                      }}
                    >
                      <Select value={selectedUserId} onChange={(e) => setSelectedUserId(e.target.value)} style={{ flex: 1 }}>
                        <option value="">Select a user to grant access...</option>
                        {users
                          ?.filter((u) => !page.permitted_users.some((p) => p.user_id === u.id))
                          .map((u) => (
                            <option key={u.id} value={u.id}>
                              {u.email} ({u.first_name || ''} {u.last_name || ''}) - {u.role}
                            </option>
                          ))}
                      </Select>
                      <Button
                        size="sm"
                        onClick={() => grantPermissionMutation.mutate({ pageKey: page.page_key, userId: selectedUserId })}
                        disabled={!selectedUserId || grantPermissionMutation.isPending}
                      >
                        Grant Access
                      </Button>
                      <Button size="sm" variant="secondary" onClick={() => setSelectedPageForPerm(null)}>
                        Cancel
                      </Button>
                    </div>
                  )}

                  {page.permitted_users.length === 0 ? (
                    <p style={{ color: '#94a3b8', fontSize: 13, margin: 0, fontStyle: 'italic' }}>
                      No users granted yet. Only Super Admins can access this page.
                    </p>
                  ) : (
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                      {page.permitted_users.map((perm) => (
                        <div
                          key={perm.id}
                          style={{
                            background: '#f1f5f9',
                            border: '1px solid #e2e8f0',
                            borderRadius: 6,
                            padding: '4px 10px',
                            display: 'flex',
                            alignItems: 'center',
                            gap: 8,
                            fontSize: 13,
                          }}
                        >
                          <span style={{ fontWeight: 600, color: '#0f172a' }}>{perm.user_email}</span>
                          <span style={{ color: '#64748b', fontSize: 11 }}>({perm.user_role})</span>
                          <button
                            onClick={() => revokePermissionMutation.mutate({ pageKey: page.page_key, userId: perm.user_id })}
                            style={{ background: 'none', border: 'none', color: '#ef4444', cursor: 'pointer', padding: 2, display: 'flex', alignItems: 'center' }}
                          >
                            <Trash2 size={12} />
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
