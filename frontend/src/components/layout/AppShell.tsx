import { useState } from 'react'
import type { ReactNode } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  Bot,
  Boxes,
  ChevronDown,
  CreditCard,
  Headphones,
  LayoutDashboard,
  Menu,
  MessageSquare,
  Package,
  Settings,
  Shield,
  Sparkles,
  Store,
  Truck,
  Users,
  Wallet,
  Warehouse,
  Workflow,
  X,
} from 'lucide-react'
import { api } from '../../api/endpoints'
import { useAuth } from '../../auth/AuthContext'
import { useRealtime } from '../../hooks/useRealtime'
import { useLocale } from '../../i18n/LocaleContext'
import type { MessageKey } from '../../i18n/messages'
import { roleAtLeast, roleLabel } from '../../lib/roles'
import { Button, Select } from '../ui/primitives'
import type { Role } from '../../types/api'

type NavChild = { to: string; label: string }

type NavItem = {
  to: string
  labelKey: MessageKey
  icon: ReactNode
  minRole?: Role
  superOnly?: boolean
  children?: NavChild[]
}

type NavGroup = { label: string; items: NavItem[] }

const NAV: NavGroup[] = [
  {
    label: 'Home',
    items: [
      { to: '/', labelKey: 'overview', icon: <LayoutDashboard size={16} /> },
      { to: '/ai-control', labelKey: 'aiControl', icon: <Bot size={16} />, minRole: 'admin' },
      { to: '/setup', labelKey: 'setup', icon: <Sparkles size={16} /> },
    ],
  },
  {
    label: 'Sell',
    items: [
      { to: '/inbox', labelKey: 'inbox', icon: <MessageSquare size={16} /> },
      { to: '/comments', labelKey: 'comments', icon: <MessageSquare size={16} /> },
      { to: '/calls', labelKey: 'calls', icon: <Headphones size={16} />, minRole: 'sales' },
      { to: '/orders', labelKey: 'orders', icon: <Package size={16} /> },
      { to: '/payments', labelKey: 'payments', icon: <CreditCard size={16} /> },
      { to: '/delivery', labelKey: 'delivery', icon: <Truck size={16} /> },
      { to: '/saved-replies', labelKey: 'savedReplies', icon: <MessageSquare size={16} /> },
    ],
  },
  {
    label: 'Catalogue',
    items: [
      { to: '/products', labelKey: 'products', icon: <Boxes size={16} /> },
      { to: '/services', labelKey: 'services', icon: <Sparkles size={16} /> },
      { to: '/inventory', labelKey: 'inventory', icon: <Warehouse size={16} /> },
    ],
  },
  {
    label: 'Customers',
    items: [
      { to: '/customers', labelKey: 'customers', icon: <Users size={16} /> },
      { to: '/reviews', labelKey: 'reviews', icon: <Users size={16} /> },
      { to: '/loyalty', labelKey: 'loyalty', icon: <Sparkles size={16} />, minRole: 'support' },
    ],
  },
  {
    label: 'Grow',
    items: [
      { to: '/social', labelKey: 'social', icon: <Sparkles size={16} />, minRole: 'sales' },
      { to: '/ai-assistant', labelKey: 'aiAssistant', icon: <Bot size={16} />, minRole: 'support' },
      { to: '/ai-training', labelKey: 'trainAi', icon: <Bot size={16} />, minRole: 'admin' },
      { to: '/campaigns', labelKey: 'campaigns', icon: <Workflow size={16} />, minRole: 'admin' },
    ],
  },
  {
    label: 'Money',
    items: [
      { to: '/finance', labelKey: 'finance', icon: <Wallet size={16} />, minRole: 'admin' },
      { to: '/documents', labelKey: 'documents', icon: <Package size={16} />, minRole: 'sales' },
    ],
  },
  {
    label: 'Automate',
    items: [
      { to: '/automations', labelKey: 'automations', icon: <Workflow size={16} />, minRole: 'admin' },
    ],
  },
  {
    label: 'Shop',
    items: [
      { to: '/team', labelKey: 'team', icon: <Users size={16} />, minRole: 'admin' },
      { to: '/integrations', labelKey: 'integrations', icon: <Store size={16} />, minRole: 'admin' },
      { to: '/plan', labelKey: 'plan', icon: <CreditCard size={16} />, minRole: 'admin' },
      { to: '/data-hygiene', labelKey: 'dataHygiene', icon: <Settings size={16} />, minRole: 'admin' },
      { to: '/settings', labelKey: 'settings', icon: <Settings size={16} />, minRole: 'admin' },
      { to: '/support', labelKey: 'support', icon: <Headphones size={16} /> },
    ],
  },
  {
    label: 'Platform',
    items: [
      {
        to: '/system-admin',
        labelKey: 'systemAdmin',
        icon: <Shield size={16} />,
        superOnly: true,
        children: [
          { to: '/system-admin/dashboard', label: 'Dashboard' },
          { to: '/system-admin/users', label: 'User List' },
          { to: '/system-admin/plans', label: 'Subscription Plans & Rates' },
          { to: '/system-admin/subscribers', label: 'Subscribers & Token Limits' },
          { to: '/system-admin/page-visibility', label: 'App Page Visibility' },
          { to: '/system-admin/cost-analysis', label: 'Cost Analysis' },
        ],
      },
    ],
  },
]

