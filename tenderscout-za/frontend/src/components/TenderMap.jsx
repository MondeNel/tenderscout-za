/**
 * File: src/components/TenderMap.jsx
 * Purpose: Interactive South Africa Map with Tender Markers
 * 
 * This component renders an interactive map of South Africa using Leaflet.
 * It displays:
 *   - District-level markers showing tender counts
 *   - Color-coded markers based on tender volume
 *   - Clickable markers that reveal tender details in a popup
 *   - User location marker (if business location is set)
 *   - Radius-based filtering for nearby tenders
 * 
 * The map integrates with:
 *   - saLocations.js: Geographic data for districts and coordinates
 *   - tenders.js API: Fetches actual tender data from the backend
 * 
 * Features:
 *   - Smooth fly-to animation when selecting a marker
 *   - Legend showing tender count color scale
 *   - Loading state while fetching data
 *   - Filtered view based on selected industries and provinces
 * 
 * Usage:
 *   <TenderMap
 *     industries={selectedIndustries}
 *     provinces={selectedProvinces}
 *     userLocation={{ lat: -26.2041, lng: 28.0473, name: 'Johannesburg' }}
 *     radiusKm={100}
 *     onSelectArea={(district) => console.log('Selected:', district)}
 *     height="500px"
 *   />
 */

import { useEffect, useState, useRef, useMemo } from 'react'
import { MapContainer, TileLayer, Marker, Popup, useMap } from 'react-leaflet'
import L from 'leaflet'
import { MapPin, Loader, X, ExternalLink, TrendingUp } from 'lucide-react'
import { searchTenders } from '../api/tenders'
import { SA_LOCATIONS } from '../data/saLocations'
import 'leaflet/dist/leaflet.css'

// =============================================================================
// LEAFLET ICON CONFIGURATION
// =============================================================================
// Fix Leaflet's default marker icons which don't load correctly in bundled apps.
// We use CDN URLs for the marker images to ensure they display properly.

delete L.Icon.Default.prototype._getIconUrl
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png',
  iconUrl:       'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png',
  shadowUrl:     'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
})

// =============================================================================
// CUSTOM MARKER ICON GENERATOR
// =============================================================================

/**
 * Create a custom div icon with a tender count badge
 * 
 * The marker size and color scale with the number of tenders:
 *   - 1-5 tenders:   Small, light green (#c8f0e3)
 *   - 6-20 tenders:  Medium-small, mint (#9FE1CB)
 *   - 21-50 tenders: Medium, teal (#5DCAA5)
 *   - 51-100 tenders: Large, deep teal (#2aa882)
 *   - 100+ tenders:  Extra large, brand green (#1D9E75)
 * 
 * Selected markers get a darker background and white border.
 * Highlighted markers (within user's radius) get the brand color.
 * 
 * @param {number} count - Number of tenders in this district
 * @param {boolean} isSelected - Whether this marker is currently selected
 * @param {boolean} isHighlighted - Whether this marker is within user's radius
 * @returns {L.DivIcon} Custom Leaflet icon
 */
function createCountIcon(count, isSelected = false, isHighlighted = false) {
  // Size scales with tender count (minimum 30px, maximum 52px)
  const size = count > 100 ? 52 : count > 50 ? 46 : count > 20 ? 40 : count > 5 ? 36 : 30
  
  // Color based on selection state, highlight state, or count
  const bgColor = isSelected    ? '#0F6E56'  // brand-600 (darkest)
                : isHighlighted ? '#1D9E75'  // brand-400 (primary)
                : count > 100   ? '#1D9E75'  // brand-400
                : count > 50    ? '#2aa882'  // custom teal
                : count > 20    ? '#5DCAA5'  // brand-200
                : count > 5     ? '#9FE1CB'  // brand-100
                :                 '#c8f0e3'  // custom light
  
  // Text color: white for dark backgrounds, dark green for light backgrounds
  const textColor = count > 20 || isSelected || isHighlighted ? '#fff' : '#085041'
  
  // Border: thicker white border for selected markers
  const border = isSelected ? '3px solid #fff' : '2px solid rgba(255,255,255,0.7)'

  return L.divIcon({
    className: '',
    html: `<div style="
      width:${size}px; height:${size}px;
      background:${bgColor};
      border:${border};
      border-radius:50%;
      display:flex; align-items:center; justify-content:center;
      box-shadow: 0 2px 8px rgba(0,0,0,0.25);
      cursor:pointer;
      transition: transform 0.15s ease;
      font-family: system-ui, sans-serif;
      font-size: ${size > 40 ? 13 : 11}px;
      font-weight: 700;
      color: ${textColor};
      line-height: 1;
    ">${count > 999 ? '999+' : count}</div>`,
    iconSize:   [size, size],
    iconAnchor: [size / 2, size / 2],      // Center the icon on the coordinate
    popupAnchor: [0, -(size / 2) - 4],     // Popup appears above the marker
  })
}

