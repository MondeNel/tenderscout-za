/**
 * File: src/pages/Onboarding.jsx
 * Purpose: First-Time User Onboarding / Preference Setup
 * 
 * This page guides new users through setting up their tender preferences
 * immediately after registration. It uses a multi-step wizard flow.
 * 
 * Steps:
 *   1. Industries - Select business sectors you work in
 *   2. Location - Set your business address (with map picker)
 *   3. Coverage - Define search radius from your location
 *   4. Provinces - Optionally monitor specific provinces
 * 
 * After completion:
 *   - Preferences are saved to the backend via updatePreferences()
 *   - User is redirected to the dashboard with personalized tenders
 *   - Free credits are already added from registration
 * 
 * Features:
 *   - Progress indicator with step icons
 *   - Form validation (can't proceed without required fields)
 *   - Skip option for optional steps
 *   - Smooth transitions between steps
 *   - Mobile-responsive design
 */

import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { updatePreferences } from '../api/auth'
import { useAuth } from '../context/AuthContext'
import { getMunicipalities, getProvinces } from '../data/saLocations'
import LocationPicker from '../components/LocationPicker'
import { 
  Zap,           // Logo icon
  Check,         // Checkmark for completed steps
  ChevronRight,  // Next button
  ChevronLeft,   // Back button
  MapPin,        // Location step icon
  Target,        // Radius/coverage step icon
  Building2,     // Provinces step icon
  Briefcase      // Industries step icon
} from 'lucide-react'
import toast from 'react-hot-toast'

// =============================================================================
// CONSTANTS
// =============================================================================

/**
 * Available industry categories for selection
 * These match the backend's industry classification system
 */
const INDUSTRIES = [
  "Accounting, Banking & Legal", 
  "Building & Trades", 
  "Civil",
  "Cleaning & Facility Management", 
  "Consultants", 
  "Electrical & Automation",
  "Engineering Consultants", 
  "General, Property & Auctions", 
  "HR & Training",
  "IT & Telecoms", 
  "Materials, Supply & Services", 
  "Mechanical, Plant & Equipment",
  "Media & Marketing", 
  "Medical & Healthcare", 
  "Security, Access, Alarms & Fire",
  "Travel, Tourism & Hospitality",
]

/**
 * All 9 South African provinces from geographic data
 */
const PROVINCES = getProvinces()

/**
 * Onboarding step configuration
 * Each step has an ID, label, icon, title, and description
 */
const STEPS = [
  { 
    id: 1, 
    label: 'Services',  
    icon: Briefcase, 
    title: 'What services do you provide?',          
    sub: 'Select all that apply — we filter tenders to match your business.' 
  },
  { 
    id: 2, 
    label: 'Location',  
    icon: MapPin,     
    title: 'Where is your business based?',          
    sub: 'We use this to prioritise nearby tenders first.' 
  },
  { 
    id: 3, 
    label: 'Coverage',  
    icon: Target,     
    title: 'How far do you want to search?',         
    sub: 'Set your default search radius from your business location.' 
  },
  { 
    id: 4, 
    label: 'Provinces', 
    icon: Building2,  
    title: 'Any specific provinces to watch?',       
    sub: 'Optional — get alerts from specific provinces even outside your radius.' 
  },
]

// =============================================================================
// HELPER COMPONENT: StepIndicator
// =============================================================================

/**
 * Progress indicator showing current onboarding step
 * 
 * Visual states:
 *   - active: Current step (brand color background)
 *   - done: Completed step (light brand background with checkmark)
 *   - pending: Future step (gray background)
 * 
 * @param {number} step - Current step number (1-4)
 */
