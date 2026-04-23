/**
 * File: src/data/saLocations.js
 * Purpose: South Africa Geographic Data for Location-Based Features
 */

// =============================================================================
// SOUTH AFRICA GEOGRAPHIC DATA
// =============================================================================

export const SA_LOCATIONS = {
  "Gauteng": {
    lat: -26.2708, lng: 28.1123,
    districts: {
      "City of Johannesburg": {
        lat: -26.2041, lng: 28.0473,
        municipalities: ["City of Johannesburg"],
        towns: [
          { name: "Johannesburg", lat: -26.2041, lng: 28.0473 },
          { name: "Soweto", lat: -26.2677, lng: 27.8585 },
          { name: "Sandton", lat: -26.1076, lng: 28.0567 },
          { name: "Midrand", lat: -25.9975, lng: 28.1284 },
        ]
      },
      "City of Tshwane": {
        lat: -25.7479, lng: 28.2293,
        municipalities: ["City of Tshwane"],
        towns: [
          { name: "Pretoria", lat: -25.7479, lng: 28.2293 },
          { name: "Centurion", lat: -25.8601, lng: 28.1881 },
        ]
      },
      "City of Ekurhuleni": {
        lat: -26.3617, lng: 28.3570,
        municipalities: ["City of Ekurhuleni"],
        towns: [
          { name: "Germiston", lat: -26.2333, lng: 28.1667 },
          { name: "Benoni", lat: -26.1876, lng: 28.3167 },
          { name: "Boksburg", lat: -26.2167, lng: 28.2500 },
          { name: "Kempton Park", lat: -26.1000, lng: 28.2333 },
        ]
      },
      "Sedibeng": {
        lat: -26.6833, lng: 27.8833,
        municipalities: ["Emfuleni", "Lesedi", "Midvaal"],
        towns: [
          { name: "Vereeniging", lat: -26.6731, lng: 27.9264 },
          { name: "Vanderbijlpark", lat: -26.7036, lng: 27.8360 },
        ]
      },
      "West Rand": {
        lat: -26.1581, lng: 27.6172,
        municipalities: ["Mogale City", "Rand West City", "Merafong"],
        towns: [
          { name: "Krugersdorp", lat: -26.1024, lng: 27.7693 },
          { name: "Randfontein", lat: -26.1863, lng: 27.6989 },
        ]
      },
    }
  },
  "Western Cape": {
    lat: -33.2278, lng: 21.8569,
    districts: {
      "City of Cape Town": {
        lat: -33.9249, lng: 18.4241,
        municipalities: ["City of Cape Town"],
        towns: [
          { name: "Cape Town", lat: -33.9249, lng: 18.4241 },
          { name: "Stellenbosch", lat: -33.9321, lng: 18.8602 },
          { name: "Paarl", lat: -33.7333, lng: 18.9667 },
        ]
      },
      "Garden Route": {
        lat: -33.9805, lng: 22.4596,
        municipalities: ["George", "Knysna", "Mossel Bay", "Hessequa", "Kannaland", "Oudtshoorn", "Bitou"],
        towns: [
          { name: "George", lat: -33.9608, lng: 22.4614 },
          { name: "Knysna", lat: -34.0363, lng: 23.0471 },
          { name: "Mossel Bay", lat: -34.1833, lng: 22.1500 },
        ]
      },
      "Cape Winelands": {
        lat: -33.7325, lng: 19.4558,
        municipalities: ["Stellenbosch", "Drakenstein", "Witzenberg", "Langeberg", "Breede Valley"],
        towns: [
          { name: "Worcester", lat: -33.6500, lng: 19.4333 },
          { name: "Paarl", lat: -33.7333, lng: 18.9667 },
        ]
      },
    }
  },
  "KwaZulu-Natal": {
    lat: -28.5305, lng: 30.8958,
    districts: {
      "eThekwini": {
        lat: -29.8587, lng: 31.0218,
        municipalities: ["eThekwini"],
        towns: [
          { name: "Durban", lat: -29.8587, lng: 31.0218 },
          { name: "Pinetown", lat: -29.8167, lng: 30.8667 },
        ]
      },
      "uMgungundlovu": {
        lat: -29.6167, lng: 30.3833,
        municipalities: ["Msunduzi", "uMshwathi", "uMngeni", "Impendle", "Mkhambathini", "Richmond"],
        towns: [
          { name: "Pietermaritzburg", lat: -29.6167, lng: 30.3833 },
        ]
      },
      "King Cetshwayo": {
        lat: -28.7667, lng: 31.9000,
        municipalities: ["uMhlathuze", "Mthonjaneni", "Nkandla", "uMlalazi", "Mandeni"],
        towns: [
          { name: "Richards Bay", lat: -28.7667, lng: 32.0383 },
          { name: "Empangeni", lat: -28.7167, lng: 31.8833 },
        ]
      },
    }
  },
  "Eastern Cape": {
    lat: -32.2968, lng: 26.4194,
    districts: {
      "Buffalo City": {
        lat: -32.9833, lng: 27.8667,
        municipalities: ["Buffalo City"],
        towns: [
          { name: "East London", lat: -33.0153, lng: 27.9116 },
        ]
      },
      "Nelson Mandela Bay": {
        lat: -33.9608, lng: 25.6022,
        municipalities: ["Nelson Mandela Bay"],
        towns: [
          { name: "Gqeberha", lat: -33.9608, lng: 25.6022 },
        ]
      },
    }
  },
  "Free State": {
    lat: -28.4541, lng: 26.7968,
    districts: {
      "Mangaung": {
        lat: -29.1217, lng: 26.2141,
        municipalities: ["Mangaung"],
        towns: [
          { name: "Bloemfontein", lat: -29.1217, lng: 26.2141 },
        ]
      },
      "Lejweleputswa": {
        lat: -28.0333, lng: 26.7167,
        municipalities: ["Masilonyana", "Tokologo", "Tswelopele", "Matjhabeng", "Nala"],
        towns: [
          { name: "Welkom", lat: -27.9833, lng: 26.7333 },
        ]
      },
    }
  },
  "Limpopo": {
    lat: -23.4013, lng: 29.4179,
    districts: {
      "Capricorn": {
        lat: -23.8962, lng: 29.4486,
        municipalities: ["Polokwane", "Blouberg", "Molemole", "Lepelle-Nkumpi"],
        towns: [
          { name: "Polokwane", lat: -23.8962, lng: 29.4486 },
        ]
      },
      "Mopani": {
        lat: -23.9667, lng: 30.4833,
        municipalities: ["Ba-Phalaborwa", "Maruleng", "Giyani", "Letaba", "Tzaneen"],
        towns: [
          { name: "Tzaneen", lat: -23.8333, lng: 30.1500 },
        ]
      },
    }
  },
  "Mpumalanga": {
    lat: -25.5653, lng: 30.5279,
    districts: {
      "Ehlanzeni": {
        lat: -25.4745, lng: 30.9694,
        municipalities: ["Mbombela", "Nkomazi", "Thaba Chweu", "Bushbuckridge"],
        towns: [
          { name: "Nelspruit", lat: -25.4745, lng: 30.9694 },
        ]
      },
      "Nkangala": {
        lat: -25.6500, lng: 29.4500,
        municipalities: ["Victor Khanye", "Emakhazeni", "Thembisile Hani", "Dr JS Moroka", "Steve Tshwete", "Emalahleni"],
        towns: [
          { name: "Witbank", lat: -25.8833, lng: 29.2000 },
          { name: "Middelburg", lat: -25.7667, lng: 29.4667 },
        ]
      },
    }
  },
  "North West": {
    lat: -26.6638, lng: 25.2838,
    districts: {
      "Bojanala": {
        lat: -25.7000, lng: 27.2167,
        municipalities: ["Rustenburg", "Moses Kotane", "Madibeng", "Kgetlengrivier"],
        towns: [
          { name: "Rustenburg", lat: -25.6667, lng: 27.2500 },
        ]
      },
      "Ngaka Modiri Molema": {
        lat: -25.8464, lng: 25.6408,
        municipalities: ["Mahikeng", "Ditsobotla", "Tswaing", "Ramotshere Moiloa"],
        towns: [
          { name: "Mahikeng", lat: -25.8464, lng: 25.6408 },
        ]
      },
    }
  },
  "Northern Cape": {
    lat: -29.0467, lng: 22.9375,
    districts: {
      "Frances Baard": {
        lat: -28.7282, lng: 24.7499,
        municipalities: ["Sol Plaatje", "Dikgatlong", "Magareng", "Phokwane"],
        towns: [
          { name: "Kimberley", lat: -28.7282, lng: 24.7499 },
        ]
      },
      "ZF Mgcawu": {
        lat: -28.4478, lng: 21.2561,
        municipalities: ["Dawid Kruiper", "Kai !Garib", "!Kheis", "Tsantsabane", "Kgatelopele"],
        towns: [
          { name: "Upington", lat: -28.4478, lng: 21.2561 },
        ]
      },
      "Namakwa": {
        lat: -29.6642, lng: 17.8836,
        municipalities: ["Richtersveld", "Nama Khoi", "Kamiesberg", "Hantam", "Karoo Hoogland", "Khai-Ma"],
        towns: [
          { name: "Springbok", lat: -29.6642, lng: 17.8836 },
          { name: "Calvinia", lat: -31.4667, lng: 19.7667 },
        ]
      },
      "Pixley ka Seme": {
        lat: -30.6462, lng: 23.9942,
        municipalities: ["Ubuntu", "Umsobomvu", "Emthanjeni", "Kareeberg", "Renosterberg", "Thembelihle", "Siyathemba", "Siyancuma"],
        towns: [
          { name: "De Aar", lat: -30.6462, lng: 23.9942 },
          { name: "Prieska", lat: -29.6667, lng: 22.7500 },
        ]
      },
      "John Taolo Gaetsewe": {
        lat: -27.4542, lng: 23.0478,
        municipalities: ["Joe Morolong", "Gamagara", "Ga-Segonyana"],
        towns: [
          { name: "Kuruman", lat: -27.4542, lng: 23.4334 },
          { name: "Kathu", lat: -27.6952, lng: 23.0478 },
        ]
      },
    }
  },
}

