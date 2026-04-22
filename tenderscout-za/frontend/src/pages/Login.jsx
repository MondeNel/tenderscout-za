/**
 * File: src/pages/Login.jsx
 * Purpose: User Login Page
 * 
 * This page allows existing users to sign in to their account.
 * It handles:
 *   - Email and password input with validation
 *   - Password visibility toggle (show/hide)
 *   - Form submission to the authentication API
 *   - Token storage and user state update via AuthContext
 *   - Redirect to dashboard on successful login
 *   - Error handling with toast notifications
 * 
 * After successful login:
 *   1. JWT token is saved to localStorage
 *   2. User profile is fetched from API
 *   3. AuthContext is updated with user data
 *   4. User is redirected to /dashboard
 */

import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { login, getProfile } from '../api/auth'
import { Zap, Eye, EyeOff } from 'lucide-react'
import toast from 'react-hot-toast'

export default function Login() {
  // ===========================================================================
  // STATE
  // ===========================================================================
  
  // Form data state
  const [form, setForm] = useState({ 
    email: '', 
    password: '' 
  })
  
  // Loading state for form submission
  const [loading, setLoading] = useState(false)
  
  // Password visibility toggle
  const [showPassword, setShowPassword] = useState(false)
  
  // ===========================================================================
  // HOOKS
  // ===========================================================================
  
  // Get loginUser function from AuthContext
  const { loginUser } = useAuth()
  
  // Navigation hook for redirecting after login
  const navigate = useNavigate()

  // ===========================================================================
  // FORM HANDLERS
  // ===========================================================================
  
  /**
   * Handle input field changes
   * @param {string} field - Field name to update
   * @param {string} value - New field value
   */
  const handleChange = (field, value) => {
    setForm(prev => ({ ...prev, [field]: value }))
  }

  /**
   * Handle form submission
   * 
   * Flow:
   *   1. Prevent default form submission
   *   2. Call login API with email and password
   *   3. Extract JWT token from response
   *   4. Save token to localStorage
   *   5. Fetch user profile with the token
   *   6. Update AuthContext with user data
   *   7. Show success toast and redirect to dashboard
   * 
   * Error handling:
   *   - 401: Invalid credentials
   *   - 400: Malformed request
   *   - Network errors
   */
  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    
    try {
      // Step 1: Authenticate and get token
      const res = await login(form)
      const token = res.data.access_token
      
      // Step 2: Store token for future API calls
      localStorage.setItem('token', token)
      
      // Step 3: Fetch the complete user profile
      const profile = await getProfile()
      
      // Step 4: Update AuthContext (saves user to state and localStorage)
      loginUser(token, profile.data)
      
      // Step 5: Show welcome message with user's first name
      const firstName = profile.data.full_name.split(' ')[0]
      toast.success(`Welcome back, ${firstName}`)
      
      // Step 6: Redirect to dashboard
      navigate('/dashboard')
    } catch (err) {
      // Handle specific error cases
      const errorMessage = err.response?.data?.detail || 'Login failed. Please try again.'
      toast.error(errorMessage)
    } finally {
      setLoading(false)
    }
  }

  // ===========================================================================
  // RENDER
  // ===========================================================================
  
  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center px-4 py-8">
      <div className="w-full max-w-md">
        {/* =====================================================================
            LOGO AND APP NAME
            ===================================================================== */}
        <div className="flex items-center gap-3 mb-8 justify-center">
          <div className="w-10 h-10 bg-brand-400 rounded-xl flex items-center justify-center shadow-sm">
            <Zap size={20} className="text-white" />
          </div>
          <span className="text-xl font-semibold text-gray-900">TenderScout ZA</span>
        </div>

        {/* =====================================================================
            LOGIN CARD
            ===================================================================== */}
        <div className="card p-6 md:p-8 space-y-5">
          {/* Header */}
          <div>
            <h1 className="text-xl font-semibold text-gray-900">Sign in</h1>
            <p className="text-base text-gray-500 mt-1">
              Access your tender dashboard
            </p>
          </div>

          {/* Login Form */}
          <form onSubmit={handleSubmit} className="space-y-4">
            {/* -------------------------------------------------------------
                EMAIL FIELD
                ------------------------------------------------------------- */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">
                Email
              </label>
              <input
                type="email"
                className="input py-2.5 text-base"
                placeholder="you@company.co.za"
                value={form.email}
                onChange={(e) => handleChange('email', e.target.value)}
                required
                autoComplete="email"
                autoFocus
              />
            </div>

            {/* -------------------------------------------------------------
                PASSWORD FIELD WITH VISIBILITY TOGGLE
                ------------------------------------------------------------- */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">
                Password
              </label>
              <div className="relative">
                <input
                  type={showPassword ? 'text' : 'password'}
                  className="input py-2.5 text-base pr-10"
                  placeholder="••••••••"
                  value={form.password}
                  onChange={(e) => handleChange('password', e.target.value)}
                  required
                  autoComplete="current-password"
                />
                {/* Password visibility toggle button */}
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 transition-colors"
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                >
                  {showPassword ? (
                    <EyeOff size={18} />
                  ) : (
                    <Eye size={18} />
                  )}
                </button>
              </div>
              {/* Forgot password link (placeholder for future feature) */}
              <p className="text-xs text-gray-400 mt-1.5">
                {/* TODO: Add forgot password functionality */}
                {/* <Link to="/forgot-password" className="text-brand-600 hover:underline">
                  Forgot password?
                </Link> */}
              </p>
            </div>

            {/* -------------------------------------------------------------
                SUBMIT BUTTON
                ------------------------------------------------------------- */}
            <button 
              type="submit" 
              disabled={loading} 
              className="btn-primary w-full py-2.5 text-base mt-1"
            >
              {loading ? (
                <span className="flex items-center justify-center gap-2">
                  <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  Signing in...
                </span>
              ) : (
                'Sign in'
              )}
            </button>
          </form>

          {/* =================================================================
              REGISTER LINK
              ================================================================= */}
          <p className="text-sm text-center text-gray-500">
            No account?{' '}
            <Link 
              to="/register" 
              className="text-brand-600 hover:underline font-medium"
            >
              Create one free
            </Link>
          </p>
        </div>

        {/* =================================================================
            DEMO CREDENTIALS (Optional - for testing)
            =================================================================
            Uncomment for development/demo purposes
        */}
        {/* {import.meta.env.DEV && (
          <div className="mt-4 p-3 bg-blue-50 rounded-lg border border-blue-200">
            <p className="text-xs text-blue-700 font-medium mb-2">Demo Credentials:</p>
            <p className="text-xs text-blue-600">Email: demo@example.com</p>
            <p className="text-xs text-blue-600">Password: password123</p>
          </div>
        )} */}
      </div>
    </div>
  )
}