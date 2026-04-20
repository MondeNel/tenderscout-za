// src/pages/Search.jsx
import { useState, useMemo, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { searchTenders } from '../api/tenders'
import { getMunicipalities, getMunicipalitiesWithinRadius } from '../data/saLocations'
import LocationPicker from '../components/LocationPicker'
import TenderMap from '../components/TenderMap'
import TenderCard from '../components/TenderCard'
import {
  Search as SearchIcon, MapPin, Navigation, ChevronDown, ChevronUp,
  X, Map, List, SlidersHorizontal, Filter
} from 'lucide-react'
import toast from 'react-hot-toast'

const INDUSTRIES = [
  "Accounting, Banking & Legal",
  "Building & Trades",
  "Civil",
  "Cleaning & Facility Management",
  "Consultants",
  "Electrical & Automation",
  "Engineering Consultants",
  "General, Property & Auctions",
  "HR & Training",
  "IT & Telecoms",
  "Materials, Supply & Services",
  "Mechanical, Plant & Equipment",
  "Media & Marketing",
  "Medical & Healthcare",
  "Security, Access, Alarms & Fire",
  "Travel, Tourism & Hospitality",
]

const PROVINCES = [
  "Eastern Cape","Free State","Gauteng","KwaZulu-Natal",
  "Limpopo","Mpumalanga","North West","Northern Cape","Western Cape",
]

function ToggleChip({ label, selected, onClick, small = false }) {
  return (
    <button
      onClick={onClick}
      className={`${small ? 'px-2 py-1 text-xs' : 'px-2.5 py-1.5 text-xs'} rounded-full border transition-colors select-none ${
        selected
          ? 'bg-brand-400 text-white border-brand-400'
          : 'bg-white text-gray-600 border-gray-200 hover:border-brand-400 hover:bg-gray-50'
      }`}
    >
      {label}
    </button>
  )
}

export default function Search() {
  const { user, refreshUser, lastSearch, saveLastSearch } = useAuth()
  const navigate = useNavigate()

  // ── Filter state ───────────────────────────────────────────────────────────
  const [keyword,       setKeyword]      = useState(lastSearch?.keyword || '')
  const [selIndustries, setSelIndustries]= useState(lastSearch?.industries || user?.industry_preferences || [])
  const [selProvinces,  setSelProvinces] = useState(lastSearch?.provinces  || user?.province_preferences || [])
  const [selMunis,      setSelMunis]     = useState(lastSearch?.municipalities || [])

  // ── Location state ─────────────────────────────────────────────────────────
  const [useMyLocation,      setUseMyLocation]      = useState(false)
  const [showLocationPicker, setShowLocationPicker] = useState(false)
  const [locationValue,      setLocationValue]      = useState({
    location: null,
    radiusKm: user?.search_radius_km || 100,
  })

  const userSavedLocation = useMemo(() => {
    if (!user?.business_lat || !user?.business_lng) return null
    return { name: user.business_location, lat: user.business_lat, lng: user.business_lng }
  }, [user])

  const activeLocation = useMyLocation
    ? (locationValue.location || userSavedLocation)
    : locationValue.location
  const activeRadius = locationValue.radiusKm

  const nearbyMunis = useMemo(() => {
    if (!activeLocation || !useMyLocation) return getMunicipalities()
    return getMunicipalitiesWithinRadius(activeLocation.lat, activeLocation.lng, activeRadius)
  }, [activeLocation, activeRadius, useMyLocation])

  // ── View mode ──────────────────────────────────────────────────────────────
  const [viewMode, setViewMode] = useState('split') // 'list' | 'map' | 'split'

  // ── Results state ──────────────────────────────────────────────────────────
  const [results,  setResults]  = useState([])
  const [total,    setTotal]    = useState(0)
  const [charged,  setCharged]  = useState(0)
  const [loading,  setLoading]  = useState(false)
  const [searched, setSearched] = useState(false)
  const [page,     setPage]     = useState(1)

  // ── UI state ───────────────────────────────────────────────────────────────
  const [showMuniFilter,  setShowMuniFilter]  = useState(false)
  const [showFilters,     setShowFilters]     = useState(true)

  const toggle = (list, setList, val) =>
    setList(list.includes(val) ? list.filter(v => v !== val) : [...list, val])

  const clearFilters = () => {
    setKeyword('')
    setSelIndustries([])
    setSelProvinces([])
    setSelMunis([])
    setUseMyLocation(false)
    setLocationValue({ location: null, radiusKm: 100 })
  }

  const handleSearch = async (p = 1) => {
    setLoading(true)
    try {
      const payload = {
        industries:     selIndustries,
        provinces:      selProvinces,
        municipalities: selMunis,
        keyword:        keyword || undefined,
        page:           p,
        page_size:      20,
      }
      if (activeLocation) {
        payload.user_lat  = activeLocation.lat
        payload.user_lng  = activeLocation.lng
        payload.radius_km = activeRadius
      }
      const res = await searchTenders(payload)
      setResults(res.data.results)
      setTotal(res.data.total)
      setCharged(res.data.credits_charged)
      setPage(p)
      setSearched(true)
      await refreshUser()
      saveLastSearch({
        industries: selIndustries, provinces: selProvinces,
        municipalities: selMunis, keyword,
        userLat: activeLocation?.lat || null,
        userLng: activeLocation?.lng || null,
        radiusKm: activeRadius, useMyLocation,
      })
      if (res.data.results.length > 0) {
        toast.success(`${res.data.results.length} tenders found`)
        setShowFilters(false)
      } else {
        toast('No tenders found — try broadening your filters', { icon: '🔍' })
      }
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Search failed')
    } finally {
      setLoading(false)
    }
  }

  // When user clicks a map marker — pre-fill the municipality filter
  const handleMapAreaSelect = useCallback((district) => {
    setSelMunis(district.municipalities.slice(0, 3))
    if (!selProvinces.includes(district.province)) {
      setSelProvinces(prev => [...prev, district.province])
    }
    toast(`${district.district} selected — hit Search to filter`, { icon: '📍' })
  }, [selProvinces])

  const activeFilterCount = selIndustries.length + selProvinces.length + selMunis.length + (activeLocation ? 1 : 0)

  // Map location for the TenderMap component
  const mapUserLocation = activeLocation
    ? { lat: activeLocation.lat, lng: activeLocation.lng, name: activeLocation.name }
    : userSavedLocation
      ? { lat: userSavedLocation.lat, lng: userSavedLocation.lng, name: userSavedLocation.name }
      : null

  return (
    <div className="h-screen flex flex-col overflow-hidden">

      {/* Top bar */}
      <div className="flex-shrink-0 px-4 md:px-6 py-4 bg-white border-b border-gray-200">
        <div className="flex items-center justify-between gap-4 max-w-7xl mx-auto">
          <div>
            <h1 className="text-lg font-semibold text-gray-900">Search tenders</h1>
            {searched && (
              <p className="text-xs text-gray-400 mt-0.5">
                {total} results · {charged} credits used
              </p>
            )}
          </div>
          <div className="flex items-center gap-2">
            {/* View mode toggle */}
            <div className="flex items-center bg-gray-100 rounded-lg p-0.5 gap-0.5">
              {[
                { id: 'list', icon: List,    label: 'List' },
                { id: 'split', icon: SlidersHorizontal, label: 'Split' },
                { id: 'map',  icon: Map,     label: 'Map' },
              ].map(({ id, icon: Icon, label }) => (
                <button
                  key={id}
                  onClick={() => setViewMode(id)}
                  title={label}
                  className={`p-1.5 rounded-md transition-colors ${
                    viewMode === id ? 'bg-white shadow-sm text-gray-900' : 'text-gray-500 hover:text-gray-700'
                  }`}
                >
                  <Icon size={15} />
                </button>
              ))}
            </div>
            <button
              onClick={() => setShowFilters(v => !v)}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm border transition-colors ${
                showFilters ? 'bg-brand-50 border-brand-200 text-brand-700' : 'bg-white border-gray-200 text-gray-600 hover:border-gray-300'
              }`}
            >
              <Filter size={13} />
              Filters
              {activeFilterCount > 0 && (
                <span className="px-1.5 py-0.5 bg-brand-400 text-white text-xs rounded-full leading-none">
                  {activeFilterCount}
                </span>
              )}
            </button>
          </div>
        </div>
      </div>

      {/* Main content area */}
      <div className="flex-1 overflow-hidden flex">

        {/* Filter panel */}
        {showFilters && (
          <div className="w-80 flex-shrink-0 border-r border-gray-200 bg-white overflow-y-auto">
            <div className="p-4 space-y-4">

              {/* Keyword */}
              <div className="relative">
                <SearchIcon size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                <input
                  className="input pl-9 text-sm"
                  placeholder="Keyword search..."
                  value={keyword}
                  onChange={e => setKeyword(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && handleSearch(1)}
                />
              </div>

              {/* Industries */}
              <div>
                <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Industry</p>
                <div className="flex flex-wrap gap-1.5">
                  {INDUSTRIES.map(i => (
                    <ToggleChip key={i} label={i} selected={selIndustries.includes(i)}
                      onClick={() => toggle(selIndustries, setSelIndustries, i)} />
                  ))}
                </div>
              </div>

              {/* Provinces */}
              <div>
                <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Province</p>
                <div className="flex flex-wrap gap-1.5">
                  {PROVINCES.map(p => (
                    <ToggleChip key={p} label={p} selected={selProvinces.includes(p)}
                      onClick={() => toggle(selProvinces, setSelProvinces, p)} />
                  ))}
                </div>
              </div>

              {/* Location */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Location</p>
                  {userSavedLocation && (
                    <button
                      onClick={() => setUseMyLocation(v => !v)}
                      className={`flex items-center gap-1 text-xs px-2 py-1 rounded-full border transition-colors ${
                        useMyLocation ? 'bg-brand-400 text-white border-brand-400' : 'bg-white text-gray-500 border-gray-200'
                      }`}
                    >
                      <Navigation size={10} />
                      My location
                    </button>
                  )}
                </div>
                <button
                  onClick={() => setShowLocationPicker(v => !v)}
                  className="flex items-center gap-1 text-xs text-brand-600 hover:text-brand-800 mb-2"
                >
                  <MapPin size={11} />
                  {showLocationPicker ? 'Hide location picker' : 'Set location & radius'}
                  {showLocationPicker ? <ChevronUp size={10} /> : <ChevronDown size={10} />}
                </button>
                {showLocationPicker && (
                  <LocationPicker
                    value={locationValue}
                    onChange={setLocationValue}
                    showRadius compact
                  />
                )}
                {activeLocation && !showLocationPicker && (
                  <div className="flex items-center gap-2 text-xs bg-brand-50 border border-brand-200 rounded-lg px-2.5 py-2">
                    <MapPin size={10} className="text-brand-400" />
                    <span className="text-brand-700"><strong>{activeRadius}km</strong> from {activeLocation.name}</span>
                    <button onClick={() => { setLocationValue({ location: null, radiusKm: 100 }); setUseMyLocation(false) }}
                      className="ml-auto text-gray-400 hover:text-gray-600">
                      <X size={11} />
                    </button>
                  </div>
                )}
              </div>

              {/* Municipality filter */}
              <div>
                <button
                  onClick={() => setShowMuniFilter(v => !v)}
                  className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-gray-700"
                >
                  {showMuniFilter ? <ChevronUp size={11} /> : <ChevronDown size={11} />}
                  Municipality filter
                  {selMunis.length > 0 && (
                    <span className="px-1.5 py-0.5 bg-brand-100 text-brand-700 rounded-full text-xs">
                      {selMunis.length}
                    </span>
                  )}
                </button>
                {showMuniFilter && (
                  <div className="mt-2 max-h-32 overflow-y-auto flex flex-wrap gap-1.5">
                    {nearbyMunis.map(m => (
                      <ToggleChip key={m} label={m} small selected={selMunis.includes(m)}
                        onClick={() => toggle(selMunis, setSelMunis, m)} />
                    ))}
                  </div>
                )}
              </div>

              {/* Actions */}
              <div className="flex gap-2 pt-2 border-t border-gray-100 sticky bottom-0 bg-white pb-1">
                {activeFilterCount > 0 && (
                  <button onClick={clearFilters} className="btn-secondary text-xs py-2 flex-1">
                    Clear
                  </button>
                )}
                <button
                  onClick={() => handleSearch(1)}
                  disabled={loading}
                  className="btn-primary text-xs py-2 flex-1"
                >
                  {loading ? 'Searching...' : `Search${activeFilterCount > 0 ? ` (${activeFilterCount})` : ''}`}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Results + Map area */}
        <div className="flex-1 flex overflow-hidden">

          {/* Results list */}
          {(viewMode === 'list' || viewMode === 'split') && (
            <div className={`overflow-y-auto ${viewMode === 'split' ? 'w-1/2' : 'w-full'} border-r border-gray-200`}>
              <div className="p-4 space-y-3">
                {!searched && !loading && (
                  <div className="text-center py-16">
                    <SearchIcon size={32} className="mx-auto text-gray-300 mb-3" />
                    <p className="text-sm text-gray-400">Set your filters and click Search</p>
                    <p className="text-xs text-gray-300 mt-1">or click a map marker to explore tenders by area</p>
                  </div>
                )}

                {loading && (
                  <div className="flex justify-center py-16">
                    <div className="w-6 h-6 border-2 border-brand-400 border-t-transparent rounded-full animate-spin" />
                  </div>
                )}

                {searched && !loading && results.length === 0 && (
                  <div className="text-center py-16 text-gray-400 text-sm">
                    No tenders found. Try broadening your filters.
                  </div>
                )}

                {results.map(t => <TenderCard key={t.id} tender={t} showBadgeColor />)}

                {total > 20 && (
                  <div className="flex items-center justify-center gap-3 pt-2">
                    <button onClick={() => handleSearch(page - 1)} disabled={page === 1} className="btn-secondary text-xs py-1.5">
                      Previous
                    </button>
                    <span className="text-xs text-gray-500">Page {page} of {Math.ceil(total / 20)}</span>
                    <button onClick={() => handleSearch(page + 1)} disabled={page >= Math.ceil(total / 20)} className="btn-secondary text-xs py-1.5">
                      Next
                    </button>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Map */}
          {(viewMode === 'map' || viewMode === 'split') && (
            <div className={`${viewMode === 'split' ? 'w-1/2' : 'w-full'} relative`}>
              <TenderMap
                industries={selIndustries}
                provinces={selProvinces}
                userLocation={mapUserLocation}
                radiusKm={activeRadius}
                onSelectArea={handleMapAreaSelect}
                height="100%"
              />
            </div>
          )}
        </div>
      </div>
    </div>
  )
}