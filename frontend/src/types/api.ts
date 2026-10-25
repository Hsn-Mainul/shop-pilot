export type Role = 'super_admin' | 'admin' | 'sales' | 'support' | 'warehouse'

export interface TokenResponse {
  access_token: string
  refresh_token: string
  token_type: string
}

export interface JwtClaims {
  sub: string
  shop_id: string
  role: Role
  type: string
  exp: number
}

export interface Shop {
  id: string
  name: string
  category: string | null
  currency: string
  timezone: string
  address: string | null
  opening_hours: Record<string, string> | null
  delivery_charge_inside_city: number | null
  delivery_charge_outside_city: number | null
  auto_hide_spam_comments: boolean
  auto_hide_phone_numbers_in_comments: boolean
  ai_auto_reply_comments: boolean
  ai_module_toggles: Record<string, any>
  plan_tier: string
}

export interface SetupStep {
  key: string
  label: string
  group: string
  is_done: boolean
  estimated_minutes: number
}

export interface SetupChecklist {
  percent_complete: number
  steps_done: number
  steps_total: number
  up_next: string | null
  steps: SetupStep[]
}

export interface TeamMember {
  id: string
  email: string
  first_name: string | null
  last_name: string | null
  role: Role
  is_active: boolean
}

export interface ProductVariant {
  id: string
  sku: string | null
  attributes: Record<string, string>
  stock_qty: number
  reorder_point: number
  batch_code: string | null
  serial_numbers: string[]
  location: string | null
}

export interface Product {
  id: string
  name: string
  page_id: string | null
  category: string | null
  description: string | null
  price: number
  cost: number | null
  photo_url: string | null
  post_link: string | null
  kind: string
  pricing_mode: string
  scheduling: Record<string, unknown>
  track_serial: boolean
  track_batch: boolean
  variants: ProductVariant[]
}

export interface StockLedgerEntry {
  id: string
  variant_id: string
  delta_qty: number
  reason: string
  order_id: string | null
  created_by: string | null
  note: string | null
  created_at: string | null
}

export interface Recipe {
  code: string
  name: string
  description: string
  trigger: string
  action: string
  config: Record<string, unknown>
  installed: boolean
}

export interface CashForecast {
  starting_cash: number
  horizon_days: number
  points: Array<{
    label: string
    projected_in: number
    projected_out: number
    net: number
    running_balance: number
  }>
}

export interface Customer {
  id: string
  name: string | null
  phone: string | null
  email: string | null
  source: string | null
  segment: string | null
  is_blocked: boolean
}

export interface Review {
  id: string
  customer_id: string
  order_id: string | null
  rating: number
  comment: string | null
  is_hidden: boolean
}

export interface Conversation {
  id: string
  customer_id: string
  channel: string
  status: string
  assigned_team_member_id: string | null
  page_id?: string | null
}

export interface Message {
  id: string
  direction: string
  type: string
  text: string | null
  audio_ref: string | null
  transcript_confidence: number | null
  detected_language: string | null
  sent_by_ai: boolean
  delivery_status?: string | null
  delivery_detail?: string | null
}

export interface InboxStats {
  conversations_waiting_for_reply: number
  price_request_messages: number
  average_reply_time_seconds: number | null
  orders_from_comments: number
}

export interface OrderItem {
  id: string
  variant_id: string | null
  name_snapshot: string
  quantity: number
  unit_price: number
  unit_cost_snapshot: number | null
}

export interface Order {
  id: string
  customer_id: string
  status: string
  source_channel: string
  total_amount: number
  items: OrderItem[]
  created_at?: string | null
}

export interface AutoIssueRule {
  id: string
  trigger: string
  document_type: string
  is_active: boolean
}

export interface MediaUploadResult {
  url: string
  path?: string
  filename: string
  content_type: string | null
  size: number
}

export interface Payment {
  id: string
  order_id: string
  method: string
  amount: number
  status: string
  sender_number: string | null
  trx_ref: string | null
  note: string | null
}

export interface Parcel {
  id: string
  order_id: string
  courier: string
  status: string
  cod_amount: number
  tracking_id: string | null
  area: string | null
  cod_remitted: boolean
}

