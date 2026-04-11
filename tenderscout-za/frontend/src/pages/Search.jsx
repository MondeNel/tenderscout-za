import { useState } from 'react'
import { useAuth } from '../context/AuthContext'
import { searchTenders } from '../api/tenders'
import { Search as SearchIcon, ExternalLink, MapPin, Building2, Clock } from 'lucide-react'
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

function timeAgo(dateStr) {
  const diff = Date.now() - new Date(dateStr).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  return `${Math.floor(hrs / 24)}d ago`
}

export default function Search() {
  const { user, refreshUser } = useAuth()
  const [keyword, setKeyword] = useState('')
  const [selIndustries, setSelIndustries] = useState(user?.industry_preferences || [])
  const [selProvinces, setSelProvinces] = useState(user?.province_preferences || [])
  const [results, setResults] = useState([])
  const [total, setTotal] = useState(0)
  const [charged, setCharged] = useState(0)
  const [loading, setLoading] = useState(false)
  const [searched, setSearched] = useState(false)
  const [page, setPage] = useState(1)

  const toggle = (list, setList, val) =>
    setList(list.includes(val) ? list.filter((v) => v !== val) : [...list, val])

  const handleSearch = async (p = 1) => {
    setLoading(true)
    try {
      const res = await searchTenders({
        industries: selIndustries,
        provinces: selProvinces,
        keyword: keyword || undefined,
        page: p,
        page_size: 10,
      })
      setResults(res.data.results)
      setTotal(res.data.total)
      setCharged(res.data.credits_charged)
      setPage(p)
      setSearched(true)
      await refreshUser()
      if (res.data.credits_charged > 0) {
        toast.success(`${res.data.results.length} results — ${res.data.credits_charged} credit${res.data.credits_charged > 1 ? 's' : ''} used`)
      }
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Search failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="p-8 md:p-10 lg:p-12 max-w-7xl mx-auto">
      <h1 className="text-2xl md:text-3xl font-semibold text-gray-900 mb-2">Search tenders</h1>
      <p className="text-base text-gray-500 mb-8">1 credit per result returned</p>

      <div className="card p-5 md:p-6 mb-6 space-y-5">
        <div className="relative">
          <SearchIcon size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input
            className="input pl-10 py-2.5 text-base"
            placeholder="Keyword — e.g. road construction, CCTV, plumbing..."
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch(1)}
          />
        </div>

        <div>
          <p className="text-sm font-medium text-gray-700 mb-2">Industries</p>
          <div className="flex flex-wrap gap-2">
            {INDUSTRIES.map((i) => (
              <button
                key={i}
                onClick={() => toggle(selIndustries, setSelIndustries, i)}
                className={`px-3 py-1.5 rounded-full text-sm border transition-all duration-150 ${
                  selIndustries.includes(i)
                    ? 'bg-brand-400 text-white border-brand-400 shadow-sm'
                    : 'bg-white text-gray-700 border-gray-200 hover:border-brand-400 hover:bg-gray-50'
                }`}
              >
                {i}
              </button>
            ))}
          </div>
        </div>

        <div>
          <p className="text-sm font-medium text-gray-700 mb-2">Provinces</p>
          <div className="flex flex-wrap gap-2">
            {PROVINCES.map((p) => (
              <button
                key={p}
                onClick={() => toggle(selProvinces, setSelProvinces, p)}
                className={`px-3 py-1.5 rounded-full text-sm border transition-all duration-150 ${
                  selProvinces.includes(p)
                    ? 'bg-brand-400 text-white border-brand-400 shadow-sm'
                    : 'bg-white text-gray-700 border-gray-200 hover:border-brand-400 hover:bg-gray-50'
                }`}
              >
                {p}
              </button>
            ))}
          </div>
        </div>

        <div className="flex items-center justify-between pt-2">
          <span className="text-sm text-gray-500">
            Estimated cost: {Math.max(selIndustries.length > 0 || selProvinces.length > 0 ? 10 : 0, 0)} credits max
          </span>
          <button onClick={() => handleSearch(1)} disabled={loading} className="btn-primary px-6 py-2.5 text-base">
            {loading ? 'Searching...' : 'Search tenders'}
          </button>
        </div>
      </div>

      {searched && (
        <div className="mb-5 flex items-center justify-between">
          <p className="text-base text-gray-700">
            {total} result{total !== 1 ? 's' : ''} found
            {charged > 0 && <span className="text-gray-500 ml-2">· {charged} credits used</span>}
          </p>
        </div>
      )}

      <div className="space-y-4">
        {results.map((t) => (
          <div key={t.id} className="card p-5 hover:border-gray-300 transition-all duration-200">
            <div className="flex items-start justify-between gap-4 mb-3">
              <h3 className="text-base font-semibold text-gray-900 leading-snug">{t.title}</h3>
              <span className="badge px-2.5 py-1 text-xs font-medium rounded-full bg-gray-100 text-gray-700 flex-shrink-0">
                {t.industry_category}
              </span>
            </div>
            <div className="flex flex-wrap gap-x-5 gap-y-1.5 mb-4">
              {t.issuing_body && (
                <span className="flex items-center gap-1.5 text-sm text-gray-500">
                  <Building2 size={14} />{t.issuing_body}
                </span>
              )}
              {t.province && (
                <span className="flex items-center gap-1.5 text-sm text-gray-500">
                  <MapPin size={14} />{t.town ? `${t.town}, ` : ''}{t.province}
                </span>
              )}
              <span className="flex items-center gap-1.5 text-sm text-gray-500">
                <Clock size={14} />{timeAgo(t.scraped_at)}
              </span>
            </div>
            <div className="flex items-center justify-between pt-3 border-t border-gray-100">
              {t.closing_date
                ? <span className="text-sm font-medium text-red-500">Closes {t.closing_date}</span>
                : <span className="text-sm text-gray-400">{t.source_site}</span>
              }
              <a href={t.source_url} target="_blank" rel="noopener noreferrer"
                className="flex items-center gap-1.5 text-sm font-medium text-brand-600 hover:text-brand-800">
                View tender <ExternalLink size={14} />
              </a>
            </div>
          </div>
        ))}
      </div>

      {total > 10 && (
        <div className="flex items-center justify-center gap-4 mt-8">
          <button onClick={() => handleSearch(page - 1)} disabled={page === 1} className="btn-secondary px-4 py-2 text-base">
            Previous
          </button>
          <span className="text-base text-gray-600">Page {page} of {Math.ceil(total / 10)}</span>
          <button onClick={() => handleSearch(page + 1)} disabled={page >= Math.ceil(total / 10)} className="btn-secondary px-4 py-2 text-base">
            Next
          </button>
        </div>
      )}
    </div>
  )
}