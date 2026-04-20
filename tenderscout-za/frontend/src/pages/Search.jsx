// src/pages/Search.jsx
import { useState, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { searchTenders } from '../api/tenders'
import { getMunicipalities, getProvinces, getMunicipalitiesWithinRadius, getTownsWithinRadius } from '../data/saLocations'
import LocationPicker from '../components/LocationPicker'
import { Search as SearchIcon, MapPin, Navigation, ChevronDown, ChevronUp, X } from 'lucide-react'
import TenderCard from '../components/TenderCard'
import toast from 'react-hot-toast'

const INDUSTRIES = [
  'Security Services','Construction','Waste Management','Electrical Services',
  'Plumbing','ICT / Technology','Maintenance','Mining Services',
  'Cleaning Services','Catering','Consulting','Transport & Logistics','Healthcare','Landscaping',
]
const PROVINCES = getProvinces()

function ToggleChip({ label, selected, onClick, small = false }) {
  return (
    <button
      onClick={onClick}
      className={`${small ? 'px-2 py-1 text-xs' : 'px-2.5 py-1 text-sm'} rounded-full border transition-colors select-none ${
        selected
          ? 'bg-brand-400 text-white border-brand-400'
          : 'bg-white text-gray-600 border-gray-200 hover:border-brand-400'
      }`}
    >
      {label}
    </button>
  )
}

export default function Search() {
  const { user, refreshUser, lastSearch, saveLastSearch } = useAuth()
  const navigate = useNavigate()

  // ── Filter state ──────────────────────────────────────────────────────────
  const [keyword,        setKeyword]       = useState(lastSearch?.keyword || '')
  const [selIndustries,  setSelIndustries] = useState(lastSearch?.industries || user?.industry_preferences || [])
  const [selProvinces,   setSelProvinces]  = useState(lastSearch?.provinces  || user?.province_preferences || [])
  const [selMunicipalities, setSelMunicipalities] = useState(lastSearch?.municipalities || [])
  const [selTowns,       setSelTowns]      = useState(lastSearch?.towns || [])

  // ── Location-aware search ─────────────────────────────────────────────────
  const [useMyLocation,  setUseMyLocation] = useState(false)
  const [showLocationPicker, setShowLocationPicker] = useState(false)
  const [locationValue,  setLocationValue] = useState({
    location: null,
    radiusKm: user?.search_radius_km || 100,
  })

  // Resolve user's saved business location for "use my location" mode
  const userSavedLocation = useMemo(() => {
    if (!user?.business_lat || !user?.business_lng) return null
    return { name: user.business_location, lat: user.business_lat, lng: user.business_lng }
  }, [user])

  // Active location (from picker OR saved profile)
  const activeLocation = useMyLocation
    ? (locationValue.location || userSavedLocation)
    : locationValue.location

  const activeRadius = locationValue.radiusKm

  // Municipalities within radius (for smart municipality list)
  const nearbyMunicipalities = useMemo(() => {
    if (!activeLocation || !useMyLocation) return getMunicipalities()
    return getMunicipalitiesWithinRadius(activeLocation.lat, activeLocation.lng, activeRadius)
  }, [activeLocation, activeRadius, useMyLocation])

  // ── Results state ──────────────────────────────────────────────────────────
  const [results,  setResults]  = useState([])
  const [total,    setTotal]    = useState(0)
  const [charged,  setCharged]  = useState(0)
  const [loading,  setLoading]  = useState(false)
  const [searched, setSearched] = useState(false)
  const [page,     setPage]     = useState(1)

  // ── UI toggles ─────────────────────────────────────────────────────────────
  const [showMuniFilter, setShowMuniFilter] = useState(false)

  const toggle = (list, setList, val) =>
    setList(list.includes(val) ? list.filter(v => v !== val) : [...list, val])

  const clearFilters = () => {
    setKeyword('')
    setSelIndustries([])
    setSelProvinces([])
    setSelMunicipalities([])
    setSelTowns([])
    setUseMyLocation(false)
    setLocationValue({ location: null, radiusKm: 100 })
  }

  const handleSearch = async (p = 1) => {
    setLoading(true)
    try {
      const payload = {
        industries:     selIndustries,
        provinces:      selProvinces,
        municipalities: selMunicipalities,
        towns:          selTowns,
        keyword:        keyword || undefined,
        page:           p,
        page_size:      10,
      }

      // Attach location params if location-aware search is active
      if (activeLocation && (useMyLocation || locationValue.location)) {
        payload.user_lat   = activeLocation.lat
        payload.user_lng   = activeLocation.lng
        payload.radius_km  = activeRadius
      }

      const res = await searchTenders(payload)
      setResults(res.data.results)
      setTotal(res.data.total)
      setCharged(res.data.credits_charged)
      setPage(p)
      setSearched(true)
      await refreshUser()

      saveLastSearch({
        industries:     selIndustries,
        provinces:      selProvinces,
        municipalities: selMunicipalities,
        towns:          selTowns,
        keyword,
        userLat:        activeLocation?.lat   || null,
        userLng:        activeLocation?.lng   || null,
        radiusKm:       activeRadius,
        useMyLocation,
      })

      if (res.data.credits_charged > 0) {
        toast.success(`${res.data.results.length} results — ${res.data.credits_charged} credit(s) used`)
      }
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Search failed')
    } finally {
      setLoading(false)
    }
  }

  const activeFilterCount = selIndustries.length + selProvinces.length + selMunicipalities.length + selTowns.length + (useMyLocation || locationValue.location ? 1 : 0)

  return (
    <div className="p-4 md:p-6 lg:p-8 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-start justify-between mb-4">
        <div>
          <h1 className="text-xl md:text-2xl font-semibold text-gray-900">Search tenders</h1>
          <p className="text-sm text-gray-500 mt-0.5">1 credit per result returned</p>
        </div>
        {searched && (
          <button onClick={() => navigate('/dashboard')} className="btn-primary text-sm py-2 px-4">
            View in Dashboard
          </button>
        )}
      </div>

      {/* Filter card */}
      <div className="card p-4 md:p-5 mb-5 space-y-4">

        {/* Keyword */}
        <div className="relative">
          <SearchIcon size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input
            className="input pl-9 text-sm"
            placeholder="Keyword — e.g. road construction, CCTV, plumbing..."
            value={keyword}
            onChange={e => setKeyword(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleSearch(1)}
          />
        </div>

        {/* Industries */}
        <div>
          <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2">Industries</p>
          <div className="flex flex-wrap gap-1.5">
            {INDUSTRIES.map(i => (
              <ToggleChip key={i} label={i} selected={selIndustries.includes(i)} onClick={() => toggle(selIndustries, setSelIndustries, i)} />
            ))}
          </div>
        </div>

        {/* Provinces */}
        <div>
          <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2">Provinces</p>
          <div className="flex flex-wrap gap-1.5">
            {PROVINCES.map(p => (
              <ToggleChip key={p} label={p} selected={selProvinces.includes(p)} onClick={() => toggle(selProvinces, setSelProvinces, p)} />
            ))}
          </div>
        </div>

        {/* Location-aware search */}
        <div className="border-t border-gray-100 pt-4 space-y-3">
          <div className="flex items-center justify-between">
            <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">Location search</p>
            <div className="flex items-center gap-3">
              {/* "Use my location" toggle */}
              {userSavedLocation && (
                <button
                  onClick={() => setUseMyLocation(v => !v)}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs border transition-all ${
                    useMyLocation
                      ? 'bg-brand-400 text-white border-brand-400'
                      : 'bg-white text-gray-600 border-gray-200 hover:border-brand-400'
                  }`}
                >
                  <Navigation size={11} />
                  {useMyLocation ? `${userSavedLocation.name} (${activeRadius}km)` : 'Use my location'}
                </button>
              )}
              {/* Toggle picker */}
              <button
                onClick={() => setShowLocationPicker(v => !v)}
                className="flex items-center gap-1 text-xs text-gray-500 hover:text-brand-600"
              >
                <MapPin size={12} />
                {showLocationPicker ? 'Hide' : 'Set location'}
                {showLocationPicker ? <ChevronUp size={11} /> : <ChevronDown size={11} />}
              </button>
            </div>
          </div>

          {showLocationPicker && (
            <div className="bg-gray-50 rounded-xl p-4 border border-gray-200">
              <LocationPicker
                value={locationValue}
                onChange={setLocationValue}
                showRadius={true}
                showPreview={true}
                compact={true}
              />
            </div>
          )}

          {activeLocation && !showLocationPicker && (
            <div className="flex items-center gap-2 text-xs text-brand-600 bg-brand-50 border border-brand-200 rounded-lg px-3 py-2">
              <MapPin size={11} />
              <span>Searching within <strong>{activeRadius}km</strong> of <strong>{activeLocation.name}</strong></span>
              <button onClick={() => { setLocationValue({ location: null, radiusKm: 100 }); setUseMyLocation(false) }} className="ml-auto text-gray-400 hover:text-gray-600">
                <X size={12} />
              </button>
            </div>
          )}
        </div>

        {/* Municipality filter (collapsible) */}
        <div className="border-t border-gray-100 pt-3">
          <button
            onClick={() => setShowMuniFilter(v => !v)}
            className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-gray-700"
          >
            {showMuniFilter ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
            Municipality / town filters
            {selMunicipalities.length + selTowns.length > 0 && (
              <span className="px-1.5 py-0.5 bg-brand-100 text-brand-700 rounded-full">
                {selMunicipalities.length + selTowns.length}
              </span>
            )}
          </button>

          {showMuniFilter && (
            <div className="mt-3 space-y-3">
              <div>
                <p className="text-xs text-gray-400 mb-1.5">Municipalities</p>
                <div className="flex flex-wrap gap-1.5 max-h-28 overflow-y-auto">
                  {nearbyMunicipalities.map(m => (
                    <ToggleChip key={m} label={m} selected={selMunicipalities.includes(m)} onClick={() => toggle(selMunicipalities, setSelMunicipalities, m)} small />
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Footer row */}
        <div className="flex items-center justify-between pt-2 border-t border-gray-100">
          <div className="flex items-center gap-3">
            <span className="text-xs text-gray-400">
              {activeFilterCount} filter{activeFilterCount !== 1 ? 's' : ''} active
            </span>
            {activeFilterCount > 0 && (
              <button onClick={clearFilters} className="text-xs text-gray-400 hover:text-gray-600 underline">
                Clear all
              </button>
            )}
          </div>
          <button
            onClick={() => handleSearch(1)}
            disabled={loading}
            className="btn-primary text-sm py-2 px-5"
          >
            {loading ? 'Searching...' : 'Search tenders'}
          </button>
        </div>
      </div>

      {/* Results summary */}
      {searched && (
        <div className="mb-4 flex items-center justify-between">
          <p className="text-sm text-gray-700">
            {total} result{total !== 1 ? 's' : ''} found
            {charged > 0 && <span className="text-gray-400 ml-2">· {charged} credits used</span>}
          </p>
        </div>
      )}

      {/* Results */}
      <div className="space-y-3">
        {results.map(t => <TenderCard key={t.id} tender={t} showBadgeColor={false} />)}
      </div>

      {/* Pagination */}
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