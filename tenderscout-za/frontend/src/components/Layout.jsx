/**
 * File: src/components/Layout.jsx
 * Purpose: Main Application Layout Wrapper
 * 
 * This component provides the consistent layout structure for all authenticated pages.
 * It includes:
 *   - Desktop sidebar with navigation and credit display
 *   - Mobile top bar with hamburger menu
 *   - Mobile slide-out drawer for navigation
 *   - Main content area that renders the current page via <Outlet />
 * 
 * The layout is responsive:
 *   - Desktop: Fixed sidebar (256px) + scrolling main content
 *   - Mobile: Top bar with drawer that slides in from the left
 * 
 * Navigation items:
 *   - Dashboard (/dashboard)
 *   - Search tenders (/search)
 *   - Account (/account)
 *   - Top up (/topup)
 */

import { useState } from 'react'
import { Outlet, NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { 
  LayoutDashboard,  // Dashboard icon
  Search,           // Search icon
  User,             // Account icon
  CreditCard,       // Top up icon
  LogOut,           // Sign out icon
  Zap,              // Lightning bolt for logo
  Menu,             // Hamburger menu (mobile)
  X                 // Close icon (mobile)
} from 'lucide-react'

// =============================================================================
// NAVIGATION CONFIGURATION
// =============================================================================
/**
 * Navigation items displayed in the sidebar.
 * Each item has:
 *   - to: Route path
 *   - icon: Lucide icon component
 *   - label: Display text
 */
const NAV = [
  { to: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/search',    icon: Search,          label: 'Search tenders' },
  { to: '/account',   icon: User,            label: 'Account' },
  { to: '/topup',     icon: CreditCard,      label: 'Top up' },
]

// =============================================================================
// MAIN COMPONENT
// =============================================================================

export default function Layout() {
  // ===========================================================================
  // HOOKS
  // ===========================================================================
  
  // Get authenticated user and logout function from context
  const { user, logoutUser } = useAuth()
  
  // Navigation hook for programmatic routing
  const navigate = useNavigate()
  
  // Mobile drawer open/closed state
  const [mobileOpen, setMobileOpen] = useState(false)

  // ===========================================================================
  // HANDLERS
  // ===========================================================================
  
  /**
   * Handle user logout
   * Calls logoutUser from context and redirects to login page
   */
  const handleLogout = () => {
    logoutUser()
    navigate('/login')
  }

  // ===========================================================================
  // SIDEBAR CONTENT (Reused for desktop and mobile)
  // ===========================================================================
  
  /**
   * SidebarContent - The actual sidebar content rendered in both desktop and mobile
   * 
   * Structure:
   *   - Header with logo and app name
   *   - Navigation links (active state highlighted)
   *   - Footer with credit balance and sign out button
   */
  const SidebarContent = () => (
    <>
      {/* =====================================================================
          SIDEBAR HEADER - Logo and App Name
          ===================================================================== */}
      <div className="px-5 py-5 border-b border-gray-200">
        <div className="flex items-center gap-3">
          {/* Logo icon */}
          <div className="w-8 h-8 bg-brand-400 rounded-xl flex items-center justify-center">
            <Zap size={17} className="text-white" />
          </div>
          {/* App name and tagline */}
          <div>
            <p className="text-sm font-semibold text-gray-900">TenderScout ZA</p>
            <p className="text-xs text-gray-400">Procurement intelligence</p>
          </div>
        </div>
      </div>

      {/* =====================================================================
          NAVIGATION LINKS
          =====================================================================
          Uses NavLink for automatic active state detection.
          Active link gets brand-colored background and text.
      */}
      <nav className="flex-1 px-3 py-4 space-y-1">
        {NAV.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            onClick={() => setMobileOpen(false)}  // Close mobile drawer on navigation
            className={({ isActive }) =>
              'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors ' +
              (isActive
                ? 'bg-brand-50 text-brand-700 font-semibold'   // Active state
                : 'text-gray-600 hover:bg-gray-100'            // Inactive state
              )
            }
          >
            <Icon size={17} />
            <span>{label}</span>
          </NavLink>
        ))}
      </nav>

      {/* =====================================================================
          SIDEBAR FOOTER - Credit Balance & Sign Out
          ===================================================================== */}
      <div className="p-4 border-t border-gray-200 space-y-3">
        {/* Credit balance card */}
        <div className="bg-gray-50 rounded-xl px-4 py-3">
          <p className="text-xs text-gray-500">Credits</p>
          <p className="text-2xl font-bold text-gray-900 mt-0.5">
            {user?.credit_balance ?? 0}
          </p>
          <p className="text-xs text-gray-400">
            R{((user?.credit_balance ?? 0) * 10).toFixed(0)} value
          </p>
        </div>
        
        {/* Sign out button */}
        <button
          onClick={handleLogout}
          className="flex items-center gap-2 w-full px-3 py-2 text-sm text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition-colors"
        >
          <LogOut size={15} />
          Sign out
        </button>
      </div>
    </>
  )

  // ===========================================================================
  // RENDER
  // ===========================================================================
  
  return (
    <div className="flex h-screen bg-gray-50 overflow-hidden">
      {/* =====================================================================
          DESKTOP SIDEBAR (Hidden on mobile: hidden md:flex)
          =====================================================================
          Fixed width sidebar (256px) visible on medium screens and above.
      */}
      <aside className="hidden md:flex w-64 flex-shrink-0 bg-white border-r border-gray-200 flex-col">
        <SidebarContent />
      </aside>

      {/* =====================================================================
          MOBILE TOP BAR (Visible only on mobile: md:hidden)
          =====================================================================
          Fixed bar at the top with logo, credit balance, and menu toggle.
      */}
      <div className="md:hidden fixed top-0 left-0 right-0 z-40 bg-white border-b border-gray-200 px-4 py-3 flex items-center justify-between">
        {/* Logo and app name */}
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 bg-brand-400 rounded-lg flex items-center justify-center">
            <Zap size={14} className="text-white" />
          </div>
          <span className="text-sm font-semibold text-gray-900">TenderScout ZA</span>
        </div>
        
        {/* Credit balance and menu toggle */}
        <div className="flex items-center gap-3">
          <span className="text-sm font-medium text-brand-600">
            {user?.credit_balance ?? 0} credits
          </span>
          <button
            onClick={() => setMobileOpen(!mobileOpen)}
            className="p-1 rounded-md hover:bg-gray-100 transition-colors"
          >
            {mobileOpen ? <X size={20} /> : <Menu size={20} />}
          </button>
        </div>
      </div>

      {/* =====================================================================
          MOBILE DRAWER (Slide-out menu)
          =====================================================================
          Rendered when mobileOpen is true.
          - Semi-transparent backdrop (click to close)
          - Sidebar slides in from the left
      */}
      {mobileOpen && (
        <div className="md:hidden fixed inset-0 z-30" onClick={() => setMobileOpen(false)}>
          {/* Backdrop */}
          <div className="absolute inset-0 bg-black bg-opacity-30" />
          
          {/* Slide-out sidebar */}
          <aside
            className="absolute top-0 left-0 bottom-0 w-72 bg-white flex flex-col shadow-xl"
            onClick={e => e.stopPropagation()}  // Prevent closing when clicking sidebar
          >
            <SidebarContent />
          </aside>
        </div>
      )}

      {/* =====================================================================
          MAIN CONTENT AREA
          =====================================================================
          - Fills remaining space (flex-1)
          - Scrollable content (overflow-y-auto)
          - Padding top on mobile to account for fixed top bar (pt-14)
          - <Outlet /> renders the current route's component
      */}
      <main className="flex-1 overflow-y-auto pt-0 md:pt-0">
        <div className="pt-14 md:pt-0">
          <Outlet />
        </div>
      </main>
    </div>
  )
}