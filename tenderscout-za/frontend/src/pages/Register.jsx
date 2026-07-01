/**
 * File: src/pages/Register.jsx
 * Purpose: User Registration Page with Company Profile & Industry Dropdown
 *
 * New users:
 *   - Enter their name, email, password
 *   - Optionally provide company details (name, reg number, BEE, size)
 *   - Select one or more industries from a dropdown (multi‑select)
 *   - Choose province and town (for map centering)
 *   - Get 5 free credits on signup
 */

import { useState, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { register, getProfile } from '../api/auth'
import { SA_LOCATIONS, getTowns, findTown } from '../data/saLocations'
import { Zap, Eye, EyeOff, Check, X, MapPin, Building2 } from 'lucide-react'
import toast from 'react-hot-toast'

const PROVINCES = Object.keys(SA_LOCATIONS)

export default function Register() {
  // ===========================================================================
  // STATE
  // ===========================================================================

  const [form, setForm] = useState({
    full_name: '',
    email: '',
    password: '',
    company_name: '',
    registration_number: '',
    bee_level: '',
    company_size: '',
    industries: [],
    province: '',
    town: '',
  })

  const [loading, setLoading] = useState(false)
  const [showPassword, setShowPassword] = useState(false)
  const [passwordTouched, setPasswordTouched] = useState(false)

  // ===========================================================================
  // HOOKS
  // ===========================================================================

  const { loginUser } = useAuth()
  const navigate = useNavigate()

  // ===========================================================================
  // COMPUTED VALUES
  // ===========================================================================

  const passwordRequirements = [
    { label: 'At least 8 characters', met: form.password.length >= 8 },
  ]

  const isPasswordValid = passwordRequirements.every(req => req.met)
  const isFormValid =
    form.full_name.trim().length > 0 &&
    form.email.trim().length > 0 &&
    isPasswordValid

  // Get towns for selected province
  const townOptions = form.province ? getTowns(form.province) : []

  // ===========================================================================
  // FORM HANDLERS
  // ===========================================================================

  const handleChange = (field, value) => {
    setForm(prev => {
      const updated = { ...prev, [field]: value }
      if (field === 'province') {
        updated.town = ''
      }
      return updated
    })

    if (field === 'password' && !passwordTouched) {
      setPasswordTouched(true)
    }
  }

  const handleIndustriesChange = (e) => {
    const options = Array.from(e.target.selectedOptions, option => option.value)
    setForm(prev => ({ ...prev, industries: options }))
  }

  /**
   * Handle form submission
   */
  const handleSubmit = async (e) => {
    e.preventDefault()

    if (!isPasswordValid) {
      toast.error('Please meet all password requirements')
      setPasswordTouched(true)
      return
    }

    setLoading(true)

    try {
      const payload = {
        email: form.email,
        full_name: form.full_name,
        password: form.password,
        industries: form.industries,
        company_name: form.company_name || undefined,
        registration_number: form.registration_number || undefined,
        bee_level: form.bee_level || undefined,
        company_size: form.company_size || undefined,
      }

      if (form.province) {
        payload.province = form.province
      }

      if (form.town) {
        payload.town = form.town
        const townData = findTown(form.town)
        if (townData) {
          payload.business_location = townData.name
          payload.business_lat = townData.lat
          payload.business_lng = townData.lng
        }
      } else if (form.province && SA_LOCATIONS[form.province]) {
        const p = SA_LOCATIONS[form.province]
        payload.business_lat = p.lat
        payload.business_lng = p.lng
        payload.business_location = form.province
      }

      const res = await register(payload)
      const token = res.data.access_token
      localStorage.setItem('token', token)

      const profile = await getProfile()
      loginUser(token, profile.data)

      toast.success('Account created — 5 free credits added!')
      navigate('/dashboard')
    } catch (err) {
      const errorMessage =
        err.response?.data?.detail || 'Registration failed. Please try again.'
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
      <div className="w-full max-w-xl">
        {/* Logo */}
        <div className="flex items-center gap-3 mb-8 justify-center">
          <div className="w-10 h-10 bg-brand-400 rounded-xl flex items-center justify-center shadow-sm">
            <Zap size={20} className="text-white" />
          </div>
          <span className="text-xl font-semibold text-gray-900">TenderScout ZA</span>
        </div>

        {/* Registration Card */}
        <div className="card p-6 md:p-8 space-y-6">
          <div>
            <h1 className="text-xl font-semibold text-gray-900">
              Create company account
            </h1>
            <p className="text-base text-gray-500 mt-1">
              Get 5 free credits on signup
            </p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-5">
            {/* Personal Details */}
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

            {/* Password */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">
                Password
              </label>
              <div className="relative">
                <input
                  type={showPassword ? 'text' : 'password'}
                  className={`input py-2.5 text-base pr-10 ${
                    passwordTouched && !isPasswordValid ? 'border-red-300' : ''
                  }`}
                  placeholder="Create a secure password"
                  value={form.password}
                  onChange={(e) => handleChange('password', e.target.value)}
                  onBlur={() => setPasswordTouched(true)}
                  required
                  minLength={8}
                  autoComplete="new-password"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                >
                  {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                </button>
              </div>
              {passwordTouched && (
                <div className="mt-2 space-y-1">
                  {passwordRequirements.map((req, index) => (
                    <div key={index} className="flex items-center gap-1.5 text-xs">
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

            {/* =================================================================
                COMPANY DETAILS
                ================================================================= */}
            <div className="border-t border-gray-100 pt-4">
              <div className="flex items-center gap-2 mb-3">
                <Building2 size={14} className="text-brand-400" />
                <p className="text-sm font-medium text-gray-700">Company details</p>
                <span className="text-xs text-gray-400">(optional)</span>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs text-gray-500 mb-1">
                    Company name
                  </label>
                  <input
                    type="text"
                    className="input py-2 text-sm"
                    placeholder="My Company (Pty) Ltd"
                    value={form.company_name}
                    onChange={(e) => handleChange('company_name', e.target.value)}
                  />
                </div>
                <div>
                  <label className="block text-xs text-gray-500 mb-1">
                    Registration number
                  </label>
                  <input
                    type="text"
                    className="input py-2 text-sm"
                    placeholder="2024/123456/07"
                    value={form.registration_number}
                    onChange={(e) =>
                      handleChange('registration_number', e.target.value)
                    }
                  />
                </div>
                <div>
                  <label className="block text-xs text-gray-500 mb-1">
                    BEE Level
                  </label>
                  <select
                    className="input py-2 text-sm"
                    value={form.bee_level}
                    onChange={(e) => handleChange('bee_level', e.target.value)}
                  >
                    <option value="">Select level</option>
                    <option value="1">Level 1</option>
                    <option value="2">Level 2</option>
                    <option value="3">Level 3</option>
                    <option value="4">Level 4</option>
                    <option value="Non-compliant">Non-compliant</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs text-gray-500 mb-1">
                    Company size
                  </label>
                  <select
                    className="input py-2 text-sm"
                    value={form.company_size}
                    onChange={(e) => handleChange('company_size', e.target.value)}
                  >
                    <option value="">Select size</option>
                    <option value="Micro">Micro</option>
                    <option value="Small">Small</option>
                    <option value="Medium">Medium</option>
                    <option value="Large">Large</option>
                  </select>
                </div>
              </div>
            </div>

        
            {/* =================================================================
                LOCATION SELECTION
                ================================================================= */}
            <div className="border-t border-gray-100 pt-4">
              <div className="flex items-center gap-2 mb-3">
                <MapPin size={14} className="text-brand-400" />
                <p className="text-sm font-medium text-gray-700">Your location</p>
                <span className="text-xs text-gray-400">(optional)</span>
              </div>
              <p className="text-xs text-gray-500 mb-3">
                Set your province and town so we can show nearby tenders on your
                dashboard.
              </p>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs text-gray-500 mb-1">
                    Province
                  </label>
                  <select
                    className="input py-2 text-sm"
                    value={form.province}
                    onChange={(e) => handleChange('province', e.target.value)}
                  >
                    <option value="">Select province</option>
                    {PROVINCES.map((p) => (
                      <option key={p} value={p}>
                        {p}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-xs text-gray-500 mb-1">
                    Town/City
                  </label>
                  <select
                    className="input py-2 text-sm"
                    value={form.town}
                    onChange={(e) => handleChange('town', e.target.value)}
                    disabled={!form.province}
                  >
                    <option value="">Select town</option>
                    {townOptions.map((t) => (
                      <option key={t.name} value={t.name}>
                        {t.name}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
            </div>

            {/* Submit Button */}
            <button
              type="submit"
              disabled={loading || (passwordTouched && !isFormValid)}
              className="btn-primary w-full py-2.5 text-base mt-1 disabled:opacity-50"
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

          {/* Login Link */}
          <p className="text-sm text-center text-gray-500">
            Already have an account?{' '}
            <Link to="/login" className="text-brand-600 hover:underline font-medium">
              Sign in
            </Link>
          </p>
        </div>

        {/* Terms */}
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