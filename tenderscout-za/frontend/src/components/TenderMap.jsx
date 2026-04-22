/**
 * File: src/components/TenderMap.jsx
 * Purpose: Interactive South Africa Map with Tender Markers
 * 
 * This component renders an interactive map of South Africa using Leaflet.
 * It displays:
 *   - District-level markers showing tender counts (aggregated)
 *   - Individual tender location pins (when district is selected)
 *   - Color-coded pins by location precision (green=town, amber=municipality, gray=province)
 *   - User location marker (if business location is set)
 * 
 * The map integrates with:
 *   - saLocations.js: Geographic data and coordinate lookup
 *   - tenders.js API: Fetches actual tender data from the backend
 */

import { useEffect, useState, useMemo } from 'react'
import { MapContainer, TileLayer, Marker, Popup, useMap } from 'react-leaflet'
import L from 'leaflet'
import { MapPin, Loader, ExternalLink, TrendingUp } from 'lucide-react'
import { searchTenders } from '../api/tenders'
import { SA_LOCATIONS, getTenderCoordinates, createTenderMarkerIcon } from '../data/saLocations'
import 'leaflet/dist/leaflet.css'

// =============================================================================
// LEAFLET ICON CONFIGURATION
// =============================================================================

delete L.Icon.Default.prototype._getIconUrl
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
})

// =============================================================================
// CUSTOM MARKER ICON GENERATOR (District Aggregates)
// =============================================================================

function createCountIcon(count, isSelected = false, isHighlighted = false) {
  const size = count > 100 ? 52 : count > 50 ? 46 : count > 20 ? 40 : count > 5 ? 36 : 30
  
  const bgColor = isSelected    ? '#0F6E56'
                : isHighlighted ? '#1D9E75'
                : count > 100   ? '#1D9E75'
                : count > 50    ? '#2aa882'
                : count > 20    ? '#5DCAA5'
                : count > 5     ? '#9FE1CB'
                :                 '#c8f0e3'
  
  const textColor = count > 20 || isSelected || isHighlighted ? '#fff' : '#085041'
  const border = isSelected ? '3px solid #fff' : '2px solid rgba(255,255,255,0.7)'

  return L.divIcon({
    className: '',
    html: `<div style="
      width:${size}px;height:${size}px;background:${bgColor};
      border:${border};border-radius:50%;
      display:flex;align-items:center;justify-content:center;
      box-shadow:0 2px 8px rgba(0,0,0,0.25);cursor:pointer;
      font-family:system-ui,sans-serif;font-weight:700;
      font-size:${size > 40 ? 13 : 11}px;color:${textColor};
    ">${count > 999 ? '999+' : count}</div>`,
    iconSize: [size, size],
    iconAnchor: [size/2, size/2],
    popupAnchor: [0, -(size/2) - 4],
  })
}

// =============================================================================
// DISTANCE CALCULATION
// =============================================================================

function haversine(lat1, lng1, lat2, lng2) {
  const R = 6371
  const dLat = (lat2 - lat1) * Math.PI / 180
  const dLng = (lng2 - lng1) * Math.PI / 180
  const a = Math.sin(dLat/2)**2 + Math.cos(lat1*Math.PI/180) * Math.cos(lat2*Math.PI/180) * Math.sin(dLng/2)**2
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a))
}

// =============================================================================
// MAP FLY-TO COMPONENT
// =============================================================================

function MapFlyTo({ center, zoom }) {
  const map = useMap()
  useEffect(() => {
    if (center) map.flyTo(center, zoom, { duration: 0.8 })
  }, [center, zoom, map])
  return null
}

// =============================================================================
// DISTRICT DATA PREPARATION
// =============================================================================

function getAllDistricts() {
  const districts = []
  for (const [province, pData] of Object.entries(SA_LOCATIONS)) {
    for (const [district, dData] of Object.entries(pData.districts)) {
      districts.push({
        key: `${province}::${district}`,
        province,
        district,
        municipalities: dData.municipalities,
        lat: dData.lat,
        lng: dData.lng,
      })
    }
  }
  return districts
}

