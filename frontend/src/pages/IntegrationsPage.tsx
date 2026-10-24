import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState, type ReactNode } from 'react'
import {
  LayoutGrid,
  Trash2,
  Plus,
  CreditCard,
  CheckCircle2,
  Globe,
  MessageCircle,
  Mail,
  MessageSquareText,
  Phone,
  Zap,
  RotateCw,
  AlertTriangle,
  ShoppingBag,
  Store,
  Settings,
} from 'lucide-react'
import { api } from '../api/endpoints'
import { ConfirmDialog } from '../components/ui/ConfirmDialog'
import type { Integration } from '../types/api'
import {
  Button,
  ErrorBox,
  Input,
  PageHeader,
  Select,
} from '../components/ui/primitives'
import './IntegrationsPage.css'

interface CardItemConfig {
  key: string
  name: string
  sub: string
  provider: string
  category: 'channel' | 'payment' | 'courier' | 'telephony'
  icon: () => ReactNode
  features: string[]
  defaultHandle: string
}

// 1. Social & Messaging Channels
const CHANNEL_ITEMS: CardItemConfig[] = [
  {
    key: 'facebook',
    name: 'Facebook',
    sub: 'Pages & Messenger',
    provider: 'facebook',
    category: 'channel',
    defaultHandle: 'behindPscene',
    icon: () => (
      <svg width="44" height="44" viewBox="0 0 40 40" fill="none">
        <circle cx="20" cy="20" r="18" fill="#1877F2" />
        <path
          d="M22.5 21H25.5L26 17H22.5V14.8C22.5 13.8 22.9 13 24.3 13H26V9.4C25.4 9.3 24.3 9.2 23.1 9.2C19.7 9.2 17.5 11.2 17.5 15.2V17H14V21H17.5V31H22.5V21Z"
          fill="white"
        />
      </svg>
    ),
    features: [
      'Auto-reply to Page messages',
      'Multi-page support',
      'OAuth 2.0 authorized',
    ],
  },
  {
    key: 'instagram',
    name: 'Instagram',
    sub: 'Direct Messages',
    provider: 'instagram',
    category: 'channel',
    defaultHandle: 'behindPscene_ig',
    icon: () => (
      <svg width="44" height="44" viewBox="0 0 40 40" fill="none">
        <defs>
          <radialGradient id="igGradChannel" cx="30%" cy="107%" r="130%">
            <stop offset="0%" stopColor="#fdf497" />
            <stop offset="5%" stopColor="#fdf497" />
            <stop offset="45%" stopColor="#fd5949" />
            <stop offset="60%" stopColor="#d6249f" />
            <stop offset="90%" stopColor="#285AEB" />
          </radialGradient>
        </defs>
        <rect x="3" y="3" width="34" height="34" rx="10" fill="url(#igGradChannel)" />
        <rect x="8.5" y="8.5" width="23" height="23" rx="6.5" stroke="white" strokeWidth="2.2" fill="none" />
        <circle cx="20" cy="20" r="5.5" stroke="white" strokeWidth="2.2" fill="none" />
        <circle cx="26" cy="14" r="1.4" fill="white" />
      </svg>
    ),
    features: [
      'Auto-reply to Instagram DMs',
      'Linked via Facebook Business',
      'Pro/Business accounts only',
    ],
  },
  {
    key: 'tiktok',
    name: 'TikTok',
    sub: 'TikTok Shop & Direct Messages',
    provider: 'tiktok',
    category: 'channel',
    defaultHandle: 'behindPscene_tiktok',
    icon: () => (
      <svg width="44" height="44" viewBox="0 0 40 40" fill="none">
        <rect x="2" y="2" width="36" height="36" rx="18" fill="#000000" />
        <g transform="translate(2, 2)">
          <path
            d="M26.5 16.2C25 15.8 23.8 14.6 23.5 13H20V23.2C19.8 24.8 18.4 26 16.7 26C14.8 26 13.3 24.4 13.3 22.5C13.3 20.6 14.8 19 16.7 19C17.2 19 17.6 19.1 18 19.3V15.7C17.6 15.6 17.1 15.5 16.7 15.5C12.8 15.5 9.7 18.6 9.7 22.5C9.7 26.4 12.8 29.5 16.7 29.5C20.6 29.5 23.7 26.4 23.7 22.5V17.5C25.2 18.6 27.1 19.2 29.1 19.2V15.7C28.2 15.7 27.3 15.4 26.5 16.2Z"
            fill="#00F2FE"
          />
          <path
            d="M26.2 15.9C24.7 15.5 23.5 14.3 23.2 12.7H20.3V22.9C20.1 24.5 18.7 25.7 17 25.7C15.1 25.7 13.6 24.1 13.6 22.2C13.6 20.3 15.1 18.7 17 18.7C17.5 18.7 17.9 18.8 18.3 19V16C17.9 15.9 17.4 15.8 17 15.8C13.1 15.8 10 18.9 10 22.8C10 26.7 13.1 29.8 17 29.8C20.9 29.8 24 26.7 24 22.8V17.2C25.5 18.3 27.4 18.9 29.4 18.9V16C28.5 16 27.6 15.7 26.2 15.9Z"
            fill="#FE2C55"
          />
          <path
            d="M25.9 15.6C24.4 15.2 23.2 14 22.9 12.4H20.6V22.6C20.4 24.2 19 25.4 17.3 25.4C15.4 25.4 13.9 23.8 13.9 21.9C13.9 20 15.4 18.4 17.3 18.4C17.8 18.4 18.2 18.5 18.6 18.7V16.3C18.2 16.2 17.7 16.1 17.3 16.1C13.4 16.1 10.3 19.2 10.3 23.1C10.3 27 13.4 30.1 17.3 30.1C21.2 30.1 24.3 27 24.3 23.1V16.9C25.8 18 27.7 18.6 29.7 18.6V16.3C28.8 16.3 27.9 16 25.9 15.6Z"
            fill="#FFFFFF"
          />
        </g>
      </svg>
    ),
    features: [
      'Auto-reply to TikTok Shop customer chats',
      'Product card sync & order inquiries',
      'TikTok Business Messaging API authorized',
    ],
  },
  {
    key: 'whatsapp',
    name: 'WhatsApp',
    sub: 'Cloud API & Twilio',
    provider: 'whatsapp',
    category: 'channel',
    defaultHandle: '+880 1700-000000',
    icon: () => (
      <svg width="44" height="44" viewBox="0 0 40 40" fill="none">
        <circle cx="20" cy="20" r="18" fill="#25D366" />
        <path
          d="M27.2 13.3C25.3 11.4 22.8 10.3 20.1 10.3C14.6 10.3 10.2 14.7 10.2 20.2C10.2 22 10.7 23.7 11.6 25.2L10.3 29.8L15.1 28.5C16.6 29.3 18.3 29.8 20.1 29.8C25.6 29.8 30 25.4 30 19.9C30 17.2 28.9 14.7 27.2 13.3ZM20.1 28.1C18.5 28.1 17 27.7 15.7 26.9L15.4 26.7L12.5 27.5L13.3 24.7L13.1 24.3C12.2 23 11.7 21.5 11.7 19.9C11.7 15.4 15.4 11.7 20 11.7C22.2 11.7 24.3 12.6 25.9 14.1C27.4 15.7 28.3 17.8 28.3 19.9C28.4 24.5 24.7 28.1 20.1 28.1ZM24.7 22.3C24.4 22.2 23.2 21.6 23 21.5C22.8 21.4 22.6 21.4 22.5 21.6C22.3 21.8 21.9 22.3 21.8 22.5C21.7 22.6 21.5 22.6 21.3 22.5C21.1 22.4 20.2 22.1 19.2 21.2C18.4 20.5 17.8 19.6 17.7 19.3C17.5 19.1 17.7 19 17.8 18.9C17.9 18.8 18.1 18.6 18.2 18.5C18.3 18.3 18.4 18.2 18.4 18.1C18.5 18 18.4 17.8 18.4 17.7C18.3 17.6 17.9 16.5 17.7 16.1C17.5 15.6 17.3 15.7 17.2 15.7H16.8C16.6 15.7 16.3 15.8 16.1 16C15.8 16.3 15.2 16.9 15.2 18.1C15.2 19.3 16 20.5 16.2 20.7C16.3 20.8 18 23.4 20.4 24.5C21 24.8 21.5 24.9 21.9 25.1C22.5 25.3 23.1 25.2 23.5 25.2C24 25.1 25.1 24.5 25.3 23.9C25.6 23.3 25.6 22.8 25.5 22.7C25.4 22.5 25 22.4 24.7 22.3Z"
          fill="white"
        />
      </svg>
    ),
    features: [
      'Auto-reply within 24h customer window',
      'Template messages & delivery status',
      'Official WhatsApp Business API',
    ],
  },
  {
    key: 'telegram',
    name: 'Telegram',
    sub: 'Bot API & Groups',
    provider: 'telegram',
    category: 'channel',
    defaultHandle: '@behindPscene_bot',
    icon: () => (
      <svg width="44" height="44" viewBox="0 0 40 40" fill="none">
        <circle cx="20" cy="20" r="18" fill="#229ED9" />
        <path
          d="M12.5 19.8L26.3 14.3C26.9 14 27.5 14.5 27.3 15.1L24.8 26.2C24.6 26.8 23.9 27 23.4 26.6L19.7 23.8L17.8 25.6C17.5 25.9 17.1 25.8 17 25.4L15.9 21.4L12.5 20.4C11.9 20.2 11.9 19.4 12.5 19.8ZM16.8 21.1L23.9 16.7L18.8 22.7L19.1 24.2L20.2 23.1L23.7 25.8L25.8 15.8L14.2 20.3L16.8 21.1Z"
          fill="white"
        />
      </svg>
    ),
    features: [
      'Instant bot message dispatch',
      'Custom slash commands support',
      'Zero setup fee & instant verification',
    ],
  },
  {
    key: 'viber',
    name: 'Viber',
    sub: 'Viber users can easily find you in the Viber directory and chat with you on their favorite messenger',
    provider: 'viber',
    category: 'channel',
    defaultHandle: 'reve_viber_channel',
    icon: () => (
      <svg width="44" height="44" viewBox="0 0 40 40" fill="none">
        <circle cx="20" cy="20" r="18" fill="#7360F2" />
        <path
          d="M26.5 21.2C25.8 20.6 24.8 20.6 24.2 21.2L23.4 22C23.2 22.2 22.9 22.3 22.6 22.1C21.4 21.4 20.1 20.1 19.4 18.9C19.2 18.6 19.3 18.3 19.5 18.1L20.3 17.3C20.9 16.7 20.9 15.7 20.3 15L18.8 13.5C18.2 12.9 17.2 12.9 16.6 13.5L15.3 14.8C14.4 15.7 14.1 17.1 14.6 18.3C15.6 20.8 17.7 23.4 20.7 24.9C21.9 25.5 23.3 25.2 24.2 24.3L25.5 23C26.1 22.4 26.1 21.4 25.5 20.8L24.2 19.5"
          fill="white"
        />
        <path
          d="M23 15C24.5 15.5 25.5 16.5 26 18M23 12C26.3 12.5 28.5 14.7 29 18"
          stroke="white"
          strokeWidth="1.8"
          strokeLinecap="round"
        />
      </svg>
    ),
    features: [
      'Viber Public Bot and Business Messages',
      'One-to-one subscriber messaging',
      'Rich keyboard and media carousels',
    ],
  },
]

