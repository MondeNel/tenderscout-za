import { useState } from 'react'
import { Outlet, NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { LayoutDashboard, Search, User, CreditCard, LogOut, Zap, Menu, X } from 'lucide-react'

const NAV = [
  { to: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/search',    icon: Search,          label: 'Search tenders' },
  { to: '/account',   icon: User,            label: 'Account' },
  { to: '/topup',     icon: CreditCard,      label: 'Top up' },
]

export default function Layout() {
  const { user, logoutUser } = useAuth()
  const navigate = useNavigate()
  const [mobileOpen, setMobileOpen] = useState(false)

  const handleLogout = () => { logoutUser(); navigate('/login') }

  const SidebarContent = () => (
    <>
      <div className="px-5 py-5 border-b border-gray-200">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 bg-brand-400 rounded-xl flex items-center justify-center">
            <Zap size={17} className="text-white" />
          </div>
          <div>
            <p className="text-sm font-semibold text-gray-900">TenderScout ZA</p>
            <p className="text-xs text-gray-400">Procurement intelligence</p>
          </div>
        </div>
      </div>
      <nav className="flex-1 px-3 py-4 space-y-1">
        {NAV.map(({ to, icon: Icon, label }) => (
          <NavLink key={to} to={to} onClick={() => setMobileOpen(false)}
            className={({ isActive }) =>
              'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors ' +
              (isActive ? 'bg-brand-50 text-brand-700 font-semibold' : 'text-gray-600 hover:bg-gray-100')
            }>
            <Icon size={17} />{label}
          </NavLink>
        ))}
      </nav>
      <div className="p-4 border-t border-gray-200 space-y-3">
        <div className="bg-gray-50 rounded-xl px-4 py-3">
          <p className="text-xs text-gray-500">Credits</p>
          <p className="text-2xl font-bold text-gray-900 mt-0.5">{user?.credit_balance ?? 0}</p>
          <p className="text-xs text-gray-400">R{((user?.credit_balance ?? 0) * 10).toFixed(0)} value</p>
        </div>
        <button onClick={handleLogout}
          className="flex items-center gap-2 w-full px-3 py-2 text-sm text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-lg">
          <LogOut size={15} />Sign out
        </button>
      </div>
    </>
  )

  return (
    <div className="flex h-screen bg-gray-50 overflow-hidden">
      {/* Desktop sidebar */}
      <aside className="hidden md:flex w-64 flex-shrink-0 bg-white border-r border-gray-200 flex-col">
        <SidebarContent />
      </aside>

      {/* Mobile top bar */}
      <div className="md:hidden fixed top-0 left-0 right-0 z-40 bg-white border-b border-gray-200 px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 bg-brand-400 rounded-lg flex items-center justify-center">
            <Zap size={14} className="text-white" />
          </div>
          <span className="text-sm font-semibold text-gray-900">TenderScout ZA</span>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-sm font-medium text-brand-600">{user?.credit_balance ?? 0} credits</span>
            {mobileOpen ? <X size={20} /> : <Menu size={20} />}
          </button>
        </div>
      </div>

      {/* Mobile drawer */}
      {mobileOpen && (
        <div className="md:hidden fixed inset-0 z-30" onClick={() => setMobileOpen(false)}>
          <div className="absolute inset-0 bg-black bg-opacity-30" />
          <aside className="absolute top-0 left-0 bottom-0 w-72 bg-white flex flex-col shadow-xl"
            onClick={e => e.stopPropagation()}>
            <SidebarContent />
          </aside>
        </div>
      )}

      {/* Main content */}
      <main className="flex-1 overflow-y-auto pt-0 md:pt-0">
        <div className="pt-14 md:pt-0">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
