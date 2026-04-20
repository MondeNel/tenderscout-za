import { useState, useEffect, useMemo } from 'react'
import { MapContainer, TileLayer, Marker, Popup, Circle, useMapEvents } from 'react-leaflet'
import L from 'leaflet'
import { MapPin, Search, X, Navigation } from 'lucide-react'
import { SA_LOCATIONS, getTowns, getMunicipalities, findTown, getMunicipalitiesWithinRadius } from '../data/saLocations'
import 'leaflet/dist/leaflet.css'

// Fix Leaflet default marker icon
delete L.Icon.Default.prototype._getIconUrl
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
})

const RADIUS_OPTIONS = [25, 50, 100, 150, 200, 300, 500]

function MapClickHandler({ onMapClick }) {
  useMapEvents({ click: (e) => onMapClick(e.latlng) })
  return null
}

function TownMarkers({ province, district, onSelect, selected }) {
  const towns = getTowns(province, district)
  return towns.map(town => (
    <Marker
      key={town.name}
      position={[town.lat, town.lng]}
      eventHandlers={{ click: () => onSelect(town) }}
    >
      <Popup>
        <div className="text-sm font-medium">{town.name}</div>
        <button
          onClick={() => onSelect(town)}
          className="text-xs text-brand-600 mt-1 underline"
        >
          Select this location
        </button>
      </Popup>
    </Marker>
  ))
}

