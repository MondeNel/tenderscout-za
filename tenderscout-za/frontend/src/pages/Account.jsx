/**
 * File: src/pages/Account.jsx
 * Purpose: User Account Management Page
 * 
 * This page allows users to view and manage their account settings:
 *   - View profile information (name, email, member since)
 *   - Update industry preferences
 *   - Update province preferences
 *   - Set business location and search radius
 *   - View transaction history (credits earned and spent)
 * 
 * All changes are saved to the backend via updatePreferences() and
 * immediately reflected in the AuthContext via refreshUser().
 * 
 * Layout:
 *   - Profile card (read-only)
 *   - Industry preferences (multi-select chips)
 *   - Province preferences (multi-select chips)
 *   - Location & radius (LocationPicker component)
 *   - Save button
 *   - Transaction history (list of credits/spending)
 */

import { useState, useEffect } from 'react'
import { useAuth } from '../context/AuthContext'
import { updatePreferences } from '../api/auth'
import { getTransactions } from '../api/credits'
import LocationPicker from '../components/LocationPicker'
import { findTown } from '../data/saLocations'
import toast from 'react-hot-toast'

// =============================================================================
// CONSTANTS
// =============================================================================

/**
 * Available industry categories (matching backend classification).
 * These are hard-coded here for the chip selection UI; the backend also
 * provides a /user/industries endpoint that returns the same list.
 */
const INDUSTRIES = [
  "Accounting, Banking & Legal", "Building & Trades", "Civil",
  "Cleaning & Facility Management", "Consultants", "Electrical & Automation",
  "Engineering Consultants", "General, Property & Auctions", "HR & Training",
  "IT & Telecoms", "Materials, Supply & Services", "Mechanical, Plant & Equipment",
  "Media & Marketing", "Medical & Healthcare", "Security, Access, Alarms & Fire",
  "Travel, Tourism & Hospitality",
]

/**
 * All 9 South African provinces.
 */
const PROVINCES = [
  'Gauteng', 'Western Cape', 'KwaZulu-Natal', 'Eastern Cape',
  'Free State', 'Limpopo', 'Mpumalanga', 'North West', 'Northern Cape',
]

// =============================================================================
// HELPER COMPONENT: SectionHeader
// =============================================================================

/**
 * Consistent section header styling.
 * @param {string} title - Section title
 */
function SectionHeader({ title }) {
  return <h2 className="text-base font-semibold text-gray-900 mb-3">{title}</h2>
}

// =============================================================================
// HELPER COMPONENT: ToggleChip
// =============================================================================

/**
 * Reusable toggle button for multi-select preferences.
 * Used for industries and provinces selection.
 * 
 * @param {string} label - Display text
 * @param {boolean} selected - Whether the chip is selected (blue highlight)
 * @param {Function} onClick - Click handler
 */
function ToggleChip({ label, selected, onClick }) {
  return (
    <button
      onClick={onClick}
      className={`px-3 py-1.5 rounded-full text-sm border transition-all duration-150 ${
        selected
          ? 'bg-brand-400 text-white border-brand-400 shadow-sm'
          : 'bg-white text-gray-700 border-gray-200 hover:border-brand-400 hover:bg-gray-50'
      }`}
    >
      {label}
    </button>
  )
}

// =============================================================================
// MAIN COMPONENT
// =============================================================================