// 2. Payment & Wallets
const PAYMENT_ITEMS: CardItemConfig[] = [
  {
    key: 'bkash',
    name: 'bKash',
    sub: 'Merchant Wallet & PGW Checkout',
    provider: 'bkash',
    category: 'payment',
    defaultHandle: '01800000000 (Merchant)',
    icon: () => (
      <svg width="44" height="44" viewBox="0 0 40 40" fill="none">
        <rect x="2" y="2" width="36" height="36" rx="10" fill="#E2136E" />
        <path
          d="M11 20L20 11L29 20L24 29H16L11 20Z"
          stroke="white"
          strokeWidth="2.4"
          fill="none"
          strokeLinejoin="round"
        />
        <circle cx="20" cy="20" r="3" fill="white" />
      </svg>
    ),
    features: [
      'Automated TrxID instant verification',
      'QR checkout & dynamic payment link',
      'Real-time IPN webhook confirmation',
    ],
  },
  {
    key: 'nagad',
    name: 'Nagad',
    sub: 'Digital Wallet & Direct Pay',
    provider: 'nagad',
    category: 'payment',
    defaultHandle: '01700000000 (Nagad)',
    icon: () => (
      <svg width="44" height="44" viewBox="0 0 40 40" fill="none">
        <defs>
          <linearGradient id="nagadGrad" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="#F7941D" />
            <stop offset="100%" stopColor="#D8232A" />
          </linearGradient>
        </defs>
        <rect x="2" y="2" width="36" height="36" rx="10" fill="url(#nagadGrad)" />
        <path
          d="M13 27V13L27 27V13"
          stroke="white"
          strokeWidth="2.8"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    ),
    features: [
      'TrxID SMS & push reconciliation',
      'Direct cash-in proof auto-detection',
      'Automated double-entry ledger entry',
    ],
  },
  {
    key: 'stripe',
    name: 'Stripe',
    sub: 'International Cards & Wallets',
    provider: 'stripe',
    category: 'payment',
    defaultHandle: 'acct_1StripeMerchant',
    icon: () => (
      <svg width="44" height="44" viewBox="0 0 40 40" fill="none">
        <rect x="2" y="2" width="36" height="36" rx="10" fill="#635BFF" />
        <path
          d="M23.5 16.5C23.5 14.8 22 13.8 20 13.8C17.5 13.8 15.5 15 15.5 15L14.5 12C14.5 12 17 10.8 20.5 10.8C24.5 10.8 27.2 13 27.2 16.8C27.2 21.8 20.2 21.5 20.2 23.5C20.2 24.5 21.2 25 22.8 25C25.2 25 27 24 27 24L28 27C28 27 25.5 28.2 22.2 28.2C18.2 28.2 16.5 26 16.5 23C16.5 18.2 23.5 18.5 23.5 16.5Z"
          fill="white"
        />
      </svg>
    ),
    features: [
      'Visa, Mastercard, Amex global checkout',
      'Real-time PaymentIntents & webhook sync',
      'Automated fraud & dispute protection',
    ],
  },
  {
    key: 'sslcommerz',
    name: 'SSLCommerz',
    sub: 'Bangladesh Card & Net Banking',
    provider: 'sslcommerz',
    category: 'payment',
    defaultHandle: 'merchant_sslcz_live',
    icon: () => (
      <svg width="44" height="44" viewBox="0 0 40 40" fill="none">
        <rect x="2" y="2" width="36" height="36" rx="10" fill="#004B91" />
        <rect x="8" y="13" width="24" height="15" rx="3" stroke="white" strokeWidth="2.2" fill="none" />
        <line x1="8" y1="18" x2="32" y2="18" stroke="white" strokeWidth="2.2" />
        <circle cx="13" cy="23" r="1.5" fill="white" />
      </svg>
    ),
    features: [
      '30+ Bangladesh bank cards & internet banking',
      'Automated payment proof verification',
      '0% EMI payment scheme support',
    ],
  },
]

