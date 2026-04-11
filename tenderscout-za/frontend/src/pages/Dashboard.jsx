import { useState, useEffect, useRef } from 'react'
import { useAuth } from '../context/AuthContext'
import { searchTenders, getLatest } from '../api/tenders'
import { RefreshCw, ExternalLink, MapPin, Clock, Building2 } from 'lucide-react'
import toast from 'react-hot-toast'

const BADGE_COLORS = {
  'ICT / Technology':    'bg-blue-50 text-blue-700',
  'Construction':        'bg-amber-50 text-amber-700',
  'Security Services':   'bg-indigo-50 text-indigo-700',
  'Electrical Services': 'bg-yellow-50 text-yellow-700',
  'Waste Management':    'bg-green-50 text-green-700',
  'Plumbing':            'bg-cyan-50 text-cyan-700',
  'Maintenance':         'bg-orange-50 text-orange-700',
  'Mining Services':     'bg-stone-50 text-stone-700',
  'Cleaning Services':   'bg-teal-50 text-teal-700',
  'Catering':            'bg-rose-50 text-rose-700',
  'Healthcare':          'bg-red-50 text-red-700',
  'Consulting':          'bg-purple-50 text-purple-700',
  'General':             'bg-gray-100 text-gray-600',
}

function timeAgo(dateStr) {
  const diff = Date.now() - new Date(dateStr).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  return `${Math.floor(hrs / 24)}d ago`
}

// Helper to get time-of-day greeting based on user's local time
function getGreeting() {
  const hour = new Date().getHours()
  if (hour < 12) return 'morning'
  if (hour < 17) return 'afternoon'
  return 'evening'
}

function TenderCard({ tender }) {
  const color = BADGE_COLORS[tender.industry_category] || BADGE_COLORS['General']
  return (
    <div className="card hover:border-gray-300 transition-all duration-200 p-5">
      <div className="flex items-start justify-between gap-4 mb-3">
        <h3 className="text-base font-semibold text-gray-900 leading-snug">{tender.title}</h3>
        <span className={`badge px-2.5 py-1 text-xs font-medium rounded-full flex-shrink-0 ${color}`}>
          {tender.industry_category}
        </span>
      </div>
      <div className="flex flex-wrap gap-x-5 gap-y-1.5 mb-4">
        {tender.issuing_body && (
          <span className="flex items-center gap-1.5 text-sm text-gray-500">
            <Building2 size={14} />
            {tender.issuing_body}
          </span>
        )}
        {tender.province && (
          <span className="flex items-center gap-1.5 text-sm text-gray-500">
            <MapPin size={14} />
            {tender.town ? `${tender.town}, ` : ''}{tender.province}
          </span>
        )}
        <span className="flex items-center gap-1.5 text-sm text-gray-500">
          <Clock size={14} />
          {timeAgo(tender.scraped_at)}
        </span>
      </div>
      <div className="flex items-center justify-between pt-3 border-t border-gray-100">
        {tender.closing_date ? (
          <span className="text-sm font-medium text-red-500">Closes {tender.closing_date}</span>
        ) : (
          <span className="text-sm text-gray-400">{tender.source_site}</span>
        )}
        <a
          href={tender.source_url}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-1.5 text-sm font-medium text-brand-600 hover:text-brand-800"
        >
          View tender <ExternalLink size={14} />
        </a>
      </div>
    </div>
  )
}

