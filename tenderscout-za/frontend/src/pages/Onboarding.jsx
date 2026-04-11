import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { updatePreferences } from '../api/auth'
import { useAuth } from '../context/AuthContext'
import toast from 'react-hot-toast'

const INDUSTRIES = [
  'Security Services', 'Construction', 'Waste Management',
  'Electrical Services', 'Plumbing', 'ICT / Technology',
  'Maintenance', 'Mining Services', 'Cleaning Services',
  'Catering', 'Consulting', 'Transport & Logistics',
  'Healthcare', 'Landscaping',
]

const PROVINCES = [
  'Gauteng', 'Western Cape', 'KwaZulu-Natal', 'Eastern Cape',
  'Free State', 'Limpopo', 'Mpumalanga', 'North West', 'Northern Cape',
]

export default function Onboarding() {
  const [step, setStep] = useState(1)
  const [industries, setIndustries] = useState([])
  const [provinces, setProvinces] = useState([])
  const [loading, setLoading] = useState(false)
  const { refreshUser } = useAuth()
  const navigate = useNavigate()

  const toggle = (list, setList, val) =>
    setList(list.includes(val) ? list.filter((v) => v !== val) : [...list, val])

  const handleFinish = async () => {
    if (!industries.length || !provinces.length) {
      toast.error('Please select at least one industry and one province')
      return
    }
    setLoading(true)
    try {
      await updatePreferences({ industry_preferences: industries, province_preferences: provinces, town_preferences: [] })
      await refreshUser()
      toast.success('Preferences saved!')
      navigate('/dashboard')
    } catch {
      toast.error('Failed to save preferences')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center px-4 py-10">
      <div className="w-full max-w-xl">
        <div className="mb-6">
          <div className="flex gap-1 mb-4">
            {[1, 2].map((s) => (
              <div key={s} className={`h-1 flex-1 rounded-full transition-colors ${s <= step ? 'bg-brand-400' : 'bg-gray-200'}`} />
            ))}
          </div>
          <h1 className="text-lg font-500 text-gray-900">
            {step === 1 ? 'What services does your company provide?' : 'Which provinces do you operate in?'}
          </h1>
          <p className="text-sm text-gray-500 mt-1">
            {step === 1 ? 'Select all that apply — we use this to filter relevant tenders for you.' : 'Select all provinces where you want to receive tender alerts.'}
          </p>
        </div>

        <div className="card">
          <div className="flex flex-wrap gap-2">
            {(step === 1 ? INDUSTRIES : PROVINCES).map((item) => {
              const selected = (step === 1 ? industries : provinces).includes(item)
              return (
                <button
                  key={item}
                  onClick={() => step === 1 ? toggle(industries, setIndustries, item) : toggle(provinces, setProvinces, item)}
                  className={`px-3 py-1.5 rounded-full text-sm border transition-colors ${
                    selected
                      ? 'bg-brand-400 text-white border-brand-400'
                      : 'bg-white text-gray-600 border-gray-200 hover:border-brand-400 hover:text-brand-600'
                  }`}
                >
                  {item}
                </button>
              )
            })}
          </div>

          <div className="flex justify-between mt-6 pt-4 border-t border-gray-100">
            {step === 2 ? (
              <button onClick={() => setStep(1)} className="btn-secondary">Back</button>
            ) : <div />}
            {step === 1 ? (
              <button onClick={() => setStep(2)} disabled={!industries.length} className="btn-primary">
                Next — choose provinces
              </button>
            ) : (
              <button onClick={handleFinish} disabled={loading || !provinces.length} className="btn-primary">
                {loading ? 'Saving...' : 'Go to dashboard'}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
