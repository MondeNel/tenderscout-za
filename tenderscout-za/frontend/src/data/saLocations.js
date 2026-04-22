/**
 * File: src/data/saLocations.js
 * Purpose: South Africa Geographic Data for Location-Based Features
 * 
 * This module provides comprehensive geographic data for South Africa including:
 *   - All 9 provinces with center coordinates
 *   - Districts within each province
 *   - Municipalities within each district
 *   - Major towns with latitude/longitude coordinates
 * 
 * Features:
 *   - Location picker dropdowns (Province → District → Municipality → Town)
 *   - Map markers for tender locations
 *   - Radius-based search (find tenders near user's business location)
 *   - Distance calculation between coordinates (Haversine formula)
 * 
 * The data structure is hierarchical:
 *   Province → District → Municipality → Town
 * 
 * Each level has latitude/longitude coordinates for mapping and distance calculations.
 */

// =============================================================================
// SOUTH AFRICA GEOGRAPHIC DATA
// =============================================================================
// Hierarchical structure of provinces, districts, municipalities, and towns.
// Each province has a center coordinate, and each district/town has precise coordinates.
// 
// Coordinate format: { lat: number, lng: number }
// Latitude: Negative for Southern Hemisphere (South Africa is ~ -22° to -35°)
// Longitude: Positive for Eastern Hemisphere (South Africa is ~ 16° to 33°)