export default function Account() {
  // ===========================================================================
  // HOOKS & CONTEXT
  // ===========================================================================
  
  // Extract the current user and the refreshUser function from the global
  // auth context. `user` contains all profile data including preferences.
  const { user, refreshUser } = useAuth()

  // ===========================================================================
  // STATE - Preferences
  // ===========================================================================
  
  // Industry preferences (initialized from user profile)
  const [industries, setIndustries] = useState(user?.industry_preferences || [])
  
  // Province preferences (initialized from user profile)
  const [provinces, setProvinces] = useState(user?.province_preferences || [])

  // Location preferences — initialized from user's saved business location.
  // The location object stores the selected town (with coordinates) and the
  // search radius in km. We use findTown() to convert a saved location string
  // into a full location object (lat, lng, municipality) from our static data.
  const [locationValue, setLocationValue] = useState(() => {
    const loc = user?.business_location 
      ? findTown(user.business_location)  // Look up coordinates from saLocations
      : null
    
    return {
      location: loc || null,
      radiusKm: user?.search_radius_km || 100,
    }
  })

  // ===========================================================================
  // STATE - Transaction History
  // ===========================================================================
  
  // Transaction list loaded from the backend (credit/debit history).
  const [transactions, setTransactions] = useState([])
  
  // ===========================================================================
  // STATE - UI
  // ===========================================================================
  
  // Flag to show a loading spinner on the save button while the API call is in
  // progress.
  const [saving, setSaving] = useState(false)

  // ===========================================================================
  // EFFECTS
  // ===========================================================================
  
  /**
   * Load transaction history on component mount.
   * If the API call fails (e.g., network error), we silently fail — transaction
   * history is not critical for core functionality.
   */
  useEffect(() => {
    getTransactions()
      .then(r => setTransactions(r.data))
      .catch(() => {
        // Silently fail — transaction history is not critical
      })
  }, [])

  // ===========================================================================
  // UTILITIES
  // ===========================================================================
  
  /**
   * Toggle an item in a list (add if not present, remove if present).
   * Used for both industries and provinces selection.
   * 
   * @param {Array} list - Current list
   * @param {Function} setList - State setter function
   * @param {any} val - Value to toggle
   */
  const toggle = (list, setList, val) =>
    setList(list.includes(val) ? list.filter(v => v !== val) : [...list, val])

  // ===========================================================================
  // SAVE HANDLER
  // ===========================================================================
  
  /**
   * Save all preferences to the backend.
   * 
   * Collects current state from all preference sections and sends to API.
   * On success:
   *   - Refreshes user context to update displayed data
   *   - Shows success toast
   * 
   * Saved preferences:
   *   - industry_preferences: Selected industries
   *   - province_preferences: Selected provinces
   *   - town_preferences: Selected town name
   *   - business_location: Human-readable address
   *   - business_lat/lng: Coordinates for distance calculations
   *   - search_radius_km: Default search radius
   *   - municipality_preferences: User's municipality
   */
  const handleSave = async () => {
    setSaving(true)
    
    try {
      const loc = locationValue.location
      
      // Build the payload for the PUT /user/preferences endpoint.
      // Only the fields we explicitly set are updated; omitted fields
      // are left unchanged on the server.
      await updatePreferences({
        industry_preferences:      industries,
        province_preferences:      provinces,
        town_preferences:          loc ? [loc.name] : [],
        business_location:         loc?.name || null,
        business_lat:              loc?.lat || null,
        business_lng:              loc?.lng || null,
        search_radius_km:          locationValue.radiusKm,
        municipality_preferences:   loc ? [loc.municipality] : [],
      })
      
      // Refresh the user object in AuthContext so the UI reflects the new
      // preferences (e.g., the profile card, and any components reading
      // user.industry_preferences).
      await refreshUser()
      
      toast.success('Preferences saved')
    } catch {
      toast.error('Failed to save preferences')
    } finally {
      setSaving(false)
    }
  }

  // ===========================================================================
  // RENDER
  // ===========================================================================
  
  return (
    <div className="p-6 md:p-8 lg:p-10 max-w-4xl mx-auto space-y-6">
      {/* =====================================================================
          PAGE TITLE
          ===================================================================== */}
      <h1 className="text-2xl font-semibold text-gray-900">Account</h1>

      {/* =====================================================================
          PROFILE CARD (Read-only)
          Displays the user's name, email, and member-since date.
          ===================================================================== */}
      <div className="card p-5 space-y-1">
        <p className="text-base font-semibold text-gray-900">{user?.full_name}</p>
        <p className="text-sm text-gray-500">{user?.email}</p>
        <p className="text-xs text-gray-400 pt-1">
          Member since {new Date(user?.created_at).toLocaleDateString('en-ZA', { 
            year: 'numeric', 
            month: 'long', 
            day: 'numeric' 
          })}
        </p>
      </div>

      {/* =====================================================================
          INDUSTRY PREFERENCES
          Multi-select chips that toggle the industries array.
          ===================================================================== */}
      <div className="card p-5">
        <SectionHeader title="Industry preferences" />
        <p className="text-sm text-gray-500 mb-4">
          Select the industries you're interested in. We'll prioritize tenders matching these categories.
        </p>
        <div className="flex flex-wrap gap-2">
          {INDUSTRIES.map(i => (
            <ToggleChip 
              key={i} 
              label={i} 
              selected={industries.includes(i)} 
              onClick={() => toggle(industries, setIndustries, i)} 
            />
          ))}
        </div>
      </div>

      {/* =====================================================================
          PROVINCE PREFERENCES
          Similar to industry chips, but for South African provinces.
          ===================================================================== */}
      <div className="card p-5">
        <SectionHeader title="Province preferences" />
        <p className="text-sm text-gray-500 mb-4">
          Select provinces you want to monitor. Leave empty to see tenders from all provinces.
        </p>
        <div className="flex flex-wrap gap-2">
          {PROVINCES.map(p => (
            <ToggleChip 
              key={p} 
              label={p} 
              selected={provinces.includes(p)} 
              onClick={() => toggle(provinces, setProvinces, p)} 
            />
          ))}
        </div>
      </div>

      {/* =====================================================================
          LOCATION & RADIUS
          Uses the LocationPicker component that lets the user select a town
          from a dropdown (or use geolocation) and choose a radius.
          ===================================================================== */}
      <div className="card p-5">
        <SectionHeader title="Location & radius" />
        <p className="text-sm text-gray-500 mb-4">
          Set your business location and default search radius so we can show nearby tenders first.
        </p>
        <LocationPicker
          value={locationValue}
          onChange={setLocationValue}
          showRadius={true}
          showPreview={true}
        />
      </div>

      {/* =====================================================================
          SAVE BUTTON
          Sends all preference changes to the server. Shows a spinner while
          the request is in flight.
          ===================================================================== */}
      <div className="flex justify-end">
        <button 
          onClick={handleSave} 
          disabled={saving} 
          className="btn-primary px-6 py-2.5"
        >
          {saving ? (
            <span className="flex items-center gap-2">
              <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
              Saving...
            </span>
          ) : (
            'Save all preferences'
          )}
        </button>
      </div>

      {/* =====================================================================
          TRANSACTION HISTORY
          Each transaction shows a description, date, and amount.
          Amount is colored green for credits, red for debits.
          ===================================================================== */}
      <div className="card p-5">
        <SectionHeader title="Transaction history" />
        {transactions.length === 0 ? (
          <p className="text-sm text-gray-400 text-center py-4">
            No transactions yet.
          </p>
        ) : (
          <div className="space-y-2">
            {transactions.map(tx => (
              <div 
                key={tx.id} 
                className="flex items-center justify-between py-2.5 border-b border-gray-100 last:border-0"
              >
                {/* Left side: description and date */}
                <div>
                  <p className="text-sm font-medium text-gray-800">
                    {tx.description}
                  </p>
                  <p className="text-xs text-gray-400 mt-0.5">
                    {new Date(tx.created_at).toLocaleString('en-ZA')}
                  </p>
                </div>
                
                {/* Right side: amount with color coding */}
                <span className={`text-sm font-semibold ${
                  tx.transaction_type === 'credit' 
                    ? 'text-brand-600'   // Credit (added)
                    : 'text-red-500'      // Debit (spent)
                }`}>
                  {tx.transaction_type === 'credit' ? '+' : '-'}{tx.amount}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}