// =============================================================================
// HELPER FUNCTIONS - LOCATION QUERIES
// =============================================================================

export function getProvinces() {
  return Object.keys(SA_LOCATIONS)
}

export function getDistricts(province) {
  return province ? Object.keys(SA_LOCATIONS[province]?.districts || {}) : []
}

export function getMunicipalities(province, district) {
  if (province && district) {
    return SA_LOCATIONS[province]?.districts[district]?.municipalities || []
  }
  if (province) {
    return Object.values(SA_LOCATIONS[province]?.districts || {}).flatMap(d => d.municipalities)
  }
  return Object.values(SA_LOCATIONS).flatMap(p =>
    Object.values(p.districts).flatMap(d => d.municipalities)
  )
}

export function getTowns(province, district) {
  if (province && district) {
    return SA_LOCATIONS[province]?.districts[district]?.towns || []
  }
  if (province) {
    return Object.values(SA_LOCATIONS[province]?.districts || {}).flatMap(d => d.towns)
  }
  return Object.values(SA_LOCATIONS).flatMap(p =>
    Object.values(p.districts).flatMap(d => d.towns)
  )
}

export function findTown(name) {
  if (!name) return null
  const searchName = name.toLowerCase().trim()
  for (const [province, pData] of Object.entries(SA_LOCATIONS)) {
    for (const [district, dData] of Object.entries(pData.districts)) {
      const town = dData.towns.find(t => 
        t.name.toLowerCase() === searchName ||
        t.name.toLowerCase().includes(searchName) ||
        searchName.includes(t.name.toLowerCase())
      )
      if (town) {
        return { ...town, province, district, municipality: dData.municipalities[0] }
      }
    }
  }
  return null
}

