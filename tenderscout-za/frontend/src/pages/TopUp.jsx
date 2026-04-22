/**
 * File: src/pages/TopUp.jsx
 * Purpose: Credit Purchase / Top-Up Page
 * 
 * This page allows users to purchase additional credits for searching tenders.
 * It displays:
 *   - Current credit balance with ZAR value
 *   - Three package options (Starter, Standard, Professional)
 *   - Demo notice (no real payment processing)
 *   - Purchase button with loading state
 * 
 * Credit Pricing:
 *   - 1 credit = 1 search result
 *   - R1 = 0.1 credits (or R10 per credit, depending on package)
 * 
 * Packages:
 *   - Starter:     R10  → 10 credits  (10 searches)
 *   - Standard:    R25  → 25 credits  (25 searches) — MOST POPULAR
 *   - Professional: R50  → 50 credits  (50 searches)
 * 
 * Note: This is a DEMO implementation. In production, this would integrate
 * with payment gateways like PayFast, Stripe, or Ozow.
 */

import { useState } from 'react'
import { topUp } from '../api/credits'
import { useAuth } from '../context/AuthContext'
import { CreditCard, Check } from 'lucide-react'
import toast from 'react-hot-toast'

// =============================================================================
// PACKAGE CONFIGURATION
// =============================================================================
// Each package defines the credit amount and display information.
// In demo mode, selecting a package instantly adds credits.

const PACKAGES = [
  { 
    value: '100',           // Package identifier sent to API (price in ZAR)
    credits: 10,            // Number of credits received
    label: 'Starter',       // Display name
    desc: '10 searches'     // Description shown to user
  },
  { 
    value: '250', 
    credits: 25, 
    label: 'Standard', 
    desc: '25 searches', 
    popular: true           // Highlights this package as "Most popular"
  },
  { 
    value: '500', 
    credits: 50, 
    label: 'Professional', 
    desc: '50 searches' 
  },
]

// =============================================================================
// MAIN COMPONENT
// =============================================================================

export default function TopUp() {
  // ===========================================================================
  // HOOKS & CONTEXT
  // ===========================================================================
  
  const { user, refreshUser } = useAuth()
  
  // ===========================================================================
  // STATE
  // ===========================================================================
  
  // Currently selected package (default: '250' - Standard)
  const [selected, setSelected] = useState('250')
  
  // Loading state during purchase
  const [loading, setLoading] = useState(false)

  // ===========================================================================
  // PURCHASE HANDLER
  // ===========================================================================
  
  /**
   * Handle credit purchase
   * 
   * Calls the topUp API with the selected package.
   * On success:
   *   - Refreshes user data to update credit balance
   *   - Shows success toast with confirmation message
   * 
   * Error handling:
   *   - Invalid package (shouldn't happen with hardcoded options)
   *   - Network errors
   *   - Backend validation errors
   */
  const handleTopUp = async () => {
    setLoading(true)
    
    try {
      // Call the topUp API with selected package value
      const res = await topUp(selected)
      
      // Refresh user context to get updated credit balance
      await refreshUser()
      
      // Show success message from backend
      toast.success(res.data.message)
    } catch (err) {
      // Handle errors gracefully
      toast.error(err.response?.data?.detail || 'Top-up failed')
    } finally {
      setLoading(false)
    }
  }

  // ===========================================================================
  // RENDER
  // ===========================================================================
  
  return (
    <div className="p-8 md:p-10 lg:p-12 max-w-3xl mx-auto">
      {/* =====================================================================
          PAGE HEADER
          ===================================================================== */}
      <h1 className="text-2xl md:text-3xl font-semibold text-gray-900 mb-2">
        Top up credits
      </h1>
      <p className="text-base text-gray-500 mb-8">
        1 credit = 1 search result = R10
      </p>

      {/* =====================================================================
          CURRENT BALANCE CARD
          ===================================================================== */}
      <div className="card p-5 md:p-6 mb-6 flex items-center justify-between">
        <div>
          <p className="text-sm font-medium text-gray-500">Current balance</p>
          <p className="text-3xl md:text-4xl font-bold text-gray-900">
            {user?.credit_balance ?? 0} credits
          </p>
          <p className="text-sm text-gray-400 mt-1">
            R{((user?.credit_balance ?? 0) * 10).toFixed(0)} value
          </p>
        </div>
        <CreditCard size={36} className="text-gray-300" />
      </div>

      {/* =====================================================================
          PACKAGE OPTIONS
          =====================================================================
          Radio-style selection cards for each credit package
      */}
      <div className="space-y-4 mb-8">
        {PACKAGES.map((pkg) => (
          <button
            key={pkg.value}
            onClick={() => setSelected(pkg.value)}
            className={`w-full card p-5 md:p-6 text-left transition-all duration-200 ${
              selected === pkg.value 
                ? 'border-brand-400 bg-brand-50 shadow-sm' 
                : 'hover:border-gray-300'
            }`}
          >
            <div className="flex items-center justify-between">
              {/* Left side: Radio indicator + Package info */}
              <div className="flex items-center gap-4">
                {/* Custom radio button */}
                <div className={`w-5 h-5 rounded-full border-2 flex items-center justify-center flex-shrink-0 ${
                  selected === pkg.value 
                    ? 'border-brand-400 bg-brand-400' 
                    : 'border-gray-300'
                }`}>
                  {selected === pkg.value && (
                    <Check size={12} className="text-white" />
                  )}
                </div>
                
                {/* Package details */}
                <div>
                  <div className="flex items-center gap-3 mb-1">
                    <p className="text-base font-semibold text-gray-900">
                      {pkg.label}
                    </p>
                    {/* "Most popular" badge */}
                    {pkg.popular && (
                      <span className="badge px-2 py-0.5 text-xs font-medium bg-brand-50 text-brand-700 rounded-full">
                        Most popular
                      </span>
                    )}
                  </div>
                  <p className="text-sm text-gray-500">
                    {pkg.credits} credits · {pkg.desc}
                  </p>
                </div>
              </div>
              
              {/* Right side: Price */}
              <p className="text-lg font-bold text-gray-900">
                R{pkg.value}
              </p>
            </div>
          </button>
        ))}
      </div>

      {/* =====================================================================
          DEMO NOTICE
          =====================================================================
          Informs users that this is a demo and no real payment is processed.
          In production, this would be replaced with actual payment form.
      */}
      <div className="card p-4 md:p-5 bg-amber-50 border-amber-200 mb-6">
        <p className="text-sm text-amber-800">
          ⚠️ This is a demo — no real payment is processed. Credits are added instantly.
        </p>
      </div>

      {/* =====================================================================
          PURCHASE BUTTON
          ===================================================================== */}
      <button 
        onClick={handleTopUp} 
        disabled={loading} 
        className="btn-primary w-full py-3.5 text-base font-semibold"
      >
        {loading ? (
          <span className="flex items-center justify-center gap-2">
            <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
            Processing...
          </span>
        ) : (
          `Add ${PACKAGES.find((p) => p.value === selected)?.credits} credits — R${selected}`
        )}
      </button>
    </div>
  )
}