export interface FinanceOverview {
  sales: number
  cost_of_goods_sold: number
  gross_profit: number
  expenses_total: number
  net_profit: number
  cash_on_hand: number
  cod_with_couriers: number
  stock_value_at_cost: number
  net_worth: number
}

export interface Expense {
  id: string
  category: string
  amount: number
  paid_from: string
  note: string | null
  receipt_photo_url: string | null
}

export interface KnowledgeItem {
  id: string
  category: string
  title: string
  content: string
  source_file_ref: string | null
  is_pending_approval: boolean
  has_embedding?: boolean
}

export interface Integration {
  id: string
  provider: string
  category: string
  status: string
  config?: Record<string, any>
}

export interface DialectPack {
  id: string
  language_code: string
  region_label: string
  accuracy_status: string
  word_error_rate: number | null
  is_enabled?: boolean
}

export interface AutomationRule {
  id: string
  kind: string
  name: string
  trigger: string
  action: string
  config: Record<string, unknown>
  is_active: boolean
  run_count: number
  failure_count: number
}

export interface BulkCampaign {
  id: string
  channel: string
  segment: string
  message_template: string
  status: string
  sent_count: number
  delivered_count: number
  opted_out_excluded_count: number
  scheduled_at: string | null
}

export interface SocialPost {
  id: string
  channel: string
  photo_urls: string[]
  caption: string | null
  hashtags: string[]
  tagged_product_id: string | null
  send_price_to_inbox: boolean
  first_comment: string | null
  page_id?: string | null
  page_name?: string | null
  error_message?: string | null
  status: string
  scheduled_at: string | null
  published_at: string | null
}

export interface SavedReply {
  id: string
  shortcut: string
  title: string
  body: string
  language: string
  usage_count: number
}

export interface Plan {
  code: string
  name: string
  monthly_price: number
  channel_limit: number
  team_seat_limit: number
  monthly_ai_credits: number
  monthly_voice_minutes: number
}

export interface ShopPlan {
  plan_code: string
  status: string
  renews_at: string | null
  ai_credits_used_this_month: number
  ai_credits_remaining: number
}

export interface SupportRequest {
  id: string
  subject: string
  body: string
  status: string
}

export interface LoyaltyReward {
  id: string
  customer_id: string
  milestone: string
  reward_type: string
  status: string
  note: string | null
}

export interface CallSession {
  id: string
  customer_id: string
  direction: string
  status: string
  duration_seconds: number | null
  recording_ref: string | null
  transcript: string | null
  handled_by_ai: boolean
}

export interface DocumentTemplate {
  document_type: string
  template_id: string
  type?: string
  is_default?: boolean
  template_key?: string
}

export interface IssuedDocument {
  id: string
  order_id: string
  type: string
  document_number: string
  pdf_ref: string | null
}

export interface Shift {
  id: string
  team_member_id: string
  shift_date: string
  planned_hours: number
  is_confirmed: boolean
}

export interface LeaveRequest {
  id: string
  team_member_id: string
  start_date: string
  end_date: string
  reason: string | null
  status: string
}

export interface DataHygieneIssue {
  id: string
  issue_type: string
  related_id: string
  is_resolved: boolean
}

export interface VoicePersona {
  voice_name?: string | null
  name?: string | null
  tone?: string | null
  speaking_pace?: string | null
  language?: string | null
  opening_script: string | null
  must_confirm_before_order?: boolean
  forbidden_topics: string[] | null
}

export interface RoutingRules {
  business_hours_start?: string | null
  business_hours_end?: string | null
  overflow_action?: string | null
  prioritize_repeat_customers?: boolean | null
  max_concurrent_human_lines?: number | null
  inbound_mode?: string | null
  business_hours_only?: boolean | null
  overflow_to_human?: boolean | null
}

export interface PageAIProfile {
  id: string
  shop_id: string
  page_id: string
  platform: string
  page_name: string
  page_category?: string | null
  detected_type: string
  about?: string | null
  bio?: string | null
  mission?: string | null
  website?: string | null
  raw_study_data?: Record<string, any>
  ai_persona_name: string
  ai_role_description?: string | null
  system_instructions?: string | null
  tone: string
  key_topics: string[]
  dos_and_donts?: string | null
  is_active: boolean
  auto_reply_enabled: boolean
  include_product_catalog: boolean
  is_visible?: boolean
  study_status: string
  last_studied_at?: string | null
  created_at: string
  updated_at: string
}