function StepIndicator({ step }) {
  return (
    <div className="flex items-center gap-2 mb-6">
      {STEPS.map((s, i) => {
        const Icon = s.icon
        const state = step === s.id ? 'active' : step > s.id ? 'done' : 'pending'
        
        return (
          <div key={s.id} className="flex items-center gap-2">
            {/* Step pill */}
            <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium transition-all duration-200 ${
              state === 'active'  ? 'bg-brand-400 text-white' :
              state === 'done'    ? 'bg-brand-100 text-brand-700' :
              'bg-gray-100 text-gray-400'
            }`}>
              {state === 'done'
                ? <Check size={11} />
                : <Icon size={11} />
              }
              <span className="hidden sm:inline">{s.label}</span>
            </div>
            
            {/* Connector line between steps */}
            {i < STEPS.length - 1 && (
              <div className={`h-px w-4 sm:w-8 transition-colors ${
                step > s.id ? 'bg-brand-300' : 'bg-gray-200'
              }`} />
            )}
          </div>
        )
      })}
    </div>
  )
}

// =============================================================================
// HELPER COMPONENT: ToggleChip
// =============================================================================

/**
 * Reusable toggle button for multi-select options
 * Used for industries and provinces selection
 * 
 * @param {string} label - Display text
 * @param {boolean} selected - Whether the chip is selected
 * @param {Function} onClick - Click handler
 */
function ToggleChip({ label, selected, onClick }) {
  return (
    <button
      onClick={onClick}
      className={`px-3 py-1.5 rounded-full text-sm border transition-all duration-150 select-none ${
        selected
          ? 'bg-brand-400 text-white border-brand-400 shadow-sm'
          : 'bg-white text-gray-600 border-gray-200 hover:border-brand-400 hover:bg-gray-50'
      }`}
    >
      {selected && <Check size={11} className="inline mr-1 -mt-0.5" />}
      {label}
    </button>
  )
}

// =============================================================================
// MAIN COMPONENT: Onboarding
// =============================================================================

export default function Onboarding() {
  // ===========================================================================
  // STATE
  // ===========================================================================
  
  // Current step (1-4)
  const [step, setStep] = useState(1)
  
  // Selected industries (Step 1)
  const [industries, setIndustries] = useState([])
  
  // Business location with coordinates (Step 2)
  const [location, setLocation] = useState(null)  // { name, lat, lng, province, district, municipality }
  
  // Search radius in kilometers (Step 3)
  const [radiusKm, setRadiusKm] = useState(100)
  
  // Selected provinces to monitor (Step 4, optional)
  const [provinces, setProvinces] = useState([])
  
  // Loading state during final submission
  const [loading, setLoading] = useState(false)
  
  // ===========================================================================
  // HOOKS
  // ===========================================================================
  
  const { refreshUser } = useAuth()
  const navigate = useNavigate()

  // ===========================================================================
  // UTILITY FUNCTIONS
  // ===========================================================================

  /**
   * Toggle an item in a list (add if not present, remove if present)
   * Used for both industries and provinces selection
   * 
   * @param {Array} list - Current list
   * @param {Function} setList - State setter function
   * @param {any} val - Value to toggle
   */
  const toggleList = (list, setList, val) =>
    setList(list.includes(val) ? list.filter(v => v !== val) : [...list, val])

  /**
   * Handle location changes from LocationPicker component
   * Updates both location and radius state
   * 
   * @param {Object} data - { location, radiusKm }
   */
  const handleLocationChange = ({ location: loc, radiusKm: r }) => {
    setLocation(loc)
    setRadiusKm(r)
  }

  // ===========================================================================
  // VALIDATION
  // ===========================================================================

  /**
   * Check if user can proceed to next step
   * 
   * Step 1: At least one industry selected
   * Step 2: Location must be set
   * Step 3: Always allowed (optional to adjust radius)
   * Step 4: Always allowed (provinces are optional)
   * 
   * @returns {boolean} Whether the current step is complete
   */
  const canProceed = () => {
    if (step === 1) return industries.length > 0
    if (step === 2) return !!location
    return true  // Steps 3 and 4 are optional to proceed
  }

  // ===========================================================================
  // SUBMISSION
  // ===========================================================================

  /**
   * Save all preferences and complete onboarding
   * 
   * Sends collected preferences to backend, refreshes user data,
   * and redirects to dashboard.
   * 
   * Preferences saved:
   *   - industry_preferences: Selected industries
   *   - province_preferences: Selected provinces (optional)
   *   - town_preferences: Selected town name
   *   - business_location: Human-readable address
   *   - business_lat/lng: Coordinates for distance calculations
   *   - search_radius_km: Default search radius
   *   - municipality_preferences: User's municipality
   */
  const handleFinish = async () => {
    setLoading(true)
    
    try {
      // Save all collected preferences to backend
      await updatePreferences({
        industry_preferences:      industries,
        province_preferences:      provinces,
        town_preferences:          location ? [location.name] : [],
        business_location:         location?.name || null,
        business_lat:              location?.lat || null,
        business_lng:              location?.lng || null,
        search_radius_km:          radiusKm,
        municipality_preferences:  location ? [location.municipality] : [],
      })
      
      // Refresh user data in AuthContext (updates credit balance, preferences)
      await refreshUser()
      
      // Show success message and redirect
      toast.success('All set! Welcome to TenderScout.')
      navigate('/dashboard')
    } catch (error) {
      toast.error('Failed to save preferences — please try again')
    } finally {
      setLoading(false)
    }
  }

  // ===========================================================================
  // RENDER
  // ===========================================================================
  
  const currentStep = STEPS[step - 1]
  const Icon = currentStep.icon

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center px-4 py-10">
      <div className="w-full max-w-xl">
        {/* =====================================================================
            LOGO
            ===================================================================== */}
        <div className="flex items-center gap-2 mb-8 justify-center">
          <div className="w-8 h-8 bg-brand-400 rounded-xl flex items-center justify-center">
            <Zap size={16} className="text-white" />
          </div>
          <span className="text-base font-semibold text-gray-900">TenderScout ZA</span>
        </div>

        {/* =====================================================================
            STEP INDICATOR
            ===================================================================== */}
        <StepIndicator step={step} />

        {/* =====================================================================
            STEP HEADER
            ===================================================================== */}
        <div className="mb-5">
          <div className="flex items-center gap-2 mb-1">
            <Icon size={16} className="text-brand-500" />
            <h1 className="text-lg font-semibold text-gray-900">{currentStep.title}</h1>
          </div>
          <p className="text-sm text-gray-500">{currentStep.sub}</p>
        </div>

        {/* =====================================================================
            STEP CONTENT CARD
            ===================================================================== */}
        <div className="card p-5 md:p-6 mb-4">

          {/* -------------------------------------------------------------
              STEP 1: INDUSTRIES SELECTION
              ------------------------------------------------------------- */}
          {step === 1 && (
            <div className="flex flex-wrap gap-2">
              {INDUSTRIES.map(i => (
                <ToggleChip
                  key={i} 
                  label={i}
                  selected={industries.includes(i)}
                  onClick={() => toggleList(industries, setIndustries, i)}
                />
              ))}
            </div>
          )}

          {/* -------------------------------------------------------------
              STEP 2: LOCATION PICKER (no radius yet)
              ------------------------------------------------------------- */}
          {step === 2 && (
            <LocationPicker
              value={{ location, radiusKm }}
              onChange={handleLocationChange}
              showRadius={false}
              showPreview={false}
            />
          )}

          {/* -------------------------------------------------------------
              STEP 3: RADIUS SELECTION (with municipality preview)
              ------------------------------------------------------------- */}
          {step === 3 && (
            <LocationPicker
              value={{ location, radiusKm }}
              onChange={handleLocationChange}
              showRadius={true}
              showPreview={true}
            />
          )}

          {/* -------------------------------------------------------------
              STEP 4: PROVINCES SELECTION (optional)
              ------------------------------------------------------------- */}
          {step === 4 && (
            <div className="space-y-4">
              <div className="flex flex-wrap gap-2">
                {PROVINCES.map(p => (
                  <ToggleChip
                    key={p} 
                    label={p}
                    selected={provinces.includes(p)}
                    onClick={() => toggleList(provinces, setProvinces, p)}
                  />
                ))}
              </div>
              {provinces.length === 0 && (
                <p className="text-sm text-gray-400 italic">
                  Skip this step if you only want to search by location radius.
                </p>
              )}
            </div>
          )}
        </div>

        {/* =====================================================================
            NAVIGATION BUTTONS
            ===================================================================== */}
        <div className="flex items-center justify-between">
          {/* Back button (hidden on first step) */}
          {step > 1 ? (
            <button
              onClick={() => setStep(s => s - 1)}
              className="flex items-center gap-1.5 px-4 py-2 text-sm text-gray-600 hover:text-gray-900 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"
            >
              <ChevronLeft size={14} /> Back
            </button>
          ) : (
            <div /> /* Empty div for flex spacing */
          )}

          {/* Next button (steps 1-3) or Finish button (step 4) */}
          {step < STEPS.length ? (
            <button
              onClick={() => setStep(s => s + 1)}
              disabled={!canProceed()}
              className="flex items-center gap-1.5 btn-primary px-5 py-2 text-sm disabled:opacity-40 disabled:cursor-not-allowed"
            >
              Next <ChevronRight size={14} />
            </button>
          ) : (
            <button
              onClick={handleFinish}
              disabled={loading}
              className="btn-primary px-6 py-2 text-sm"
            >
              {loading ? 'Saving...' : 'Go to dashboard →'}
            </button>
          )}
        </div>

        {/* =====================================================================
            STEP COUNTER
            ===================================================================== */}
        <p className="text-center text-xs text-gray-400 mt-4">
          Step {step} of {STEPS.length}
        </p>
      </div>
    </div>
  )
}