export const SA_LOCATIONS = {
  // ===========================================================================
  // GAUTENG - Economic Hub
  // ===========================================================================
  // Population: ~15 million | Major cities: Johannesburg, Pretoria
  "Gauteng": {
    lat: -26.2708, lng: 28.1123,  // Centered near Johannesburg
    districts: {
      "City of Johannesburg": {
        lat: -26.2041, lng: 28.0473,
        municipalities: ["City of Johannesburg"],
        towns: [
          { name: "Johannesburg", lat: -26.2041, lng: 28.0473 },  // CBD
          { name: "Soweto", lat: -26.2677, lng: 27.8585 },        // Largest township
          { name: "Sandton", lat: -26.1076, lng: 28.0567 },       // Financial district
          { name: "Midrand", lat: -25.9975, lng: 28.1284 },       // Between JHB and PTA
        ]
      },
      "City of Tshwane": {
        lat: -25.7479, lng: 28.2293,
        municipalities: ["City of Tshwane"],
        towns: [
          { name: "Pretoria", lat: -25.7479, lng: 28.2293 },      // Administrative capital
          { name: "Centurion", lat: -25.8601, lng: 28.1881 },     // Between JHB and PTA
        ]
      },
      "City of Ekurhuleni": {
        lat: -26.3617, lng: 28.3570,
        municipalities: ["City of Ekurhuleni"],
        towns: [
          { name: "Germiston", lat: -26.2333, lng: 28.1667 },     // Industrial hub
          { name: "Benoni", lat: -26.1876, lng: 28.3167 },        // East Rand
          { name: "Boksburg", lat: -26.2167, lng: 28.2500 },      // Mining history
        ]
      },
      "Sedibeng": {
        lat: -26.6833, lng: 27.8833,
        municipalities: ["Emfuleni", "Lesedi", "Midvaal"],
        towns: [
          { name: "Vereeniging", lat: -26.6731, lng: 27.9264 },   // Vaal Triangle
          { name: "Vanderbijlpark", lat: -26.7036, lng: 27.8360 }, // Steel industry
        ]
      },
      "West Rand": {
        lat: -26.1581, lng: 27.6172,
        municipalities: ["Mogale City", "Rand West City"],
        towns: [
          { name: "Krugersdorp", lat: -26.1024, lng: 27.7693 },   // Mining town
          { name: "Randfontein", lat: -26.1863, lng: 27.6989 },   // Gold mining
        ]
      },
    }
  },
  
  // ===========================================================================
  // WESTERN CAPE - Coastal Province
  // ===========================================================================
  // Population: ~7 million | Major cities: Cape Town, Stellenbosch
  "Western Cape": {
    lat: -33.2278, lng: 21.8569,  // Centered in the Karoo region
    districts: {
      "City of Cape Town": {
        lat: -33.9249, lng: 18.4241,
        municipalities: ["City of Cape Town"],
        towns: [
          { name: "Cape Town", lat: -33.9249, lng: 18.4241 },     // Mother City
          { name: "Stellenbosch", lat: -33.9321, lng: 18.8602 },  // Wine region
          { name: "Paarl", lat: -33.7333, lng: 18.9667 },         // Wine valley
        ]
      },
      "Garden Route": {
        lat: -33.9805, lng: 22.4596,
        municipalities: ["George", "Knysna", "Mossel Bay", "Hessequa", "Kannaland", "Oudtshoorn", "Bitou"],
        towns: [
          { name: "George", lat: -33.9608, lng: 22.4614 },        // Garden Route hub
          { name: "Knysna", lat: -34.0363, lng: 23.0471 },        // Lagoon town
          { name: "Mossel Bay", lat: -34.1833, lng: 22.1500 },    // Historic port
        ]
      },
      "Cape Winelands": {
        lat: -33.7325, lng: 19.4558,
        municipalities: ["Stellenbosch", "Drakenstein", "Witzenberg", "Langeberg", "Breede Valley"],
        towns: [
          { name: "Worcester", lat: -33.6500, lng: 19.4333 },     // Wine production
          { name: "Paarl", lat: -33.7333, lng: 18.9667 },
        ]
      },
    }
  },
  
  // ===========================================================================
  // KWAZULU-NATAL - East Coast Province
  // ===========================================================================
  // Population: ~11 million | Major cities: Durban, Pietermaritzburg
  "KwaZulu-Natal": {
    lat: -28.5305, lng: 30.8958,  // Centered near Tugela River
    districts: {
      "eThekwini": {
        lat: -29.8587, lng: 31.0218,
        municipalities: ["eThekwini"],
        towns: [
          { name: "Durban", lat: -29.8587, lng: 31.0218 },        // Major port city
          { name: "Pinetown", lat: -29.8167, lng: 30.8667 },      // Industrial suburb
        ]
      },
      "uMgungundlovu": {
        lat: -29.6167, lng: 30.3833,
        municipalities: ["Msunduzi", "uMshwathi", "uMngeni", "Impendle", "Mkhambathini", "Richmond"],
        towns: [
          { name: "Pietermaritzburg", lat: -29.6167, lng: 30.3833 }, // Capital city
        ]
      },
      "King Cetshwayo": {
        lat: -28.7667, lng: 31.9000,
        municipalities: ["uMhlathuze", "Mthonjaneni", "Nkandla", "uMlalazi", "Mandeni"],
        towns: [
          { name: "Richards Bay", lat: -28.7667, lng: 32.0383 },  // Deep-water port
          { name: "Empangeni", lat: -28.7167, lng: 31.8833 },     // Sugar industry
        ]
      },
    }
  },
  
  // ===========================================================================
  // EASTERN CAPE - Coastal Province
  // ===========================================================================
  // Population: ~7 million | Major cities: Gqeberha (Port Elizabeth), East London
  "Eastern Cape": {
    lat: -32.2968, lng: 26.4194,
    districts: {
      "Buffalo City": {
        lat: -32.9833, lng: 27.8667,
        municipalities: ["Buffalo City"],
        towns: [
          { name: "East London", lat: -33.0153, lng: 27.9116 },   // River port
          { name: "King Williams Town", lat: -32.8833, lng: 27.4000 },
        ]
      },
      "Nelson Mandela Bay": {
        lat: -33.9608, lng: 25.6022,
        municipalities: ["Nelson Mandela Bay"],
        towns: [
          { name: "Gqeberha", lat: -33.9608, lng: 25.6022 },      // Former Port Elizabeth
          { name: "Uitenhage", lat: -33.7500, lng: 25.4000 },     // Automotive industry
        ]
      },
      "Sarah Baartman": {
        lat: -33.3000, lng: 25.5667,
        municipalities: ["Makana", "Ndlambe", "Sunday River Valley", "Kouga", "Kou-Kamma", "Ikwezi", "Camdeboo", "Blue Crane Route"],
        towns: [
          { name: "Makhanda", lat: -33.3000, lng: 26.5167 },      // Former Grahamstown
          { name: "Graaff-Reinet", lat: -32.2500, lng: 24.5333 }, // Historic town
        ]
      },
    }
  },
  
  // ===========================================================================
  // FREE STATE - Central Province
  // ===========================================================================
  // Population: ~3 million | Major cities: Bloemfontein, Welkom
  "Free State": {
    lat: -28.4541, lng: 26.7968,
    districts: {
      "Mangaung": {
        lat: -29.1217, lng: 26.2141,
        municipalities: ["Mangaung"],
        towns: [
          { name: "Bloemfontein", lat: -29.1217, lng: 26.2141 },  // Judicial capital
          { name: "Botshabelo", lat: -29.2667, lng: 26.7167 },    // Township
        ]
      },
      "Lejweleputswa": {
        lat: -28.0333, lng: 26.7167,
        municipalities: ["Masilonyana", "Tokologo", "Tswelopele", "Matjhabeng", "Nala"],
        towns: [
          { name: "Welkom", lat: -27.9833, lng: 26.7333 },        // Gold mining
          { name: "Odendaalsrus", lat: -27.8667, lng: 26.6833 },  // Gold mining
        ]
      },
    }
  },
  
  // ===========================================================================
  // LIMPOPO - Northern Province
  // ===========================================================================
  // Population: ~6 million | Major cities: Polokwane, Tzaneen
  "Limpopo": {
    lat: -23.4013, lng: 29.4179,
    districts: {
      "Capricorn": {
        lat: -23.8962, lng: 29.4486,
        municipalities: ["Polokwane", "Blouberg", "Molemole", "Lepelle-Nkumpi"],
        towns: [
          { name: "Polokwane", lat: -23.8962, lng: 29.4486 },     // Capital city
        ]
      },
      "Mopani": {
        lat: -23.9667, lng: 30.4833,
        municipalities: ["Ba-Phalaborwa", "Maruleng", "Giyani", "Letaba", "Tzaneen"],
        towns: [
          { name: "Tzaneen", lat: -23.8333, lng: 30.1500 },       // Tropical fruit
          { name: "Phalaborwa", lat: -23.9500, lng: 31.1333 },    // Mining (copper)
        ]
      },
      "Waterberg": {
        lat: -24.1167, lng: 27.9167,
        municipalities: ["Bela-Bela", "Modimolle-Mookgophong", "Mogalakwena", "Lephalale", "Thabazimbi"],
        towns: [
          { name: "Mokopane", lat: -24.1833, lng: 29.0000 },      // Platinum mining
          { name: "Lephalale", lat: -23.6833, lng: 27.7000 },     // Coal mining
        ]
      },
    }
  },
  
  // ===========================================================================
  // MPUMALANGA - Eastern Province
  // ===========================================================================
  // Population: ~5 million | Major cities: Nelspruit, Witbank
  "Mpumalanga": {
    lat: -25.5653, lng: 30.5279,
    districts: {
      "Ehlanzeni": {
        lat: -25.4745, lng: 30.9694,
        municipalities: ["Mbombela", "Nkomazi", "Thaba Chweu", "Bushbuckridge"],
        towns: [
          { name: "Nelspruit", lat: -25.4745, lng: 30.9694 },     // Capital, Kruger Park gateway
          { name: "White River", lat: -25.3333, lng: 31.0167 },   // Agriculture
        ]
      },
      "Nkangala": {
        lat: -25.6500, lng: 29.4500,
        municipalities: ["Victor Khanye", "Emakhazeni", "Thembisile Hani", "Dr JS Moroka", "Steve Tshwete", "Emalahleni"],
        towns: [
          { name: "Witbank", lat: -25.8833, lng: 29.2000 },       // Coal mining (now Emalahleni)
          { name: "Middelburg", lat: -25.7667, lng: 29.4667 },    // Steel/coal
          { name: "Secunda", lat: -26.5167, lng: 29.2000 },       // Sasol (synthetic fuel)
        ]
      },
    }
  },
  
  // ===========================================================================
  // NORTH WEST - Mining Province
  // ===========================================================================
  // Population: ~4 million | Major cities: Rustenburg, Mahikeng
  "North West": {
    lat: -26.6638, lng: 25.2838,
    districts: {
      "Bojanala": {
        lat: -25.7000, lng: 27.2167,
        municipalities: ["Rustenburg", "Moses Kotane", "Madibeng", "Kgetlengrivier"],
        towns: [
          { name: "Rustenburg", lat: -25.6667, lng: 27.2500 },    // Platinum mining
          { name: "Brits", lat: -25.6333, lng: 27.7667 },         // Platinum mining
        ]
      },
      "Ngaka Modiri Molema": {
        lat: -25.8464, lng: 25.6408,
        municipalities: ["Mahikeng", "Ditsobotla", "Tswaing", "Ramotshere Moiloa"],
        towns: [
          { name: "Mahikeng", lat: -25.8464, lng: 25.6408 },      // Provincial capital
        ]
      },
      "Dr Kenneth Kaunda": {
        lat: -26.7167, lng: 26.9833,
        municipalities: ["JB Marks", "Maquassi Hills"],
        towns: [
          { name: "Klerksdorp", lat: -26.8667, lng: 26.6667 },    // Gold mining
          { name: "Potchefstroom", lat: -26.7167, lng: 27.1000 }, // University town
        ]
      },
    }
  },
  
  // ===========================================================================
  // NORTHERN CAPE - Largest, Least Populated
  // ===========================================================================
  // Population: ~1.3 million | Major cities: Kimberley, Upington
  "Northern Cape": {
    lat: -29.0467, lng: 22.9375,
    districts: {
      "Frances Baard": {
        lat: -28.7282, lng: 24.7499,
        municipalities: ["Sol Plaatje", "Dikgatlong", "Magareng", "Phokwane"],
        towns: [
          { name: "Kimberley", lat: -28.7282, lng: 24.7499 },     // Diamond capital
          { name: "Barkly West", lat: -28.5333, lng: 24.5167 },   // Diamond mining
          { name: "Warrenton", lat: -28.1167, lng: 24.8667 },     // Agriculture
          { name: "Hartswater", lat: -27.7667, lng: 24.8167 },    // Irrigation scheme
        ]
      },
      "ZF Mgcawu": {
        lat: -28.4478, lng: 21.2561,
        municipalities: ["Dawid Kruiper", "Kai Garib", "Khara Hais", "Kheis", "Tsantsabane"],
        towns: [
          { name: "Upington", lat: -28.4478, lng: 21.2561 },      // Wine, dried fruit
          { name: "Kakamas", lat: -28.7667, lng: 20.6167 },       // Vineyards
          { name: "Groblershoop", lat: -28.8833, lng: 22.0000 },  // Wine
          { name: "Postmasburg", lat: -28.3500, lng: 23.0833 },   // Manganese mining
        ]
      },
      "Namakwa": {
        lat: -29.6642, lng: 17.8836,
        municipalities: ["Richtersveld", "Nama Khoi", "Kamiesberg", "Hantam", "Karoo Hoogland", "Khai-Ma"],
        towns: [
          { name: "Springbok", lat: -29.6642, lng: 17.8836 },     // Copper mining
          { name: "Port Nolloth", lat: -29.2500, lng: 16.8667 },  // Coastal town
          { name: "Garies", lat: -30.5667, lng: 17.9833 },        // Agriculture
          { name: "Calvinia", lat: -31.4667, lng: 19.7667 },      // Sheep farming
          { name: "Sutherland", lat: -32.4000, lng: 20.6667 },    // Observatory (SALT)
          { name: "Pofadder", lat: -29.1333, lng: 19.4000 },      // Remote town
        ]
      },
      "Pixley ka Seme": {
        lat: -30.6462, lng: 23.9942,
        municipalities: ["Ubuntu", "Umsobomvu", "Emthanjeni", "Kareeberg", "Renosterberg", "Thembelihle", "Siyathemba", "Siyancuma"],
        towns: [
          { name: "De Aar", lat: -30.6462, lng: 23.9942 },        // Railway junction
          { name: "Colesberg", lat: -30.7167, lng: 25.1000 },     // Historic town
          { name: "Victoria West", lat: -31.4000, lng: 23.1333 }, // Karoo town
          { name: "Carnarvon", lat: -30.9667, lng: 22.1333 },     // SKA telescope
          { name: "Petrusville", lat: -30.0833, lng: 24.6833 },   // Dam nearby
          { name: "Hopetown", lat: -29.6167, lng: 24.0833 },      // First diamond found
          { name: "Prieska", lat: -29.6667, lng: 22.7500 },       // Copper/zinc mining
          { name: "Douglas", lat: -29.0500, lng: 23.7667 },       // Confluence of rivers
        ]
      },
      "John Taolo Gaetsewe": {
        lat: -27.4542, lng: 23.0478,
        municipalities: ["Joe Morolong", "Gamagara", "Ga-Segonyana"],
        towns: [
          { name: "Kuruman", lat: -27.4542, lng: 23.4334 },       // Oasis town
          { name: "Kathu", lat: -27.6952, lng: 23.0478 },         // Iron ore mining
        ]
      },
    }
  },
}