const ALL_DISTRICTS = getAllDistricts()

// =============================================================================
// MAIN COMPONENT
// =============================================================================

export default function TenderMap({
  industries = [],
  provinces = [],
  userLocation = null,
  radiusKm = 100,
  onSelectArea,
  height = '480px',
  className = '',
}) {
  const [tendersByMuni, setTendersByMuni] = useState({})
  const [loading, setLoading] = useState(false)
  const [selected, setSelected] = useState(null)
  const [flyTarget, setFlyTarget] = useState(null)

  // Fetch tender data
  useEffect(() => {
    let cancelled = false
    
    const fetchCounts = async () => {
      setLoading(true)
      try {
        const res = await searchTenders({
          industries,
          provinces: provinces.length ? provinces : Object.keys(SA_LOCATIONS),
          page: 1,
          page_size: 200,
        })
        
        if (cancelled) return
        
        const grouped = {}
        for (const t of res.data.results) {
          const key = t.municipality || t.province || 'Unknown'
          if (!grouped[key]) grouped[key] = []
          grouped[key].push(t)
        }
        
        const byProvince = {}
        for (const t of res.data.results) {
          const p = t.province || 'Unknown'
          if (!byProvince[p]) byProvince[p] = 0
          byProvince[p]++
        }
        
        setTendersByMuni({ ...grouped, _byProvince: byProvince, _total: res.data.total })
      } catch (e) {
        console.warn('TenderMap fetch failed:', e)
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    
    fetchCounts()
    return () => { cancelled = true }
  }, [JSON.stringify(industries), JSON.stringify(provinces)])

  // Count tenders for a district
  const countForDistrict = (district) => {
    if (!tendersByMuni._byProvince) return 0
    
    let count = 0
    for (const muni of district.municipalities) {
      count += (tendersByMuni[muni] || []).length
    }
    
    if (count === 0) {
      const provCount = tendersByMuni._byProvince?.[district.province] || 0
      const provDistricts = ALL_DISTRICTS.filter(d => d.province === district.province).length
      count = Math.round(provCount / Math.max(provDistricts, 1))
    }
    
    return count
  }

  // Filter visible districts
  const visibleDistricts = useMemo(() => {
    const filtered = provinces.length
      ? ALL_DISTRICTS.filter(d => provinces.includes(d.province))
      : ALL_DISTRICTS
    
    return filtered.filter(d => {
      const count = countForDistrict(d)
      if (count === 0) return false
      
      if (userLocation) {
        const dist = haversine(userLocation.lat, userLocation.lng, d.lat, d.lng)
        return dist <= radiusKm * 1.5
      }
      
      return true
    })
  }, [provinces, tendersByMuni, userLocation, radiusKm])

  // Selected district details
  const selectedDistrict = ALL_DISTRICTS.find(d => d.key === selected)
  
  const selectedTenders = useMemo(() => {
    if (!selectedDistrict) return []
    const result = []
    for (const muni of selectedDistrict.municipalities) {
      result.push(...(tendersByMuni[muni] || []))
    }
    return result
  }, [selected, tendersByMuni])

  // Map center
  const defaultCenter = userLocation
    ? [userLocation.lat, userLocation.lng]
    : provinces.length === 1
      ? [SA_LOCATIONS[provinces[0]]?.lat || -29, SA_LOCATIONS[provinces[0]]?.lng || 25]
      : [-29.0, 25.0]
      
  const defaultZoom = userLocation ? 8 : provinces.length === 1 ? 7 : 5

  return (
    <div className={`relative rounded-xl overflow-hidden border border-gray-200 shadow-sm ${className}`} style={{ height }}>
      {/* Loading overlay */}
      {loading && (
        <div className="absolute inset-0 z-20 bg-white bg-opacity-60 flex items-center justify-center">
          <div className="flex items-center gap-2 bg-white rounded-full px-4 py-2 shadow-md border border-gray-200">
            <Loader size={14} className="animate-spin text-brand-400" />
            <span className="text-xs text-gray-600">Loading...</span>
          </div>
        </div>
      )}

      {/* Stats bar */}
      <div className="absolute top-3 left-3 z-10 flex items-center gap-2">
        <div className="bg-white rounded-full px-3 py-1.5 shadow-md border border-gray-200 flex items-center gap-1.5">
          <TrendingUp size={12} className="text-brand-400" />
          <span className="text-xs font-semibold text-gray-700">{tendersByMuni._total || 0} tenders</span>
        </div>
        {userLocation && (
          <div className="bg-white rounded-full px-3 py-1.5 shadow-md border border-gray-200 flex items-center gap-1">
            <MapPin size={11} className="text-brand-400" />
            <span className="text-xs text-gray-600">{userLocation.name} · {radiusKm}km</span>
          </div>
        )}
      </div>

      {/* Legend */}
      <div className="absolute bottom-8 left-3 z-10">
        <div className="bg-white rounded-xl px-3 py-2 shadow-md border border-gray-200">
          <p className="text-xs text-gray-400 mb-1.5">Tender count</p>
          <div className="flex items-center gap-2">
            {[
              { color: '#c8f0e3', label: '1–5' },
              { color: '#9FE1CB', label: '6–20' },
              { color: '#5DCAA5', label: '21–50' },
              { color: '#2aa882', label: '51–100' },
              { color: '#1D9E75', label: '100+' },
            ].map(({ color, label }) => (
              <div key={label} className="flex items-center gap-1">
                <div className="w-3 h-3 rounded-full" style={{ background: color }} />
                <span className="text-xs text-gray-500">{label}</span>
              </div>
            ))}
          </div>
          <p className="text-xs text-gray-400 mt-2 mb-1">Location precision</p>
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-1"><div className="w-3 h-3 rounded-full bg-[#1D9E75]" /><span className="text-xs text-gray-500">Town</span></div>
            <div className="flex items-center gap-1"><div className="w-3 h-3 rounded-full bg-[#F59E0B]" /><span className="text-xs text-gray-500">Municipality</span></div>
            <div className="flex items-center gap-1"><div className="w-3 h-3 rounded-full bg-[#6B7280]" /><span className="text-xs text-gray-500">Province</span></div>
          </div>
        </div>
      </div>

      <MapContainer center={defaultCenter} zoom={defaultZoom} style={{ height: '100%', width: '100%' }} className="z-0" zoomControl={true}>
        <TileLayer attribution='© <a href="https://www.openstreetmap.org">OpenStreetMap</a>' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
        {flyTarget && <MapFlyTo center={flyTarget.center} zoom={flyTarget.zoom} />}

        {/* =====================================================================
            DISTRICT MARKERS (Aggregated Counts)
            ===================================================================== */}
        {visibleDistricts.map(district => {
          const count = countForDistrict(district)
          if (count === 0) return null
          
          const isSelected = district.key === selected
          const isNearby = userLocation
            ? haversine(userLocation.lat, userLocation.lng, district.lat, district.lng) <= radiusKm
            : false

          return (
            <Marker
              key={district.key}
              position={[district.lat, district.lng]}
              icon={createCountIcon(count, isSelected, isNearby)}
              eventHandlers={{
                click: () => {
                  setSelected(district.key)
                  setFlyTarget({ center: [district.lat, district.lng], zoom: 9 })
                  if (onSelectArea) onSelectArea(district)
                }
              }}
            >
              <Popup className="tender-map-popup" maxWidth={320} minWidth={260}>
                <div className="p-1">
                  <div className="flex items-center justify-between mb-2">
                    <div>
                      <p className="text-sm font-semibold text-gray-900">{district.district}</p>
                      <p className="text-xs text-gray-400">{district.province}</p>
                    </div>
                    <span className="px-2 py-0.5 bg-brand-50 text-brand-700 text-xs font-bold rounded-full border border-brand-200">
                      {count} tender{count !== 1 ? 's' : ''}
                    </span>
                  </div>
                  
                  <div className="space-y-1.5 max-h-48 overflow-y-auto">
                    {selectedTenders.slice(0, 5).map((t, i) => (
                      <div key={i} className="flex items-start gap-2 p-2 bg-gray-50 rounded-lg">
                        <div className="flex-1 min-w-0">
                          <p className="text-xs font-medium text-gray-800 truncate">{t.title}</p>
                          <p className="text-xs text-gray-400">{t.issuing_body}</p>
                        </div>
                        {(t.document_url || t.source_url) && (
                          <a href={t.document_url || t.source_url} target="_blank" rel="noopener noreferrer" className="text-brand-600">
                            <ExternalLink size={12} />
                          </a>
                        )}
                      </div>
                    ))}
                  </div>
                  
                  <div className="mt-2 pt-2 border-t border-gray-100">
                    <p className="text-xs text-gray-400">
                      {district.municipalities.slice(0, 3).join(', ')}
                      {district.municipalities.length > 3 && ` +${district.municipalities.length - 3}`}
                    </p>
                  </div>
                </div>
              </Popup>
            </Marker>
          )
        })}

        {/* =====================================================================
            INDIVIDUAL TENDER LOCATION PINS
            ===================================================================== */}
        {selectedDistrict && selectedTenders.map((tender, index) => {
          const coords = getTenderCoordinates(tender)
          if (!coords) return null
          
          const iconConfig = createTenderMarkerIcon(coords.type)
          
          return (
            <Marker
              key={`pin-${tender.id || index}`}
              position={[coords.lat, coords.lng]}
              icon={L.divIcon(iconConfig)}
            >
              <Popup>
                <div style={{ maxWidth: '220px' }}>
                  <p className="text-xs font-semibold text-gray-900 mb-1">{tender.title}</p>
                  <p className="text-xs text-gray-500">{tender.issuing_body}</p>
                  <p className="text-xs text-gray-400 mt-1">
                    📍 {coords.name} 
                    <span className="ml-1 text-gray-300">
                      ({coords.type === 'town' ? 'Town' : coords.type === 'municipality' ? 'Municipality' : 'Province'})
                    </span>
                  </p>
                  {tender.closing_date && (
                    <p className="text-xs text-red-500 mt-1">⏰ Closes {tender.closing_date}</p>
                  )}
                  {(tender.document_url || tender.source_url) && (
                    <a href={tender.document_url || tender.source_url} target="_blank" rel="noopener noreferrer" className="inline-block mt-2 text-xs text-brand-600">
                      View tender →
                    </a>
                  )}
                </div>
              </Popup>
            </Marker>
          )
        })}

        {/* =====================================================================
            USER LOCATION MARKER
            ===================================================================== */}
        {userLocation && (
          <Marker
            position={[userLocation.lat, userLocation.lng]}
            icon={L.divIcon({
              html: `<div style="width:16px;height:16px;background:#1D9E75;border:3px solid white;border-radius:50%;box-shadow:0 0 0 3px rgba(29,158,117,0.3);"></div>`,
              iconSize: [16, 16],
              iconAnchor: [8, 8],
            })}
          >
            <Popup><strong>{userLocation.name}</strong><br/>Your location</Popup>
          </Marker>
        )}
      </MapContainer>

      <style>{`
        .leaflet-popup-content-wrapper { border-radius: 12px !important; border: 1px solid #e5e7eb !important; padding: 0 !important; }
        .leaflet-popup-content { margin: 12px !important; }
        .leaflet-popup-tip { background: white !important; }
      `}</style>
    </div>
  )
}