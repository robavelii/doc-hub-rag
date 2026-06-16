import { useEffect, useState } from 'react'
import { NavLink, useLocation, useNavigate } from 'react-router-dom'
import {
  ChevronLeft,
  FileText,
  LayoutDashboard,
  Link2,
  LogOut,
  Menu,
  MessageSquare,
  Puzzle,
  Settings,
  Shield,
  User,
  X,
} from 'lucide-react'
import type { UsageSummary } from '@shared/types'
import api from '../lib/api'
import { useAuthStore } from '../store/authStore'
import {
  Avatar,
  Badge,
  Dropdown,
  DropdownItem,
  DropdownSeparator,
  IconButton,
  ThemeToggle,
} from './ui'
import { cn } from '../lib/cn'

interface LayoutProps {
  children: React.ReactNode
}

const navItems = [
  { to: '/chat', label: 'Chat', icon: MessageSquare },
  { to: '/documents', label: 'Documents', icon: FileText },
  { to: '/usage', label: 'Analytics', icon: LayoutDashboard },
  { to: '/widget', label: 'Widget', icon: Puzzle },
  { to: '/integrations', label: 'Integrations', icon: Link2 },
  { to: '/settings', label: 'Settings', icon: Settings },
]

const adminNavItems = [
  { to: '/admin/tenants', label: 'Tenants', icon: Shield },
  { to: '/admin/usage', label: 'Global Usage', icon: LayoutDashboard },
]

function getBreadcrumb(pathname: string) {
  const all = [...navItems, ...adminNavItems]
  const item = all.find((n) => pathname.startsWith(n.to))
  if (pathname.startsWith('/admin')) return `Admin / ${item?.label ?? 'Panel'}`
  return item?.label || 'Dashboard'
}