// =============================================================================
// DISTANCE CALCULATION (Haversine Formula)
// =============================================================================

/**
 * Calculate the great-circle distance between two coordinates
 * Used for radius-based filtering of markers.
 * 
 * @param {number} lat1 - Latitude of first point
 * @param {number} lng1 - Longitude of first point
 * @param {number} lat2 - Latitude of second point
 * @param {number} lng2 - Longitude of second point
 * @returns {number} Distance in kilometers
 */
function haversine(lat1, lng1, lat2, lng2) {
  const R = 6371  // Earth's radius in kilometers
  const dLat = (lat2 - lat1) * Math.PI / 180
  const dLng = (lng2 - lng1) * Math.PI / 180
  const a = Math.sin(dLat/2)**2 + Math.cos(lat1*Math.PI/180) * Math.cos(lat2*Math.PI/180) * Math.sin(dLng/2)**2
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a))
}

// =============================================================================
// MAP FLY-TO COMPONENT
// =============================================================================

/**
 * Helper component that flies the map to a new center when coordinates change.
 * Uses Leaflet's flyTo method for smooth animated transitions.
 * 
 * @param {Object} props
 * @param {[number, number]} props.center - [lat, lng] to fly to
 * @param {number} props.zoom - Target zoom level
 */
function MapFlyTo({ center, zoom }) {
  const map = useMap()
  useEffect(() => {
    if (center) {
      map.flyTo(center, zoom, { duration: 0.8 })  // 0.8 second animation
    }
  }, [center, zoom, map])
  return null
}

// =============================================================================
// DISTRICT DATA PREPARATION
// =============================================================================

/**
 * Build a flat list of all districts from the SA_LOCATIONS data.
 * Each district includes:
 *   - key: Unique identifier (province::district)
 *   - province, district, municipalities
 *   - lat, lng: Center coordinates for the marker
 * 
 * This is memoized at module level since the data never changes.
 * 
 * @returns {Array} Array of district objects
 */
function getAllDistricts() {
  const districts = []
  for (const [province, pData] of Object.entries(SA_LOCATIONS)) {
    for (const [district, dData] of Object.entries(pData.districts)) {
      districts.push({
        key:           `${province}::${district}`,
        province,
        district,
        municipalities: dData.municipalities,
        lat:           dData.lat,
        lng:           dData.lng,
      })
    }
  }
  return districts
}

const ALL_DISTRICTS = getAllDistricts()  // Static data, computed once

// =============================================================================
// MAIN COMPONENT
// =============================================================================