// =============================================================================
// HELPER FUNCTIONS
// =============================================================================

/**
 * Get all province names
 * @returns {string[]} Array of province names
 */
export function getProvinces() {
  return Object.keys(SA_LOCATIONS)
}

/**
 * Get districts for a specific province
 * @param {string} province - Province name
 * @returns {string[]} Array of district names
 */
export function getDistricts(province) {
  return province ? Object.keys(SA_LOCATIONS[province]?.districts || {}) : []
}

/**
 * Get municipalities for a province and optional district
 * @param {string} province - Province name
 * @param {string} district - District name (optional)
 * @returns {string[]} Array of municipality names
 */
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

/**
 * Get towns for a province and optional district
 * @param {string} province - Province name
 * @param {string} district - District name (optional)
 * @returns {Array} Array of town objects { name, lat, lng }
 */
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

/**
 * Find a town by name (case-insensitive)
 * @param {string} name - Town name to search for
 * @returns {Object|null} Town object with province and district info
 */
export function findTown(name) {
  for (const [province, pData] of Object.entries(SA_LOCATIONS)) {
    for (const [district, dData] of Object.entries(pData.districts)) {
      const town = dData.towns.find(t => t.name.toLowerCase() === name.toLowerCase())
      if (town) {
        return { ...town, province, district, municipality: dData.municipalities[0] }
      }
    }
  }
  return null
}