function canSee(item: NavItem, role: Role | null, hiddenPages: string[]) {
  if (item.superOnly && role !== 'super_admin') return false
  if (item.minRole && !roleAtLeast(role, item.minRole)) return false
  if (
    role === 'warehouse' &&
    ['/inbox', '/comments', '/calls', '/ai-assistant', '/ai-training', '/campaigns', '/social'].includes(
      item.to,
    )
  ) {
    return false
  }
  // System Admin-controlled visibility for our own app modules. Fail-open:
  // an empty/unloaded/errored list (the default) never hides anything.
  if (hiddenPages.includes(item.to.replace(/^\//, ''))) return false
  return true
}

export function AppShell() {
  const { role, logout, isAuthenticated } = useAuth()
  const { t, locale, setLocale } = useLocale()
  const location = useLocation()
  const [open, setOpen] = useState(false)
  const [expandedGroups, setExpandedGroups] = useState<Record<string, boolean>>({})
  const shopQuery = useQuery({ queryKey: ['shop'], queryFn: api.shop.me })
  const hiddenPagesQuery = useQuery({
    queryKey: ['hidden-pages'],
    queryFn: api.me.hiddenPages,
    enabled: isAuthenticated,
    staleTime: 60_000,
  })
  useRealtime(isAuthenticated)

  return (
    <div className="app-shell">
      {open ? <div className="sidebar-backdrop" onClick={() => setOpen(false)} /> : null}
      <aside className={`sidebar ${open ? 'open' : ''}`}>
        <div className="sidebar-brand">
          <div className="logo">S</div>
          <div>
            <strong>{t('brand')}</strong>
            <span>AI commerce console</span>
          </div>
        </div>
        <nav>
          {NAV.map((group) => {
            const items = group.items.filter((i) => canSee(i, role, hiddenPagesQuery.data ?? []))
            if (!items.length) return null
            const groupHasActiveItem = items.some(
              (i) => location.pathname === i.to || i.children?.some((c) => location.pathname.startsWith(c.to)),
            )
            const groupKey = `group:${group.label}`
            const isGroupExpanded = expandedGroups[groupKey] ?? groupHasActiveItem
            return (
              <div className="nav-group" key={group.label}>
                <button
                  type="button"
                  className="nav-group-label nav-group-label-toggle"
                  onClick={() => setExpandedGroups((prev) => ({ ...prev, [groupKey]: !isGroupExpanded }))}
                >
                  <span>{group.label}</span>
                  <ChevronDown
                    size={12}
                    style={{
                      transition: 'transform 0.15s ease',
                      transform: isGroupExpanded ? 'rotate(180deg)' : 'rotate(0deg)',
                    }}
                  />
                </button>
                {!isGroupExpanded ? null : items.map((item) => {
                  if (item.children && item.children.length > 0) {
                    const isChildActive = item.children.some((c) => location.pathname.startsWith(c.to))
                    const isExpanded = expandedGroups[item.to] ?? isChildActive
                    return (
                      <div key={item.to}>
                        <button
                          type="button"
                          className={`nav-link nav-link-expandable${isChildActive ? ' active' : ''}`}
                          onClick={() =>
                            setExpandedGroups((prev) => ({ ...prev, [item.to]: !isExpanded }))
                          }
                        >
                          {item.icon}
                          <span style={{ flex: 1, textAlign: 'left' }}>{t(item.labelKey)}</span>
                          <ChevronDown
                            size={14}
                            style={{
                              transition: 'transform 0.15s ease',
                              transform: isExpanded ? 'rotate(180deg)' : 'rotate(0deg)',
                            }}
                          />
                        </button>
                        {isExpanded && (
                          <div style={{ display: 'flex', flexDirection: 'column', gap: 2, marginTop: 2 }}>
                            {item.children.map((child) => (
                              <NavLink
                                key={child.to}
                                to={child.to}
                                className={({ isActive }) => `nav-link nav-link-child${isActive ? ' active' : ''}`}
                                onClick={() => setOpen(false)}
                              >
                                {child.label}
                              </NavLink>
                            ))}
                          </div>
                        )}
                      </div>
                    )
                  }
                  return (
                    <NavLink
                      key={item.to}
                      to={item.to}
                      end={item.to === '/'}
                      className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}
                      onClick={() => setOpen(false)}
                    >
                      {item.icon}
                      {t(item.labelKey)}
                    </NavLink>
                  )
                })}
              </div>
            )
          })}
        </nav>
        <div className="sidebar-foot">
          <div className="role-chip">{role ? roleLabel(role) : '—'}</div>
          <label className="field-label sidebar-foot-label">
            {t('language')}
            <Select
              value={locale}
              onChange={(e) => setLocale(e.target.value as 'en' | 'bn')}
              style={{ marginTop: 4 }}
            >
              <option value="en">English</option>
              <option value="bn">বাংলা</option>
            </Select>
          </label>
          <Button variant="secondary" size="sm" onClick={logout}>
            {t('signOut')}
          </Button>
        </div>
      </aside>

      <div className="main-column">
        <header className="topbar">
          <div className="row">
            <Button
              className="mobile-nav-toggle"
              variant="secondary"
              size="sm"
              onClick={() => setOpen((v) => !v)}
              aria-label="Toggle navigation"
            >
              {open ? <X size={16} /> : <Menu size={16} />}
            </Button>
            <span className="shop-pill">{shopQuery.data?.name ?? t('loading')}</span>
          </div>
          <div className="muted" style={{ fontSize: '0.85rem' }}>
            {shopQuery.data?.currency ?? 'BDT'} · {shopQuery.data?.plan_tier ?? '—'}
          </div>
        </header>
        <main className="content">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
