import { useEffect, useState } from 'react'
import { NavLink, useLocation, useNavigate } from 'react-router-dom'
import {
  BarChart3,
  FileText,
  Link2,
  LogOut,
  Moon,
  PanelLeft,
  Puzzle,
  Settings,
  Shield,
  SquarePen,
  Sun,
  User,
  X,
} from 'lucide-react'
import type { UsageSummary } from '@shared/types'
import api from '../lib/api'
import { useAuthStore } from '../store/authStore'
import { useTheme } from '../theme/ThemeProvider'
import ConversationSidebar from './ConversationSidebar'
import { Avatar, Dropdown, DropdownItem, DropdownSeparator, IconButton } from './ui'
import { cn } from '../lib/cn'

interface LayoutProps {
  children: React.ReactNode
}

const navItems = [
  { to: '/documents', label: 'Documents', icon: FileText },
  { to: '/usage', label: 'Analytics', icon: BarChart3 },
  { to: '/widget', label: 'Widget', icon: Puzzle },
  { to: '/integrations', label: 'Integrations', icon: Link2 },
  { to: '/settings', label: 'Settings', icon: Settings },
]

const adminNavItems = [
  { to: '/admin/tenants', label: 'Tenants', icon: Shield },
  { to: '/admin/usage', label: 'Global usage', icon: BarChart3 },
]

const COLLAPSE_KEY = 'doc-hub-sidebar-collapsed'

function pageTitle(pathname: string) {
  if (pathname.startsWith('/chat')) return 'Chat'
  const item = [...navItems, ...adminNavItems].find((n) => pathname.startsWith(n.to))
  if (pathname.startsWith('/admin')) return `Admin: ${item?.label ?? 'Panel'}`
  return item?.label || 'Dashboard'
}

function readCollapsed() {
  try {
    return localStorage.getItem(COLLAPSE_KEY) === 'true'
  } catch {
    return false
  }
}

