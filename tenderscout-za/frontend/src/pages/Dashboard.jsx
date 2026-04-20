// src/pages/Dashboard.jsx
import { useState, useEffect, useRef } from 'react'
import { useAuth } from '../context/AuthContext'
import { searchTenders, getLatest } from '../api/tenders'
import { RefreshCw, MapPin } from 'lucide-react'
import TenderCard from '../components/TenderCard'
import toast from 'react-hot-toast'

export default function Dashboard() {
  const { user, refreshUser, lastSearch } = useAuth()
  const [tenders,        setTenders]       = useState([])
  const [loading,        setLoading]       = useState(true)
  const [total,          setTotal]         = useState(0)
  const [newCount,       setNewCount]      = useState(0)
  const [pendingTenders, setPendingTenders] = useState([])
  const lastScrapeRef = useRef(new Date().toISOString())
  const pollRef       = useRef(null)
  const initialLoadDone = useRef(false)

  // Build search payload from lastSearch or user profile
  const getPayload = () => {
    const ind  = lastSearch?.industries?.length  ? lastSearch.industries  : (user?.industry_preferences  || [])
    const prov = lastSearch?.provinces?.length   ? lastSearch.provinces   : (user?.province_preferences  || [])
    const muni = lastSearch?.municipalities?.length ? lastSearch.municipalities : []

    const payload = { industries: ind, provinces: prov, municipalities: muni, page: 1, page_size: 20 }

    // Attach location if set in last search
    if (lastSearch?.userLat && lastSearch?.userLng && lastSearch?.useMyLocation) {
      payload.user_lat  = lastSearch.userLat
      payload.user_lng  = lastSearch.userLng
      payload.radius_km = lastSearch.radiusKm || 100
    } else if (user?.business_lat && user?.business_lng && !lastSearch?.industries?.length) {
      // First load with no search — use user's saved location
      payload.user_lat  = user.business_lat
      payload.user_lng  = user.business_lng
      payload.radius_km = user.search_radius_km || 100
    }

    return { payload, ind, prov, muni }
  }

  const loadTenders = async () => {
    setLoading(true)
    const { payload } = getPayload()
    try {
      const res = await searchTenders(payload)
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
    const { payload } = getPayload()
    try {
      const ind  = payload.industries  || []
      const prov = payload.provinces   || []
      const muni = payload.municipalities || []
      const res = await getLatest(lastScrapeRef.current, ind, prov, muni)
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

  useEffect(() => {
    if (user && !initialLoadDone.current) {
      initialLoadDone.current = true
      loadTenders()
    }
  }, [user])

  const lastSearchKey = JSON.stringify(lastSearch)
  const prevSearchKey = useRef(lastSearchKey)
  useEffect(() => {
    if (!initialLoadDone.current) return
    if (prevSearchKey.current !== lastSearchKey) {
      prevSearchKey.current = lastSearchKey
      loadTenders()
    }
  }, [lastSearchKey])

  useEffect(() => {
    pollRef.current = setInterval(pollForNew, 60000)
    return () => clearInterval(pollRef.current)
  }, [user, lastSearch])

  const { ind, prov, muni } = getPayload()
  const isFromSearch = lastSearch?.industries?.length > 0 || lastSearch?.provinces?.length > 0
  const hasLocation  = (lastSearch?.useMyLocation && lastSearch?.userLat) || (user?.business_lat && !isFromSearch)
  const locationName = lastSearch?.userLat
    ? `${lastSearch.radiusKm || 100}km radius`
    : user?.business_location
      ? `near ${user.business_location}`
      : null

  const greeting = new Date().getHours() < 12 ? 'Good morning' : new Date().getHours() < 17 ? 'Good afternoon' : 'Good evening'

  return (
    <div className="p-4 md:p-6 max-w-4xl mx-auto">
      {/* Header */}
      <div className="flex items-start justify-between mb-4 md:mb-6">
        <div>
          <h1 className="text-lg md:text-xl font-semibold text-gray-900">
            {greeting}, {user?.full_name?.split(' ')[0]}
          </h1>
          <p className="text-sm text-gray-500 mt-0.5">
            {total} tenders{isFromSearch ? ' — filtered by your last search' : ' matching your preferences'}
          </p>
          {hasLocation && locationName && (
            <div className="flex items-center gap-1 mt-1 text-xs text-brand-600">
              <MapPin size={11} />
              <span>{locationName}</span>
            </div>
          )}
        </div>
        <div className="flex items-center gap-2">
          <span className="hidden md:flex items-center gap-1.5 text-xs text-gray-400">
            <span className="w-1.5 h-1.5 rounded-full bg-brand-400 animate-pulse" />
            Live
          </span>
          <button onClick={loadTenders} className="p-1.5 rounded-lg hover:bg-gray-100 border border-gray-200">
            <RefreshCw size={14} />
          </button>
        </div>
      </div>

      {/* Active filter chips */}
      {(isFromSearch || muni.length > 0) && (
        <div className="mb-4 flex flex-wrap gap-1.5">
          {ind.map(i  => <span key={i}  className="px-2 py-0.5 bg-brand-50 text-brand-700 text-xs rounded-full border border-brand-200">{i}</span>)}
          {prov.map(p => <span key={p}  className="px-2 py-0.5 bg-gray-100 text-gray-600 text-xs rounded-full border border-gray-200">{p}</span>)}
          {muni.map(m => <span key={m}  className="px-2 py-0.5 bg-purple-50 text-purple-700 text-xs rounded-full border border-purple-200">{m}</span>)}
        </div>
      )}

      {/* New tenders notification */}
      {newCount > 0 && (
        <div className="mb-4 flex items-center justify-between bg-brand-50 border border-brand-200 rounded-xl px-4 py-3">
          <span className="text-sm text-brand-600">{newCount} new tender{newCount > 1 ? 's' : ''} found</span>
          <button onClick={loadNewTenders} className="text-sm font-medium text-brand-600 hover:text-brand-800">Load</button>
        </div>
      )}

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-2 md:gap-3 mb-4 md:mb-6">
        {[
          { label: 'Total tenders', val: total,                        sub: 'matching filters' },
          { label: 'Credits',       val: user?.credit_balance ?? 0,    sub: `R${(((user?.credit_balance ?? 0) * 10)).toFixed(0)} value` },
          { label: 'Industries',    val: ind.length,                   sub: 'active filters' },
          { label: 'Provinces',     val: prov.length,                  sub: 'active filters' },
        ].map(({ label, val, sub }) => (
          <div key={label} className="bg-gray-100 rounded-xl px-3 py-2.5 md:px-4 md:py-3">
            <p className="text-xs text-gray-500">{label}</p>
            <p className="text-2xl md:text-3xl font-semibold text-gray-900 mt-0.5">{val}</p>
            <p className="text-xs text-gray-400">{sub}</p>
          </div>
        ))}
      </div>

      {/* Tender list */}
      {loading ? (
        <div className="flex justify-center py-16">
          <div className="w-6 h-6 border-2 border-brand-400 border-t-transparent rounded-full animate-spin" />
        </div>
      ) : tenders.length === 0 ? (
        <div className="text-center py-16 text-gray-400 text-sm">
          No tenders found. Try adjusting your filters or location on the Search page.
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-3">
          {tenders.map(t => <TenderCard key={t.id} tender={t} showBadgeColor />)}
        </div>
      )}
    </div>
  )
}