export default function Dashboard() {
  const { user, refreshUser } = useAuth()
  const [tenders, setTenders] = useState([])
  const [loading, setLoading] = useState(true)
  const [total, setTotal] = useState(0)
  const [newCount, setNewCount] = useState(0)
  const [pendingTenders, setPendingTenders] = useState([])
  const lastScrapeRef = useRef(new Date().toISOString())
  const pollRef = useRef(null)

  const loadTenders = async () => {
    if (!user) return
    setLoading(true)
    try {
      const res = await searchTenders({
        industries: user.industry_preferences || [],
        provinces: user.province_preferences || [],
        page: 1,
        page_size: 20,
      })
      setTenders(res.data.results)
      setTotal(res.data.total)
      await refreshUser()
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to load tenders')
    } finally {
      setLoading(false)
    }
  }

  const pollForNew = async () => {
    if (!user) return
    try {
      const res = await getLatest(
        lastScrapeRef.current,
        user.industry_preferences,
        user.province_preferences
      )
      if (res.data.new_count > 0) {
        setPendingTenders(res.data.tenders)
        setNewCount(res.data.new_count)
        lastScrapeRef.current = new Date().toISOString()
      }
    } catch {}
  }

  const loadNewTenders = () => {
    setTenders((prev) => [...pendingTenders, ...prev])
    setTotal((prev) => prev + pendingTenders.length)
    setPendingTenders([])
    setNewCount(0)
    refreshUser()
  }

  useEffect(() => {
    loadTenders()
  }, [])

  useEffect(() => {
    pollRef.current = setInterval(pollForNew, 60000)
    return () => clearInterval(pollRef.current)
  }, [user])

  const prefs = user?.industry_preferences?.length || user?.province_preferences?.length

  return (
    <div className="p-8 md:p-10 lg:p-12 max-w-screen-xl mx-auto">
      <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-4 mb-8">
        <div>
          <h1 className="text-2xl md:text-3xl font-semibold text-gray-900">
            Good {getGreeting()}, {user?.full_name?.split(' ')[0]}
          </h1>
          <p className="text-base text-gray-500 mt-1">
            {total} tenders matching your preferences
          </p>
        </div>
        <div className="flex items-center gap-3">
          <span className="flex items-center gap-2 text-sm text-gray-400">
            <span className="w-2 h-2 rounded-full bg-brand-400 animate-pulse" />
            Live — updating every 60s
          </span>
          <button onClick={loadTenders} className="btn-ghost p-2">
            <RefreshCw size={18} />
          </button>
        </div>
      </div>

      {newCount > 0 && (
        <div className="mb-6 flex items-center justify-between bg-brand-50 border border-brand-200 rounded-xl px-5 py-4">
          <span className="text-base font-medium text-brand-700">
            {newCount} new tender{newCount > 1 ? 's' : ''} found
          </span>
          <button onClick={loadNewTenders} className="text-base font-semibold text-brand-700 hover:text-brand-900">
            Load results
          </button>
        </div>
      )}

      {!prefs && (
        <div className="mb-6 card bg-amber-50 border-amber-200 p-5">
          <p className="text-base text-amber-800">
            You have not set preferences yet.{' '}
            <a href="/onboarding" className="font-semibold underline">Set your industries and provinces</a>
            {' '}to get relevant results.
          </p>
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5 mb-8">
        {[
          { label: 'Total tenders', val: total, sub: 'matching your filters' },
          { label: 'Credit balance', val: user?.credit_balance ?? 0, sub: `R${((user?.credit_balance ?? 0) * 10).toFixed(0)} value` },
          { label: 'Industries', val: user?.industry_preferences?.length ?? 0, sub: 'selected' },
          { label: 'Provinces', val: user?.province_preferences?.length ?? 0, sub: 'selected' },
        ].map(({ label, val, sub }) => (
          <div key={label} className="bg-gray-100 rounded-2xl px-5 py-4">
            <p className="text-sm text-gray-500">{label}</p>
            <p className="text-3xl font-bold text-gray-900 mt-1">{val}</p>
            <p className="text-sm text-gray-400 mt-0.5">{sub}</p>
          </div>
        ))}
      </div>

      {loading ? (
        <div className="flex justify-center py-20">
          <div className="w-8 h-8 border-3 border-brand-400 border-t-transparent rounded-full animate-spin" />
        </div>
      ) : tenders.length === 0 ? (
        <div className="text-center py-20 text-gray-500 text-base">
          No tenders found.{' '}
          {!prefs ? 'Set your preferences to get started.' : 'Try adjusting your filters.'}
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4">
          {tenders.map((t) => <TenderCard key={t.id} tender={t} />)}
        </div>
      )}
    </div>
  )
}