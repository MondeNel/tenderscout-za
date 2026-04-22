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
function LoadingSpinner({ fullScreen = false, size = 'md', message }) {
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
function PrivateRoute({ children }) {
  const { user, loading } = useAuth()
  
  if (loading) {
    return (
      <LoadingSpinner 
        fullScreen 
        size="lg" 
        message="Verifying your session..." 
      />
    )
  }
  
  return user ? children : <Navigate to="/login" replace />
}

// =============================================================================
// PUBLIC ROUTE GUARD
// =============================================================================
function PublicRoute({ children }) {
  const { user, loading } = useAuth()
  
  if (loading) return null
  
  return user ? <Navigate to="/dashboard" replace /> : children
}

// =============================================================================
// ROOT APP COMPONENT
// =============================================================================
export default function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        
        {/* Public Routes */}
        <Route path="/login" element={<PublicRoute><Login /></PublicRoute>} />
        <Route path="/register" element={<PublicRoute><Register /></PublicRoute>} />
        
        {/* Onboarding (Private, no Layout) */}
        <Route path="/onboarding" element={<PrivateRoute><Onboarding /></PrivateRoute>} />
        
        {/* Protected Routes with Layout */}
        <Route element={<PrivateRoute><Layout /></PrivateRoute>}>
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/search" element={<Search />} />
          <Route path="/account" element={<Account />} />
          <Route path="/topup" element={<TopUp />} />
        </Route>
        
        {/* 404 Not Found */}
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