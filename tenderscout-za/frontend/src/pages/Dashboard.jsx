import { useState, useEffect, useRef } from 'react'
import { useAuth } from '../context/AuthContext'
import { searchTenders, getLatest } from '../api/tenders'
import { RefreshCw, ExternalLink, MapPin, Clock, Building2, AlertCircle } from 'lucide-react'
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
const BADGE_COLORS = {
  'ICT / Technology':'bg-blue-50 text-blue-700',
  'Construction':'bg-amber-50 text-amber-700',
  'Security Services':'bg-indigo-50 text-indigo-700',
  'Electrical Services':'bg-yellow-50 text-yellow-700',
  'Waste Management':'bg-green-50 text-green-700',
  'Plumbing':'bg-cyan-50 text-cyan-700',
  'Maintenance':'bg-orange-50 text-orange-700',
  'Mining Services':'bg-stone-50 text-stone-700',
  'Cleaning Services':'bg-teal-50 text-teal-700',
  'Catering':'bg-rose-50 text-rose-700',
  'Healthcare':'bg-red-50 text-red-700',
  'Consulting':'bg-purple-50 text-purple-700',
  'General':'bg-gray-100 text-gray-600',
}

function timeAgo(dateStr) {
  const diff = Date.now() - new Date(dateStr).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 60) return mins + 'm ago'
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return hrs + 'h ago'
  return Math.floor(hrs / 24) + 'd ago'
}

function isValidUrl(url) {
  try { return Boolean(new URL(url)) } catch { return false }
}

