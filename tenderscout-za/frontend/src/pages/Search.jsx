/**
 * File: src/pages/Search.jsx
 * Purpose: Advanced Tender Search Page with Interactive Map
 * 
 * This is the most comprehensive page in the application, providing:
 *   - Multi-filter search (industries, provinces, municipalities, keyword)
 *   - Location-based search with radius control
 *   - Interactive Leaflet map with tender count markers
 *   - Real-time search results with pagination
 *   - Credit tracking (search consumes credits)
 *   - Mobile-responsive tabs (filters, results, map)
 * 
 * Features:
 *   - Click province → map zooms to that province
 *   - Click map marker → see tenders in that district
 *   - "Search all in district" button from popup
 *   - Save search context to AuthContext for Dashboard
 *   - Free map data fetch (no credits consumed)
 * 
 * Layout (Desktop):
 *   ┌──────────┬─────────────────┬─────────────────┐
 *   │ Filters  │    Results      │      Map        │
 *   │ (272px)  │   (380px)       │   (remaining)   │
 *   └──────────┴─────────────────┴─────────────────┘
 * 
 * Layout (Mobile):
 *   Tabs: [Filters] [Results] [Map]
 */

import { useState, useMemo, useCallback, useEffect, useRef } from 'react'
import { useAuth } from '../context/AuthContext'
import { searchTenders } from '../api/tenders'
import { getMunicipalities, SA_LOCATIONS } from '../data/saLocations'
import TenderCard from '../components/TenderCard'
import {
  Search as SearchIcon, X, Filter, Navigation,
  ChevronDown, ChevronUp, Loader, TrendingUp, ExternalLink,
  Eye, EyeOff, MapPin,
} from 'lucide-react'
import { MapContainer, TileLayer, Marker, Popup, useMap, Circle } from 'react-leaflet'
import L from 'leaflet'
import toast from 'react-hot-toast'
import 'leaflet/dist/leaflet.css'

// =============================================================================
// LEAFLET ICON CONFIGURATION
// =============================================================================
delete L.Icon.Default.prototype._getIconUrl
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png',
  iconUrl:       'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png',
  shadowUrl:     'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
})

// =============================================================================
// MAP CONSTANTS
// =============================================================================

const SA_BOUNDS  = [[-35.5, 16.2], [-22.0, 33.0]]  // South Africa bounding box
const SA_CENTER  = [-29.0, 25.0]                    // Center of South Africa
const SA_ZOOM    = 5                                 // Default zoom (whole country)
const PROV_ZOOM  = 7                                 // Zoom when province selected

// =============================================================================
// FILTER OPTIONS
// =============================================================================

const INDUSTRIES = [
  "Accounting, Banking & Legal","Building & Trades","Civil",
  "Cleaning & Facility Management","Consultants","Electrical & Automation",
  "Engineering Consultants","General, Property & Auctions","HR & Training",
  "IT & Telecoms","Materials, Supply & Services","Mechanical, Plant & Equipment",
  "Media & Marketing","Medical & Healthcare","Security, Access, Alarms & Fire",
  "Travel, Tourism & Hospitality",
]

const PROVINCES = [
  "Eastern Cape","Free State","Gauteng","KwaZulu-Natal",
  "Limpopo","Mpumalanga","North West","Northern Cape","Western Cape",
]

// Province center coordinates for map fly-to
const PROVINCE_CENTERS = {
  "Gauteng":[-26.27,28.11],"Western Cape":[-33.23,21.86],
  "KwaZulu-Natal":[-28.53,30.90],"Eastern Cape":[-32.30,26.42],
  "Free State":[-28.45,26.80],"Limpopo":[-23.40,29.42],
  "Mpumalanga":[-25.57,30.53],"North West":[-26.66,25.28],
  "Northern Cape":[-29.05,22.94],
}

