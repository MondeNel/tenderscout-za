/**
 * File: src/pages/Register.jsx
 * Purpose: User Registration Page
 * 
 * This page allows new users to create an account.
 * It handles:
 *   - Full name, email, and password input with validation
 *   - Password visibility toggle (show/hide)
 *   - Minimum password length enforcement (8 characters)
 *   - Form submission to the registration API
 *   - Automatic login after successful registration
 *   - Redirect to onboarding for preference setup
 *   - Error handling with toast notifications
 * 
 * After successful registration:
 *   1. Account is created with 5 free credits
 *   2. JWT token is returned and saved to localStorage
 *   3. User profile is fetched from API
 *   4. AuthContext is updated with user data
 *   5. User is redirected to /onboarding (first-time setup)
 */

import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { register, getProfile } from '../api/auth'
import { Zap, Eye, EyeOff, Check, X } from 'lucide-react'
import toast from 'react-hot-toast'

export default function Register() {
  // ===========================================================================
  // STATE
  // ===========================================================================
  
  // Form data state
  const [form, setForm] = useState({ 
    full_name: '', 
    email: '', 
    password: '' 
  })
  
  // Loading state for form submission
  const [loading, setLoading] = useState(false)
  
  // Password visibility toggle
  const [showPassword, setShowPassword] = useState(false)
  
  // Track if password field has been touched (for validation display)
  const [passwordTouched, setPasswordTouched] = useState(false)
  
  // ===========================================================================
  // HOOKS
  // ===========================================================================
  
  // Get loginUser function from AuthContext
  const { loginUser } = useAuth()
  
  // Navigation hook for redirecting after registration
  const navigate = useNavigate()

  // ===========================================================================
  // PASSWORD VALIDATION
  // ===========================================================================
  
  /**
   * Password strength requirements
   * Currently requires minimum 8 characters
   * Can be extended with more rules (uppercase, numbers, special chars)
   */
  const passwordRequirements = [
    { 
      label: 'At least 8 characters', 
      met: form.password.length >= 8 
    },
    // Additional rules can be added here:
    // { label: 'One uppercase letter', met: /[A-Z]/.test(form.password) },
    // { label: 'One number', met: /[0-9]/.test(form.password) },
    // { label: 'One special character', met: /[!@#$%^&*]/.test(form.password) },
  ]
  
  // Check if all password requirements are met
  const isPasswordValid = passwordRequirements.every(req => req.met)
  
  // Check if form is valid for submission
  const isFormValid = form.full_name.trim().length > 0 && 
                      form.email.trim().length > 0 && 
                      isPasswordValid

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
    
    // Mark password as touched when user starts typing
    if (field === 'password' && !passwordTouched) {
      setPasswordTouched(true)
    }
  }

  /**
   * Handle form submission
   * 
   * Flow:
   *   1. Prevent default form submission
   *   2. Validate form data
   *   3. Call register API with user details
   *   4. Extract JWT token from response
   *   5. Save token to localStorage
   *   6. Fetch user profile with the token
   *   7. Update AuthContext with user data
   *   8. Show success toast and redirect to onboarding
   * 
   * Note: New users receive 5 free credits automatically from backend
   * 
   * Error handling:
   *   - 400: Email already registered or invalid data
   *   - Network errors
   */
  const handleSubmit = async (e) => {
    e.preventDefault()
    
    // Additional validation before submission
    if (!isPasswordValid) {
      toast.error('Please meet all password requirements')
      setPasswordTouched(true)
      return
    }
    
    setLoading(true)
    
    try {
      // Step 1: Create account and get token
      const res = await register(form)
      const token = res.data.access_token
      
      // Step 2: Store token for future API calls
      localStorage.setItem('token', token)
      
      // Step 3: Fetch the complete user profile
      const profile = await getProfile()
      
      // Step 4: Update AuthContext (saves user to state and localStorage)
      loginUser(token, profile.data)
      
      // Step 5: Show success message
      toast.success('Account created — 5 free credits added!')
      
      // Step 6: Redirect to onboarding for first-time setup
      // Onboarding allows user to set industry and location preferences
      navigate('/onboarding')
    } catch (err) {
      // Handle specific error cases
      const errorMessage = err.response?.data?.detail || 'Registration failed. Please try again.'
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
            REGISTRATION CARD
            ===================================================================== */}
        <div className="card p-6 md:p-8 space-y-5">
          {/* Header */}
          <div>
            <h1 className="text-xl font-semibold text-gray-900">Create account</h1>
            <p className="text-base text-gray-500 mt-1">
              Get 5 free credits on signup
            </p>
          </div>

          {/* Registration Form */}
          <form onSubmit={handleSubmit} className="space-y-4">
            {/* -------------------------------------------------------------
                FULL NAME FIELD
                ------------------------------------------------------------- */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">
                Full name
              </label>
              <input
                type="text"
                className="input py-2.5 text-base"
                placeholder="Jane Dlamini"
                value={form.full_name}
                onChange={(e) => handleChange('full_name', e.target.value)}
                required
                autoComplete="name"
                autoFocus
              />
            </div>

            {/* -------------------------------------------------------------
                EMAIL FIELD
                ------------------------------------------------------------- */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">
                Work email
              </label>
              <input
                type="email"
                className="input py-2.5 text-base"
                placeholder="jane@company.co.za"
                value={form.email}
                onChange={(e) => handleChange('email', e.target.value)}
                required
                autoComplete="email"
              />
            </div>

            {/* -------------------------------------------------------------
                PASSWORD FIELD WITH VISIBILITY TOGGLE & VALIDATION
                ------------------------------------------------------------- */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">
                Password
              </label>
              <div className="relative">
                <input
                  type={showPassword ? 'text' : 'password'}
                  className={`input py-2.5 text-base pr-10 ${
                    passwordTouched && !isPasswordValid 
                      ? 'border-red-300 focus:ring-red-400 focus:border-red-400' 
                      : ''
                  }`}
                  placeholder="Create a secure password"
                  value={form.password}
                  onChange={(e) => handleChange('password', e.target.value)}
                  onBlur={() => setPasswordTouched(true)}
                  required
                  minLength={8}
                  autoComplete="new-password"
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
              
              {/* Password requirements checklist */}
              {passwordTouched && (
                <div className="mt-2 space-y-1">
                  {passwordRequirements.map((req, index) => (
                    <div 
                      key={index} 
                      className="flex items-center gap-1.5 text-xs"
                    >
                      {req.met ? (
                        <Check size={12} className="text-green-500" />
                      ) : (
                        <X size={12} className="text-gray-300" />
                      )}
                      <span className={req.met ? 'text-green-700' : 'text-gray-500'}>
                        {req.label}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* -------------------------------------------------------------
                SUBMIT BUTTON
                ------------------------------------------------------------- */}
            <button 
              type="submit" 
              disabled={loading || (passwordTouched && !isFormValid)} 
              className="btn-primary w-full py-2.5 text-base mt-1 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? (
                <span className="flex items-center justify-center gap-2">
                  <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  Creating account...
                </span>
              ) : (
                'Create account'
              )}
            </button>
          </form>

          {/* =================================================================
              LOGIN LINK
              ================================================================= */}
          <p className="text-sm text-center text-gray-500">
            Already have an account?{' '}
            <Link 
              to="/login" 
              className="text-brand-600 hover:underline font-medium"
            >
              Sign in
            </Link>
          </p>
        </div>

        {/* =================================================================
            TERMS AND PRIVACY NOTE
            ================================================================= */}
        <p className="text-xs text-center text-gray-400 mt-6">
          By creating an account, you agree to our{' '}
          <a href="#" className="text-brand-600 hover:underline">
            Terms of Service
          </a>{' '}
          and{' '}
          <a href="#" className="text-brand-600 hover:underline">
            Privacy Policy
          </a>
        </p>
      </div>
    </div>
  )
}