export default function Layout({ children }: LayoutProps) {
  const { tenant, user, logout } = useAuthStore()
  const { theme, toggleTheme } = useTheme()
  const location = useLocation()
  const navigate = useNavigate()
  const [mobileOpen, setMobileOpen] = useState(false)
  const [collapsed, setCollapsed] = useState(readCollapsed)
  const [usage, setUsage] = useState<UsageSummary | null>(null)
  const isChat = location.pathname.startsWith('/chat')
  const tokenPct = usage ? Math.min(100, Math.round((usage.tokens_used / usage.tokens_limit) * 100)) : 0

  useEffect(() => {
    void api.get<UsageSummary>('/usage/summary').then(({ data }) => setUsage(data))
  }, [location.pathname])

  useEffect(() => {
    try {
      localStorage.setItem(COLLAPSE_KEY, String(collapsed))
    } catch {
      // per-visit only
    }
  }, [collapsed])

  const closeMobile = () => setMobileOpen(false)

  return (
    <div className="flex h-dvh overflow-hidden bg-bg">
      {mobileOpen && (
        <div className="fixed inset-0 z-40 bg-scrim/40 lg:hidden" onClick={closeMobile} aria-hidden="true" />
      )}

      <aside
        aria-label="Sidebar"
        className={cn(
          'fixed inset-y-0 left-0 z-50 flex w-sidebar flex-col bg-sidebar',
          'transition-transform duration-short ease-out lg:static lg:z-auto',
          mobileOpen ? 'translate-x-0 shadow-lg' : '-translate-x-full',
          collapsed ? 'lg:hidden' : 'lg:translate-x-0'
        )}
      >
        <div className="flex h-14 items-center justify-between px-3">
          <NavLink to="/chat" onClick={closeMobile} className="rounded-md px-1.5 py-1 text-[17px] font-semibold tracking-tight text-text">
            Doc-Hub
          </NavLink>
          <IconButton label="Close sidebar" onClick={closeMobile} className="lg:hidden">
            <X size={18} />
          </IconButton>
          <IconButton label="Hide sidebar" onClick={() => setCollapsed(true)} className="hidden lg:inline-flex">
            <PanelLeft size={18} />
          </IconButton>
        </div>

        <nav aria-label="Workspace" className="px-2">
          <NavLink
            to="/chat"
            end
            onClick={closeMobile}
            className={({ isActive }) =>
              cn(
                'flex h-9 items-center gap-2.5 rounded-lg px-2 text-sm font-medium transition-colors duration-micro',
                isActive ? 'bg-primary-muted text-text' : 'text-text hover:bg-primary-muted'
              )
            }
          >
            <SquarePen size={16} />
            New chat
          </NavLink>
          <ul className="mt-1">
            {navItems.map(({ to, label, icon: Icon }) => (
              <li key={to}>
                <NavLink
                  to={to}
                  onClick={closeMobile}
                  className={({ isActive }) =>
                    cn(
                      'flex h-9 items-center gap-2.5 rounded-lg px-2 text-sm transition-colors duration-micro',
                      isActive ? 'bg-primary-muted font-medium text-text' : 'text-text-secondary hover:bg-primary-muted hover:text-text'
                    )
                  }
                >
                  <Icon size={16} className="text-muted" />
                  {label}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>

        <h2 className="mt-4 px-4 pb-1.5 text-xs font-medium text-muted">Chats</h2>
        <ConversationSidebar onNavigate={closeMobile} />

        <div className="border-t border-border p-2">
          {usage && (
            <NavLink to="/usage" onClick={closeMobile} className="mb-1 block rounded-lg px-2 py-2 hover:bg-primary-muted">
              <span className="flex items-baseline justify-between text-xs text-muted">
                <span>
                  Tokens, <span className="font-medium text-text-secondary">{usage.plan}</span> plan
                </span>
                <span className="tabular">{tokenPct}%</span>
              </span>
              <span className="mt-1.5 block h-1 overflow-hidden rounded-full bg-surface-3">
                <span className="block h-full origin-left rounded-full bg-text" style={{ transform: `scaleX(${tokenPct / 100})` }} />
              </span>
            </NavLink>
          )}

          <Dropdown
            side="top"
            align="left"
            className="w-full"
            menuClassName="w-[244px]"
            trigger={
              <button type="button" className="flex w-full items-center gap-2.5 rounded-lg px-2 py-1.5 text-left hover:bg-primary-muted">
                <Avatar name={user?.email || tenant?.name} size="sm" />
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-medium text-text">{user?.email?.split('@')[0] || 'Account'}</span>
                  <span className="block truncate text-xs text-muted">{tenant?.name}</span>
                </span>
              </button>
            }
          >
            <div className="px-2.5 py-2">
              <p className="truncate text-sm font-medium text-text">{user?.email}</p>
              <p className="text-xs text-muted">{user?.role || 'member'}</p>
            </div>
            <DropdownSeparator />
            <DropdownItem icon={<User size={15} />} onClick={() => navigate('/settings')}>
              Profile
            </DropdownItem>
            <DropdownItem icon={<Settings size={15} />} onClick={() => navigate('/settings')}>
              Settings
            </DropdownItem>
            <DropdownItem icon={theme === 'dark' ? <Sun size={15} /> : <Moon size={15} />} onClick={toggleTheme}>
              {theme === 'dark' ? 'Light theme' : 'Dark theme'}
            </DropdownItem>
            {user?.is_superadmin && (
              <>
                <DropdownSeparator />
                {adminNavItems.map(({ to, label, icon: Icon }) => (
                  <DropdownItem key={to} icon={<Icon size={15} />} onClick={() => navigate(to)}>
                    {label}
                  </DropdownItem>
                ))}
              </>
            )}
            <DropdownSeparator />
            <DropdownItem icon={<LogOut size={15} />} danger onClick={logout}>
              Sign out
            </DropdownItem>
          </Dropdown>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 shrink-0 items-center gap-2 px-3 lg:px-4">
          <IconButton label="Open sidebar" onClick={() => setMobileOpen(true)} className="lg:hidden">
            <PanelLeft size={18} />
          </IconButton>
          {collapsed && (
            <>
              <IconButton label="Show sidebar" onClick={() => setCollapsed(false)} className="hidden lg:inline-flex">
                <PanelLeft size={18} />
              </IconButton>
              <IconButton label="New chat" onClick={() => navigate('/chat')} className="hidden lg:inline-flex">
                <SquarePen size={18} />
              </IconButton>
            </>
          )}
          <h1 className="truncate text-[15px] font-medium text-text">{pageTitle(location.pathname)}</h1>
        </header>

        <main className={cn('min-h-0 flex-1', isChat ? 'flex flex-col' : 'overflow-y-auto')}>
          {isChat ? children : <div className="mx-auto w-full max-w-6xl px-4 pb-12 pt-2 lg:px-8">{children}</div>}
        </main>
      </div>
    </div>
  )
}