// 3. Couriers & Logistics
const COURIER_ITEMS: CardItemConfig[] = [
  {
    key: 'pathao',
    name: 'Pathao Courier',
    sub: 'On-Demand Parcel Delivery & Logistics',
    provider: 'pathao',
    category: 'courier',
    defaultHandle: 'PathaoMerchant_880',
    icon: () => (
      <svg width="44" height="44" viewBox="0 0 40 40" fill="none">
        <rect x="2" y="2" width="36" height="36" rx="10" fill="#EB2227" />
        <path
          d="M12 24C12 24 15 15 20 15C25 15 28 24 28 24"
          stroke="white"
          strokeWidth="2.6"
          strokeLinecap="round"
        />
        <circle cx="20" cy="23" r="3" fill="white" />
        <path d="M16 19H24" stroke="white" strokeWidth="2" strokeLinecap="round" />
      </svg>
    ),
    features: [
      'One-click merchant consignment booking',
      'Real-time parcel tracking & rider status',
      'Automated COD collection reconciliation',
    ],
  },
  {
    key: 'steadfast',
    name: 'Steadfast Courier',
    sub: 'Nationwide Doorstep Parcel Courier',
    provider: 'steadfast',
    category: 'courier',
    defaultHandle: 'SF_Client_7410',
    icon: () => (
      <svg width="44" height="44" viewBox="0 0 40 40" fill="none">
        <rect x="2" y="2" width="36" height="36" rx="10" fill="#00A651" />
        <path
          d="M11 20L17 26L29 14"
          stroke="white"
          strokeWidth="3.2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    ),
    features: [
      'Doorstep delivery across all 64 districts',
      'Automated return & exchange management',
      'Next-day COD disbursement sync',
    ],
  },
]

// 4. Telephony & Productivity
const TELEPHONY_ITEMS: CardItemConfig[] = [
  {
    key: 'twilio',
    name: 'Twilio Voice',
    sub: 'AI Telephony & Interactive Calls',
    provider: 'twilio',
    category: 'telephony',
    defaultHandle: '+1 (555) 019-2834',
    icon: () => (
      <svg width="44" height="44" viewBox="0 0 40 40" fill="none">
        <circle cx="20" cy="20" r="18" fill="#F22F46" />
        <circle cx="15" cy="15" r="2.6" fill="white" />
        <circle cx="25" cy="15" r="2.6" fill="white" />
        <circle cx="15" cy="25" r="2.6" fill="white" />
        <circle cx="25" cy="25" r="2.6" fill="white" />
      </svg>
    ),
    features: [
      'Outbound AI phone calling & verification',
      'High-fidelity dual-channel recording',
      'Direct connection to AI voice orchestrator',
    ],
  },
  {
    key: 'google',
    name: 'Google Workspace',
    sub: 'OAuth, Contacts & Cloud Backup',
    provider: 'google',
    category: 'telephony',
    defaultHandle: 'shop.admin@gmail.com',
    icon: () => (
      <svg width="44" height="44" viewBox="0 0 40 40" fill="none">
        <rect x="2" y="2" width="36" height="36" rx="10" fill="#ffffff" stroke="#e2e8f0" strokeWidth="1" />
        <path
          d="M28.6 20.2C28.6 19.5 28.5 18.9 28.4 18.3H20V21.8H24.8C24.6 23 23.9 24 22.8 24.7V27H25.7C27.4 25.4 28.6 23 28.6 20.2Z"
          fill="#4285F4"
        />
        <path
          d="M20 29C22.4 29 24.5 28.2 25.7 27L22.8 24.7C22 25.2 21.1 25.5 20 25.5C17.7 25.5 15.7 23.9 15 21.8H12V24.1C13.5 27 16.5 29 20 29Z"
          fill="#34A853"
        />
        <path
          d="M15 21.8C14.8 21.2 14.7 20.6 14.7 20C14.7 19.4 14.8 18.8 15 18.2V15.9H12C11.4 17.1 11 18.5 11 20C11 21.5 11.4 22.9 12 24.1L15 21.8Z"
          fill="#FBBC05"
        />
        <path
          d="M20 14.5C21.3 14.5 22.5 15 23.4 15.8L25.8 13.4C24.5 12.2 22.4 11.5 20 11.5C16.5 11.5 13.5 13.5 12 16.4L15 18.7C15.7 16.6 17.7 14.5 20 14.5Z"
          fill="#EA4335"
        />
      </svg>
    ),
    features: [
      'Google single sign-on authentication',
      'Customer contact & lead synchronization',
      'Automated invoices & receipt cloud storage',
    ],
  },
]

interface FBConnectedPage {
  id: string
  name: string
  category: string
  messenger_enabled: boolean
  comments_enabled: boolean
}

interface IGConnectedAccount {
  id: string
  username: string
  name?: string
  profile_picture_url?: string
  comments_enabled: boolean
  dm_enabled: boolean
  story_replies_enabled: boolean
  story_mentions_enabled: boolean
}

const REVE_SUBNAV_ITEMS = [
  { key: 'website', label: 'Website Integration', icon: Globe },
  { key: 'social', label: 'Social Media Channels', icon: MessageCircle },
  { key: 'email', label: 'Email Integration', icon: Mail },
  { key: 'sms', label: 'SMS Integration', icon: MessageSquareText },
  { key: 'phone', label: 'Phone Integrations', icon: Phone },
  { key: 'integrations', label: 'Integrations', icon: Zap },
  { key: 'google', label: 'Google Integration', icon: () => (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
      <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
      <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
      <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z" fill="#FBBC05"/>
      <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z" fill="#EA4335"/>
    </svg>
  )},
  { key: 'app_store', label: 'App Store Integration', icon: Store },
  { key: 'payment', label: 'Payment Method', icon: CreditCard },
  { key: 'ecommerce', label: 'E-Commerce Integration', icon: ShoppingBag },
  { key: 'tiktok', label: 'TikTok Integration', icon: () => (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
      <path d="M19.59 6.69a4.83 4.83 0 0 1-3.77-4.25V2h-3.45v13.67a2.89 2.89 0 0 1-5.2 1.74 2.89 2.89 0 0 1 2.31-4.64c.29 0 .58.04.86.12V9.42a6.33 6.33 0 0 0-.86-.06 6.34 6.34 0 0 0-6.34 6.34 6.34 6.34 0 0 0 6.34 6.34 6.34 6.34 0 0 0 6.34-6.34V8.58a8.28 8.28 0 0 0 4.84 1.56V6.69z"/>
    </svg>
  )},
  { key: 'whatsapp', label: 'WhatsApp Integration', icon: () => (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
      <path d="M12.04 2C6.58 2 2.13 6.45 2.13 11.91C2.13 13.66 2.59 15.36 3.45 16.86L2.05 22L7.3 20.62C8.75 21.41 10.38 21.83 12.04 21.83C17.5 21.83 21.95 17.38 21.95 11.92C21.95 9.27 20.92 6.78 19.05 4.91C17.18 3.03 14.69 2 12.04 2M12.05 3.67C14.25 3.67 16.31 4.53 17.87 6.09C19.42 7.65 20.28 9.72 20.28 11.92C20.28 16.46 16.58 20.15 12.04 20.15C10.56 20.15 9.11 19.76 7.85 19L7.55 18.83L4.43 19.65L5.26 16.61L5.06 16.29C4.24 14.99 3.8 13.47 3.8 11.91C3.81 7.37 7.5 3.67 12.05 3.67Z"/>
    </svg>
  )},
]

export function IntegrationsPage() {
  const qc = useQueryClient()
  const [reveTab, setReveTab] = useState<string>('social')
  const [isRefreshing, setIsRefreshing] = useState(false)
  const [disconnectProvider, setDisconnectProvider] = useState<string | null>(null)
  const [connectModalItem, setConnectModalItem] = useState<CardItemConfig | null>(null)
  const [modalHandle, setModalHandle] = useState('')
  const [modalPageId, setModalPageId] = useState('')
  const [modalAccessToken, setModalAccessToken] = useState('')
  const [copiedKey, setCopiedKey] = useState(false)

  // Listen for OAuth completion from popup and window focus
  useEffect(() => {
    const handleMessage = (e: MessageEvent) => {
      if (e.data?.type === 'oauth_connected') {
        qc.invalidateQueries({ queryKey: ['integrations'] })
      }
    }
    const handleFocus = () => {
      qc.invalidateQueries({ queryKey: ['integrations'] })
    }
    window.addEventListener('message', handleMessage)
    window.addEventListener('focus', handleFocus)
    return () => {
      window.removeEventListener('message', handleMessage)
      window.removeEventListener('focus', handleFocus)
    }
  }, [qc])

  // Webhooks state
  const [cfgProvider, setCfgProvider] = useState('bkash')
  const [webhookSecret, setWebhookSecret] = useState('')
  const [sigAlgo, setSigAlgo] = useState('hmac_sha256')
  const [sigHeader, setSigHeader] = useState('X-Signature')

  const integrations = useQuery({ queryKey: ['integrations'], queryFn: () => api.integrations.list() })

  const connect = useMutation({
    mutationFn: ({ provider, config = {} }: { provider: string; config?: Record<string, unknown> }) =>
      api.integrations.connect(provider, config),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['integrations'] })
      setConnectModalItem(null)
      setModalHandle('')
      setModalPageId('')
      setModalAccessToken('')
    },
  })

  const disconnect = useMutation({
    mutationFn: (provider: string) => api.integrations.disconnect(provider),
    onSuccess: () => {
      setDisconnectProvider(null)
      qc.invalidateQueries({ queryKey: ['integrations'] })
    },
  })

  const facebook = useMutation({
    mutationFn: api.integrations.facebookAuthUrl,
    onSuccess: (data) => {
      window.open(data.authorize_url, '_blank', 'noopener,noreferrer')
    },
  })

  const oauth = useMutation({
    mutationFn: (provider: string) => api.integrations.oauthAuthorizeUrl(provider),
    onSuccess: (data) => {
      window.open(data.authorize_url, '_blank', 'noopener,noreferrer')
    },
  })

  const syncCatalogue = useMutation({
    mutationFn: api.integrations.syncFacebookCatalogue,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['products'] }),
  })

  const saveWebhook = useMutation({
    mutationFn: () =>
      api.integrations.connect(cfgProvider, {
        webhook_secret: webhookSecret || undefined,
        signature_algo: sigAlgo,
        signature_header: sigHeader,
      }),
    onSuccess: () => {
      setWebhookSecret('')
      qc.invalidateQueries({ queryKey: ['integrations'] })
    },
  })

  // Provider map for fast lookup
  const integrationMap = (integrations.data ?? []).reduce<Record<string, Integration>>(
    (acc, item) => {
      acc[item.provider] = item
      return acc
    },
    {},
  )

  const handleOpenConnect = (item: CardItemConfig) => {
    const existing = integrationMap[item.provider]
    setModalHandle(
      (existing?.config?.page_name as string) ||
        (existing?.config?.account_name as string) ||
        (item.defaultHandle === 'behindPscene' ? '' : item.defaultHandle)
    )
    setModalPageId(String(existing?.config?.page_id || ''))
    setModalAccessToken(String(existing?.config?.page_access_token || ''))

    if (item.provider === 'facebook' || item.provider === 'instagram') {
      facebook.mutate(undefined, {
        onError: () => {
          setConnectModalItem(item)
        },
      })
      return
    }

    if (item.provider === 'google' || item.provider === 'stripe') {
      oauth.mutate(item.provider, {
        onError: () => {
          setConnectModalItem(item)
        },
      })
      return
    }

    setConnectModalItem(item)
  }

  const handleModalSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!connectModalItem) return
    const handle = modalHandle.trim() || connectModalItem.defaultHandle

    if (connectModalItem.provider === 'facebook') {
      const pageId = modalPageId.trim() || `fb_${Date.now()}`
      const pageName = handle.trim() || 'Facebook Page'
      const token = modalAccessToken.trim() || undefined
      connect.mutate({
        provider: 'facebook',
        config: {
          page_id: pageId,
          page_name: pageName,
          page_access_token: token,
          pages: [
            {
              id: pageId,
              name: pageName,
              category: 'Business Page',
              access_token: token,
              messenger_enabled: true,
              comments_enabled: true,
            },
          ],
          connected_count: 1,
        },
      })
      return
    }

    if (connectModalItem.provider === 'instagram') {
      connect.mutate({
        provider: 'instagram',
        config: {
          account_name: handle,
          username: handle,
          accounts: [
            {
              id: `ig_${Date.now()}`,
              username: handle,
              name: handle,
              comments_enabled: true,
              dm_enabled: true,
              story_replies_enabled: false,
              story_mentions_enabled: false,
            },
          ],
          connected_count: 1,
        },
      })
      return
    }

    connect.mutate({
      provider: connectModalItem.provider,
      config: {
        page_name: handle,
        account_name: handle,
        handle: handle,
      },
    })
  }

  // Facebook dynamic state
  const fbInteg = integrationMap['facebook']
  const isFbConnected = fbInteg?.status === 'connected'
  const fbPages: FBConnectedPage[] = (fbInteg?.config?.pages as FBConnectedPage[]) || (
    fbInteg?.config?.page_name ? [{
      id: String(fbInteg.config.page_id || 'page_1'),
      name: String(fbInteg.config.page_name),
      category: String(fbInteg.config.category || 'Business'),
      messenger_enabled: true,
      comments_enabled: true,
    }] : []
  )

  const handleTogglePageFeature = (pageId: string, feature: 'messenger_enabled' | 'comments_enabled') => {
    const updated = fbPages.map((p) => (p.id === pageId ? { ...p, [feature]: !p[feature] } : p))
    connect.mutate({
      provider: 'facebook',
      config: {
        ...(fbInteg?.config || {}),
        pages: updated,
        connected_count: updated.length,
      },
    })
  }

  // Instagram dynamic state
  const igInteg = integrationMap['instagram']
  const isIgConnected = igInteg?.status === 'connected'
  const igAccounts: IGConnectedAccount[] = (igInteg?.config?.accounts as IGConnectedAccount[]) || (
    igInteg?.config?.account_name ? [{
      id: String(igInteg.config.id || 'ig_1'),
      username: String(igInteg.config.account_name),
      name: String(igInteg.config.name || igInteg.config.account_name),
      comments_enabled: Boolean(igInteg.config.comments_enabled ?? false),
      dm_enabled: Boolean(igInteg.config.dm_enabled ?? false),
      story_replies_enabled: Boolean(igInteg.config.story_replies_enabled ?? false),
      story_mentions_enabled: Boolean(igInteg.config.story_mentions_enabled ?? false),
    }] : []
  )

  const handleToggleIgFeature = (
    accountId: string,
    feature: 'comments_enabled' | 'dm_enabled' | 'story_replies_enabled' | 'story_mentions_enabled',
  ) => {
    const updated = igAccounts.map((a) => (a.id === accountId ? { ...a, [feature]: !a[feature] } : a))
    connect.mutate({
      provider: 'instagram',
      config: {
        ...(igInteg?.config || {}),
        accounts: updated,
        connected_count: updated.length,
      },
    })
  }

  const handleRefreshPages = () => {
    setIsRefreshing(true)
    setTimeout(() => {
      qc.invalidateQueries({ queryKey: ['integrations'] })
      setIsRefreshing(false)
    }, 600)
  }

  const renderReveChannelCard = (
    title: string,
    sub: string,
    provider: string,
    itemConfig?: CardItemConfig,
  ) => {
    const integ = integrationMap[provider]
    const isConnected = integ?.status === 'connected'

    return (
      <div key={provider} className="reve-channel-card">
        <div className="reve-channel-card-header">
          <div className="reve-channel-card-main">
            <div className="reve-channel-card-icon">
              {itemConfig ? itemConfig.icon() : <MessageCircle size={32} />}
            </div>
            <div>
              <h3 className="reve-channel-card-title">{title}</h3>
              <p className="reve-channel-card-sub">{sub}</p>
            </div>
          </div>

          {isConnected ? (
            <CheckCircle2 size={22} className="reve-channel-success-icon" />
          ) : (
            <AlertTriangle size={20} className="reve-channel-warning-icon" />
          )}
        </div>

        <div className="reve-connect-box">
          {isConnected ? (
            <div className="reve-connected-status-row">
              <span className="reve-connected-status-text">
                ✓ Connected: {integ?.config?.page_name || integ?.config?.account_name || 'Active'}
              </span>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setDisconnectProvider(provider)}
              >
                Disconnect
              </Button>
            </div>
          ) : (
            <button
              type="button"
              className="reve-btn-connect-fb"
              onClick={() => {
                if (itemConfig) handleOpenConnect(itemConfig)
              }}
            >
              Connect {title}
            </button>
          )}
        </div>
      </div>
    )
  }

  // Render uniform modern card grid for any group of items
  const renderCardGrid = (items: CardItemConfig[], headerTitle: string, badgeLabel: string) => (
    <div className="channels-section-container">
      <div className="channels-header-bar">
        <div className="channels-title-row">
          <span className="channels-title-icon">
            <LayoutGrid size={20} strokeWidth={2.4} />
          </span>
          <h2 className="channels-heading-text">{headerTitle}</h2>
        </div>
        <div className="live-sync-pill">
          <span className="live-sync-dot" />
          <span>{badgeLabel}</span>
        </div>
      </div>

      <div className="active-channels-grid">
        {items.map((ch) => {
          const integ = integrationMap[ch.provider]
          const isConnected = integ?.status === 'connected'
          const accountName =
            integ?.config?.page_name ||
            integ?.config?.account_name ||
            integ?.config?.handle ||
            (isConnected ? ch.defaultHandle : null)

          return (
            <div key={ch.key} className="channel-card-modern">
              <div>
                <div className="channel-top-row">
                  <div className="channel-brand-group">
                    <div className="channel-brand-icon-wrap">{ch.icon()}</div>
                    <div className="channel-brand-info">
                      <h3>{ch.name}</h3>
                      <p className="channel-brand-sub">{ch.sub}</p>
                    </div>
                  </div>

                  {isConnected ? (
                    <div className="channel-status-pill-active">
                      <span className="channel-status-active-dot" />
                      <span>Active</span>
                    </div>
                  ) : (
                    <span className="channel-status-not-linked">Not Linked</span>
                  )}
                </div>

                <div className="channel-usage-counter">
                  {isConnected ? '1 / 1 account used on this plan' : '0 / 1 account used on this plan'}
                </div>

                <div className="channel-features-list">
                  {ch.features.map((feat) => (
                    <div key={feat} className="channel-feature-bullet">
                      <svg
                        className="channel-feature-check"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="#2563eb"
                        strokeWidth="2.2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      >
                        <circle cx="12" cy="12" r="10" stroke="#3b82f6" />
                        <path d="m9 12 2 2 4-4" stroke="#2563eb" />
                      </svg>
                      <span>{feat}</span>
                    </div>
                  ))}
                </div>
              </div>

              <div className="channel-account-block">
                {isConnected ? (
                  <>
                    <div className="channel-linked-label">LINKED ACCOUNTS</div>
                    <div className="channel-linked-item">
                      <div className="channel-account-profile">
                        <div className="channel-avatar-wrapper">
                          <span>{(accountName || 'b')[0]}</span>
                          <span className="channel-avatar-online-dot" />
                        </div>
                        <span className="channel-account-handle">
                          {accountName || ch.defaultHandle}
                        </span>
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <button
                          type="button"
                          className="channel-trash-action"
                          style={{ color: '#2563eb' }}
                          title="Configure / Edit Credentials"
                          onClick={() => {
                            setConnectModalItem(ch)
                            setModalHandle(accountName || '')
                            setModalPageId(String(integ?.config?.page_id || ''))
                            setModalAccessToken(String(integ?.config?.page_access_token || ''))
                          }}
                        >
                          <Settings size={17} strokeWidth={2} />
                        </button>
                        <button
                          type="button"
                          className="channel-trash-action"
                          title="Disconnect account"
                          onClick={() => setDisconnectProvider(ch.provider)}
                        >
                          <Trash2 size={17} strokeWidth={2} />
                        </button>
                      </div>
                    </div>

                    <button type="button" disabled className="channel-btn-limit-reached">
                      Account limit reached
                    </button>
                    <p className="channel-limit-caption">
                      Upgrade or disconnect an account to add another {ch.name} account.
                    </p>

                    {(ch.provider === 'facebook' || ch.provider === 'instagram') && (
                      <a
                        href="/ai-training?tab=pages"
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          gap: '6px',
                          marginTop: '8px',
                          padding: '8px 12px',
                          background: 'rgba(59, 130, 246, 0.12)',
                          border: '1px solid rgba(59, 130, 246, 0.3)',
                          borderRadius: '8px',
                          color: '#60a5fa',
                          fontSize: '12px',
                          fontWeight: 600,
                          textDecoration: 'none',
                        }}
                      >
                        Train Page AI & Study Personas
                      </a>
                    )}
                  </>
                ) : (
                  <button
                    type="button"
                    className="channel-connect-button"
                    onClick={() => handleOpenConnect(ch)}
                    disabled={connect.isPending}
                  >
                    <Plus size={18} strokeWidth={2.4} />
                    <span>Connect {ch.name}</span>
                  </button>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )

  return (
    <>
      <PageHeader
        title="Integrations & Channels"
        subtitle="Connect and manage your active social channels to automate messaging and commerce across every platform."
        actions={
          <Button
            variant="secondary"
            size="sm"
            onClick={() => syncCatalogue.mutate()}
            disabled={syncCatalogue.isPending}
          >
            Sync FB catalogue
          </Button>
        }
      />

      {facebook.isError ? <ErrorBox error={facebook.error} /> : null}
      {connect.isError ? <ErrorBox error={connect.error} /> : null}
      {syncCatalogue.isError ? <ErrorBox error={syncCatalogue.error} /> : null}
      {syncCatalogue.data ? (
        <div className="demo-hint integrations-demo-hint">
          Catalogue sync: {syncCatalogue.data.created} created, {syncCatalogue.data.updated} updated
          ({syncCatalogue.data.fetched} fetched).
        </div>
      ) : null}

      {/* Revechat 2-Column Integrations Layout */}
      <div className="reve-integrations-layout">
        {/* Left Sub-Navigation Menu */}
        <div className="reve-integrations-subnav">
          <div className="reve-subnav-header">INTEGRATIONS</div>
          {REVE_SUBNAV_ITEMS.map((item) => {
            const Icon = item.icon
            const isActive = reveTab === item.key
            return (
              <button
                key={item.key}
                type="button"
                className={`reve-subnav-btn ${isActive ? 'active' : ''}`}
                onClick={() => setReveTab(item.key)}
              >
                <Icon size={16} />
                <span>{item.label}</span>
              </button>
            )
          })}
        </div>

        {/* Right Content Area */}
        <div className="reve-integrations-content">
          {/* TAB 1: SOCIAL MEDIA CHANNELS */}
          {reveTab === 'social' && (
            <div>
              <div className="reve-content-header">
                <h2 className="reve-content-title">Social Media Channels</h2>
                <p className="reve-content-sub">
                  Chat with social media users in REVE Chat! Make sure no fans or customers are lost.
                </p>
              </div>

              {/* Facebook Comments & Messenger Card */}
              <div className="reve-channel-card">
                <div className="reve-channel-card-header">
                  <div className="reve-channel-card-main">
                    <div className="reve-channel-card-icon">
                      <svg width="40" height="40" viewBox="0 0 40 40" fill="none">
                        <circle cx="20" cy="20" r="18" fill="#1877F2" />
                        <path
                          d="M22.5 21H25.5L26 17H22.5V14.8C22.5 13.8 22.9 13 24.3 13H26V9.4C25.4 9.3 24.3 9.2 23.1 9.2C19.7 9.2 17.5 11.2 17.5 15.2V17H14V21H17.5V31H22.5V21Z"
                          fill="white"
                        />
                      </svg>
                    </div>
                    <div>
                      <h3 className="reve-channel-card-title">Facebook Comments & Messenger</h3>
                      <p className="reve-channel-card-sub">
                        {isFbConnected
                          ? `${fbPages.length} page(s) connected`
                          : 'Connect your Facebook page and respond to your fans messages from Reve Chat dashboard'}
                      </p>
                    </div>
                  </div>

                  {isFbConnected ? (
                    <CheckCircle2 size={22} className="reve-channel-success-icon" />
                  ) : (
                    <AlertTriangle size={20} className="reve-channel-warning-icon" />
                  )}
                </div>

                {/* If Connected: Show Connected Facebook Pages List */}
                {isFbConnected ? (
                  <div className="reve-fb-connected-box">
                    <div className="reve-fb-connected-header">
                      <h4 className="reve-fb-connected-title">Connected Facebook Pages</h4>
                      <div className="reve-fb-actions">
                        <button
                          type="button"
                          className="reve-icon-btn"
                          title="Refresh pages"
                          onClick={handleRefreshPages}
                          disabled={isRefreshing}
                        >
                          <RotateCw size={15} className={isRefreshing ? 'spin' : ''} />
                        </button>
                        <button
                          type="button"
                          className="reve-icon-btn"
                          title="Disconnect Facebook"
                          onClick={() => setDisconnectProvider('facebook')}
                        >
                          <Trash2 size={15} />
                        </button>
                      </div>
                    </div>

                    <div className="reve-pages-list">
                      {fbPages.map((page) => (
                        <div key={page.id} className="reve-page-item">
                          <div className="reve-page-info">
                            <div className="reve-page-avatar">{page.name[0]}</div>
                            <div>
                              <div className="reve-page-name">{page.name}</div>
                              <div className="reve-page-category">{page.category}</div>
                            </div>
                          </div>
                          <div className="reve-page-toggles">
                            <label className="reve-checkbox-label">
                              <input
                                type="checkbox"
                                className="reve-checkbox-input"
                                checked={page.messenger_enabled}
                                onChange={() => handleTogglePageFeature(page.id, 'messenger_enabled')}
                              />
                              <span>Messenger</span>
                            </label>
                            <label className="reve-checkbox-label">
                              <input
                                type="checkbox"
                                className="reve-checkbox-input"
                                checked={page.comments_enabled}
                                onChange={() => handleTogglePageFeature(page.id, 'comments_enabled')}
                              />
                              <span>Comments</span>
                            </label>
                          </div>
                        </div>
                      ))}
                    </div>

                    <div className="reve-help-footer">
                      <span>Need Help?</span>{' '}
                      <a href="#tutorial" className="reve-help-link">
                        Watch Tutorial
                      </a>{' '}
                      <span>or</span>{' '}
                      <a href="#chat" className="reve-help-link">
                        Chat with us
                      </a>
                    </div>
                  </div>
                ) : (
                  /* If Not Connected: Show Connect Button */
                  <div className="reve-connect-box">
                    <button
                      type="button"
                      className="reve-btn-connect-fb"
                      onClick={() => handleOpenConnect(CHANNEL_ITEMS.find((c) => c.provider === 'facebook')!)}
                    >
                      Connect Facebook Page
                    </button>
                    <p className="reve-connect-note">
                      To connect your Facebook page you must be the admin of the page.
                    </p>
                    <div className="reve-help-footer">
                      <span>Need Help?</span>{' '}
                      <a href="#tutorial" className="reve-help-link">
                        Watch Tutorial
                      </a>{' '}
                      <span>or</span>{' '}
                      <a href="#chat" className="reve-help-link">
                        Chat with us
                      </a>
                    </div>
                  </div>
                )}
              </div>

              {/* Instagram Card & Guidelines matching Revechat screenshot */}
              <div className="reve-channel-card">
                <div className="reve-content-header">
                  <h3 className="reve-content-title-md">
                    Connected Instagram accounts
                  </h3>
                </div>

                {isIgConnected && igAccounts.length > 0 ? (
                  <div className="reve-ig-card">
                    {igAccounts.map((account) => (
                      <div key={account.id} className="reve-ig-account-row">
                        <div className="reve-ig-account-left">
                          <div className="reve-ig-avatar">
                            {account.username ? account.username.slice(0, 2).toUpperCase() : 'IG'}
                          </div>
                          <span className="reve-ig-username">{account.username}</span>
                        </div>

                        <div className="reve-ig-features-col">
                          <label className="reve-checkbox-label">
                            <input
                              type="checkbox"
                              className="reve-checkbox-input"
                              checked={account.comments_enabled}
                              onChange={() => handleToggleIgFeature(account.id, 'comments_enabled')}
                            />
                            <span>Comments</span>
                          </label>
                          <label className="reve-checkbox-label">
                            <input
                              type="checkbox"
                              className="reve-checkbox-input"
                              checked={account.dm_enabled}
                              onChange={() => handleToggleIgFeature(account.id, 'dm_enabled')}
                            />
                            <span>Direct Messages</span>
                          </label>
                          <label className="reve-checkbox-label">
                            <input
                              type="checkbox"
                              className="reve-checkbox-input"
                              checked={account.story_replies_enabled}
                              onChange={() => handleToggleIgFeature(account.id, 'story_replies_enabled')}
                            />
                            <span>Story Replies</span>
                          </label>
                          <label className="reve-checkbox-label">
                            <input
                              type="checkbox"
                              className="reve-checkbox-input"
                              checked={account.story_mentions_enabled}
                              onChange={() => handleToggleIgFeature(account.id, 'story_mentions_enabled')}
                            />
                            <span>Story Mentions</span>
                          </label>
                        </div>

                        <button
                          type="button"
                          className="reve-icon-btn"
                          title="Disconnect Instagram"
                          onClick={() => setDisconnectProvider('instagram')}
                        >
                          <Trash2 size={15} />
                        </button>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="reve-connect-box">
                    <button
                      type="button"
                      className="reve-btn-connect-fb"
                      onClick={() => handleOpenConnect(CHANNEL_ITEMS.find((c) => c.provider === 'instagram')!)}
                    >
                      Connect Instagram Account
                    </button>
                  </div>
                )}

                {/* Integration Guideline */}
                <div className="reve-ig-guideline-section">
                  <h4 className="reve-ig-guideline-header">Integration Guideline</h4>

                  <div className="reve-ig-guideline-card">
                    <div className="reve-ig-guideline-title">
                      Change your Instagram account from Creator to Business
                    </div>
                    <a
                      href="https://help.instagram.com/502981923235522"
                      target="_blank"
                      rel="noopener noreferrer"
                      className="reve-ig-guideline-link"
                    >
                      How to set up a business account.
                    </a>
                  </div>

                  <div className="reve-ig-guideline-card">
                    <div className="reve-ig-guideline-title">
                      Link your Instagram business account to a Facebook fan page.
                    </div>
                    <a
                      href="https://www.facebook.com/help/instagram/356902681064399"
                      target="_blank"
                      rel="noopener noreferrer"
                      className="reve-ig-guideline-link"
                    >
                      How to link to a Facebook fan page.
                    </a>
                  </div>

                  <div className="reve-ig-help-footer">
                    <span>Still Need Help?</span>{' '}
                    <a href="#tutorial" className="reve-help-link">
                      Watch Tutorial
                    </a>{' '}
                    <span>or</span>{' '}
                    <a href="#chat" className="reve-help-link">
                      Chat with us
                    </a>
                  </div>
                </div>
              </div>

              {/* Viber Card */}
              {renderReveChannelCard(
                'Viber',
                'Viber users can easily find you in the Viber directory and chat with you on their favorite messenger',
                'viber',
                CHANNEL_ITEMS.find((c) => c.provider === 'viber'),
              )}

              {/* Telegram Card */}
              {renderReveChannelCard(
                'Telegram',
                'Connect Telegram Account to manage your customer communication from REVE Chat Dashboard',
                'telegram',
                CHANNEL_ITEMS.find((c) => c.provider === 'telegram'),
              )}

              {/* TikTok Integration Card */}
              {renderReveChannelCard(
                'TikTok Integration',
                'Connect your TikTok Shop & messaging to engage short-video customers directly.',
                'tiktok',
                CHANNEL_ITEMS.find((c) => c.provider === 'tiktok'),
              )}

              {/* WhatsApp Integration Card */}
              {renderReveChannelCard(
                'WhatsApp Integration',
                'Connect WhatsApp Business API for official verified automated customer messaging.',
                'whatsapp',
                CHANNEL_ITEMS.find((c) => c.provider === 'whatsapp'),
              )}
            </div>
          )}

          {/* TAB 2: WEBSITE INTEGRATION */}
          {reveTab === 'website' && (
            <div>
              <div className="reve-content-header">
                <h2 className="reve-content-title">Website Integration</h2>
                <p className="reve-content-sub">
                  Install live chat widget script on your ecommerce website to chat with site visitors in real time.
                </p>
              </div>
              <div className="reve-channel-card">
                <h3 className="reve-channel-card-title">Live Chat Widget Script</h3>
                <p className="reve-channel-card-sub reve-channel-card-sub-spaced">
                  Paste this snippet just before the closing <code>&lt;/body&gt;</code> tag of your website:
                </p>
                <div className="reve-code-block">
                  {`<script src="${window.location.origin}/widget.js" data-shop-id="demo" async></script>`}
                </div>
                <Button
                  variant="primary"
                  size="sm"
                  onClick={() => {
                    navigator.clipboard.writeText(`<script src="${window.location.origin}/widget.js" data-shop-id="demo" async></script>`)
                    setCopiedKey(true)
                    setTimeout(() => setCopiedKey(false), 2000)
                  }}
                >
                  {copiedKey ? 'Snippet Copied!' : 'Copy Script Code'}
                </Button>
              </div>
            </div>
          )}

          {/* TAB 3: EMAIL INTEGRATION */}
          {reveTab === 'email' && (
            <div>
              <div className="reve-content-header">
                <h2 className="reve-content-title">Email Integration</h2>
                <p className="reve-content-sub">
                  Connect your customer support email address (SMTP/IMAP) to automatically convert incoming emails into inbox threads.
                </p>
              </div>
              <div className="reve-channel-card">
                <h3 className="reve-channel-card-title">Support Inbound Email Forwarder</h3>
                <p className="reve-channel-card-sub reve-channel-card-sub-spaced">
                  Forward your custom support emails (e.g. support@yourshop.com) to:
                </p>
                <div className="reve-forwarder-box">
                  inbox+support@yourbrand.revechat.io
                </div>
                <Button variant="secondary" size="sm">Configure SMTP Credentials</Button>
              </div>
            </div>
          )}

          {/* TAB 4: SMS INTEGRATION */}
          {reveTab === 'sms' && (
            <div>
              <div className="reve-content-header">
                <h2 className="reve-content-title">SMS Integration</h2>
                <p className="reve-content-sub">
                  Automate SMS delivery updates, order confirmation notifications, and OTP verification codes.
                </p>
              </div>
              <div className="reve-channel-card">
                <h3 className="reve-channel-card-title">Onnorokom & Twilio SMS Gateway</h3>
                <p className="reve-channel-card-sub reve-channel-card-sub-spaced">
                  Connect your Bangladesh DLR compliant SMS gateway masking:
                </p>
                <div className="reve-btn-group">
                  <Button variant="primary" size="sm">Connect Onnorokom SMS</Button>
                  <Button variant="secondary" size="sm">Connect Twilio SMS</Button>
                </div>
              </div>
            </div>
          )}

          {/* TAB 5: PHONE INTEGRATIONS */}
          {reveTab === 'phone' && (
            <div>
              <div className="reve-content-header">
                <h2 className="reve-content-title">Phone & Voice Integrations</h2>
                <p className="reve-content-sub">
                  Cloud telephony and AI voice call routing for instant customer support.
                </p>
              </div>
              {renderCardGrid(
                TELEPHONY_ITEMS.filter((t) => t.provider !== 'google'),
                'VOICE & PRODUCTIVITY INTEGRATIONS',
                'Connected',
              )}
            </div>
          )}

          {/* TAB 6: INTEGRATIONS & WEBHOOKS */}
          {reveTab === 'integrations' && (
            <div>
              <div className="reve-content-header">
                <h2 className="reve-content-title">Webhooks & API Integrations</h2>
                <p className="reve-content-sub">
                  Cryptographic HMAC signature verification and incoming webhooks for custom external apps.
                </p>
              </div>
              <div className="reve-channel-card">
                <h3 className="reve-channel-card-title">Universal Inbound Webhook</h3>
                <p className="reve-channel-card-sub reve-channel-card-sub-spaced">
                  Endpoint URL: <code>{`${window.location.origin}/api/v1/webhooks/{provider}`}</code>
                </p>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => {
                    navigator.clipboard.writeText(`${window.location.origin}/api/v1/webhooks/meta`)
                    setCopiedKey(true)
                    setTimeout(() => setCopiedKey(false), 2000)
                  }}
                >
                  {copiedKey ? 'Copied!' : 'Copy Webhook URL'}
                </Button>
              </div>

              <div className="reve-channel-card">
                <h3 className="reve-channel-card-title">Signing Secret Vault</h3>
                <div className="integrations-webhook-form">
                  <label className="field-label integrations-field-label">
                    Provider
                    <Select value={cfgProvider} onChange={(e) => setCfgProvider(e.target.value)}>
                      {['bkash', 'nagad', 'pathao', 'steadfast', 'custom'].map((p) => (
                        <option key={p} value={p}>{p.toUpperCase()}</option>
                      ))}
                    </Select>
                  </label>
                  <label className="field-label integrations-field-label">
                    Algorithm
                    <Select value={sigAlgo} onChange={(e) => setSigAlgo(e.target.value)}>
                      {['hmac_sha256', 'hmac_sha1', 'stripe', 'twilio', 'svix', 'meta_sha256', 'md5_body'].map((a) => (
                        <option key={a} value={a}>{a}</option>
                      ))}
                    </Select>
                  </label>
                  <label className="field-label integrations-field-label">
                    Signature Header
                    <Input value={sigHeader} onChange={(e) => setSigHeader(e.target.value)} placeholder="e.g. X-Signature" />
                  </label>
                  <label className="field-label integrations-field-label">
                    Secret Key
                    <Input type="password" value={webhookSecret} onChange={(e) => setWebhookSecret(e.target.value)} placeholder="Paste signing secret" />
                  </label>
                  <Button variant="primary" size="sm" onClick={() => saveWebhook.mutate()} disabled={!webhookSecret || saveWebhook.isPending}>
                    {saveWebhook.isPending ? 'Saving…' : 'Save Secret'}
                  </Button>
                </div>
              </div>
            </div>
          )}

          {/* TAB 7: GOOGLE INTEGRATION */}
          {reveTab === 'google' && (
            <div>
              <div className="reve-content-header">
                <h2 className="reve-content-title">Google Integration</h2>
                <p className="reve-content-sub">
                  Connect Google Business Messages & Analytics to capture search leads.
                </p>
              </div>
              {renderCardGrid(
                TELEPHONY_ITEMS.filter((t) => t.provider === 'google'),
                'GOOGLE ENTERPRISE APIS',
                'Verified',
              )}
            </div>
          )}

          {/* TAB 8: APP STORE INTEGRATION */}
          {reveTab === 'app_store' && (
            <div>
              <div className="reve-content-header">
                <h2 className="reve-content-title">App Store & Mobile SDK Integration</h2>
                <p className="reve-content-sub">
                  Embed live chat directly into your iOS and Android native applications.
                </p>
              </div>
              <div className="reve-channel-card">
                <h3 className="reve-channel-card-title">Mobile SDK App ID</h3>
                <p className="reve-channel-card-sub reve-channel-card-sub-spaced">
                  Use this App Key in your React Native, Flutter, iOS Swift or Android Kotlin SDK initialization:
                </p>
                <div className="reve-forwarder-box">
                  app_live_9f82d19a4e8b3c1024
                </div>
                <Button variant="secondary" size="sm">Download Mobile SDKs</Button>
              </div>
            </div>
          )}

          {/* TAB 9: PAYMENT METHOD */}
          {reveTab === 'payment' && (
            <div>
              <div className="reve-content-header">
                <h2 className="reve-content-title">Payment Methods & Wallets</h2>
                <p className="reve-content-sub">
                  Connect Bangladesh mobile wallets & international cards for instant chat checkout.
                </p>
              </div>
              {renderCardGrid(PAYMENT_ITEMS, 'PAYMENT GATEWAYS & WALLETS', 'Instant Settlement')}
            </div>
          )}

          {/* TAB 10: E-COMMERCE INTEGRATION */}
          {reveTab === 'ecommerce' && (
            <div>
              <div className="reve-content-header">
                <h2 className="reve-content-title">E-Commerce & Courier Integrations</h2>
                <p className="reve-content-sub">
                  Sync parcel shipments and rider status with leading courier networks.
                </p>
              </div>
              {renderCardGrid(COURIER_ITEMS, 'COURIER & LOGISTICS SERVICES', 'Live Tracking')}
            </div>
          )}

          {/* TAB 11: TIKTOK INTEGRATION */}
          {reveTab === 'tiktok' && (
            <div>
              <div className="reve-content-header">
                <h2 className="reve-content-title">TikTok Integration</h2>
                <p className="reve-content-sub">
                  Direct TikTok Shop & creator messaging integration.
                </p>
              </div>
              {renderReveChannelCard(
                'TikTok Integration',
                'Connect your TikTok Shop & messaging to engage short-video customers directly.',
                'tiktok',
                CHANNEL_ITEMS.find((c) => c.provider === 'tiktok'),
              )}
            </div>
          )}

          {/* TAB 12: WHATSAPP INTEGRATION */}
          {reveTab === 'whatsapp' && (
            <div>
              <div className="reve-content-header">
                <h2 className="reve-content-title">WhatsApp Integration</h2>
                <p className="reve-content-sub">
                  Official Meta WhatsApp Cloud API for verified green-badge business messaging.
                </p>
              </div>
              {renderReveChannelCard(
                'WhatsApp Integration',
                'Connect WhatsApp Business API for official verified automated customer messaging.',
                'whatsapp',
                CHANNEL_ITEMS.find((c) => c.provider === 'whatsapp'),
              )}
            </div>
          )}
        </div>
      </div>

      {/* Disconnect Confirmation Modal */}
      <ConfirmDialog
        open={Boolean(disconnectProvider)}
        title={`Disconnect ${disconnectProvider || 'integration'}?`}
        message={`This will unlink your ${disconnectProvider} account from the shop. You can reconnect it anytime.`}
        danger
        busy={disconnect.isPending}
        confirmLabel="Disconnect"
        onCancel={() => setDisconnectProvider(null)}
        onConfirm={() => disconnectProvider && disconnect.mutate(disconnectProvider)}
      />

      {/* Connect Channel Modal */}
      {connectModalItem ? (
        <div className="channel-modal-overlay" onClick={() => setConnectModalItem(null)}>
          <div className="channel-modal-dialog" onClick={(e) => e.stopPropagation()}>
            <div className="channel-modal-header">
              <div className="channel-modal-icon">{connectModalItem.icon()}</div>
              <div>
                <h3 className="channel-modal-title">
                  Connect {connectModalItem.name}
                </h3>
                <p className="muted channel-modal-sub">
                  {connectModalItem.sub}
                </p>
              </div>
            </div>

            <form onSubmit={handleModalSubmit} className="stack channel-modal-form">
              <label className="field-label">
                Account ID / Handle / Merchant Number
                <Input
                  value={modalHandle}
                  onChange={(e) => setModalHandle(e.target.value)}
                  placeholder={connectModalItem.defaultHandle}
                  required
                  autoFocus
                />
              </label>

              <div className="channel-modal-actions">
                <Button
                  type="button"
                  variant="secondary"
                  onClick={() => setConnectModalItem(null)}
                >
                  Cancel
                </Button>
                <Button type="submit" disabled={connect.isPending}>
                  {connect.isPending ? 'Connecting…' : `Confirm & Link ${connectModalItem.name}`}
                </Button>
              </div>
            </form>
          </div>
        </div>
      ) : null}
    </>
  )
}
