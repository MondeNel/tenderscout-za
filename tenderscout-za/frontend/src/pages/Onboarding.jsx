// src/pages/Onboarding.jsx
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { updatePreferences } from '../api/auth'
import { useAuth } from '../context/AuthContext'
import { getMunicipalities, getProvinces } from '../data/saLocations'
import LocationPicker from '../components/LocationPicker'
import { Zap, Check, ChevronRight, ChevronLeft, MapPin, Target, Building2, Briefcase } from 'lucide-react'
import toast from 'react-hot-toast'

const INDUSTRIES = [
  'Security Services', 'Construction', 'Waste Management', 'Electrical Services',
  'Plumbing', 'ICT / Technology', 'Maintenance', 'Mining Services',
  'Cleaning Services', 'Catering', 'Consulting', 'Transport & Logistics',
  'Healthcare', 'Landscaping',
]

const PROVINCES = getProvinces()

const STEPS = [
  { id: 1, label: 'Services',  icon: Briefcase, title: 'What services do you provide?',          sub: 'Select all that apply — we filter tenders to match your business.' },
  { id: 2, label: 'Location',  icon: MapPin,     title: 'Where is your business based?',          sub: 'We use this to prioritise nearby tenders first.' },
  { id: 3, label: 'Coverage',  icon: Target,     title: 'How far do you want to search?',         sub: 'Set your default search radius from your business location.' },
  { id: 4, label: 'Provinces', icon: Building2,  title: 'Any specific provinces to watch?',       sub: 'Optional — get alerts from specific provinces even outside your radius.' },
]

function StepIndicator({ step }) {
  return (
    <div className="flex items-center gap-2 mb-6">
      {STEPS.map((s, i) => {
        const Icon = s.icon
        const state = step === s.id ? 'active' : step > s.id ? 'done' : 'pending'
        return (
          <div key={s.id} className="flex items-center gap-2">
            <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium transition-all duration-200 ${
              state === 'active'  ? 'bg-brand-400 text-white' :
              state === 'done'   ? 'bg-brand-100 text-brand-700' :
              'bg-gray-100 text-gray-400'
            }`}>
              {state === 'done'
                ? <Check size={11} />
                : <Icon size={11} />
              }
              <span className="hidden sm:inline">{s.label}</span>
            </div>
            {i < STEPS.length - 1 && (
              <div className={`h-px w-4 sm:w-8 transition-colors ${step > s.id ? 'bg-brand-300' : 'bg-gray-200'}`} />
            )}
          </div>
        )
      })}
    </div>
  )
}

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

export default function Onboarding() {
  const [step, setStep]             = useState(1)
  const [industries, setIndustries] = useState([])
  const [location, setLocation]     = useState(null)    // { name, lat, lng, province, district, municipality }
  const [radiusKm, setRadiusKm]     = useState(100)
  const [provinces, setProvinces]   = useState([])
  const [loading, setLoading]       = useState(false)
  const { refreshUser }             = useAuth()
  const navigate                    = useNavigate()

  const toggleList = (list, setList, val) =>
    setList(list.includes(val) ? list.filter(v => v !== val) : [...list, val])

  const handleLocationChange = ({ location: loc, radiusKm: r }) => {
    setLocation(loc)
    setRadiusKm(r)
  }

  const canProceed = () => {
    if (step === 1) return industries.length > 0
    if (step === 2) return !!location
    return true  // Steps 3 and 4 are always optional to proceed
  }

  const handleFinish = async () => {
    setLoading(true)
    try {
      await updatePreferences({
        industry_preferences:    industries,
        province_preferences:    provinces,
        town_preferences:        location ? [location.name] : [],
        business_location:       location?.name || null,
        business_lat:            location?.lat  || null,
        business_lng:            location?.lng  || null,
        search_radius_km:        radiusKm,
        municipality_preferences: location ? [location.municipality] : [],
      })
      await refreshUser()
      toast.success('All set! Welcome to TenderScout.')
      navigate('/dashboard')
    } catch {
      toast.error('Failed to save preferences — please try again')
    } finally {
      setLoading(false)
    }
  }

  const currentStep = STEPS[step - 1]
  const Icon = currentStep.icon

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center px-4 py-10">
      <div className="w-full max-w-xl">
        {/* Logo */}
        <div className="flex items-center gap-2 mb-8 justify-center">
          <div className="w-8 h-8 bg-brand-400 rounded-xl flex items-center justify-center">
            <Zap size={16} className="text-white" />
          </div>
          <span className="text-base font-semibold text-gray-900">TenderScout ZA</span>
        </div>

        <StepIndicator step={step} />

        {/* Step header */}
        <div className="mb-5">
          <div className="flex items-center gap-2 mb-1">
            <Icon size={16} className="text-brand-500" />
            <h1 className="text-lg font-semibold text-gray-900">{currentStep.title}</h1>
          </div>
          <p className="text-sm text-gray-500">{currentStep.sub}</p>
        </div>

        {/* Step content */}
        <div className="card p-5 md:p-6 mb-4">

          {/* Step 1 — Industries */}
          {step === 1 && (
            <div className="flex flex-wrap gap-2">
              {INDUSTRIES.map(i => (
                <ToggleChip
                  key={i} label={i}
                  selected={industries.includes(i)}
                  onClick={() => toggleList(industries, setIndustries, i)}
                />
              ))}
            </div>
          )}

          {/* Step 2 — Location picker (no radius, no preview yet) */}
          {step === 2 && (
            <LocationPicker
              value={{ location, radiusKm }}
              onChange={handleLocationChange}
              showRadius={false}
              showPreview={false}
            />
          )}

          {/* Step 3 — Radius (with preview) */}
          {step === 3 && (
            <LocationPicker
              value={{ location, radiusKm }}
              onChange={handleLocationChange}
              showRadius={true}
              showPreview={true}
            />
          )}

          {/* Step 4 — Province targets */}
          {step === 4 && (
            <div className="space-y-4">
              <div className="flex flex-wrap gap-2">
                {PROVINCES.map(p => (
                  <ToggleChip
                    key={p} label={p}
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

        {/* Navigation */}
        <div className="flex items-center justify-between">
          {step > 1 ? (
            <button
              onClick={() => setStep(s => s - 1)}
              className="flex items-center gap-1.5 px-4 py-2 text-sm text-gray-600 hover:text-gray-900 border border-gray-200 rounded-lg hover:bg-gray-50"
            >
              <ChevronLeft size={14} /> Back
            </button>
          ) : <div />}

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

        {/* Step counter */}
        <p className="text-center text-xs text-gray-400 mt-4">
          Step {step} of {STEPS.length}
        </p>
      </div>
    </div>
  )
}