export default function LocationPicker({ value, onChange, showRadius = true, showPreview = true, compact = false }) {
  const { location, radiusKm } = value

  const [query,         setQuery]         = useState(location?.name || '')
  const [suggestions,   setSuggestions]   = useState([])
  const [selProvince,   setSelProvince]   = useState(location?.province || '')
  const [selDistrict,   setSelDistrict]   = useState(location?.district || '')
  const [mapCenter,     setMapCenter]     = useState(
    location ? [location.lat, location.lng] : [-28.4541, 24.7499]
  )
  const [zoom, setZoom] = useState(location ? 10 : 5)
  const [showMap,       setShowMap]       = useState(false)

  // Search suggestions from saLocations
  useEffect(() => {
    if (query.length < 2) { setSuggestions([]); return }
    const q = query.toLowerCase()
    const matches = []
    for (const [province, pData] of Object.entries(SA_LOCATIONS)) {
      for (const [district, dData] of Object.entries(pData.districts)) {
        for (const town of dData.towns) {
          if (town.name.toLowerCase().includes(q) || district.toLowerCase().includes(q) || province.toLowerCase().includes(q)) {
            matches.push({ ...town, province, district, municipality: dData.municipalities[0] })
          }
        }
      }
    }
    setSuggestions(matches.slice(0, 8))
  }, [query])

  const selectLocation = (loc) => {
    setQuery(loc.name)
    setSuggestions([])
    setSelProvince(loc.province)
    setSelDistrict(loc.district)
    setMapCenter([loc.lat, loc.lng])
    setZoom(11)
    onChange({ location: loc, radiusKm })
  }

  const clearLocation = () => {
    setQuery('')
    setSuggestions([])
    setSelProvince('')
    setSelDistrict('')
    onChange({ location: null, radiusKm })
  }

  const nearbyMunicipalities = useMemo(() => {
    if (!location) return []
    return getMunicipalitiesWithinRadius(location.lat, location.lng, radiusKm)
  }, [location, radiusKm])

  const districtOptions = selProvince ? Object.keys(SA_LOCATIONS[selProvince]?.districts || {}) : []

  return (
    <div className="space-y-4">
      {/* Search input */}
      <div className="relative">
        <div className="flex items-center gap-2 border border-gray-200 rounded-xl bg-white px-3 py-2.5 focus-within:border-brand-400 focus-within:ring-1 focus-within:ring-brand-400">
          <Search size={15} className="text-gray-400 flex-shrink-0" />
          <input
            type="text"
            className="flex-1 text-sm bg-transparent outline-none text-gray-900 placeholder-gray-400"
            placeholder="Search town, city or district..."
            value={query}
            onChange={e => setQuery(e.target.value)}
          />
          {query && (
            <button onClick={clearLocation} className="text-gray-400 hover:text-gray-600">
              <X size={14} />
            </button>
          )}
        </div>

        {/* Suggestions dropdown */}
        {suggestions.length > 0 && (
          <div className="absolute top-full left-0 right-0 mt-1 bg-white border border-gray-200 rounded-xl shadow-lg z-50 overflow-hidden">
            {suggestions.map((s, i) => (
              <button
                key={i}
                onClick={() => selectLocation(s)}
                className="w-full flex items-start gap-3 px-4 py-3 hover:bg-gray-50 text-left border-b border-gray-50 last:border-0"
              >
                <MapPin size={13} className="text-brand-400 mt-0.5 flex-shrink-0" />
                <div>
                  <p className="text-sm font-medium text-gray-900">{s.name}</p>
                  <p className="text-xs text-gray-400">{s.district} · {s.province}</p>
                </div>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Province / District selectors */}
      <div className="grid grid-cols-2 gap-2">
        <div>
          <label className="text-xs text-gray-500 mb-1 block">Province</label>
          <select
            className="w-full border border-gray-200 rounded-lg text-sm px-3 py-2 bg-white"
            value={selProvince}
            onChange={e => {
              setSelProvince(e.target.value)
              setSelDistrict('')
              const p = SA_LOCATIONS[e.target.value]
              if (p) setMapCenter([p.lat, p.lng])
              setZoom(7)
            }}
          >
            <option value="">All provinces</option>
            {Object.keys(SA_LOCATIONS).map(p => <option key={p} value={p}>{p}</option>)}
          </select>
        </div>
        <div>
          <label className="text-xs text-gray-500 mb-1 block">District</label>
          <select
            className="w-full border border-gray-200 rounded-lg text-sm px-3 py-2 bg-white"
            value={selDistrict}
            onChange={e => {
              setSelDistrict(e.target.value)
              const d = SA_LOCATIONS[selProvince]?.districts[e.target.value]
              if (d) { setMapCenter([d.lat, d.lng]); setZoom(10) }
            }}
            disabled={!selProvince}
          >
            <option value="">All districts</option>
            {districtOptions.map(d => <option key={d} value={d}>{d}</option>)}
          </select>
        </div>
      </div>

      {/* Map toggle */}
      <button
        onClick={() => setShowMap(v => !v)}
        className="flex items-center gap-2 text-sm text-brand-600 hover:text-brand-800 font-medium"
      >
        <MapPin size={14} />
        {showMap ? 'Hide map' : 'Show interactive map'}
      </button>

      {/* Leaflet map */}
      {showMap && (
        <div className="rounded-xl overflow-hidden border border-gray-200 shadow-sm">
          <MapContainer
            center={mapCenter}
            zoom={zoom}
            style={{ height: compact ? '250px' : '380px', width: '100%' }}
            className="z-0"
          >
            <TileLayer
              attribution='© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            />
            <MapClickHandler onMapClick={(latlng) => {
              // Snap to nearest known town
              let nearest = null
              let nearestDist = Infinity
              for (const [province, pData] of Object.entries(SA_LOCATIONS)) {
                for (const [district, dData] of Object.entries(pData.districts)) {
                  for (const town of dData.towns) {
                    const d = Math.hypot(town.lat - latlng.lat, town.lng - latlng.lng)
                    if (d < nearestDist) { nearestDist = d; nearest = { ...town, province, district, municipality: dData.municipalities[0] } }
                  }
                }
              }
              if (nearest) selectLocation(nearest)
            }} />

            {location && (
              <>
                <Marker position={[location.lat, location.lng]}>
                  <Popup>
                    <strong>{location.name}</strong><br/>
                    {location.district} · {location.province}
                  </Popup>
                </Marker>
                {showRadius && (
                  <Circle
                    center={[location.lat, location.lng]}
                    radius={radiusKm * 1000}
                    pathOptions={{ color: '#1D9E75', fillColor: '#1D9E75', fillOpacity: 0.08, weight: 2 }}
                  />
                )}
              </>
            )}

            <TownMarkers
              province={selProvince}
              district={selDistrict}
              onSelect={selectLocation}
              selected={location}
            />
          </MapContainer>

          <div className="px-3 py-2 bg-gray-50 border-t border-gray-100 text-xs text-gray-400">
            Click anywhere on the map or a marker to select a location
          </div>
        </div>
      )}

      {/* Radius slider */}
      {showRadius && location && (
        <div>
          <div className="flex items-center justify-between mb-2">
            <label className="text-sm font-medium text-gray-700">Search radius</label>
            <span className="text-sm font-semibold text-brand-600">{radiusKm} km</span>
          </div>
          <input
            type="range"
            min={25} max={500} step={25}
            value={radiusKm}
            onChange={e => onChange({ location, radiusKm: Number(e.target.value) })}
            className="w-full accent-brand-400"
          />
          <div className="flex justify-between text-xs text-gray-400 mt-1">
            <span>25 km</span>
            <span>500 km</span>
          </div>
          <div className="flex flex-wrap gap-1.5 mt-2">
            {RADIUS_OPTIONS.map(r => (
              <button
                key={r}
                onClick={() => onChange({ location, radiusKm: r })}
                className={`px-2.5 py-1 rounded-full text-xs border transition-colors ${
                  radiusKm === r
                    ? 'bg-brand-400 text-white border-brand-400'
                    : 'bg-white text-gray-600 border-gray-200 hover:border-brand-400'
                }`}
              >
                {r}km
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Preview — municipalities in radius */}
      {showPreview && location && nearbyMunicipalities.length > 0 && (
        <div className="bg-brand-50 border border-brand-200 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-2">
            <Navigation size={13} className="text-brand-600" />
            <p className="text-sm font-medium text-brand-800">
              {nearbyMunicipalities.length} municipalities within {radiusKm}km of {location.name}
            </p>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {nearbyMunicipalities.slice(0, 12).map(m => (
              <span key={m} className="px-2 py-0.5 bg-white text-brand-700 text-xs rounded-full border border-brand-200">
                {m}
              </span>
            ))}
            {nearbyMunicipalities.length > 12 && (
              <span className="text-xs text-brand-500 self-center">
                +{nearbyMunicipalities.length - 12} more
              </span>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
