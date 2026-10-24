import { apiFetch, getAccessToken, API_BASE } from './client'
import type {
  AutoIssueRule,
  AutomationRule,
  BulkCampaign,
  CallSession,
  CashForecast,
  Conversation,
  Customer,
  DataHygieneIssue,
  DialectPack,
  DocumentTemplate,
  Expense,
  FinanceOverview,
  InboxStats,
  Integration,
  IssuedDocument,
  KnowledgeItem,
  LeaveRequest,
  LoyaltyReward,
  MediaUploadResult,
  Message,
  Order,
  Parcel,
  Payment,
  Plan,
  Product,
  Recipe,
  Review,
  RoutingRules,
  SavedReply,
  SetupChecklist,
  Shift,
  Shop,
  ShopPlan,
  SocialPost,
  StockLedgerEntry,
  SupportRequest,
  TeamMember,
  VoicePersona,
  PageAIProfile,
  PageSimulateResponse,
  AdminPlan,
  AdminPageItem,
  AdminShopItem,
  PagePermissionItem,
  SystemUser,
  SystemAdminOverview,
  TokenAnalytics,
  AdminDashboardRow,
  AdminUserUsageHistory,
  AdminCostAnalysis,
  AdminAppPageItem,
  AdminAppPagePermission,
} from '../types/api'

