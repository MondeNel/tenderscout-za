import { Outlet, NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { LayoutDashboard, Search, User, CreditCard, LogOut, Zap } from 'lucide-react'

const NAV = [
  { to: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/search',    icon: Search,          label: 'Search tenders' },
  { to: '/account',   icon: User,            label: 'Account' },
  { to: '/topup',     icon: CreditCard,      label: 'Top up credits' },
]

export default function Layout() {
  const { user, logoutUser } = useAuth()
  const navigate = useNavigate()

  const handleLogout = () => {
    logoutUser()
    navigate('/login')
  }

  return (
    <div className="flex h-screen bg-gray-50 overflow-hidden">
      {/* Sidebar - wider and more spacious */}
      <aside className="w-72 flex-shrink-0 bg-white border-r border-gray-200 flex flex-col">
        {/* Logo area - larger */}
        <div className="px-5 py-6 border-b border-gray-200">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 bg-brand-400 rounded-xl flex items-center justify-center shadow-sm">
              <Zap size={20} className="text-white" />
            </div>
            <div>
              <p className="text-base font-semibold text-gray-900 leading-tight">TenderScout</p>
              <p className="text-xs text-gray-400 mt-0.5">ZA Procurement</p>
            </div>
          </div>
        </div>

        {/* Navigation - larger items */}
        <nav className="flex-1 px-3 py-4 space-y-1">
          {NAV.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-lg text-base transition-all duration-150 ${
                  isActive
                    ? 'bg-brand-50 text-brand-700 font-semibold'
                    : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'
                }`
              }
            >
              <Icon size={18} />
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>

        {/* Footer area - larger credit display and sign out */}
        <div className="p-4 border-t border-gray-200 space-y-4">
          <div className="bg-gray-50 rounded-xl px-4 py-3">
            <p className="text-xs text-gray-500 uppercase tracking-wide font-medium">Credits</p>
            <p className="text-2xl font-bold text-gray-900 mt-1">{user?.credit_balance ?? 0}</p>
            <p className="text-xs text-gray-400 mt-0.5">R{((user?.credit_balance ?? 0) * 10).toFixed(0)} value</p>
          </div>
          <button
            onClick={handleLogout}
            className="flex items-center gap-2 w-full px-3 py-2.5 text-sm font-medium text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition-colors"
          >
            <LogOut size={16} />
            Sign out
          </button>
        </div>
      </aside>

      {/* Main content area - takes remaining space */}
      <main className="flex-1 overflow-y-auto">
        <Outlet />
      </main>
    </div>
  )
}