/**
 * Get the center coordinates of a province
 * @param {string} province - Province name
 * @returns {Object|null} { lat, lng } or null if not found
 */
export function getProvinceCenter(province) {
  const p = SA_LOCATIONS[province]
  return p ? { lat: p.lat, lng: p.lng } : null
}

// =============================================================================
// DISTANCE CALCULATION (Haversine Formula)
// =============================================================================

/**
 * Calculate the great-circle distance between two coordinates
 * using the Haversine formula.
 * 
 * @param {number} lat1 - Latitude of first point
 * @param {number} lng1 - Longitude of first point
 * @param {number} lat2 - Latitude of second point
 * @param {number} lng2 - Longitude of second point
 * @returns {number} Distance in kilometers
 */
function haversine(lat1, lng1, lat2, lng2) {
  const R = 6371  // Earth's radius in kilometers
  
  // Convert degrees to radians
  const dLat = (lat2 - lat1) * Math.PI / 180
  const dLng = (lng2 - lng1) * Math.PI / 180
  
  // Haversine formula
  const a = Math.sin(dLat/2)**2 + 
            Math.cos(lat1*Math.PI/180) * Math.cos(lat2*Math.PI/180) * 
            Math.sin(dLng/2)**2
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a))
  
  return R * c
}

/**
 * Get all municipalities within a radius of a point
 * Used for location-based tender filtering.
 * 
 * @param {number} lat - Center latitude
 * @param {number} lng - Center longitude
 * @param {number} radiusKm - Search radius in kilometers
 * @returns {string[]} Array of municipality names within radius
 */
export function getMunicipalitiesWithinRadius(lat, lng, radiusKm) {
  const result = []
  for (const pData of Object.values(SA_LOCATIONS)) {
    for (const dData of Object.values(pData.districts)) {
      const dist = haversine(lat, lng, dData.lat, dData.lng)
      if (dist <= radiusKm) {
        result.push(...dData.municipalities)
      }
    }
  }
  return [...new Set(result)]  // Remove duplicates
}

/**
 * Get all towns within a radius of a point
 * Used for location-based tender filtering and map markers.
 * 
 * @param {number} lat - Center latitude
 * @param {number} lng - Center longitude
 * @param {number} radiusKm - Search radius in kilometers
 * @returns {Object[]} Array of town objects within radius
 */
export function getTownsWithinRadius(lat, lng, radiusKm) {
  const result = []
  for (const pData of Object.values(SA_LOCATIONS)) {
    for (const dData of Object.values(pData.districts)) {
      for (const town of dData.towns) {
        const dist = haversine(lat, lng, town.lat, town.lng)
        if (dist <= radiusKm) {
          result.push(town)
        }
      }
    }
  }
  return result
}