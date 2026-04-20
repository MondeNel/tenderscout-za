// src/pages/Account.jsx
import { useState, useEffect } from 'react'
import { useAuth } from '../context/AuthContext'
import { updatePreferences } from '../api/auth'
import { getTransactions } from '../api/credits'
import LocationPicker from '../components/LocationPicker'
import { findTown } from '../data/saLocations'
import toast from 'react-hot-toast'

const INDUSTRIES = [
  "Accounting, Banking & Legal", "Building & Trades", "Civil",
  "Cleaning & Facility Management", "Consultants", "Electrical & Automation",
  "Engineering Consultants", "General, Property & Auctions", "HR & Training",
  "IT & Telecoms", "Materials, Supply & Services", "Mechanical, Plant & Equipment",
  "Media & Marketing", "Medical & Healthcare", "Security, Access, Alarms & Fire",
  "Travel, Tourism & Hospitality",
]

const PROVINCES = [
  'Gauteng','Western Cape','KwaZulu-Natal','Eastern Cape',
  'Free State','Limpopo','Mpumalanga','North West','Northern Cape',
]

function SectionHeader({ title }) {
  return <h2 className="text-base font-semibold text-gray-900 mb-3">{title}</h2>
}

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

export default function Account() {
  const { user, refreshUser } = useAuth()

  // Industry / province preferences
  const [industries, setIndustries] = useState(user?.industry_preferences || [])
  const [provinces,  setProvinces]  = useState(user?.province_preferences || [])

  // Location preferences — initialised from user profile
  const [locationValue, setLocationValue] = useState(() => {
    const loc = user?.business_location ? findTown(user.business_location) : null
    return {
      location: loc || null,
      radiusKm: user?.search_radius_km || 100,
    }
  })

  const [transactions, setTransactions] = useState([])
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    getTransactions().then(r => setTransactions(r.data)).catch(() => {})
  }, [])

  const toggle = (list, setList, val) =>
    setList(list.includes(val) ? list.filter(v => v !== val) : [...list, val])

  const handleSave = async () => {
    setSaving(true)
    try {
      const loc = locationValue.location
      await updatePreferences({
        industry_preferences:    industries,
        province_preferences:    provinces,
        town_preferences:        loc ? [loc.name] : [],
        business_location:       loc?.name  || null,
        business_lat:            loc?.lat   || null,
        business_lng:            loc?.lng   || null,
        search_radius_km:        locationValue.radiusKm,
        municipality_preferences: loc ? [loc.municipality] : [],
      })
      await refreshUser()
      toast.success('Preferences saved')
    } catch {
      toast.error('Failed to save')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="p-6 md:p-8 lg:p-10 max-w-4xl mx-auto space-y-6">
      <h1 className="text-2xl font-semibold text-gray-900">Account</h1>

      {/* Profile */}
      <div className="card p-5 space-y-1">
        <p className="text-base font-semibold text-gray-900">{user?.full_name}</p>
        <p className="text-sm text-gray-500">{user?.email}</p>
        <p className="text-xs text-gray-400 pt-1">
          Member since {new Date(user?.created_at).toLocaleDateString('en-ZA', { year: 'numeric', month: 'long', day: 'numeric' })}
        </p>
      </div>

      {/* Industry preferences */}
      <div className="card p-5">
        <SectionHeader title="Industry preferences" />
        <div className="flex flex-wrap gap-2">
          {INDUSTRIES.map(i => (
            <ToggleChip key={i} label={i} selected={industries.includes(i)} onClick={() => toggle(industries, setIndustries, i)} />
          ))}
        </div>
      </div>

      {/* Province preferences */}
      <div className="card p-5">
        <SectionHeader title="Province preferences" />
        <div className="flex flex-wrap gap-2">
          {PROVINCES.map(p => (
            <ToggleChip key={p} label={p} selected={provinces.includes(p)} onClick={() => toggle(provinces, setProvinces, p)} />
          ))}
        </div>
      </div>

      {/* Location preferences */}
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

      {/* Save button */}
      <div className="flex justify-end">
        <button onClick={handleSave} disabled={saving} className="btn-primary px-6 py-2.5">
          {saving ? 'Saving...' : 'Save all preferences'}
        </button>
      </div>

      {/* Transaction history */}
      <div className="card p-5">
        <SectionHeader title="Transaction history" />
        {transactions.length === 0 ? (
          <p className="text-sm text-gray-400 text-center py-4">No transactions yet.</p>
        ) : (
          <div className="space-y-2">
            {transactions.map(tx => (
              <div key={tx.id} className="flex items-center justify-between py-2.5 border-b border-gray-100 last:border-0">
                <div>
                  <p className="text-sm font-medium text-gray-800">{tx.description}</p>
                  <p className="text-xs text-gray-400 mt-0.5">{new Date(tx.created_at).toLocaleString('en-ZA')}</p>
                </div>
                <span className={`text-sm font-semibold ${tx.transaction_type === 'credit' ? 'text-brand-600' : 'text-red-500'}`}>
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