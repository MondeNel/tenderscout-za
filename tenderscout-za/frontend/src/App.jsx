/**
 * File: src/App.jsx
 * Purpose: Root application component – sets up routing, authentication
 *          guards, and the main layout.
 *
 * This file is the entry point for the React app. It wraps the entire
 * component tree in the AuthProvider, defines the route structure (public,
 * private, and 404), and provides reusable components for loading states
 * and route protection.
 */

import { Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './context/AuthContext'
import Login from './pages/Login'
import Register from './pages/Register'
import Onboarding from './pages/Onboarding'
import Dashboard from './pages/Dashboard'
import Search from './pages/Search'
import Account from './pages/Account'
import TopUp from './pages/TopUp'
import Layout from './components/Layout'

// =============================================================================
// LOADING SPINNER COMPONENT
// =============================================================================

/**
 * Reusable loading spinner with optional full‑screen mode and size variants.
 *
 * @param {boolean} fullScreen  - if true, the spinner is vertically centred on the viewport.
 * @param {string}  size        - 'sm', 'md', or 'lg' (default 'md').
 * @param {string}  message     - optional text shown below the spinner.
 */
function LoadingSpinner({ fullScreen = false, size = 'md', message }) {
  // Map size prop to Tailwind classes
  const sizeClasses = {
    sm: 'w-4 h-4 border-2',
    md: 'w-6 h-6 border-2',
    lg: 'w-10 h-10 border-3',
  }
  
  const spinnerSize = sizeClasses[size] || sizeClasses.md
  const containerClasses = fullScreen
    ? "min-h-screen flex flex-col items-center justify-center"
    : "flex flex-col items-center justify-center p-8"
  
  return (
    <div className={containerClasses}>
      <div 
        className={`${spinnerSize} border-brand-400 border-t-transparent rounded-full animate-spin`} 
      />
      {message && (
        <p className="mt-3 text-sm text-gray-500">{message}</p>
      )}
    </div>
  )
}

// =============================================================================
// PRIVATE ROUTE GUARD
// =============================================================================

/**
 * Wraps routes that require authentication.
 *
 * While the auth context is still loading (e.g., after a page refresh), a
 * full‑screen spinner is shown. Once loading completes, the user is either
 * granted access to the child components or redirected to /login.
 */
function PrivateRoute({ children }) {
  const { user, loading } = useAuth()
  
  // Session verification in progress – avoid a flash of the login page
  if (loading) {
    return (
      <LoadingSpinner 
        fullScreen 
        size="lg" 
        message="Verifying your session..." 
      />
    )
  }
  
  // If there's a valid user, render the protected content; otherwise redirect
  return user ? children : <Navigate to="/login" replace />
}

// =============================================================================
// PUBLIC ROUTE GUARD
// =============================================================================

/**
 * Wraps routes that should only be accessible to unauthenticated users
 * (login, register).
 *
 * If a user is already logged in, they are redirected to the dashboard to
 * avoid seeing the login / registration forms again.
 */
function PublicRoute({ children }) {
  const { user, loading } = useAuth()
  
  // Don't flash any content while the auth state is being restored
  if (loading) return null
  
  return user ? <Navigate to="/dashboard" replace /> : children
}

// =============================================================================
// ROOT APP COMPONENT
// =============================================================================

export default function App() {
  return (
    // AuthProvider must wrap the entire tree so that useAuth() is available
    // inside route components and guards.
    <AuthProvider>
      <Routes>
        {/* Default route redirects to the dashboard */}
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        
        {/* ----------------------------------------------------------------
            PUBLIC ROUTES (only accessible when not logged in)
            ---------------------------------------------------------------- */}
        <Route path="/login" element={<PublicRoute><Login /></PublicRoute>} />
        <Route path="/register" element={<PublicRoute><Register /></PublicRoute>} />
        
        {/* ----------------------------------------------------------------
            ONBOARDING (private, but without the standard Layout wrapper)
            ---------------------------------------------------------------- */}
        <Route path="/onboarding" element={<PrivateRoute><Onboarding /></PrivateRoute>} />
        
        {/* ----------------------------------------------------------------
            PROTECTED ROUTES WITH LAYOUT
            These routes share the common Layout component (sidebar, header).
            ---------------------------------------------------------------- */}
        <Route element={<PrivateRoute><Layout /></PrivateRoute>}>
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/search" element={<Search />} />
          <Route path="/account" element={<Account />} />
          <Route path="/topup" element={<TopUp />} />
        </Route>
        
        {/* ----------------------------------------------------------------
            404 NOT FOUND – any unmatched path shows a simple fallback page
            ---------------------------------------------------------------- */}
        <Route path="*" element={
          <div className="min-h-screen flex items-center justify-center bg-gray-50">
            <div className="text-center p-8">
              <h1 className="text-6xl font-bold text-gray-400 mb-4">404</h1>
              <p className="text-xl text-gray-600 mb-6">Page not found</p>
              <a 
                href="/dashboard" 
                className="px-6 py-2 bg-brand-500 text-white rounded-lg hover:bg-brand-600 transition-colors"
              >
                Go to Dashboard
              </a>
            </div>
          </div>
        } />
      </Routes>
    </AuthProvider>
  )
}