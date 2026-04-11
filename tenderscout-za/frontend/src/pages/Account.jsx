import { useState, useEffect } from 'react'
import { useAuth } from '../context/AuthContext'
import { updatePreferences } from '../api/auth'
import { getTransactions } from '../api/credits'
import toast from 'react-hot-toast'

const INDUSTRIES = [
  'Security Services','Construction','Waste Management','Electrical Services',
  'Plumbing','ICT / Technology','Maintenance','Mining Services',
  'Cleaning Services','Catering','Consulting','Transport & Logistics','Healthcare','Landscaping',
]
const PROVINCES = [
  'Gauteng','Western Cape','KwaZulu-Natal','Eastern Cape',
  'Free State','Limpopo','Mpumalanga','North West','Northern Cape',
]

export default function Account() {
  const { user, refreshUser } = useAuth()
  const [industries, setIndustries] = useState(user?.industry_preferences || [])
  const [provinces, setProvinces] = useState(user?.province_preferences || [])
  const [transactions, setTransactions] = useState([])
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    getTransactions().then((r) => setTransactions(r.data)).catch(() => {})
  }, [])

  const toggle = (list, setList, val) =>
    setList(list.includes(val) ? list.filter((v) => v !== val) : [...list, val])

  const handleSave = async () => {
    setSaving(true)
    try {
      await updatePreferences({ industry_preferences: industries, province_preferences: provinces, town_preferences: [] })
      await refreshUser()
      toast.success('Preferences updated')
    } catch {
      toast.error('Failed to save')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="p-8 md:p-10 lg:p-12 max-w-5xl mx-auto space-y-8">
      <h1 className="text-2xl md:text-3xl font-semibold text-gray-900">Account</h1>

      {/* User profile card */}
      <div className="card p-5 md:p-6 space-y-2">
        <p className="text-lg font-semibold text-gray-900">{user?.full_name}</p>
        <p className="text-base text-gray-500">{user?.email}</p>
        <p className="text-sm text-gray-400 pt-1">
          Member since {new Date(user?.created_at).toLocaleDateString('en-ZA', { year: 'numeric', month: 'long', day: 'numeric' })}
        </p>
      </div>

      {/* Preferences card */}
      <div className="card p-5 md:p-6 space-y-5">
        <div>
          <h2 className="text-base font-semibold text-gray-900 mb-3">Industry preferences</h2>
          <div className="flex flex-wrap gap-2">
            {INDUSTRIES.map((i) => (
              <button key={i} onClick={() => toggle(industries, setIndustries, i)}
                className={`px-3 py-1.5 rounded-full text-sm border transition-all duration-150 ${
                  industries.includes(i) 
                    ? 'bg-brand-400 text-white border-brand-400 shadow-sm' 
                    : 'bg-white text-gray-700 border-gray-200 hover:border-brand-400 hover:bg-gray-50'
                }`}>
                {i}
              </button>
            ))}
          </div>
        </div>

        <div>
          <h2 className="text-base font-semibold text-gray-900 mb-3">Province preferences</h2>
          <div className="flex flex-wrap gap-2">
            {PROVINCES.map((p) => (
              <button key={p} onClick={() => toggle(provinces, setProvinces, p)}
                className={`px-3 py-1.5 rounded-full text-sm border transition-all duration-150 ${
                  provinces.includes(p) 
                    ? 'bg-brand-400 text-white border-brand-400 shadow-sm' 
                    : 'bg-white text-gray-700 border-gray-200 hover:border-brand-400 hover:bg-gray-50'
                }`}>
                {p}
              </button>
            ))}
          </div>
        </div>

        <div className="flex justify-end pt-3">
          <button onClick={handleSave} disabled={saving} className="btn-primary px-6 py-2.5 text-base">
            {saving ? 'Saving...' : 'Save preferences'}
          </button>
        </div>
      </div>

      {/* Transaction history card */}
      <div className="card p-5 md:p-6">
        <h2 className="text-base font-semibold text-gray-900 mb-4">Transaction history</h2>
        {transactions.length === 0 ? (
          <p className="text-base text-gray-400 py-4 text-center">No transactions yet.</p>
        ) : (
          <div className="space-y-3">
            {transactions.map((tx) => (
              <div key={tx.id} className="flex items-center justify-between py-3 border-b border-gray-100 last:border-0">
                <div>
                  <p className="text-sm font-medium text-gray-800">{tx.description}</p>
                  <p className="text-xs text-gray-400 mt-0.5">{new Date(tx.created_at).toLocaleString('en-ZA')}</p>
                </div>
                <span className={`text-base font-semibold ${tx.transaction_type === 'credit' ? 'text-brand-600' : 'text-red-500'}`}>
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