export function getProvinceCenter(province) {
  const p = SA_LOCATIONS[province]
  return p ? { lat: p.lat, lng: p.lng } : null
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

export function getMunicipalitiesWithinRadius(lat, lng, radiusKm) {
  const result = []
  for (const pData of Object.values(SA_LOCATIONS)) {
    for (const dData of Object.values(pData.districts)) {
      const dist = haversine(lat, lng, dData.lat, dData.lng)
      if (dist <= radiusKm) result.push(...dData.municipalities)
    }
  }
  return [...new Set(result)]
}

// =============================================================================
// TENDER COORDINATE LOOKUP
// =============================================================================

export function getTenderCoordinates(tender) {
  if (!tender) return null
  
  if (tender.town) {
    const town = findTown(tender.town)
    if (town) return { lat: town.lat, lng: town.lng, name: town.name, type: 'town' }
  }
  
  if (tender.municipality) {
    for (const [province, pData] of Object.entries(SA_LOCATIONS)) {
      for (const [district, dData] of Object.entries(pData.districts)) {
        const matches = dData.municipalities.some(m => 
          m.toLowerCase() === tender.municipality.toLowerCase() ||
          m.toLowerCase().includes(tender.municipality.toLowerCase()) ||
          tender.municipality.toLowerCase().includes(m.toLowerCase())
        )
        if (matches) return { lat: dData.lat, lng: dData.lng, name: tender.municipality, type: 'municipality' }
      }
    }
  }
  
  if (tender.province && SA_LOCATIONS[tender.province]) {
    const p = SA_LOCATIONS[tender.province]
    return { lat: p.lat, lng: p.lng, name: tender.province, type: 'province' }
  }
  
  return null
}

// =============================================================================
// GROUPED LOCATION PINS (FIXED EXPORTS)
// =============================================================================

/**
 * Group tenders by location coordinates
 * Returns aggregated counts for each unique location
 */
export function groupTendersByLocation(tenders) {
  const grouped = {}
  
  for (const tender of tenders) {
    const coords = getTenderCoordinates(tender)
    if (!coords) continue
    
    const key = `${coords.lat.toFixed(4)},${coords.lng.toFixed(4)}`
    
    if (!grouped[key]) {
      grouped[key] = {
        lat: coords.lat,
        lng: coords.lng,
        name: coords.name,
        type: coords.type,
        count: 0,
        tenders: []
      }
    }
    
    grouped[key].count++
    grouped[key].tenders.push(tender)
  }
  
  return Object.values(grouped)
}

/**
 * Create a marker icon for grouped location pins with count badge
 */
export function createGroupedMarkerIcon(count, type = 'town') {
  const size = count > 50 ? 44 : count > 20 ? 38 : count > 10 ? 32 : 28
  
  return {
    html: `<div style="
      position: relative;
      width: ${size}px;
      height: ${size + 6}px;
    ">
      <!-- Pin circle with count -->
      <div style="
        width: ${size}px;
        height: ${size}px;
        background: linear-gradient(135deg, #EF4444, #DC2626);
        border: 3px solid white;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        box-shadow: 0 3px 8px rgba(0,0,0,0.4);
        cursor: pointer;
        font-family: system-ui, sans-serif;
        font-weight: 700;
        font-size: ${size > 36 ? 13 : 11}px;
        color: white;
        position: relative;
        z-index: 2;
      ">${count > 99 ? '99+' : count}</div>
      <!-- Pin point (triangle) -->
      <div style="
        position: absolute;
        bottom: 0;
        left: 50%;
        transform: translateX(-50%);
        width: 0;
        height: 0;
        border-left: 6px solid transparent;
        border-right: 6px solid transparent;
        border-top: 8px solid #DC2626;
        z-index: 1;
      "></div>
      <!-- Small shadow dot -->
      <div style="
        position: absolute;
        bottom: -2px;
        left: 50%;
        transform: translateX(-50%);
        width: 8px;
        height: 4px;
        background: rgba(0,0,0,0.2);
        border-radius: 50%;
      "></div>
    </div>`,
    iconSize: [size, size + 10],
    iconAnchor: [size/2, size + 8],
    popupAnchor: [0, -(size/2) - 4],
    className: ''
  }
}

/**
 * Fetch a driving route between two points using OSRM
 * Returns an array of [lat, lng] coordinates for the route line
 */
export async function getRoute(fromLat, fromLng, toLat, toLng) {
  try {
    const url = `https://router.project-osrm.org/route/v1/driving/${fromLng},${fromLat};${toLng},${toLat}?overview=full&geometries=geojson`
    const response = await fetch(url)
    const data = await response.json()
    if (data.code === 'Ok' && data.routes.length > 0) {
      return data.routes[0].geometry.coordinates.map(([lng, lat]) => [lat, lng])
    }
    return null
  } catch {
    return null
  }
}