import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { searchTenders } from '../api/tenders'
import { Search as SearchIcon } from 'lucide-react'
import TenderCard from '../components/TenderCard'
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

export default function Search() {
  const { user, refreshUser, lastSearch, saveLastSearch } = useAuth()
  const navigate = useNavigate()
  const [keyword, setKeyword] = useState(lastSearch?.keyword || '')
  const [selIndustries, setSelIndustries] = useState(lastSearch?.industries?.length ? lastSearch.industries : (user?.industry_preferences || []))
  const [selProvinces, setSelProvinces] = useState(lastSearch?.provinces?.length ? lastSearch.provinces : (user?.province_preferences || []))
  const [results, setResults] = useState([])
  const [total, setTotal] = useState(0)
  const [charged, setCharged] = useState(0)
  const [loading, setLoading] = useState(false)
  const [searched, setSearched] = useState(false)
  const [page, setPage] = useState(1)

  const toggle = (list, setList, val) =>
    setList(list.includes(val) ? list.filter(v => v !== val) : [...list, val])

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
      saveLastSearch({ industries: selIndustries, provinces: selProvinces, keyword })
      if (res.data.credits_charged > 0) {
        toast.success(res.data.results.length + ' results — ' + res.data.credits_charged + ' credit(s) used')
      }
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Search failed')
    } finally {
      setLoading(false)
    }
  }

  const goToDashboard = () => {
    saveLastSearch({ industries: selIndustries, provinces: selProvinces, keyword })
    navigate('/dashboard')
  }

  return (
    <div className="p-4 md:p-8 lg:p-10 max-w-7xl mx-auto">
      <div className="flex items-start justify-between mb-2">
        <div>
          <h1 className="text-xl md:text-2xl font-semibold text-gray-900">Search tenders</h1>
          <p className="text-sm text-gray-500 mt-1">1 credit per result returned</p>
        </div>
        {searched && (
          <button onClick={goToDashboard} className="btn-primary text-sm py-2 px-4">
            View in Dashboard
          </button>
        )}
      </div>

      <div className="card p-4 md:p-6 mb-6 space-y-4 mt-4">
        <div className="relative">
          <SearchIcon size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input
            className="input pl-9 text-sm"
            placeholder="Keyword — e.g. road construction, CCTV, plumbing..."
            value={keyword}
            onChange={e => setKeyword(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleSearch(1)}
          />
        </div>

        <div>
          <p className="text-xs font-medium text-gray-700 mb-2">Industries</p>
          <div className="flex flex-wrap gap-1.5">
            {INDUSTRIES.map(i => (
              <button key={i} onClick={() => toggle(selIndustries, setSelIndustries, i)}
                className={'px-2.5 py-1 rounded-full text-xs border transition-colors ' +
                  (selIndustries.includes(i)
                    ? 'bg-brand-400 text-white border-brand-400'
                    : 'bg-white text-gray-600 border-gray-200 hover:border-brand-400')}>
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
                    : 'bg-white text-gray-600 border-gray-200 hover:border-brand-400')}>
                {p}
              </button>
            ))}
          </div>
        </div>

        <div className="flex items-center justify-between pt-2 border-t border-gray-100">
          <span className="text-xs text-gray-400">
            {selIndustries.length} industry · {selProvinces.length} province filters active
          </span>
          <button onClick={() => handleSearch(1)} disabled={loading} className="btn-primary text-sm py-2 px-5">
            {loading ? 'Searching...' : 'Search tenders'}
          </button>
        </div>
      </div>

      {searched && (
        <div className="mb-4 flex items-center justify-between">
          <p className="text-sm text-gray-700">
            {total} result{total !== 1 ? 's' : ''} found
            {charged > 0 && <span className="text-gray-400 ml-2">· {charged} credits used</span>}
          </p>
        </div>
      )}

      <div className="space-y-3">
        {results.map(t => <TenderCard key={t.id} tender={t} showBadgeColor={false} />)}
      </div>

      {total > 10 && (
        <div className="flex items-center justify-center gap-4 mt-6">
          <button onClick={() => handleSearch(page - 1)} disabled={page === 1} className="btn-secondary text-sm">Previous</button>
          <span className="text-sm text-gray-600">Page {page} of {Math.ceil(total / 10)}</span>
          <button onClick={() => handleSearch(page + 1)} disabled={page >= Math.ceil(total / 10)} className="btn-secondary text-sm">Next</button>
        </div>
      )}
    </div>
  )
}