export interface PageSimulateResponse {
  reply: string
  persona: string
  detected_type: string
  used_knowledge_count: number
  used_products_count: number
}

export interface AdminPlan {
  id: string
  code: string
  name: string
  monthly_price: number
  monthly_ai_credits: number
  monthly_voice_minutes: number
  extra_credit_rate_per_k: number
  extra_voice_rate_per_min: number
  channel_limit: number
  team_seat_limit: number
  is_active: boolean
}

export interface PagePermissionItem {
  id: string
  page_id: string
  user_id: string
  user_email: string
  user_name: string
  user_role: string
  can_view: boolean
  can_manage: boolean
  created_at: string
}

export interface AdminPageItem {
  page_id: string
  page_name: string
  platform: string
  page_category?: string | null
  detected_type: string
  is_visible: boolean
  is_active: boolean
  auto_reply_enabled: boolean
  study_status: string
  shop_id: string
  shop_name: string
  permitted_users: PagePermissionItem[]
}

export interface AdminAppPagePermission {
  id: string
  page_key: string
  user_id: string
  user_email: string
  user_name: string
  user_role: string
}

export interface AdminAppPageItem {
  page_key: string
  label: string
  is_restricted: boolean
  permitted_users: AdminAppPagePermission[]
}

export interface SystemUser {
  id: string
  email: string
  first_name?: string | null
  last_name?: string | null
  role: string
  is_active: boolean
}

export interface SystemAdminOverview {
  total_shops: number
  total_pages: number
  visible_pages: number
  invisible_pages: number
  total_users: number
  total_credits_allocated: number
}

export interface AdminShopItem {
  id: string
  name: string
  category?: string | null
  plan_tier: string
  subscription_status: string
  total_credits_granted: number
  total_credits_used: number
  credits_balance: number
  channels_count: number
  members_count: number
  created_at?: string | null
}

export interface TokenAnalytics {
  total_tokens_consumed: number
  total_credits_consumed: number
  channel_breakdown: Record<string, number>
  estimated_wholesale_cost_usd: number
  total_subscriber_revenue_usd: number
  net_margin_percentage: number
  top_consuming_shops: Array<{
    shop_id: string
    shop_name: string
    plan_tier: string
    credits_used: number
  }>
}

export interface AdminDashboardRow {
  shop_id: string
  shop_name: string
  plan_tier: string
  pages_count: number
  platforms: string[]
  credits_used_today: number
  credits_used_this_month: number
  credits_used_total: number
  last_active_at: string | null
}

export interface AdminUsagePoint {
  period: string
  credits_used: number
  tokens_used: number
}

export interface AdminPageUsageBreakdown {
  page_id: string
  page_name: string
  platform: string
  credits_used_total: number
  tokens_used_total: number
  daily: AdminUsagePoint[]
  monthly: AdminUsagePoint[]
  yearly: AdminUsagePoint[]
}

export interface AdminUserUsageHistory {
  shop_id: string
  shop_name: string
  plan_tier: string
  credits_balance: number
  pages: AdminPageUsageBreakdown[]
  daily: AdminUsagePoint[]
  monthly: AdminUsagePoint[]
  yearly: AdminUsagePoint[]
}

export interface AdminCostPoint {
  period: string
  credits_used: number
  tokens_used: number
  cost_usd: number
}

export interface AdminCostAnalysis {
  wholesale_rate_per_million_usd: number
  bdt_to_usd_rate: number
  total_tokens_consumed: number
  total_wholesale_cost_usd: number
  total_subscriber_revenue_usd: number
  net_margin_percentage: number
  daily: AdminCostPoint[]
  monthly: AdminCostPoint[]
  yearly: AdminCostPoint[]
  top_pages_by_cost: Array<{
    page_id: string
    page_name: string
    platform: string
    credits_used: number
    tokens_used: number
    cost_usd: number
  }>
}