// =============================================================================
// HELPER: Create custom marker icon with tender count
// =============================================================================
function makeIcon(count, sel = false) {
  const s  = count > 100 ? 52 : count > 50 ? 46 : count > 20 ? 40 : count > 5 ? 34 : 28
  const bg = sel ? '#085041' : count > 100 ? '#1D9E75' : count > 50 ? '#2aa882'
           : count > 20 ? '#5DCAA5' : count > 5 ? '#9FE1CB' : '#c8f0e3'
  const fg = (count > 10 || sel) ? '#fff' : '#085041'
  return L.divIcon({
    className: '',
    html: `<div style="width:${s}px;height:${s}px;background:${bg};
      border:2.5px solid rgba(255,255,255,.9);border-radius:50%;
      display:flex;align-items:center;justify-content:center;
      box-shadow:0 2px 10px rgba(0,0,0,.28);cursor:pointer;
      font-family:system-ui,sans-serif;font-weight:700;
      font-size:${s > 38 ? 12 : 10}px;color:${fg};">
      ${count > 999 ? '999+' : count}
    </div>`,
    iconSize: [s, s], iconAnchor: [s/2, s/2], popupAnchor: [0, -(s/2) - 4],
  })
}

// =============================================================================
// HELPER: Map fly-to controller
// =============================================================================
function FlyCtrl({ target }) {
  const map = useMap()
  const prev = useRef(null)
  useEffect(() => {
    if (target && target.key !== prev.current) {
      prev.current = target.key
      map.flyTo(target.c, target.z, { duration: 0.85 })
    }
  }, [target?.key])
  return null
}

// =============================================================================
// HELPER: Toggle chip component
// =============================================================================
function Chip({ label, selected, onClick, small = false }) {
  return (
    <button onClick={onClick}
      className={`${small ? 'px-2 py-1 text-xs' : 'px-2.5 py-1.5 text-xs'}
        rounded-full border transition-colors select-none whitespace-nowrap
        ${selected
          ? 'bg-brand-400 text-white border-brand-400'
          : 'bg-white text-gray-600 border-gray-200 hover:border-brand-400 hover:bg-gray-50'
        }`}
    >{label}</button>
  )
}