export default function TenderMap({
  industries = [],           // Selected industry categories for filtering
  provinces  = [],           // Selected provinces for filtering
  userLocation = null,       // { lat, lng, name } - User's business location
  radiusKm   = 100,          // Search radius in kilometers
  onSelectArea,              // Callback when user clicks a district marker
  height     = '480px',      // Map container height
  className  = '',           // Additional CSS classes
}) {
  // ===========================================================================
  // STATE
  // ===========================================================================
  
  // Tender data grouped by municipality: { municipality: [tenders] }
  // Also includes _byProvince and _total for fallback calculations
  const [tendersByMuni, setTendersByMuni] = useState({})
  
  // Loading state while fetching tender data
  const [loading, setLoading] = useState(false)
  
  // Currently selected district key (e.g., "Gauteng::City of Johannesburg")
  const [selected, setSelected] = useState(null)
  
  // Target for fly-to animation (center and zoom)
  const [flyTarget, setFlyTarget] = useState(null)

  // ===========================================================================
  // FETCH TENDER DATA
  // ===========================================================================
  
  /**
   * Fetch tenders from the API and group them by municipality.
   * Runs whenever industries or provinces filters change.
   */
  useEffect(() => {
    let cancelled = false
    
    const fetchCounts = async () => {
      setLoading(true)
      try {
        // Fetch a broad set of tenders (up to 200) for counting
        // If no provinces selected, fetch all provinces
        const res = await searchTenders({
          industries,
          provinces: provinces.length ? provinces : Object.keys(SA_LOCATIONS),
          page: 1,
          page_size: 200,
        })
        
        if (cancelled) return
        
        // Group tenders by municipality
        const grouped = {}
        for (const t of res.data.results) {
          const key = t.municipality || t.province || 'Unknown'
          if (!grouped[key]) grouped[key] = []
          grouped[key].push(t)
        }
        
        // Also count by province for fallback when municipality data is missing
        const byProvince = {}
        for (const t of res.data.results) {
          const p = t.province || 'Unknown'
          if (!byProvince[p]) byProvince[p] = 0
          byProvince[p]++
        }
        
        setTendersByMuni({ 
          ...grouped, 
          _byProvince: byProvince, 
          _total: res.data.total 
        })
      } catch (e) {
        console.warn('TenderMap fetch failed:', e)
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    
    fetchCounts()
    return () => { cancelled = true }
  }, [JSON.stringify(industries), JSON.stringify(provinces)])

  // ===========================================================================
  // HELPER: COUNT TENDERS FOR A DISTRICT
  // ===========================================================================
  
  /**
   * Calculate the number of tenders in a district.
   * Sums tenders across all municipalities in the district.
   * Falls back to province-level distribution if no municipality data.
   * 
   * @param {Object} district - District object from ALL_DISTRICTS
   * @returns {number} Tender count for this district
   */
  const countForDistrict = (district) => {
    if (!tendersByMuni._byProvince) return 0
    
    let count = 0
    // Sum tenders for each municipality in the district
    for (const muni of district.municipalities) {
      count += (tendersByMuni[muni] || []).length
    }
    
    // Fallback: If no municipality-level data, distribute province count
    // evenly across districts (rough estimate)
    if (count === 0) {
      const provCount = tendersByMuni._byProvince?.[district.province] || 0
      const provDistricts = ALL_DISTRICTS.filter(d => d.province === district.province).length
      count = Math.round(provCount / Math.max(provDistricts, 1))
    }
    
    return count
  }

  // ===========================================================================
  // FILTER VISIBLE DISTRICTS
  // ===========================================================================
  
  /**
   * Determine which districts should be visible on the map.
   * Filters by:
   *   - Selected provinces (if any)
   *   - Minimum tender count (> 0)
   *   - Radius from user location (if set)
   */
  const visibleDistricts = useMemo(() => {
    // Start with all districts or filter by selected provinces
    const filtered = provinces.length
      ? ALL_DISTRICTS.filter(d => provinces.includes(d.province))
      : ALL_DISTRICTS
    
    return filtered.filter(d => {
      const count = countForDistrict(d)
      
      // Must have at least one tender to display
      if (count === 0) return false
      
      // If user location is set, filter by radius
      // Use 1.5x radius to show slightly beyond for context
      if (userLocation) {
        const dist = haversine(userLocation.lat, userLocation.lng, d.lat, d.lng)
        return dist <= radiusKm * 1.5
      }
      
      return true
    })
  }, [ALL_DISTRICTS, provinces, tendersByMuni, userLocation, radiusKm])

  // ===========================================================================
  // SELECTED DISTRICT DETAILS
  // ===========================================================================
  
  const selectedDistrict = ALL_DISTRICTS.find(d => d.key === selected)
  
  /**
   * Get tenders for the currently selected district.
   * Returns up to 8 tenders to display in the popup.
   */
  const selectedTenders = useMemo(() => {
    if (!selectedDistrict) return []
    const munis = selectedDistrict.municipalities
    const result = []
    for (const muni of munis) {
      result.push(...(tendersByMuni[muni] || []))
    }
    return result.slice(0, 8)  // Limit to 8 for popup space
  }, [selected, tendersByMuni])

  // ===========================================================================
  // MAP DEFAULT CENTER
  // ===========================================================================
  
  /**
   * Determine the initial map center:
   *   1. User's location (if set)
   *   2. Center of selected province (if exactly one province selected)
   *   3. Center of South Africa (-29, 25)
   */
  const defaultCenter = userLocation
    ? [userLocation.lat, userLocation.lng]
    : provinces.length === 1
      ? [SA_LOCATIONS[provinces[0]]?.lat || -29, SA_LOCATIONS[provinces[0]]?.lng || 25]
      : [-29.0, 25.0]
      
  const defaultZoom = userLocation ? 8 : provinces.length === 1 ? 7 : 5

  // ===========================================================================
  // RENDER
  // ===========================================================================
  
  return (
    <div 
      className={`relative rounded-xl overflow-hidden border border-gray-200 shadow-sm ${className}`}
      style={{ height }}
    >
      {/* =====================================================================
          LOADING OVERLAY
          ===================================================================== */}
      {loading && (
        <div className="absolute inset-0 z-20 bg-white bg-opacity-60 flex items-center justify-center">
          <div className="flex items-center gap-2 bg-white rounded-full px-4 py-2 shadow-md border border-gray-200">
            <Loader size={14} className="animate-spin text-brand-400" />
            <span className="text-xs text-gray-600">Loading tender data...</span>
          </div>
        </div>
      )}

      {/* =====================================================================
          STATS BAR (Top Left)
          ===================================================================== */}
      <div className="absolute top-3 left-3 z-10 flex items-center gap-2">
        <div className="bg-white rounded-full px-3 py-1.5 shadow-md border border-gray-200 flex items-center gap-1.5">
          <TrendingUp size={12} className="text-brand-400" />
          <span className="text-xs font-semibold text-gray-700">
            {tendersByMuni._total || 0} tenders
          </span>
          {(industries.length > 0 || provinces.length > 0) && (
            <span className="text-xs text-gray-400">filtered</span>
          )}
        </div>
        {userLocation && (
          <div className="bg-white rounded-full px-3 py-1.5 shadow-md border border-gray-200 flex items-center gap-1">
            <MapPin size={11} className="text-brand-400" />
            <span className="text-xs text-gray-600">{userLocation.name} · {radiusKm}km</span>
          </div>
        )}
      </div>

      {/* =====================================================================
          LEGEND (Bottom Left)
          ===================================================================== */}
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
        </div>
      </div>

      {/* =====================================================================
          LEAFLET MAP
          ===================================================================== */}
      <MapContainer
        center={defaultCenter}
        zoom={defaultZoom}
        style={{ height: '100%', width: '100%' }}
        className="z-0"
        zoomControl={true}
      >
        {/* OpenStreetMap tile layer */}
        <TileLayer
          attribution='© <a href="https://www.openstreetmap.org">OpenStreetMap</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />

        {/* Fly-to animation controller */}
        {flyTarget && <MapFlyTo center={flyTarget.center} zoom={flyTarget.zoom} />}

        {/* =================================================================
            DISTRICT MARKERS
            ================================================================= */}
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
              {/* =============================================================
                  POPUP CONTENT
                  ============================================================= */}
              <Popup
                className="tender-map-popup"
                maxWidth={320}
                minWidth={260}
              >
                <div className="p-1">
                  {/* District header */}
                  <div className="flex items-center justify-between mb-2">
                    <div>
                      <p className="text-sm font-semibold text-gray-900">{district.district}</p>
                      <p className="text-xs text-gray-400">{district.province}</p>
                    </div>
                    <span className="px-2 py-0.5 bg-brand-50 text-brand-700 text-xs font-bold rounded-full border border-brand-200">
                      {count} tender{count !== 1 ? 's' : ''}
                    </span>
                  </div>

                  {/* Tender list */}
                  {selectedTenders.length > 0 ? (
                    <div className="space-y-1.5 max-h-48 overflow-y-auto">
                      {selectedTenders.map((t, i) => (
                        <div key={i} className="flex items-start gap-2 p-2 bg-gray-50 rounded-lg">
                          <div className="flex-1 min-w-0">
                            <p className="text-xs font-medium text-gray-800 leading-tight truncate">
                              {t.title}
                            </p>
                            <p className="text-xs text-gray-400 mt-0.5">{t.issuing_body}</p>
                            {t.closing_date && (
                              <p className="text-xs text-red-500 mt-0.5">
                                Closes {t.closing_date}
                              </p>
                            )}
                          </div>
                          {(t.document_url || t.source_url) && (
                            <a
                              href={t.document_url || t.source_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="flex-shrink-0 text-brand-600 hover:text-brand-800"
                              onClick={e => e.stopPropagation()}
                            >
                              <ExternalLink size={12} />
                            </a>
                          )}
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-xs text-gray-400 py-2 text-center">Loading tenders...</p>
                  )}

                  {/* Municipalities footer */}
                  <div className="mt-2 pt-2 border-t border-gray-100">
                    <p className="text-xs text-gray-400">
                      Municipalities: {district.municipalities.slice(0, 3).join(', ')}
                      {district.municipalities.length > 3 && (
                        ` +${district.municipalities.length - 3} more`
                      )}
                    </p>
                  </div>
                </div>
              </Popup>
            </Marker>
          )
        })}

        {/* =================================================================
            USER LOCATION MARKER
            ================================================================= */}
        {userLocation && (
          <Marker
            position={[userLocation.lat, userLocation.lng]}
            icon={L.divIcon({
              className: '',
              html: `<div style="
                width:16px;height:16px;
                background:#1D9E75;
                border:3px solid white;
                border-radius:50%;
                box-shadow:0 0 0 3px rgba(29,158,117,0.3);
              "></div>`,
              iconSize:   [16, 16],
              iconAnchor: [8, 8],
            })}
          >
            <Popup>
              <strong>{userLocation.name}</strong><br/>
              Your location
            </Popup>
          </Marker>
        )}
      </MapContainer>

      {/* =====================================================================
          CUSTOM POPUP STYLES
          ===================================================================== */}
      <style>{`
        .leaflet-popup-content-wrapper {
          border-radius: 12px !important;
          border: 1px solid #e5e7eb !important;
          box-shadow: 0 4px 20px rgba(0,0,0,0.12) !important;
          padding: 0 !important;
        }
        .leaflet-popup-content {
          margin: 12px !important;
        }
        .leaflet-popup-tip { 
          background: white !important; 
        }
      `}</style>
    </div>
  )
}