import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Plus } from 'lucide-react'
import { api } from '../../api/endpoints'
import { Button, Input, Badge, Select } from '../../components/ui/primitives'
import { useToast } from '../../components/ui/ToastProvider'
import type { AdminShopItem } from '../../types/api'

export function SubscribersPage() {
  const queryClient = useQueryClient()
  const { showToast } = useToast()
  const [adjustingShop, setAdjustingShop] = useState<AdminShopItem | null>(null)
  const [adjustAmount, setAdjustAmount] = useState<string>('50000')
  const [adjustReason, setAdjustReason] = useState<string>('admin_bonus_grant')
  const [changingPlanShop, setChangingPlanShop] = useState<AdminShopItem | null>(null)
  const [newPlanCode, setNewPlanCode] = useState<string>('pro')

  const { data: shops, isLoading } = useQuery({
    queryKey: ['system-admin', 'shops'],
    queryFn: api.systemAdmin.listShops,
  })

  const adjustTokensMutation = useMutation({
    mutationFn: ({ shopId, amount, reason }: { shopId: string; amount: number; reason: string }) =>
      api.systemAdmin.adjustTokens(shopId, { amount, reason }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['system-admin', 'shops'] })
      queryClient.invalidateQueries({ queryKey: ['system-admin', 'token-analytics'] })
      queryClient.invalidateQueries({ queryKey: ['system-admin', 'dashboard'] })
      setAdjustingShop(null)
      showToast('Shop tokens adjusted successfully.', 'success')
    },
    onError: (err: unknown) => {
      showToast(err instanceof Error ? err.message : 'Could not adjust tokens.', 'error')
    },
  })

  const changePlanMutation = useMutation({
    mutationFn: ({ shopId, planCode }: { shopId: string; planCode: string }) =>
      api.systemAdmin.changePlan(shopId, planCode),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['system-admin', 'shops'] })
      queryClient.invalidateQueries({ queryKey: ['system-admin', 'token-analytics'] })
      setChangingPlanShop(null)
      showToast('Shop plan updated successfully.', 'success')
    },
    onError: (err: unknown) => {
      showToast(err instanceof Error ? err.message : 'Could not change plan.', 'error')
    },
  })

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
        <div>
          <h2 style={{ fontSize: 18, fontWeight: 700, color: '#0f172a', margin: 0 }}>
            Tenant Subscribers & Token Quota Management
          </h2>
          <p style={{ color: '#64748b', fontSize: 13, margin: '4px 0 0' }}>
            Monitor subscriber token balances, grant manual token bonuses, and upgrade or downgrade subscription tiers.
          </p>
        </div>
      </div>

      {isLoading ? (
        <div style={{ padding: 40, textAlign: 'center', color: '#64748b' }}>Loading tenant shops...</div>
      ) : (
        <div style={{ background: '#ffffff', borderRadius: 14, border: '1px solid #e2e8f0', overflow: 'hidden' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: 14 }}>
            <thead>
              <tr style={{ background: '#f8fafc', borderBottom: '1px solid #e2e8f0', color: '#475569' }}>
                <th style={{ padding: '14px 20px', fontWeight: 600 }}>Subscriber / Shop</th>
                <th style={{ padding: '14px 20px', fontWeight: 600 }}>Plan Tier</th>
                <th style={{ padding: '14px 20px', fontWeight: 600 }}>Channels</th>
                <th style={{ padding: '14px 20px', fontWeight: 600 }}>Tokens Granted</th>
                <th style={{ padding: '14px 20px', fontWeight: 600 }}>Tokens Consumed</th>
                <th style={{ padding: '14px 20px', fontWeight: 600 }}>Live Balance</th>
                <th style={{ padding: '14px 20px', fontWeight: 600, textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {shops?.map((s) => {
                const pctUsed = s.total_credits_granted > 0
                  ? Math.min(100, Math.round((s.total_credits_used / s.total_credits_granted) * 100))
                  : 0

                return (
                  <tr key={s.id} style={{ borderBottom: '1px solid #f1f5f9' }}>
                    <td style={{ padding: '16px 20px' }}>
                      <div style={{ fontWeight: 700, color: '#0f172a' }}>{s.name}</div>
                      <div style={{ fontSize: 12, color: '#64748b' }}>{s.category || 'General Store'}</div>
                    </td>
                    <td style={{ padding: '16px 20px' }}>
                      <Badge tone={s.plan_tier === 'enterprise' || s.plan_tier === 'business' ? 'info' : s.plan_tier === 'pro' ? 'good' : 'neutral'}>
                        {s.plan_tier.toUpperCase()}
                      </Badge>
                    </td>
                    <td style={{ padding: '16px 20px', fontWeight: 600, color: '#0f172a' }}>{s.channels_count} connected</td>
                    <td style={{ padding: '16px 20px', fontWeight: 600, color: '#0f172a' }}>
                      {s.total_credits_granted.toLocaleString()}
                    </td>
                    <td style={{ padding: '16px 20px' }}>
                      <div style={{ fontWeight: 600, color: s.total_credits_used > s.total_credits_granted ? '#dc2626' : '#0f172a' }}>
                        {s.total_credits_used.toLocaleString()} ({pctUsed}%)
                      </div>
                      <div style={{ width: 120, height: 6, background: '#f1f5f9', borderRadius: 3, marginTop: 4, overflow: 'hidden' }}>
                        <div
                          style={{
                            width: `${pctUsed}%`,
                            height: '100%',
                            background: pctUsed > 90 ? '#ef4444' : pctUsed > 70 ? '#f59e0b' : '#10b981',
                          }}
                        />
                      </div>
                    </td>
                    <td style={{ padding: '16px 20px' }}>
                      <span style={{ fontWeight: 700, color: s.credits_balance <= 0 ? '#dc2626' : '#16a34a', fontSize: 15 }}>
                        {s.credits_balance.toLocaleString()}
                      </span>
                    </td>
                    <td style={{ padding: '16px 20px', textAlign: 'right' }}>
                      <div style={{ display: 'flex', gap: 6, justifyContent: 'flex-end' }}>
                        <Button
                          size="sm"
                          variant="secondary"
                          onClick={() => {
                            setAdjustingShop(s)
                            setAdjustAmount('50000')
                          }}
                          style={{ display: 'flex', alignItems: 'center', gap: 4 }}
                        >
                          <Plus size={13} /> Grant Tokens
                        </Button>
                        <Button
                          size="sm"
                          variant="secondary"
                          onClick={() => {
                            setChangingPlanShop(s)
                            setNewPlanCode(s.plan_tier)
                          }}
                        >
                          Change Plan
                        </Button>
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      {adjustingShop && (
        <div
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: 'rgba(15,23,42,0.45)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 9999,
          }}
        >
          <div style={{ background: '#ffffff', borderRadius: 14, padding: 24, maxWidth: 440, width: '100%', boxShadow: '0 20px 25px -5px rgba(0,0,0,0.1)' }}>
            <h3 style={{ margin: '0 0 8px', fontSize: 18, fontWeight: 700, color: '#0f172a' }}>
              Grant / Adjust Tokens for {adjustingShop.name}
            </h3>
            <p style={{ margin: '0 0 16px', fontSize: 13, color: '#64748b' }}>
              Add bonus tokens or deduct usage directly from the shop credit ledger.
            </p>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 12, marginBottom: 20 }}>
              <label className="field-label">
                Amount (positive to grant, negative to deduct)
                <Input type="number" value={adjustAmount} onChange={(e) => setAdjustAmount(e.target.value)} />
              </label>
              <label className="field-label">
                Audit Reason
                <Input
                  value={adjustReason}
                  onChange={(e) => setAdjustReason(e.target.value)}
                  placeholder="e.g. promo_campaign_bonus, support_courtesy"
                />
              </label>
            </div>

            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
              <Button variant="secondary" onClick={() => setAdjustingShop(null)}>
                Cancel
              </Button>
              <Button
                onClick={() =>
                  adjustTokensMutation.mutate({
                    shopId: adjustingShop.id,
                    amount: Number(adjustAmount),
                    reason: adjustReason,
                  })
                }
                disabled={adjustTokensMutation.isPending || !adjustAmount}
              >
                {adjustTokensMutation.isPending ? 'Updating...' : 'Confirm Token Adjustment'}
              </Button>
            </div>
          </div>
        </div>
      )}

      {changingPlanShop && (
        <div
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: 'rgba(15,23,42,0.45)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 9999,
          }}
        >
          <div style={{ background: '#ffffff', borderRadius: 14, padding: 24, maxWidth: 440, width: '100%', boxShadow: '0 20px 25px -5px rgba(0,0,0,0.1)' }}>
            <h3 style={{ margin: '0 0 8px', fontSize: 18, fontWeight: 700, color: '#0f172a' }}>
              Change Subscription Plan for {changingPlanShop.name}
            </h3>
            <p style={{ margin: '0 0 16px', fontSize: 13, color: '#64748b' }}>
              Select the plan tier to immediately update this tenant's privileges and quota.
            </p>

            <div style={{ marginBottom: 20 }}>
              <label className="field-label">
                Plan Tier
                <Select value={newPlanCode} onChange={(e) => setNewPlanCode(e.target.value)}>
                  <option value="free">Free Plan (50k tokens, 1 channel)</option>
                  <option value="pro">Pro Plan (500k tokens, 5 channels)</option>
                  <option value="business">Business Plan (2M tokens, 15 channels)</option>
                  <option value="enterprise">Enterprise Plan (Unlimited)</option>
                </Select>
              </label>
            </div>

            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
              <Button variant="secondary" onClick={() => setChangingPlanShop(null)}>
                Cancel
              </Button>
              <Button
                onClick={() =>
                  changePlanMutation.mutate({
                    shopId: changingPlanShop.id,
                    planCode: newPlanCode,
                  })
                }
                disabled={changePlanMutation.isPending}
              >
                {changePlanMutation.isPending ? 'Updating...' : 'Apply New Plan'}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