export default function Layout({ children }: LayoutProps) {
  const { tenant, user, logout } = useAuthStore()
  const location = useLocation()
  const navigate = useNavigate()
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [collapsed, setCollapsed] = useState(false)
  const [usage, setUsage] = useState<UsageSummary | null>(null)
  const breadcrumb = getBreadcrumb(location.pathname)

  useEffect(() => {
    void api.get<UsageSummary>('/usage/summary').then(({ data }) => setUsage(data))
  }, [location.pathname])

  return (
    <div className="flex min-h-screen">
      {/* Mobile overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/40 backdrop-blur-sm lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={cn(
          'fixed top-0 left-0 z-50 flex h-screen flex-col border-r border-glass-border',
          'glass transition-all duration-300 ease-out',
          'lg:sticky lg:translate-x-0',
          collapsed ? 'w-[68px]' : 'w-sidebar',
          sidebarOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'
        )}
      >
        {/* Brand */}
        <div className={cn('flex items-center gap-3 p-4 border-b border-border-subtle', collapsed && 'justify-center px-2')}>
          <img src="/brand/logo.svg" alt="Doc-Hub" className="h-8 w-8 shrink-0" />
          {!collapsed && (
            <div className="flex-1 min-w-0 animate-fade-in">
              <h2 className="text-sm font-bold text-text truncate">Doc-Hub</h2>
              <p className="text-[10px] text-muted truncate">{tenant?.name || 'Dashboard'}</p>
            </div>
          )}
          {/* Mobile close */}
          <button
            className="lg:hidden p-1 rounded-md text-muted hover:text-text"
            onClick={() => setSidebarOpen(false)}
          >
            <X size={18} />
          </button>
        </div>

        {/* Nav */}
        <nav className={cn('flex-1 flex flex-col gap-0.5 p-2 overflow-y-auto', collapsed && 'items-center')}>
          {navItems.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              onClick={() => setSidebarOpen(false)}
              className={({ isActive }) =>
                cn(
                  'group relative flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium',
                  'transition-all duration-200',
                  collapsed && 'justify-center px-2',
                  isActive
                    ? 'bg-primary-muted text-primary'
                    : 'text-muted hover:text-text hover:bg-surface-2/50'
                )
              }
            >
              {({ isActive }) => (
                <>
                  {/* Active indicator bar */}
                  {isActive && (
                    <div className="absolute left-0 top-1/2 -translate-y-1/2 h-5 w-[3px] rounded-r-full bg-primary" />
                  )}
                  <Icon size={18} className={cn('shrink-0', isActive && 'text-primary')} />
                  {!collapsed && <span>{label}</span>}
                </>
              )}
            </NavLink>
          ))}
          {user?.is_superadmin && (
            <div className={cn('mt-4 pt-4 border-t border-border-subtle', collapsed && 'w-full')}>
              {!collapsed && (
                <p className="px-3 text-[10px] uppercase tracking-wider text-muted mb-2">Admin</p>
              )}
              {adminNavItems.map(({ to, label, icon: Icon }) => (
                <NavLink
                  key={to}
                  to={to}
                  title={label}
                  className={({ isActive }) => cn(
                    'flex items-center gap-3 rounded-xl px-3 py-2 text-sm font-medium',
                    collapsed && 'justify-center px-2',
                    isActive ? 'bg-primary-muted text-primary' : 'text-muted hover:text-text'
                  )}
                >
                  <Icon size={16} />
                  {!collapsed && <span>{label}</span>}
                </NavLink>
              ))}
            </div>
          )}
        </nav>

        {/* Bottom section */}
        <div className={cn('p-3 border-t border-border-subtle', collapsed && 'flex flex-col items-center gap-2')}>
          {!collapsed && usage && (
            <div className="mb-3 w-full">
              <div className="flex justify-between text-[10px] text-muted mb-1">
                <span>Tokens</span>
                <span>{Math.round((usage.tokens_used / usage.tokens_limit) * 100)}%</span>
              </div>
              <div className="h-1 rounded-full bg-border overflow-hidden">
                <div className="h-full bg-primary rounded-full" style={{ width: `${Math.min(100, (usage.tokens_used / usage.tokens_limit) * 100)}%` }} />
              </div>
            </div>
          )}
          {!collapsed && (
            <div className="flex items-center gap-2 mb-3">
              <Badge variant="primary" className="text-[10px]">{usage?.plan ?? tenant?.slug ?? 'free'}</Badge>
            </div>
          )}
          <div className={cn('flex items-center', collapsed ? 'flex-col gap-2' : 'justify-between')}>
            <ThemeToggle />
            <IconButton
              label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
              onClick={() => setCollapsed(!collapsed)}
              className="hidden lg:inline-flex"
            >
              <ChevronLeft size={16} className={cn('transition-transform', collapsed && 'rotate-180')} />
            </IconButton>
          </div>
        </div>
      </aside>

      {/* Main content area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Header bar */}
        <header className="sticky top-0 z-30 flex items-center justify-between gap-4 px-4 lg:px-6 h-header border-b border-border-subtle glass">
          <div className="flex items-center gap-3">
            <IconButton
              label="Open menu"
              onClick={() => setSidebarOpen(true)}
              className="lg:hidden"
            >
              <Menu size={20} />
            </IconButton>
            <div className="flex items-center gap-2 text-sm">
              <span className="text-muted hidden sm:inline">Dashboard</span>
              <span className="text-muted hidden sm:inline">/</span>
              <span className="font-medium text-text">{breadcrumb}</span>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {/* User dropdown */}
            <Dropdown
              trigger={
                <button className="flex items-center gap-2 rounded-lg px-2 py-1.5 hover:bg-surface-2/50 transition-colors">
                  <Avatar name={user?.email || tenant?.name} size="sm" />
                  <span className="text-sm text-text-secondary hidden sm:inline max-w-[120px] truncate">
                    {user?.email?.split('@')[0] || 'User'}
                  </span>
                </button>
              }
            >
              <div className="px-3 py-2">
                <p className="text-sm font-medium text-text truncate">{user?.email}</p>
                <p className="text-xs text-muted">{user?.role || 'member'}</p>
              </div>
              <DropdownSeparator />
              <DropdownItem icon={<User size={15} />} onClick={() => navigate('/settings')}>
                Profile
              </DropdownItem>
              <DropdownItem icon={<Settings size={15} />} onClick={() => navigate('/settings')}>
                Settings
              </DropdownItem>
              <DropdownSeparator />
              <DropdownItem icon={<LogOut size={15} />} danger onClick={logout}>
                Sign out
              </DropdownItem>
            </Dropdown>
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 overflow-auto p-4 lg:p-6">
          <div className="animate-fade-in-up" key={location.pathname}>
            {children}
          </div>
        </main>
      </div>
    </div>
  )
}