// =============================================================================
// MAIN COMPONENT
// =============================================================================
export default function Search() {
  const { user, refreshUser, lastSearch, saveLastSearch } = useAuth()

  // ===========================================================================
  // FILTER STATE
  // ===========================================================================
  const [keyword,   setKeyword]   = useState(lastSearch?.keyword || '')
  const [selInd,    setSelInd]    = useState(lastSearch?.industries     || user?.industry_preferences || [])
  const [selProv,   setSelProv]   = useState(lastSearch?.provinces      || user?.province_preferences || [])
  const [selMunis,  setSelMunis]  = useState(lastSearch?.municipalities || [])
  const [showMunis, setShowMunis] = useState(false)

  // ===========================================================================
  // LOCATION STATE
  // ===========================================================================
  const [useMyLoc, setUseMyLoc] = useState(false)
  const [radiusKm, setRadiusKm] = useState(user?.search_radius_km || 100)
  const userLoc = useMemo(() => {
    if (!user?.business_lat) return null
    return { lat: user.business_lat, lng: user.business_lng, name: user.business_location || 'My location' }
  }, [user])

  // ===========================================================================
  // MAP STATE
  // ===========================================================================
  const [showMap,    setShowMap]    = useState(true)
  const [flyTarget,  setFlyTarget]  = useState(null)
  const [mapData,    setMapData]    = useState({ districts: [], total: 0 })
  const [mapLoading, setMapLoading] = useState(false)
  const [activePop,  setActivePop]  = useState(null)  // Currently open popup

  // ===========================================================================
  // RESULTS STATE
  // ===========================================================================
  const [results,   setResults]   = useState([])
  const [total,     setTotal]     = useState(0)
  const [charged,   setCharged]   = useState(0)
  const [loading,   setLoading]   = useState(false)
  const [searched,  setSearched]  = useState(false)
  const [page,      setPage]      = useState(1)

  // ===========================================================================
  // UI STATE
  // ===========================================================================
  const [showFilters, setShowFilters] = useState(true)
  const [mobileTab,   setMobileTab]   = useState('filters')

  // ===========================================================================
  // UTILITIES
  // ===========================================================================
  const tog = (list, set, v) =>
    set(list.includes(v) ? list.filter(x => x !== v) : [...list, v])

  const filterCount = selInd.length + selProv.length + selMunis.length + (useMyLoc && userLoc ? 1 : 0)

  // ===========================================================================
  // PROVINCE TOGGLE WITH MAP FLY-TO
  // ===========================================================================
  const handleProvToggle = (prov) => {
    const adding = !selProv.includes(prov)
    setSelProv(prev => adding ? [...prev, prov] : prev.filter(v => v !== prov))
    const c = PROVINCE_CENTERS[prov]
    if (adding && c) setFlyTarget({ c, z: PROV_ZOOM, key: prov + Date.now() })
    else setFlyTarget({ c: SA_CENTER, z: SA_ZOOM, key: 'sa' + Date.now() })
  }

  // ===========================================================================
  // FETCH MAP DATA (Free - no credits consumed)
  // ===========================================================================
  const fetchMapData = useCallback(async () => {
    setMapLoading(true)
    try {
      const res = await searchTenders({
        industries: selInd,
        provinces:  selProv,
        page: 1,
        page_size: 500,
      })

      const dm = {}
      for (const t of res.data.results) {
        let placed = false
        for (const [prov, pD] of Object.entries(SA_LOCATIONS)) {
          if (t.province && t.province !== prov) continue
          for (const [dist, dD] of Object.entries(pD.districts)) {
            const inMuni = dD.municipalities.some(m =>
              t.municipality &&
              m.toLowerCase().split(' ')[0] === t.municipality.toLowerCase().split(' ')[0]
            )
            const byProv = t.province === prov && !t.municipality
            if (inMuni || byProv) {
              const k = `${prov}::${dist}`
              if (!dm[k]) dm[k] = { key: k, province: prov, district: dist, lat: dD.lat, lng: dD.lng, municipalities: dD.municipalities, tenders: [] }
              dm[k].tenders.push(t)
              placed = true
              break
            }
          }
          if (placed) break
        }
        if (!placed && t.province && SA_LOCATIONS[t.province]) {
          const pD = SA_LOCATIONS[t.province]
          const fd = Object.keys(pD.districts)[0]
          const dD = pD.districts[fd]
          const k  = `${t.province}::${fd}`
          if (!dm[k]) dm[k] = { key: k, province: t.province, district: fd, lat: dD.lat, lng: dD.lng, municipalities: dD.municipalities, tenders: [] }
          dm[k].tenders.push(t)
        }
      }
      setMapData({ districts: Object.values(dm), total: res.data.total })
    } catch (e) {
      console.warn('Map fetch error:', e)
    } finally {
      setMapLoading(false)
    }
  }, [JSON.stringify(selInd), JSON.stringify(selProv)])

  useEffect(() => { fetchMapData() }, [fetchMapData])

  // ===========================================================================
  // AUTO-LOAD ON MOUNT
  // ===========================================================================
  useEffect(() => {
    if (!user) return
    const indPref  = user.industry_preferences  || []
    const provPref = user.province_preferences   || []
    doSearch(1, indPref, provPref, [], '')
  }, [user?.id])

  // ===========================================================================
  // SEARCH EXECUTION
  // ===========================================================================
  const doSearch = async (p = 1, industries = selInd, provinces = selProv, munis = selMunis, kw = keyword) => {
    setLoading(true)
    try {
      const payload = {
        industries, provinces, municipalities: munis,
        keyword: kw || undefined,
        page: p, page_size: 20,
      }
      if (useMyLoc && userLoc) {
        payload.user_lat  = userLoc.lat
        payload.user_lng  = userLoc.lng
        payload.radius_km = radiusKm
      }
      const res = await searchTenders(payload)
      setResults(res.data.results)
      setTotal(res.data.total)
      setCharged(res.data.credits_charged || 0)
      setPage(p)
      setSearched(true)
      await refreshUser()
      saveLastSearch({ industries, provinces, municipalities: munis, keyword: kw })

      if (res.data.results.length === 0 && (industries.length || provinces.length || munis.length || kw)) {
        toast('No tenders found — try broader filters', { icon: '🔍' })
      } else if (res.data.results.length > 0 && p === 1 && (industries.length || provinces.length || munis.length || kw)) {
        toast.success(`${res.data.total} tenders found`)
        setMobileTab('results')
      }
    } catch (err) {
      if (err.response?.status === 402) toast.error('Not enough credits — please top up')
      else toast.error(err.response?.data?.detail || 'Search failed')
    } finally {
      setLoading(false)
    }
  }

  const handleSearch = () => doSearch(1)

  const clearFilters = () => {
    setKeyword(''); setSelInd([]); setSelProv([]); setSelMunis([])
    setUseMyLoc(false)
    setFlyTarget({ c: SA_CENTER, z: SA_ZOOM, key: 'clear' + Date.now() })
    doSearch(1, [], [], [], '')
  }

  // ===========================================================================
  // COMPUTED VALUES
  // ===========================================================================
  const muniList = useMemo(() =>
    selProv.length ? selProv.flatMap(p => getMunicipalities(p)) : getMunicipalities()
  , [selProv])

  const visibleDistricts = useMemo(() =>
    mapData.districts.filter(d =>
      (selProv.length ? selProv.includes(d.province) : true) && d.tenders.length > 0
    )
  , [mapData, selProv])

  // ===========================================================================
  // MAP COMPONENT
  // ===========================================================================
  const TheMap = ({ scrollWheel = true }) => (
    <div className="relative w-full h-full">
      <div className="absolute top-3 left-3 z-10 pointer-events-none flex gap-2">
        <div className="bg-white rounded-full px-3 py-1.5 shadow border border-gray-200 flex items-center gap-1.5">
          <TrendingUp size={12} className="text-brand-400" />
          <span className="text-xs font-semibold text-gray-700">
            {mapData.total} tender{mapData.total !== 1 ? 's' : ''}
          </span>
          {mapLoading && <Loader size={11} className="animate-spin text-gray-300 ml-1" />}
        </div>
      </div>

      <button onClick={() => setShowMap(false)}
        className="absolute top-3 right-3 z-10 bg-white rounded-full px-3 py-1.5 shadow border border-gray-200 flex items-center gap-1.5 text-xs text-gray-500 hover:text-brand-600 hover:border-brand-300 transition-colors">
        <EyeOff size={11} /> Hide map
      </button>

      <div className="absolute bottom-8 right-3 z-10 bg-white rounded-xl px-3 py-2 shadow border border-gray-200">
        <p className="text-xs text-gray-400 mb-1.5 font-medium">Tenders</p>
        {[['#c8f0e3','1–5'],['#9FE1CB','6–20'],['#5DCAA5','21–50'],['#2aa882','51–100'],['#1D9E75','100+']].map(([c,l]) => (
          <div key={l} className="flex items-center gap-1.5 mb-0.5">
            <div className="w-3 h-3 rounded-full" style={{ background: c }} />
            <span className="text-xs text-gray-500">{l}</span>
          </div>
        ))}
      </div>

      <MapContainer
        center={SA_CENTER} zoom={SA_ZOOM}
        maxBounds={SA_BOUNDS} maxBoundsViscosity={1.0}
        minZoom={5} maxZoom={14}
        style={{ height: '100%', width: '100%' }}
        scrollWheelZoom={scrollWheel}
      >
        <TileLayer
          attribution='© <a href="https://www.openstreetmap.org">OpenStreetMap</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          bounds={SA_BOUNDS}
        />
        <FlyCtrl target={flyTarget} />

        {useMyLoc && userLoc && (
          <>
            <Marker position={[userLoc.lat, userLoc.lng]}
              icon={L.divIcon({
                className: '',
                html: `<div style="width:14px;height:14px;background:#1D9E75;border:3px solid white;border-radius:50%;box-shadow:0 0 0 4px rgba(29,158,117,.2)"></div>`,
                iconSize: [14,14], iconAnchor: [7,7],
              })}>
              <Popup><strong>{userLoc.name}</strong><br />Your business location</Popup>
            </Marker>
            <Circle center={[userLoc.lat, userLoc.lng]} radius={radiusKm * 1000}
              pathOptions={{ color: '#1D9E75', fillColor: '#1D9E75', fillOpacity: .05, weight: 1.5, dashArray: '5 5' }} />
          </>
        )}

        {visibleDistricts.map(d => {
          const count = d.tenders.length
          const isSel = activePop === d.key
          return (
            <Marker key={d.key} position={[d.lat, d.lng]} icon={makeIcon(count, isSel)}
              eventHandlers={{ click: () => setActivePop(d.key) }}>
              <Popup onClose={() => setActivePop(null)} maxWidth={300} minWidth={250}>
                <div>
                  <div className="flex items-center justify-between mb-2 pb-2 border-b border-gray-100">
                    <div>
                      <p className="text-sm font-semibold text-gray-900">{d.district}</p>
                      <p className="text-xs text-gray-400">{d.province}</p>
                    </div>
                    <span className="px-2 py-0.5 bg-brand-50 text-brand-700 text-xs font-bold rounded-full border border-brand-200">
                      {count} tender{count !== 1 ? 's' : ''}
                    </span>
                  </div>
                  <div className="space-y-1.5 max-h-52 overflow-y-auto">
                    {d.tenders.slice(0, 5).map((t, i) => (
                      <div key={i} className="flex items-start gap-2 p-2 bg-gray-50 rounded-lg">
                        <div className="flex-1 min-w-0">
                          <p className="text-xs font-medium text-gray-800 leading-snug" style={{ display:'-webkit-box', WebkitLineClamp:2, WebkitBoxOrient:'vertical', overflow:'hidden' }}>
                            {t.title}
                          </p>
                          <div className="flex items-center gap-1 mt-0.5 flex-wrap">
                            {t.issuing_body && <span className="text-xs text-gray-400 truncate max-w-[120px]">{t.issuing_body}</span>}
                            {t.closing_date && <span className="text-xs text-red-500 flex-shrink-0">· {t.closing_date}</span>}
                          </div>
                        </div>
                        {(t.document_url || t.source_url) && (
                          <a href={t.document_url || t.source_url} target="_blank" rel="noopener noreferrer"
                            className="flex-shrink-0 text-brand-500 hover:text-brand-700 mt-0.5"
                            onClick={e => e.stopPropagation()}>
                            <ExternalLink size={11} />
                          </a>
                        )}
                      </div>
                    ))}
                  </div>
                  <button
                    onClick={() => {
                      const munis = d.municipalities.slice(0, 3)
                      setSelMunis(munis)
                      if (!selProv.includes(d.province)) setSelProv(p => [...p, d.province])
                      doSearch(1, selInd, selProv.includes(d.province) ? selProv : [...selProv, d.province], munis, keyword)
                    }}
                    className="mt-2 w-full py-1.5 text-xs bg-brand-400 hover:bg-brand-600 text-white rounded-lg font-medium transition-colors">
                    Search all {count} tenders in {d.district} →
                  </button>
                  <p className="text-xs text-gray-400 mt-1.5">
                    {d.municipalities.slice(0, 3).join(' · ')}
                    {d.municipalities.length > 3 ? ` +${d.municipalities.length - 3}` : ''}
                  </p>
                </div>
              </Popup>
            </Marker>
          )
        })}
      </MapContainer>
    </div>
  )

  // ===========================================================================
  // FILTERS PANEL
  // ===========================================================================
  const FiltersPanel = () => (
    <div className="h-full overflow-y-auto bg-white">
      <div className="p-4 space-y-5">
        <div className="relative">
          <SearchIcon size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input className="input pl-9 text-sm" placeholder="Keyword..."
            value={keyword} onChange={e => setKeyword(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleSearch()} />
        </div>

        <div>
          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">Industry</p>
          <div className="flex flex-wrap gap-1.5">
            {INDUSTRIES.map(i => <Chip key={i} label={i} selected={selInd.includes(i)} onClick={() => tog(selInd, setSelInd, i)} />)}
          </div>
        </div>

        <div>
          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-1">
            Province <span className="font-normal text-gray-300 normal-case">(click to zoom map)</span>
          </p>
          <div className="flex flex-wrap gap-1.5">
            {PROVINCES.map(p => <Chip key={p} label={p} selected={selProv.includes(p)} onClick={() => handleProvToggle(p)} />)}
          </div>
        </div>

        {userLoc && (
          <div>
            <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">Location</p>
            <button onClick={() => {
              const n = !useMyLoc
              setUseMyLoc(n)
              if (n) setFlyTarget({ c: [userLoc.lat, userLoc.lng], z: 8, key: 'loc' + Date.now() })
            }} className={`flex items-center gap-1.5 px-3 py-2 rounded-lg border text-xs w-full transition-colors ${
              useMyLoc ? 'bg-brand-50 border-brand-300 text-brand-700' : 'border-gray-200 text-gray-600 hover:border-brand-300'
            }`}>
              <Navigation size={12} />
              {useMyLoc ? `✓ ${userLoc.name}` : `Use my business location (${userLoc.name})`}
            </button>
            {useMyLoc && (
              <div className="mt-2 px-1">
                <div className="flex justify-between text-xs text-gray-500 mb-1">
                  <span>Radius</span>
                  <span className="font-semibold text-brand-600">{radiusKm}km</span>
                </div>
                <input type="range" min={25} max={500} step={25} value={radiusKm}
                  onChange={e => setRadiusKm(Number(e.target.value))} className="w-full accent-brand-400" />
              </div>
            )}
          </div>
        )}

        <div>
          <button onClick={() => setShowMunis(v => !v)}
            className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-gray-700 font-medium">
            {showMunis ? <ChevronUp size={11} /> : <ChevronDown size={11} />}
            Municipality filter
            {selMunis.length > 0 && <span className="px-1.5 py-0.5 bg-brand-100 text-brand-700 rounded-full">{selMunis.length}</span>}
          </button>
          {showMunis && (
            <div className="mt-2 max-h-36 overflow-y-auto flex flex-wrap gap-1.5">
              {muniList.slice(0, 60).map(m => <Chip key={m} label={m} small selected={selMunis.includes(m)} onClick={() => tog(selMunis, setSelMunis, m)} />)}
            </div>
          )}
        </div>

        <div className="hidden md:flex items-center justify-between py-2 border-t border-gray-100">
          <span className="text-xs text-gray-500">Map</span>
          <button onClick={() => setShowMap(v => !v)}
            className={`flex items-center gap-1.5 text-xs px-2.5 py-1.5 rounded-lg border transition-colors ${
              showMap ? 'bg-brand-50 border-brand-200 text-brand-700' : 'bg-white border-gray-200 text-gray-500'
            }`}>
            {showMap ? <><Eye size={11} /> On</> : <><EyeOff size={11} /> Off</>}
          </button>
        </div>

        <div className="pb-2 space-y-2">
          <button onClick={handleSearch} disabled={loading}
            className="btn-primary w-full py-2.5 text-sm flex items-center justify-center gap-2">
            {loading
              ? <><Loader size={14} className="animate-spin" /> Searching...</>
              : <>Search{filterCount > 0 ? ` (${filterCount} filter${filterCount > 1 ? 's' : ''})` : ''}</>
            }
          </button>
          {filterCount > 0 && (
            <button onClick={clearFilters} className="w-full text-xs text-gray-400 hover:text-gray-600 py-1">
              Clear all filters
            </button>
          )}
        </div>
      </div>
    </div>
  )

  // ===========================================================================
  // RESULTS PANEL
  // ===========================================================================
  const ResultsPanel = () => (
    <div className="h-full overflow-y-auto bg-gray-50">
      <div className="p-4 space-y-3">
        {searched && !loading && (
          <div className="flex items-center justify-between">
            <p className="text-sm font-medium text-gray-700">{total} result{total !== 1 ? 's' : ''}</p>
            {charged > 0 && <p className="text-xs text-gray-400">{charged} credit{charged !== 1 ? 's' : ''} used</p>}
          </div>
        )}

        {loading && (
          <div className="flex flex-col items-center justify-center py-24 gap-3">
            <div className="w-8 h-8 border-2 border-brand-400 border-t-transparent rounded-full animate-spin" />
            <p className="text-sm text-gray-400">Loading tenders...</p>
          </div>
        )}

        {!loading && searched && results.length === 0 && (
          <div className="flex flex-col items-center justify-center py-20 gap-2 text-center">
            <p className="text-sm text-gray-500">No tenders found</p>
            <p className="text-xs text-gray-400">Try removing filters or selecting a different province</p>
          </div>
        )}

        {!loading && results.map(t => <TenderCard key={t.id} tender={t} showBadgeColor />)}

        {total > 20 && !loading && (
          <div className="flex items-center justify-center gap-3 pt-2 pb-4">
            <button onClick={() => doSearch(page - 1)} disabled={page === 1} className="btn-secondary text-xs py-1.5 px-3">← Prev</button>
            <span className="text-xs text-gray-500">Page {page} of {Math.ceil(total / 20)}</span>
            <button onClick={() => doSearch(page + 1)} disabled={page >= Math.ceil(total / 20)} className="btn-secondary text-xs py-1.5 px-3">Next →</button>
          </div>
        )}
      </div>
    </div>
  )

  // ===========================================================================
  // RENDER
  // ===========================================================================
  return (
    <div className="flex flex-col overflow-hidden" style={{ height: 'calc(100vh - 0px)' }}>
      <div className="flex-shrink-0 bg-white border-b border-gray-200 px-4 py-3 flex items-center justify-between gap-3">
        <div className="min-w-0">
          <h1 className="text-base font-semibold text-gray-900">Search tenders</h1>
          {searched && <p className="text-xs text-gray-400">{total} results{charged > 0 ? ` · ${charged} credit${charged !== 1 ? 's' : ''} used` : ''}</p>}
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          <button onClick={() => setShowMap(v => !v)}
            className={`hidden md:flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-xs transition-colors ${
              showMap ? 'bg-brand-50 border-brand-200 text-brand-700' : 'bg-white border-gray-200 text-gray-500 hover:border-gray-300'
            }`}>
            {showMap ? <><Eye size={12} /> Map on</> : <><EyeOff size={12} /> Map off</>}
          </button>
          <button onClick={() => setShowFilters(v => !v)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-xs transition-colors ${
              showFilters ? 'bg-brand-50 border-brand-200 text-brand-700' : 'bg-white border-gray-200 text-gray-600'
            }`}>
            <Filter size={12} /> Filters
            {filterCount > 0 && <span className="bg-brand-400 text-white rounded-full px-1.5 py-0.5 text-xs">{filterCount}</span>}
          </button>
        </div>
      </div>

      <div className="hidden md:flex flex-1 overflow-hidden">
        {showFilters && (
          <div className="w-72 flex-shrink-0 border-r border-gray-200 overflow-hidden">
            <FiltersPanel />
          </div>
        )}

        <div className="flex-1 flex overflow-hidden">
          <div className={`flex flex-col overflow-hidden border-r border-gray-200 ${showMap ? 'w-[380px] flex-shrink-0' : 'flex-1'}`}>
            <div className="flex-1 overflow-y-auto"><ResultsPanel /></div>
          </div>

          {showMap && (
            <div className="flex-1 relative overflow-hidden">
              <TheMap scrollWheel />
            </div>
          )}
        </div>
      </div>

      <div className="md:hidden flex-1 flex flex-col overflow-hidden">
        <div className="flex-shrink-0 flex border-b border-gray-200 bg-white">
          {[
            { id: 'filters', label: 'Filters', badge: filterCount },
            { id: 'results', label: total > 0 ? `Results (${total})` : 'Results' },
            { id: 'map',     label: 'Map' },
          ].map(tab => (
            <button key={tab.id} onClick={() => setMobileTab(tab.id)}
              className={`flex-1 flex items-center justify-center gap-1 py-3 text-xs font-medium border-b-2 transition-colors ${
                mobileTab === tab.id ? 'border-brand-400 text-brand-600' : 'border-transparent text-gray-500'
              }`}>
              {tab.label}
              {tab.badge > 0 && <span className="bg-brand-400 text-white rounded-full px-1.5 py-0.5 text-xs">{tab.badge}</span>}
            </button>
          ))}
        </div>
        <div className="flex-1 overflow-hidden">
          {mobileTab === 'filters' && <FiltersPanel />}
          {mobileTab === 'results' && <ResultsPanel />}
          {mobileTab === 'map'     && <div className="h-full"><TheMap scrollWheel={false} /></div>}
        </div>
      </div>

      <style>{`
        .leaflet-popup-content-wrapper {
          border-radius: 12px !important;
          border: 1px solid #e5e7eb !important;
          box-shadow: 0 8px 24px rgba(0,0,0,.12) !important;
          padding: 0 !important;
        }
        .leaflet-popup-content { margin: 12px !important; min-width: 0 !important; }
        .leaflet-popup-tip { background: white !important; }
        .leaflet-control-zoom {
          border: 1px solid #e5e7eb !important;
          border-radius: 8px !important;
          overflow: hidden;
          box-shadow: 0 2px 8px rgba(0,0,0,.1) !important;
        }
        .leaflet-control-zoom a { color: #374151 !important; border-color: #e5e7eb !important; }
      `}</style>
    </div>
  )
}