import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Sliders } from 'lucide-react'
import { api } from '../../api/endpoints'
import { Button, Input, Badge } from '../../components/ui/primitives'
import { useToast } from '../../components/ui/ToastProvider'
import type { AdminPlan } from '../../types/api'

export function PlansPage() {
  const queryClient = useQueryClient()
  const { showToast } = useToast()
  const [editingPlanCode, setEditingPlanCode] = useState<string | null>(null)
  const [planForm, setPlanForm] = useState<Partial<AdminPlan>>({})

  const { data: plans, isLoading } = useQuery({
    queryKey: ['system-admin', 'plans'],
    queryFn: api.systemAdmin.listPlans,
  })

  const updatePlanMutation = useMutation({
    mutationFn: ({ code, payload }: { code: string; payload: Partial<AdminPlan> }) =>
      api.systemAdmin.updatePlan(code, payload),
    onSuccess: (updated) => {
      queryClient.invalidateQueries({ queryKey: ['system-admin', 'plans'] })
      queryClient.invalidateQueries({ queryKey: ['plan-catalogue'] })
      setEditingPlanCode(null)
      showToast(`Plan '${updated.name}' rates updated successfully.`, 'success')
    },
    onError: (err: unknown) => {
      showToast(err instanceof Error ? err.message : 'Could not update plan.', 'error')
    },
  })

  const handleEditPlan = (plan: AdminPlan) => {
    setEditingPlanCode(plan.code)
    setPlanForm({
      name: plan.name,
      monthly_price: plan.monthly_price,
      monthly_ai_credits: plan.monthly_ai_credits,
      monthly_voice_minutes: plan.monthly_voice_minutes,
      extra_credit_rate_per_k: plan.extra_credit_rate_per_k,
      extra_voice_rate_per_min: plan.extra_voice_rate_per_min,
      channel_limit: plan.channel_limit,
      team_seat_limit: plan.team_seat_limit,
      is_active: plan.is_active,
    })
  }

  const handleSavePlan = (code: string) => {
    updatePlanMutation.mutate({ code, payload: planForm })
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
        <div>
          <h2 style={{ fontSize: 18, fontWeight: 700, color: '#0f172a', margin: 0 }}>
            Subscription Tiers & Usage Rate Configurations
          </h2>
          <p style={{ color: '#64748b', fontSize: 13, margin: '4px 0 0' }}>
            As product owner, adjust base monthly quotas, prices, channel allocations, and extra usage rates.
          </p>
        </div>
      </div>

      {isLoading ? (
        <div style={{ padding: 40, textAlign: 'center', color: '#64748b' }}>Loading subscription plans...</div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 20 }}>
          {plans?.map((plan) => {
            const isEditing = editingPlanCode === plan.code

            return (
              <div
                key={plan.code}
                style={{
                  background: '#ffffff',
                  border: isEditing ? '2px solid #0284c7' : '1px solid #e2e8f0',
                  borderRadius: 14,
                  padding: 24,
                  boxShadow: '0 2px 10px rgba(0,0,0,0.03)',
                  display: 'flex',
                  flexDirection: 'column',
                  justifyContent: 'space-between',
                }}
              >
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 16 }}>
                    <div>
                      <Badge tone={plan.code === 'enterprise' || plan.code === 'business' ? 'info' : plan.code === 'pro' ? 'good' : 'neutral'}>
                        {plan.code.toUpperCase()} TIER
                      </Badge>
                      <h3 style={{ fontSize: 20, fontWeight: 800, color: '#0f172a', margin: '8px 0 2px' }}>
                        {isEditing ? (
                          <Input
                            value={planForm.name ?? ''}
                            onChange={(e) => setPlanForm({ ...planForm, name: e.target.value })}
                            style={{ fontWeight: 700, fontSize: 16 }}
                          />
                        ) : (
                          plan.name
                        )}
                      </h3>
                    </div>
                    <div style={{ textAlign: 'right' }}>
                      {isEditing ? (
                        <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                          <span>৳</span>
                          <Input
                            type="number"
                            value={planForm.monthly_price ?? 0}
                            onChange={(e) => setPlanForm({ ...planForm, monthly_price: Number(e.target.value) })}
                            style={{ width: 100, fontWeight: 800 }}
                          />
                        </div>
                      ) : (
                        <div style={{ fontSize: 24, fontWeight: 800, color: '#0f172a' }}>
                          ৳{plan.monthly_price}
                          <span style={{ fontSize: 12, fontWeight: 500, color: '#64748b' }}>/mo</span>
                        </div>
                      )}
                    </div>
                  </div>

                  <div style={{ display: 'flex', flexDirection: 'column', gap: 12, borderTop: '1px solid #f1f5f9', paddingTop: 16 }}>
                    <div>
                      <label style={{ fontSize: 12, fontWeight: 600, color: '#64748b', display: 'block', marginBottom: 4 }}>
                        Monthly AI Token / Reply Quota:
                      </label>
                      {isEditing ? (
                        <Input
                          type="number"
                          value={planForm.monthly_ai_credits ?? 0}
                          onChange={(e) => setPlanForm({ ...planForm, monthly_ai_credits: Number(e.target.value) })}
                        />
                      ) : (
                        <span style={{ fontSize: 15, fontWeight: 700, color: '#0f172a' }}>
                          {plan.monthly_ai_credits.toLocaleString()} tokens / credits
                        </span>
                      )}
                    </div>

                    <div>
                      <label style={{ fontSize: 12, fontWeight: 600, color: '#64748b', display: 'block', marginBottom: 4 }}>
                        Channels Included (Facebook, WhatsApp, Viber, etc.):
                      </label>
                      {isEditing ? (
                        <Input
                          type="number"
                          value={planForm.channel_limit ?? 1}
                          onChange={(e) => setPlanForm({ ...planForm, channel_limit: Number(e.target.value) })}
                        />
                      ) : (
                        <span style={{ fontSize: 14, fontWeight: 600, color: '#0f172a' }}>
                          Up to {plan.channel_limit} combined platform channels
                        </span>
                      )}
                    </div>

                    <div>
                      <label style={{ fontSize: 12, fontWeight: 600, color: '#64748b', display: 'block', marginBottom: 4 }}>
                        Extra Usage Rate (Per 1,000 Credits):
                      </label>
                      {isEditing ? (
                        <Input
                          type="number"
                          step="0.5"
                          value={planForm.extra_credit_rate_per_k ?? 10}
                          onChange={(e) => setPlanForm({ ...planForm, extra_credit_rate_per_k: Number(e.target.value) })}
                        />
                      ) : (
                        <span style={{ fontSize: 14, fontWeight: 600, color: '#0f172a' }}>
                          ৳{plan.extra_credit_rate_per_k} per 1k extra tokens
                        </span>
                      )}
                    </div>

                    <div>
                      <label style={{ fontSize: 12, fontWeight: 600, color: '#64748b', display: 'block', marginBottom: 4 }}>
                        Team Seat Limit:
                      </label>
                      {isEditing ? (
                        <Input
                          type="number"
                          value={planForm.team_seat_limit ?? 2}
                          onChange={(e) => setPlanForm({ ...planForm, team_seat_limit: Number(e.target.value) })}
                        />
                      ) : (
                        <span style={{ fontSize: 14, fontWeight: 600, color: '#0f172a' }}>
                          {plan.team_seat_limit} user seats
                        </span>
                      )}
                    </div>
                  </div>
                </div>

                <div style={{ marginTop: 24, paddingTop: 16, borderTop: '1px solid #f1f5f9' }}>
                  {isEditing ? (
                    <div style={{ display: 'flex', gap: 8 }}>
                      <Button onClick={() => handleSavePlan(plan.code)} disabled={updatePlanMutation.isPending} style={{ flex: 1 }}>
                        {updatePlanMutation.isPending ? 'Saving...' : 'Save Plan Rates'}
                      </Button>
                      <Button variant="secondary" onClick={() => setEditingPlanCode(null)}>
                        Cancel
                      </Button>
                    </div>
                  ) : (
                    <Button variant="secondary" onClick={() => handleEditPlan(plan)} style={{ width: '100%', fontWeight: 600 }}>
                      <Sliders size={14} style={{ marginRight: 6 }} /> Edit Plan & Usage Rates
                    </Button>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
