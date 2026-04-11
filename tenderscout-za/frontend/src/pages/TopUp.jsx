import { useState } from 'react'
import { topUp } from '../api/credits'
import { useAuth } from '../context/AuthContext'
import { CreditCard, Check } from 'lucide-react'
import toast from 'react-hot-toast'

const PACKAGES = [
  { value: '100', credits: 10, label: 'Starter',    desc: '10 searches' },
  { value: '250', credits: 25, label: 'Standard',   desc: '25 searches', popular: true },
  { value: '500', credits: 50, label: 'Professional', desc: '50 searches' },
]

export default function TopUp() {
  const { user, refreshUser } = useAuth()
  const [selected, setSelected] = useState('250')
  const [loading, setLoading] = useState(false)

  const handleTopUp = async () => {
    setLoading(true)
    try {
      const res = await topUp(selected)
      await refreshUser()
      toast.success(res.data.message)
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Top-up failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="p-8 md:p-10 lg:p-12 max-w-3xl mx-auto">
      <h1 className="text-2xl md:text-3xl font-semibold text-gray-900 mb-2">Top up credits</h1>
      <p className="text-base text-gray-500 mb-8">1 credit = 1 search result = R10</p>

      {/* Balance card */}
      <div className="card p-5 md:p-6 mb-6 flex items-center justify-between">
        <div>
          <p className="text-sm font-medium text-gray-500">Current balance</p>
          <p className="text-3xl md:text-4xl font-bold text-gray-900">{user?.credit_balance ?? 0} credits</p>
          <p className="text-sm text-gray-400 mt-1">R{((user?.credit_balance ?? 0) * 10).toFixed(0)} value</p>
        </div>
        <CreditCard size={36} className="text-gray-300" />
      </div>

      {/* Package options */}
      <div className="space-y-4 mb-8">
        {PACKAGES.map((pkg) => (
          <button
            key={pkg.value}
            onClick={() => setSelected(pkg.value)}
            className={`w-full card p-5 md:p-6 text-left transition-all duration-200 ${
              selected === pkg.value ? 'border-brand-400 bg-brand-50 shadow-sm' : 'hover:border-gray-300'
            }`}
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <div className={`w-5 h-5 rounded-full border-2 flex items-center justify-center flex-shrink-0 ${
                  selected === pkg.value ? 'border-brand-400 bg-brand-400' : 'border-gray-300'
                }`}>
                  {selected === pkg.value && <Check size={12} className="text-white" />}
                </div>
                <div>
                  <div className="flex items-center gap-3 mb-1">
                    <p className="text-base font-semibold text-gray-900">{pkg.label}</p>
                    {pkg.popular && (
                      <span className="badge px-2 py-0.5 text-xs font-medium bg-brand-50 text-brand-700 rounded-full">
                        Most popular
                      </span>
                    )}
                  </div>
                  <p className="text-sm text-gray-500">{pkg.credits} credits · {pkg.desc}</p>
                </div>
              </div>
              <p className="text-lg font-bold text-gray-900">R{pkg.value}</p>
            </div>
          </button>
        ))}
      </div>

      {/* Demo notice */}
      <div className="card p-4 md:p-5 bg-amber-50 border-amber-200 mb-6">
        <p className="text-sm text-amber-800">
          This is a demo — no real payment is processed. Credits are added instantly.
        </p>
      </div>

      {/* Action button */}
      <button onClick={handleTopUp} disabled={loading} className="btn-primary w-full py-3.5 text-base font-semibold">
        {loading ? 'Processing...' : `Add ${PACKAGES.find((p) => p.value === selected)?.credits} credits — R${selected}`}
      </button>
    </div>
  )
}