export const api = {
  system: {
    providers: () =>
      apiFetch<{
        public_base_url: string
        providers: Record<string, { configured: boolean; label: string; voice_webhook?: boolean }>
        demo_login: { email: string; password: string }
        note: string
      }>('/system/providers', { auth: false }),
  },
  me: {
    hiddenPages: () => apiFetch<string[]>('/me/hidden-pages'),
  },
  shop: {
    me: () => apiFetch<Shop>('/shops/me'),
    update: (body: Partial<Shop>) =>
      apiFetch<Shop>('/shops/me', { method: 'PATCH', body: JSON.stringify(body) }),
    checklist: () => apiFetch<SetupChecklist>('/shops/me/setup-checklist'),
  },
  team: {
    list: () => apiFetch<TeamMember[]>('/team-members'),
    invite: (body: { email: string; role: string; first_name?: string; last_name?: string }) =>
      apiFetch<TeamMember>('/team-members/invite', { method: 'POST', body: JSON.stringify(body) }),
  },
  products: {
    list: (q?: string, kind?: string) => {
      const params = new URLSearchParams()
      if (q) params.set('q', q)
      if (kind) params.set('kind', kind)
      const qs = params.toString()
      return apiFetch<Product[]>(`/products${qs ? `?${qs}` : ''}`)
    },
    create: (body: unknown) =>
      apiFetch<Product>('/products', { method: 'POST', body: JSON.stringify(body) }),
    update: (id: string, body: unknown) =>
      apiFetch<Product>(`/products/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),
    remove: (id: string) => apiFetch<void>(`/products/${id}`, { method: 'DELETE' }),
    importBulk: (items: unknown[]) =>
      apiFetch<{ created: number; product_ids: string[] }>('/products/import', {
        method: 'POST',
        body: JSON.stringify({ items }),
      }),
    stockLedger: (variantId?: string) =>
      apiFetch<StockLedgerEntry[]>(
        `/products/stock-ledger${variantId ? `?variant_id=${encodeURIComponent(variantId)}` : ''}`,
      ),
    adjustStock: (body: {
      variant_id: string
      delta_qty: number
      reason?: string
      note?: string
      batch_code?: string
      serial_numbers?: string[]
    }) =>
      apiFetch<StockLedgerEntry>('/products/stock-adjust', {
        method: 'POST',
        body: JSON.stringify(body),
      }),
  },
  customers: {
    list: (q?: string) => apiFetch<Customer[]>(`/customers${q ? `?q=${encodeURIComponent(q)}` : ''}`),
    create: (body: unknown) =>
      apiFetch<Customer>('/customers', { method: 'POST', body: JSON.stringify(body) }),
    update: (id: string, body: unknown) =>
      apiFetch<Customer>(`/customers/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),
    block: (id: string, blocked: boolean) =>
      apiFetch<Customer>(`/customers/${id}/block?blocked=${blocked}`, { method: 'PATCH' }),
    recomputeSegments: () =>
      apiFetch<{ updated: number }>('/customers/segments/recompute', { method: 'POST' }),
  },
  reviews: {
    list: (includeHidden = false) =>
      apiFetch<Review[]>(`/reviews?include_hidden=${includeHidden}`),
    create: (body: { customer_id: string; order_id?: string; rating: number; comment?: string }) =>
      apiFetch<Review>('/reviews', { method: 'POST', body: JSON.stringify(body) }),
    hide: (id: string, hidden: boolean) =>
      apiFetch<Review>(`/reviews/${id}/hide?hidden=${hidden}`, { method: 'PATCH' }),
  },
  conversations: {
    list: (status?: string, channel?: string) => {
      const params = new URLSearchParams()
      if (status) params.set('status_filter', status)
      if (channel) params.set('channel_filter', channel)
      const qs = params.toString()
      return apiFetch<Conversation[]>(`/conversations${qs ? `?${qs}` : ''}`)
    },
    create: (body: { customer_id: string; channel?: string; initial_message?: string }) =>
      apiFetch<Conversation>('/conversations', { method: 'POST', body: JSON.stringify(body) }),
    stats: () => apiFetch<InboxStats>('/conversations/stats'),
    messages: (id: string) => apiFetch<Message[]>(`/conversations/${id}/messages`),
    send: (
      id: string,
      body: { direction: string; type: string; text?: string; audio_ref?: string },
    ) =>
      apiFetch<Message>(`/conversations/${id}/messages`, {
        method: 'POST',
        body: JSON.stringify(body),
      }),
    handover: (id: string, body: { assigned_team_member_id: string; summary_note?: string }) =>
      apiFetch<Conversation>(`/conversations/${id}/handover`, {
        method: 'POST',
        body: JSON.stringify(body),
      }),
    transcribe: (cid: string, mid: string, languageHint?: string) =>
      apiFetch<Message>(
        `/conversations/${cid}/messages/${mid}/transcribe${
          languageHint ? `?language_hint=${encodeURIComponent(languageHint)}` : ''
        }`,
        { method: 'POST' },
      ),
  },
  savedReplies: {
    list: () => apiFetch<SavedReply[]>('/saved-replies'),
    create: (body: unknown) =>
      apiFetch<SavedReply>('/saved-replies', { method: 'POST', body: JSON.stringify(body) }),
    update: (id: string, body: unknown) =>
      apiFetch<SavedReply>(`/saved-replies/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),
    remove: (id: string) => apiFetch<void>(`/saved-replies/${id}`, { method: 'DELETE' }),
  },
  orders: {
    list: (status?: string) =>
      apiFetch<Order[]>(`/orders${status ? `?status_filter=${encodeURIComponent(status)}` : ''}`),
    create: (body: unknown) =>
      apiFetch<Order>('/orders', { method: 'POST', body: JSON.stringify(body) }),
    setStatus: (id: string, status: string) =>
      apiFetch<Order>(`/orders/${id}/status`, {
        method: 'PATCH',
        body: JSON.stringify({ status }),
      }),
    importRows: (rows: unknown[]) =>
      apiFetch<{ created: number; order_ids: string[] }>('/orders/import', {
        method: 'POST',
        body: JSON.stringify({ rows }),
      }),
    exportCsv: async () => {
      const res = await fetch(`${API_BASE}/orders/export.csv`, {
        headers: { Authorization: `Bearer ${getAccessToken() ?? ''}` },
      })
      if (!res.ok) throw new Error(`Export failed (${res.status})`)
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = 'orders.csv'
      a.click()
      URL.revokeObjectURL(url)
    },
  },
  media: {
    upload: async (file: File) => {
      const form = new FormData()
      form.append('file', file)
      const res = await fetch(`${API_BASE}/media/upload`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${getAccessToken() ?? ''}` },
        body: form,
      })
      if (!res.ok) {
        const detail = await res.text()
        throw new Error(detail || `Upload failed (${res.status})`)
      }
      return (await res.json()) as MediaUploadResult
    },
    open: async (path: string) => {
      const url = path.startsWith('http')
        ? path
        : `${API_BASE.replace(/\/api\/v1\/?$/, '')}${path.startsWith('/') ? path : `/${path}`}`
      const res = await fetch(url, {
        headers: { Authorization: `Bearer ${getAccessToken() ?? ''}` },
      })
      if (!res.ok) throw new Error(`Open failed (${res.status})`)
      const blob = await res.blob()
      const objectUrl = URL.createObjectURL(blob)
      window.open(objectUrl, '_blank', 'noopener,noreferrer')
      setTimeout(() => URL.revokeObjectURL(objectUrl), 60_000)
    },
  },
  payments: {
    list: (status?: string) =>
      apiFetch<Payment[]>(
        `/payments${status ? `?status_filter=${encodeURIComponent(status)}` : ''}`,
      ),
    create: (body: unknown) =>
      apiFetch<Payment>('/payments', { method: 'POST', body: JSON.stringify(body) }),
    confirm: (id: string) =>
      apiFetch<Payment>(`/payments/${id}/confirm`, { method: 'POST' }),
  },
  delivery: {
    parcels: (status?: string) =>
      apiFetch<Parcel[]>(
        `/delivery/parcels${status ? `?status_filter=${encodeURIComponent(status)}` : ''}`,
      ),
    book: (order_ids: string[], courier: string) =>
      apiFetch<Parcel[]>('/delivery/parcels/book', {
        method: 'POST',
        body: JSON.stringify({ order_ids, courier }),
      }),
    setStatus: (id: string, status: string) =>
      apiFetch<Parcel>(`/delivery/parcels/${id}/status`, {
        method: 'PATCH',
        body: JSON.stringify({ status }),
      }),
    codSummary: () =>
      apiFetch<{ total_outstanding: number; by_courier: Record<string, number> }>(
        '/delivery/cod-summary',
      ),
  },
  finance: {
    overview: () => apiFetch<FinanceOverview>('/finance/overview'),
    expenses: () => apiFetch<Expense[]>('/finance/expenses'),
    addExpense: (body: unknown) =>
      apiFetch<Expense>('/finance/expenses', { method: 'POST', body: JSON.stringify(body) }),
    statement: (period: string) =>
      apiFetch<Record<string, unknown>>(`/finance/statements/${encodeURIComponent(period)}`),
    cashForecast: (days = 30) =>
      apiFetch<CashForecast>(`/finance/cash-forecast?days=${days}`),
    exportCsv: async (exportType: 'sales_book' | 'expenses' | 'stock_value') => {
      const res = await fetch(`${API_BASE}/finance/exports/${exportType}`, {
        headers: { Authorization: `Bearer ${getAccessToken() ?? ''}` },
      })
      if (!res.ok) throw new Error(`Export failed (${res.status})`)
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${exportType}.csv`
      a.click()
      URL.revokeObjectURL(url)
    },
  },
  documents: {
    templates: () => apiFetch<DocumentTemplate[]>('/documents/templates'),
    setDefault: (document_type: string, template_id: string) =>
      apiFetch<DocumentTemplate>('/documents/templates/default', {
        method: 'PATCH',
        body: JSON.stringify({ document_type, template_id }),
      }),
    list: (orderId?: string) =>
      apiFetch<IssuedDocument[]>(
        `/documents${orderId ? `?order_id=${encodeURIComponent(orderId)}` : ''}`,
      ),
    issue: (order_id: string, type: string) =>
      apiFetch<IssuedDocument>('/documents/issue', {
        method: 'POST',
        body: JSON.stringify({ order_id, type }),
      }),
    autoIssue: () => apiFetch<AutoIssueRule[]>('/documents/auto-issue'),
    createAutoIssue: (body: { trigger: string; document_type: string; is_active?: boolean }) =>
      apiFetch<AutoIssueRule>('/documents/auto-issue', {
        method: 'POST',
        body: JSON.stringify(body),
      }),
    updateAutoIssue: (id: string, body: { is_active?: boolean; trigger?: string; document_type?: string }) =>
      apiFetch<AutoIssueRule>(`/documents/auto-issue/${id}`, {
        method: 'PATCH',
        body: JSON.stringify(body),
      }),
    download: async (id: string, filename = 'document.pdf') => {
      const res = await fetch(`${API_BASE}/documents/${id}/download`, {
        headers: { Authorization: `Bearer ${getAccessToken() ?? ''}` },
      })
      if (!res.ok) throw new Error(`Download failed (${res.status})`)
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = filename
      a.click()
      URL.revokeObjectURL(url)
    },
  },
  integrations: {
    list: (category?: string) =>
      apiFetch<Integration[]>(
        `/integrations${category ? `?category=${encodeURIComponent(category)}` : ''}`,
      ),
    connect: (provider: string, config: Record<string, unknown> = {}) =>
      apiFetch<Integration>(`/integrations/${provider}/connect`, {
        method: 'POST',
        body: JSON.stringify({ config }),
      }),
    disconnect: (provider: string) =>
      apiFetch<void>(`/integrations/${provider}`, { method: 'DELETE' }),
    facebookAuthUrl: () =>
      apiFetch<{ authorize_url: string }>('/integrations/facebook/oauth/authorize-url'),
    oauthAuthorizeUrl: (provider: string) =>
      apiFetch<{ authorize_url: string; provider: string }>(
        `/integrations/${provider}/oauth/authorize-url`,
      ),
    syncFacebookCatalogue: () =>
      apiFetch<{ created: number; updated: number; fetched: number }>(
        '/integrations/facebook/sync-catalogue',
        { method: 'POST' },
      ),
  },
  dialects: {
    list: () => apiFetch<DialectPack[]>('/dialect-packs', { auth: false }),
    toggle: (id: string, is_enabled: boolean) =>
      apiFetch<DialectPack>(`/dialect-packs/${id}`, {
        method: 'PATCH',
        body: JSON.stringify({ is_enabled }),
      }),
  },
  automation: {
    rules: () => apiFetch<AutomationRule[]>('/automations/rules'),
    createRule: (body: unknown) =>
      apiFetch<AutomationRule>('/automations/rules', {
        method: 'POST',
        body: JSON.stringify(body),
      }),
    toggle: (id: string, is_active: boolean) =>
      apiFetch<AutomationRule>(`/automations/rules/${id}/toggle?is_active=${is_active}`, {
        method: 'PATCH',
      }),
    recipes: () => apiFetch<Recipe[]>('/automations/recipes'),
    installRecipe: (code: string) =>
      apiFetch<AutomationRule>('/automations/recipes/install', {
        method: 'POST',
        body: JSON.stringify({ code }),
      }),
    campaigns: () => apiFetch<BulkCampaign[]>('/campaigns'),
    bulkCampaign: (body: unknown) =>
      apiFetch<BulkCampaign>('/campaigns/bulk-message', {
        method: 'POST',
        body: JSON.stringify(body),
      }),
    campaignReport: (id: string) => apiFetch<BulkCampaign>(`/campaigns/${id}/report`),
  },
  social: {
    list: () => apiFetch<SocialPost[]>('/social-posts'),
    create: (body: unknown) =>
      apiFetch<SocialPost>('/social-posts', { method: 'POST', body: JSON.stringify(body) }),
    update: (id: string, body: unknown) =>
      apiFetch<SocialPost>(`/social-posts/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),
    delete: (id: string) =>
      apiFetch<void>(`/social-posts/${id}`, { method: 'DELETE' }),
    publish: (id: string) =>
      apiFetch<SocialPost>(`/social-posts/${id}/publish`, { method: 'POST' }),
  },
  loyalty: {
    list: (status = 'waiting') =>
      apiFetch<LoyaltyReward[]>(
        `/loyalty-rewards?status_filter=${encodeURIComponent(status)}`,
      ),
    decide: (id: string, approve: boolean) =>
      apiFetch<LoyaltyReward>(`/loyalty-rewards/${id}/decide`, {
        method: 'PATCH',
        body: JSON.stringify({ approve }),
      }),
  },
  teamOps: {
    shifts: () => apiFetch<Shift[]>('/shifts'),
    draftShifts: (days = 7) =>
      apiFetch<Shift[]>(`/shifts/draft?days=${days}`, { method: 'POST' }),
    confirmShift: (id: string, is_confirmed = true) =>
      apiFetch<Shift>(`/shifts/${id}`, {
        method: 'PATCH',
        body: JSON.stringify({ is_confirmed }),
      }),
    leaveList: () => apiFetch<LeaveRequest[]>('/leave-requests'),
    requestLeave: (body: { start_date: string; end_date: string; reason?: string }) =>
      apiFetch<LeaveRequest>('/leave-requests', { method: 'POST', body: JSON.stringify(body) }),
    decideLeave: (id: string, status: string) =>
      apiFetch<LeaveRequest>(`/leave-requests/${id}`, {
        method: 'PATCH',
        body: JSON.stringify({ status }),
      }),
    hygieneIssues: () => apiFetch<DataHygieneIssue[]>('/data-hygiene/issues'),
    hygieneScan: () =>
      apiFetch<DataHygieneIssue[]>('/data-hygiene/scan', { method: 'POST' }),
    resolveIssue: (id: string) =>
      apiFetch<DataHygieneIssue>(`/data-hygiene/issues/${id}/resolve`, { method: 'PATCH' }),
  },
  plan: {
    catalogue: () => apiFetch<Plan[]>('/plan/catalogue', { auth: false }),
    current: () => apiFetch<ShopPlan>('/plan'),
    change: (plan_code: string) =>
      apiFetch<ShopPlan>('/plan/change', {
        method: 'POST',
        body: JSON.stringify({ plan_code }),
      }),
  },
  support: {
    list: (status?: string) =>
      apiFetch<SupportRequest[]>(
        `/support-requests${status ? `?status_filter=${encodeURIComponent(status)}` : ''}`,
      ),
    create: (body: { subject: string; body: string }) =>
      apiFetch<SupportRequest>('/support-requests', {
        method: 'POST',
        body: JSON.stringify(body),
      }),
    close: (id: string) =>
      apiFetch<SupportRequest>(`/support-requests/${id}/close`, { method: 'PATCH' }),
  },
  ai: {
    knowledge: () => apiFetch<KnowledgeItem[]>('/ai/knowledge'),
    teach: (body: unknown) =>
      apiFetch<KnowledgeItem>('/ai/knowledge', { method: 'POST', body: JSON.stringify(body) }),
    pending: () => apiFetch<KnowledgeItem[]>('/ai/knowledge/pending'),
    approve: (id: string, approve: boolean) =>
      apiFetch<KnowledgeItem>(`/ai/knowledge/pending/${id}/approve?approve=${approve}`, {
        method: 'POST',
      }),
    ask: (question: string) =>
      apiFetch<{ answer: string; used_knowledge_item_ids: string[] }>('/ai/ask', {
        method: 'POST',
        body: JSON.stringify({ question }),
      }),
    socialCaption: (body: {
      kind: 'caption' | 'hashtags'
      language: 'en' | 'bn'
      page_id?: string
      product_id?: string
      photo_url?: string
      context?: string
    }) =>
      apiFetch<{ answer: string; used_image: boolean }>('/ai/social-caption', {
        method: 'POST',
        body: JSON.stringify(body),
      }),
    simulateChat: (message: string) =>
      apiFetch<{ reply: string; note: string }>('/ai/simulate-chat', {
        method: 'POST',
        body: JSON.stringify({ message }),
      }),
    simulateCall: (body: { dialect_code?: string; opening_message?: string } = {}) =>
      apiFetch<{ transcript_preview: string; dialect_used: string; note: string }>(
        '/ai/simulate-call',
        { method: 'POST', body: JSON.stringify(body) },
      ),
    ragStatus: () =>
      apiFetch<{
        ollama_online: boolean
        ollama_version?: string
        chat_model: string
        chat_ready: boolean
        embed_model: string
        embed_ready: boolean
        knowledge_indexed: number
        knowledge_total: number
        products_indexed: number
        products_total: number
        models_available: string[]
      }>('/ai/rag/status'),
    ragReindex: () =>
      apiFetch<{
        shop_id: string
        indexed_knowledge_count: number
        total_knowledge_count: number
        indexed_products_count: number
        total_products_count: number
        message: string
      }>('/ai/rag/reindex', { method: 'POST' }),
    ragSearch: (query: string, top_k = 5) =>
      apiFetch<{
        query: string
        mode: string
        knowledge: Array<{
          id: string
          title: string
          content: string
          category: string
          similarity: number
        }>
        products: Array<{
          id: string
          name: string
          category?: string
          price: number
          similarity: number
          text_summary: string
        }>
      }>('/ai/rag/search', {
        method: 'POST',
        body: JSON.stringify({ query, top_k }),
      }),
  },
  calls: {
    list: () => apiFetch<CallSession[]>('/calls'),
    outbound: (customer_id: string, script_note?: string) =>
      apiFetch<CallSession>('/calls/outbound', {
        method: 'POST',
        body: JSON.stringify({ customer_id, script_note }),
      }),
    get: (id: string) => apiFetch<CallSession>(`/calls/${id}`),
    handover: (id: string) =>
      apiFetch<CallSession>(`/calls/${id}/handover`, { method: 'POST' }),
    monitor: (id: string) =>
      apiFetch<CallSession>(`/calls/${id}/monitor`, { method: 'POST' }),
    voicePersona: () => apiFetch<VoicePersona>('/calls/config/voice-persona'),
    updateVoicePersona: (body: Partial<VoicePersona>) =>
      apiFetch<VoicePersona>('/calls/config/voice-persona', {
        method: 'PATCH',
        body: JSON.stringify(body),
      }),
    routing: () => apiFetch<RoutingRules>('/calls/config/routing-rules'),
    updateRouting: (body: Partial<RoutingRules>) =>
      apiFetch<RoutingRules>('/calls/config/routing-rules', {
        method: 'PATCH',
        body: JSON.stringify(body),
      }),
    metrics: () => apiFetch<Record<string, unknown>>('/calls/config/metrics'),
  },
  pageAi: {
    list: () => apiFetch<PageAIProfile[]>('/ai/pages'),
    get: (pageId: string) => apiFetch<PageAIProfile>(`/ai/pages/${pageId}`),
    study: (pageId: string) =>
      apiFetch<PageAIProfile>(`/ai/pages/${pageId}/study`, { method: 'POST' }),
    trainFromPosts: (pageId: string) =>
      apiFetch<{ fetched_posts: number; new_facts_learned: number; message: string }>(
        `/ai/pages/${pageId}/train-from-posts`,
        { method: 'POST' },
      ),
    update: (pageId: string, body: Partial<PageAIProfile>) =>
      apiFetch<PageAIProfile>(`/ai/pages/${pageId}`, {
        method: 'PATCH',
        body: JSON.stringify(body),
      }),
    knowledge: (pageId: string) => apiFetch<KnowledgeItem[]>(`/ai/pages/${pageId}/knowledge`),
    addKnowledge: (pageId: string, body: { title: string; content: string; category?: string }) =>
      apiFetch<KnowledgeItem>(`/ai/pages/${pageId}/knowledge`, {
        method: 'POST',
        body: JSON.stringify(body),
      }),
    deleteKnowledge: (pageId: string, itemId: string) =>
      apiFetch<void>(`/ai/pages/${pageId}/knowledge/${itemId}`, { method: 'DELETE' }),
    simulateChat: (pageId: string, message: string) =>
      apiFetch<PageSimulateResponse>(`/ai/pages/${pageId}/simulate-chat`, {
        method: 'POST',
        body: JSON.stringify({ message }),
      }),
  },
  systemAdmin: {
    overview: () => apiFetch<SystemAdminOverview>('/system-admin/overview'),
    listPlans: () => apiFetch<AdminPlan[]>('/system-admin/plans'),
    updatePlan: (code: string, body: Partial<AdminPlan>) =>
      apiFetch<AdminPlan>(`/system-admin/plans/${code}`, {
        method: 'PUT',
        body: JSON.stringify(body),
      }),
    listSocialPages: () => apiFetch<AdminPageItem[]>('/system-admin/pages'),
    updateSocialPageVisibility: (pageId: string, is_visible: boolean) =>
      apiFetch<AdminPageItem>(`/system-admin/pages/${pageId}/visibility`, {
        method: 'PUT',
        body: JSON.stringify({ is_visible }),
      }),
    grantSocialPagePermission: (pageId: string, body: { user_id: string; can_view?: boolean; can_manage?: boolean }) =>
      apiFetch<PagePermissionItem>(`/system-admin/pages/${pageId}/permissions`, {
        method: 'POST',
        body: JSON.stringify(body),
      }),
    revokeSocialPagePermission: (pageId: string, userId: string) =>
      apiFetch<void>(`/system-admin/pages/${pageId}/permissions/${userId}`, {
        method: 'DELETE',
      }),
    listAppPages: () => apiFetch<AdminAppPageItem[]>('/system-admin/app-pages'),
    updateAppPageVisibility: (pageKey: string, is_restricted: boolean) =>
      apiFetch<AdminAppPageItem>(`/system-admin/app-pages/${pageKey}/visibility`, {
        method: 'PUT',
        body: JSON.stringify({ is_restricted }),
      }),
    grantAppPagePermission: (pageKey: string, userId: string) =>
      apiFetch<AdminAppPagePermission>(`/system-admin/app-pages/${pageKey}/permissions`, {
        method: 'POST',
        body: JSON.stringify({ user_id: userId }),
      }),
    revokeAppPagePermission: (pageKey: string, userId: string) =>
      apiFetch<void>(`/system-admin/app-pages/${pageKey}/permissions/${userId}`, {
        method: 'DELETE',
      }),
    listUsers: () => apiFetch<SystemUser[]>('/system-admin/users'),
    listShops: () => apiFetch<AdminShopItem[]>('/system-admin/shops'),
    adjustTokens: (shopId: string, body: { amount: number; kind?: string; reason?: string }) =>
      apiFetch<{ status: string; message: string }>(`/system-admin/shops/${shopId}/adjust-tokens`, {
        method: 'POST',
        body: JSON.stringify(body),
      }),
    changePlan: (shopId: string, plan_code: string) =>
      apiFetch<{ status: string; message: string }>(`/system-admin/shops/${shopId}/change-plan`, {
        method: 'POST',
        body: JSON.stringify({ plan_code }),
      }),
    tokenAnalytics: () => apiFetch<TokenAnalytics>('/system-admin/token-analytics'),
    dashboard: () => apiFetch<AdminDashboardRow[]>('/system-admin/dashboard'),
    userUsageHistory: (shopId: string) =>
      apiFetch<AdminUserUsageHistory>(`/system-admin/users/${shopId}/usage`),
    costAnalysis: () => apiFetch<AdminCostAnalysis>('/system-admin/cost-analysis'),
  },
}