function TenderCard({ tender }) {
  const color = BADGE_COLORS[tender.industry_category] || BADGE_COLORS['General']
  const validUrl = isValidUrl(tender.source_url)
  return (
    <div className="card hover:border-gray-300 transition-colors">
      <div className="flex items-start justify-between gap-3 mb-2">
        <h3 className="text-sm font-medium text-gray-900 leading-snug">{tender.title}</h3>
        <span className={'badge flex-shrink-0 ' + color}>{tender.industry_category}</span>
      </div>
      {tender.description && tender.description.length > 20 && (
        <p className="text-xs text-gray-500 mb-2 line-clamp-2">{tender.description}</p>
      )}
      <div className="flex flex-wrap gap-x-4 gap-y-1 mb-3">
        {tender.issuing_body && (
          <span className="flex items-center gap-1 text-xs text-gray-500">
            <Building2 size={11} />{tender.issuing_body}
          </span>
        )}
        {tender.province && (
          <span className="flex items-center gap-1 text-xs text-gray-500">
            <MapPin size={11} />{tender.town ? tender.town + ', ' : ''}{tender.province}
          </span>
        )}
        <span className="flex items-center gap-1 text-xs text-gray-500">
          <Clock size={11} />{timeAgo(tender.scraped_at)}
        </span>
      </div>
      <div className="flex items-center justify-between pt-2 border-t border-gray-100">
        {tender.closing_date
          ? <span className="text-xs text-red-500">Closes {tender.closing_date}</span>
          : <span className="text-xs text-gray-400">{tender.source_site}</span>
        }
        {validUrl ? (
          <a href={tender.source_url} target="_blank" rel="noopener noreferrer"
            className="flex items-center gap-1 text-xs text-brand-600 hover:text-brand-800">
            View tender <ExternalLink size={11} />
          </a>
        ) : (
          <span className="flex items-center gap-1 text-xs text-gray-400">
            <AlertCircle size={11} /> Link unavailable
          </span>
        )}
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
  const [selIndustries, setSelIndustries] = useState([])
  const [selProvinces, setSelProvinces] = useState([])
  const [showFilters, setShowFilters] = useState(false)
  const lastScrapeRef = useRef(new Date().toISOString())
  const pollRef = useRef(null)

  const toggle = (list, setList, val) =>
    setList(list.includes(val) ? list.filter(v => v !== val) : [...list, val])

  const loadTenders = async (industries, provinces) => {
    setLoading(true)
    try {
      const res = await searchTenders({
        industries: industries || selIndustries,
        provinces: provinces || selProvinces,
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
    try {
      const res = await getLatest(lastScrapeRef.current, selIndustries, selProvinces)
      if (res.data.new_count > 0) {
        setPendingTenders(res.data.tenders)
        setNewCount(res.data.new_count)
        lastScrapeRef.current = new Date().toISOString()
      }
    } catch {}
  }

  const loadNewTenders = () => {
    setTenders(prev => [...pendingTenders, ...prev])
    setTotal(prev => prev + pendingTenders.length)
    setPendingTenders([])
    setNewCount(0)
    refreshUser()
  }

  const applyFilters = () => {
    loadTenders(selIndustries, selProvinces)
    setShowFilters(false)
  }

  const clearFilters = () => {
    setSelIndustries([])
    setSelProvinces([])
    loadTenders([], [])
    setShowFilters(false)
  }

  useEffect(() => {
    if (user) {
      const ind = user.industry_preferences || []
      const prov = user.province_preferences || []
      setSelIndustries(ind)
      setSelProvinces(prov)
      loadTenders(ind, prov)
    }
  }, [user?.email])

  useEffect(() => {
    pollRef.current = setInterval(pollForNew, 60000)
    return () => clearInterval(pollRef.current)
  }, [user, selIndustries, selProvinces])

  const activeFilters = selIndustries.length + selProvinces.length

  return (
    <div className="p-4 md:p-6 max-w-4xl mx-auto">
      <div className="flex items-start justify-between mb-4 md:mb-6">
        <div>
          <h1 className="text-base md:text-lg font-semibold text-gray-900">
            Good {new Date().getHours() < 12 ? 'morning' : 'afternoon'}, {user?.full_name?.split(' ')[0]}
          </h1>
          <p className="text-xs md:text-sm text-gray-500 mt-0.5">{total} tenders found</p>
        </div>
        <div className="flex items-center gap-2">
          <span className="hidden md:flex items-center gap-1.5 text-xs text-gray-400">
            <span className="w-1.5 h-1.5 rounded-full bg-brand-400 animate-pulse" />
            Live — 60s
          </span>
            className={'flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm border transition-colors ' +
              (showFilters || activeFilters > 0
                ? 'bg-brand-400 text-white border-brand-400'
                : 'bg-white text-gray-700 border-gray-200 hover:border-gray-300')}>
            Filters {activeFilters > 0 ? '(' + activeFilters + ')' : ''}
          </button>
          <button onClick={() => loadTenders(selIndustries, selProvinces)}
            className="p-1.5 rounded-lg hover:bg-gray-100 border border-gray-200">
            <RefreshCw size={14} />
          </button>
        </div>
      </div>

      {showFilters && (
        <div className="card mb-4 space-y-4">
          <div>
            <p className="text-xs font-medium text-gray-700 mb-2">Industries</p>
            <div className="flex flex-wrap gap-1.5">
              {INDUSTRIES.map(i => (
                <button key={i} onClick={() => toggle(selIndustries, setSelIndustries, i)}
                  className={'px-2.5 py-1 rounded-full text-xs border transition-colors ' +
                    (selIndustries.includes(i)
                      ? 'bg-brand-400 text-white border-brand-400'
                      : 'bg-white text-gray-600 border-gray-200 hover:border-brand-300')}>
                  {i}
                </button>
              ))}
            </div>
          </div>
          <div>
            <p className="text-xs font-medium text-gray-700 mb-2">Provinces</p>
            <div className="flex flex-wrap gap-1.5">
              {PROVINCES.map(p => (
                <button key={p} onClick={() => toggle(selProvinces, setSelProvinces, p)}
                  className={'px-2.5 py-1 rounded-full text-xs border transition-colors ' +
                    (selProvinces.includes(p)
                      ? 'bg-brand-400 text-white border-brand-400'
                      : 'bg-white text-gray-600 border-gray-200 hover:border-brand-300')}>
                  {p}
                </button>
              ))}
            </div>
          </div>
          <div className="flex justify-between pt-2 border-t border-gray-100">
            <button onClick={clearFilters} className="text-sm text-gray-500 hover:text-gray-700">Clear all</button>
            <button onClick={applyFilters} className="btn-primary py-1.5 px-4 text-sm">Apply filters</button>
          </div>
        </div>
      )}

      {newCount > 0 && (
        <div className="mb-4 flex items-center justify-between bg-brand-50 border border-brand-200 rounded-xl px-4 py-3">
          <span className="text-sm text-brand-600">{newCount} new tender{newCount > 1 ? 's' : ''} found</span>
          <button onClick={loadNewTenders} className="text-sm font-medium text-brand-600 hover:text-brand-800">Load</button>
        </div>
      )}

      <div className="grid grid-cols-2 md:grid-cols-4 gap-2 md:gap-3 mb-4 md:mb-6">
        {[
          { label: 'Total tenders', val: total, sub: 'matching filters' },
          { label: 'Credits', val: user?.credit_balance ?? 0, sub: 'R' + (((user?.credit_balance ?? 0) * 10).toFixed(0)) + ' value' },
          { label: 'Industries', val: user?.industry_preferences?.length ?? 0, sub: 'selected' },
          { label: 'Provinces', val: user?.province_preferences?.length ?? 0, sub: 'selected' },
        ].map(({ label, val, sub }) => (
          <div key={label} className="bg-gray-100 rounded-xl px-3 py-2.5 md:px-4 md:py-3">
            <p className="text-xs text-gray-500">{label}</p>
            <p className="text-xl md:text-2xl font-semibold text-gray-900 mt-0.5">{val}</p>
            <p className="text-xs text-gray-400">{sub}</p>
          </div>
        ))}
      </div>

      {loading ? (
        <div className="flex justify-center py-16">
          <div className="w-6 h-6 border-2 border-brand-400 border-t-transparent rounded-full animate-spin" />
        </div>
      ) : tenders.length === 0 ? (
        <div className="text-center py-16 text-gray-400 text-sm">
          No tenders found. Try adjusting your filters.
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-3">
          {tenders.map(t => <TenderCard key={t.id} tender={t} />)}
        </div>
      )}
    </div>
  )
}
