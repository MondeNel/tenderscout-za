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
 *   - Map markers for tender locations (district aggregates + individual pins)
 *   - Radius-based search (find tenders near user's business location)
 *   - Distance calculation between coordinates (Haversine formula)
 *   - Tender coordinate lookup (town → municipality → province fallback)
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
          { name: "Randburg", lat: -26.0936, lng: 27.9944 },
          { name: "Roodepoort", lat: -26.1625, lng: 27.8725 },
        ]
      },
      "City of Tshwane": {
        lat: -25.7479, lng: 28.2293,
        municipalities: ["City of Tshwane"],
        towns: [
          { name: "Pretoria", lat: -25.7479, lng: 28.2293 },
          { name: "Centurion", lat: -25.8601, lng: 28.1881 },
          { name: "Hammanskraal", lat: -25.4000, lng: 28.2833 },
          { name: "Soshanguve", lat: -25.5167, lng: 28.1000 },
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
          { name: "Alberton", lat: -26.2672, lng: 28.1219 },
          { name: "Springs", lat: -26.2500, lng: 28.4333 },
        ]
      },
      "Sedibeng": {
        lat: -26.6833, lng: 27.8833,
        municipalities: ["Emfuleni", "Lesedi", "Midvaal"],
        towns: [
          { name: "Vereeniging", lat: -26.6731, lng: 27.9264 },
          { name: "Vanderbijlpark", lat: -26.7036, lng: 27.8360 },
          { name: "Heidelberg", lat: -26.5000, lng: 28.3500 },
          { name: "Meyerton", lat: -26.5500, lng: 28.0167 },
        ]
      },
      "West Rand": {
        lat: -26.1581, lng: 27.6172,
        municipalities: ["Mogale City", "Rand West City", "Merafong"],
        towns: [
          { name: "Krugersdorp", lat: -26.1024, lng: 27.7693 },
          { name: "Randfontein", lat: -26.1863, lng: 27.6989 },
          { name: "Westonaria", lat: -26.3167, lng: 27.6500 },
          { name: "Carletonville", lat: -26.3667, lng: 27.4000 },
        ]
      },
    }
  },
  
  // ===========================================================================
  // WESTERN CAPE - Coastal Province
  // ===========================================================================
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
          { name: "Bellville", lat: -33.9000, lng: 18.6333 },
          { name: "Khayelitsha", lat: -34.0400, lng: 18.6778 },
          { name: "Mitchells Plain", lat: -34.0500, lng: 18.6167 },
        ]
      },
      "Garden Route": {
        lat: -33.9805, lng: 22.4596,
        municipalities: ["George", "Knysna", "Mossel Bay", "Hessequa", "Kannaland", "Oudtshoorn", "Bitou"],
        towns: [
          { name: "George", lat: -33.9608, lng: 22.4614 },
          { name: "Knysna", lat: -34.0363, lng: 23.0471 },
          { name: "Mossel Bay", lat: -34.1833, lng: 22.1500 },
          { name: "Oudtshoorn", lat: -33.5833, lng: 22.2000 },
          { name: "Plettenberg Bay", lat: -34.0500, lng: 23.3667 },
        ]
      },
      "Cape Winelands": {
        lat: -33.7325, lng: 19.4558,
        municipalities: ["Stellenbosch", "Drakenstein", "Witzenberg", "Langeberg", "Breede Valley"],
        towns: [
          { name: "Worcester", lat: -33.6500, lng: 19.4333 },
          { name: "Paarl", lat: -33.7333, lng: 18.9667 },
          { name: "Wellington", lat: -33.6333, lng: 19.0000 },
          { name: "Ceres", lat: -33.3667, lng: 19.3167 },
        ]
      },
      "Overberg": {
        lat: -34.4167, lng: 19.5000,
        municipalities: ["Theewaterskloof", "Overstrand", "Cape Agulhas", "Swellendam"],
        towns: [
          { name: "Hermanus", lat: -34.4167, lng: 19.2333 },
          { name: "Swellendam", lat: -34.0333, lng: 20.4333 },
          { name: "Caledon", lat: -34.2333, lng: 19.4333 },
        ]
      },
      "West Coast": {
        lat: -32.8333, lng: 18.5000,
        municipalities: ["Saldanha Bay", "Swartland", "Bergrivier", "Matzikama", "Cederberg"],
        towns: [
          { name: "Saldanha", lat: -33.0167, lng: 17.9500 },
          { name: "Vredenburg", lat: -32.9000, lng: 17.9833 },
          { name: "Malmesbury", lat: -33.4500, lng: 18.7333 },
          { name: "Vredendal", lat: -31.6667, lng: 18.5000 },
        ]
      },
    }
  },
  
  // ===========================================================================
  // KWAZULU-NATAL - East Coast Province
  // ===========================================================================
  "KwaZulu-Natal": {
    lat: -28.5305, lng: 30.8958,
    districts: {
      "eThekwini": {
        lat: -29.8587, lng: 31.0218,
        municipalities: ["eThekwini"],
        towns: [
          { name: "Durban", lat: -29.8587, lng: 31.0218 },
          { name: "Pinetown", lat: -29.8167, lng: 30.8667 },
          { name: "Umhlanga", lat: -29.7167, lng: 31.0667 },
          { name: "Phoenix", lat: -29.7000, lng: 31.0000 },
          { name: "Umlazi", lat: -29.9667, lng: 30.8833 },
        ]
      },
      "uMgungundlovu": {
        lat: -29.6167, lng: 30.3833,
        municipalities: ["Msunduzi", "uMshwathi", "uMngeni", "Impendle", "Mkhambathini", "Richmond"],
        towns: [
          { name: "Pietermaritzburg", lat: -29.6167, lng: 30.3833 },
          { name: "Howick", lat: -29.4833, lng: 30.2333 },
        ]
      },
      "King Cetshwayo": {
        lat: -28.7667, lng: 31.9000,
        municipalities: ["uMhlathuze", "Mthonjaneni", "Nkandla", "uMlalazi", "Mandeni"],
        towns: [
          { name: "Richards Bay", lat: -28.7667, lng: 32.0383 },
          { name: "Empangeni", lat: -28.7167, lng: 31.8833 },
          { name: "Eshowe", lat: -28.8833, lng: 31.4667 },
        ]
      },
      "Ugu": {
        lat: -30.7500, lng: 30.4500,
        municipalities: ["Ray Nkonyeni", "uMdoni", "Umzumbe", "uMuziwabantu"],
        towns: [
          { name: "Port Shepstone", lat: -30.7500, lng: 30.4500 },
          { name: "Margate", lat: -30.8500, lng: 30.3667 },
          { name: "Harding", lat: -30.5833, lng: 29.8833 },
        ]
      },
      "Zululand": {
        lat: -27.8333, lng: 31.4167,
        municipalities: ["Ulundi", "Nongoma", "AbaQulusi", "eDumbe", "uPhongolo"],
        towns: [
          { name: "Ulundi", lat: -28.3333, lng: 31.4167 },
          { name: "Vryheid", lat: -27.7667, lng: 30.8000 },
        ]
      },
      "Harry Gwala": {
        lat: -30.1333, lng: 29.8167,
        municipalities: ["Dr Nkosazana Dlamini-Zuma", "Ubuhlebezwe", "Greater Kokstad", "Umzimkhulu"],
        towns: [
          { name: "Kokstad", lat: -30.5500, lng: 29.4333 },
          { name: "Ixopo", lat: -30.1500, lng: 30.0833 },
        ]
      },
    }
  },
  
  // ===========================================================================
  // EASTERN CAPE - Coastal Province
  // ===========================================================================
  "Eastern Cape": {
    lat: -32.2968, lng: 26.4194,
    districts: {
      "Buffalo City": {
        lat: -32.9833, lng: 27.8667,
        municipalities: ["Buffalo City"],
        towns: [
          { name: "East London", lat: -33.0153, lng: 27.9116 },
          { name: "King Williams Town", lat: -32.8833, lng: 27.4000 },
          { name: "Mdantsane", lat: -32.9333, lng: 27.7333 },
        ]
      },
      "Nelson Mandela Bay": {
        lat: -33.9608, lng: 25.6022,
        municipalities: ["Nelson Mandela Bay"],
        towns: [
          { name: "Gqeberha", lat: -33.9608, lng: 25.6022 },
          { name: "Uitenhage", lat: -33.7500, lng: 25.4000 },
          { name: "Despatch", lat: -33.8000, lng: 25.4667 },
        ]
      },
      "Sarah Baartman": {
        lat: -33.3000, lng: 25.5667,
        municipalities: ["Makana", "Ndlambe", "Sunday River Valley", "Kouga", "Kou-Kamma", "Ikwezi", "Camdeboo", "Blue Crane Route"],
        towns: [
          { name: "Makhanda", lat: -33.3000, lng: 26.5167 },
          { name: "Graaff-Reinet", lat: -32.2500, lng: 24.5333 },
          { name: "Jeffreys Bay", lat: -34.0333, lng: 24.9167 },
          { name: "Port Alfred", lat: -33.6000, lng: 26.8833 },
        ]
      },
      "Chris Hani": {
        lat: -31.9000, lng: 26.8833,
        municipalities: ["Enoch Mgijima", "Intsika Yethu", "Emalahleni", "Engcobo", "Sakhisizwe", "Inxuba Yethemba"],
        towns: [
          { name: "Queenstown", lat: -31.9000, lng: 26.8833 },
          { name: "Cradock", lat: -32.1667, lng: 25.6167 },
          { name: "Dordrecht", lat: -31.3667, lng: 27.0500 },
        ]
      },
      "Joe Gqabi": {
        lat: -30.9833, lng: 26.8333,
        municipalities: ["Senqu", "Walter Sisulu", "Elundini"],
        towns: [
          { name: "Aliwal North", lat: -30.7000, lng: 26.7000 },
          { name: "Barkly East", lat: -30.9667, lng: 27.5833 },
          { name: "Maclear", lat: -31.0667, lng: 28.3500 },
        ]
      },
      "O.R. Tambo": {
        lat: -31.5833, lng: 28.7833,
        municipalities: ["King Sabata Dalindyebo", "Nyandeni", "Mhlontlo", "Port St Johns", "Ingquza Hill"],
        towns: [
          { name: "Mthatha", lat: -31.5833, lng: 28.7833 },
          { name: "Port St Johns", lat: -31.6333, lng: 29.5500 },
          { name: "Lusikisiki", lat: -31.3667, lng: 29.5833 },
        ]
      },
      "Alfred Nzo": {
        lat: -30.7333, lng: 29.4167,
        municipalities: ["Matatiele", "Umzimvubu", "Winnie Madikizela-Mandela", "Ntabankulu"],
        towns: [
          { name: "Matatiele", lat: -30.3333, lng: 28.8000 },
          { name: "Mount Frere", lat: -30.9000, lng: 28.9833 },
          { name: "Bizana", lat: -30.8500, lng: 29.8500 },
        ]
      },
      "Amathole": {
        lat: -32.7000, lng: 27.2000,
        municipalities: ["Amahlathi", "Great Kei", "Mbhashe", "Mnquma", "Ngqushwa", "Raymond Mhlaba"],
        towns: [
          { name: "Stutterheim", lat: -32.5667, lng: 27.4167 },
          { name: "Butterworth", lat: -32.3333, lng: 28.1500 },
          { name: "Fort Beaufort", lat: -32.7833, lng: 26.6333 },
        ]
      },
    }
  },
  
  // ===========================================================================
  // FREE STATE - Central Province
  // ===========================================================================
  "Free State": {
    lat: -28.4541, lng: 26.7968,
    districts: {
      "Mangaung": {
        lat: -29.1217, lng: 26.2141,
        municipalities: ["Mangaung"],
        towns: [
          { name: "Bloemfontein", lat: -29.1217, lng: 26.2141 },
          { name: "Botshabelo", lat: -29.2667, lng: 26.7167 },
          { name: "Thaba Nchu", lat: -29.2167, lng: 26.8333 },
        ]
      },
      "Lejweleputswa": {
        lat: -28.0333, lng: 26.7167,
        municipalities: ["Masilonyana", "Tokologo", "Tswelopele", "Matjhabeng", "Nala"],
        towns: [
          { name: "Welkom", lat: -27.9833, lng: 26.7333 },
          { name: "Odendaalsrus", lat: -27.8667, lng: 26.6833 },
          { name: "Virginia", lat: -28.1167, lng: 26.9000 },
        ]
      },
      "Fezile Dabi": {
        lat: -26.8333, lng: 27.8000,
        municipalities: ["Metsimaholo", "Mafube", "Ngwathe", "Moqhaka"],
        towns: [
          { name: "Sasolburg", lat: -26.8167, lng: 27.8167 },
          { name: "Parys", lat: -26.9000, lng: 27.4500 },
          { name: "Kroonstad", lat: -27.6500, lng: 27.2333 },
        ]
      },
      "Thabo Mofutsanyana": {
        lat: -28.5000, lng: 29.0000,
        municipalities: ["Dihlabeng", "Maluti-a-Phofung", "Mantsopa", "Phumelela", "Setsoto"],
        towns: [
          { name: "Phuthaditjhaba", lat: -28.5333, lng: 28.8167 },
          { name: "Bethlehem", lat: -28.2333, lng: 28.3000 },
          { name: "Harrismith", lat: -28.2833, lng: 29.1333 },
        ]
      },
      "Xhariep": {
        lat: -30.2500, lng: 25.6667,
        municipalities: ["Letsemeng", "Kopanong", "Mohokare"],
        towns: [
          { name: "Trompsburg", lat: -30.0333, lng: 25.7833 },
          { name: "Zastron", lat: -30.3000, lng: 27.0833 },
        ]
      },
    }
  },
  
  // ===========================================================================
  // LIMPOPO - Northern Province
  // ===========================================================================
  "Limpopo": {
    lat: -23.4013, lng: 29.4179,
    districts: {
      "Capricorn": {
        lat: -23.8962, lng: 29.4486,
        municipalities: ["Polokwane", "Blouberg", "Molemole", "Lepelle-Nkumpi"],
        towns: [
          { name: "Polokwane", lat: -23.8962, lng: 29.4486 },
          { name: "Seshego", lat: -23.8500, lng: 29.3833 },
        ]
      },
      "Mopani": {
        lat: -23.9667, lng: 30.4833,
        municipalities: ["Ba-Phalaborwa", "Maruleng", "Giyani", "Letaba", "Tzaneen"],
        towns: [
          { name: "Tzaneen", lat: -23.8333, lng: 30.1500 },
          { name: "Phalaborwa", lat: -23.9500, lng: 31.1333 },
          { name: "Giyani", lat: -23.3167, lng: 30.7167 },
        ]
      },
      "Waterberg": {
        lat: -24.1167, lng: 27.9167,
        municipalities: ["Bela-Bela", "Modimolle-Mookgophong", "Mogalakwena", "Lephalale", "Thabazimbi"],
        towns: [
          { name: "Mokopane", lat: -24.1833, lng: 29.0000 },
          { name: "Lephalale", lat: -23.6833, lng: 27.7000 },
          { name: "Bela-Bela", lat: -24.8833, lng: 28.2833 },
          { name: "Modimolle", lat: -24.7000, lng: 28.4000 },
        ]
      },
      "Vhembe": {
        lat: -22.9833, lng: 30.4167,
        municipalities: ["Thulamela", "Makhado", "Musina", "Collins Chabane"],
        towns: [
          { name: "Thohoyandou", lat: -22.9500, lng: 30.4833 },
          { name: "Makhado", lat: -23.0500, lng: 29.9000 },
          { name: "Musina", lat: -22.3333, lng: 30.0333 },
        ]
      },
      "Sekhukhune": {
        lat: -24.5000, lng: 29.8000,
        municipalities: ["Elias Motsoaledi", "Ephraim Mogale", "Fetakgomo Tubatse", "Makhuduthamaga"],
        towns: [
          { name: "Groblersdal", lat: -25.1667, lng: 29.4000 },
          { name: "Burgersfort", lat: -24.6667, lng: 30.3167 },
        ]
      },
    }
  },
  
  // ===========================================================================
  // MPUMALANGA - Eastern Province
  // ===========================================================================
  "Mpumalanga": {
    lat: -25.5653, lng: 30.5279,
    districts: {
      "Ehlanzeni": {
        lat: -25.4745, lng: 30.9694,
        municipalities: ["Mbombela", "Nkomazi", "Thaba Chweu", "Bushbuckridge"],
        towns: [
          { name: "Nelspruit", lat: -25.4745, lng: 30.9694 },
          { name: "White River", lat: -25.3333, lng: 31.0167 },
          { name: "Malelane", lat: -25.4833, lng: 31.5167 },
          { name: "Sabie", lat: -25.1000, lng: 30.7833 },
          { name: "Hazyview", lat: -25.0500, lng: 31.1333 },
        ]
      },
      "Nkangala": {
        lat: -25.6500, lng: 29.4500,
        municipalities: ["Victor Khanye", "Emakhazeni", "Thembisile Hani", "Dr JS Moroka", "Steve Tshwete", "Emalahleni"],
        towns: [
          { name: "Witbank", lat: -25.8833, lng: 29.2000 },
          { name: "Middelburg", lat: -25.7667, lng: 29.4667 },
          { name: "Secunda", lat: -26.5167, lng: 29.2000 },
          { name: "Delmas", lat: -26.1500, lng: 28.6833 },
        ]
      },
      "Gert Sibande": {
        lat: -26.6667, lng: 29.5833,
        municipalities: ["Albert Luthuli", "Msukaligwa", "Mkhondo", "Pixley Ka Seme", "Lekwa", "Dipaleseng", "Govan Mbeki"],
        towns: [
          { name: "Ermelo", lat: -26.5333, lng: 29.9833 },
          { name: "Standerton", lat: -26.9500, lng: 29.2500 },
          { name: "Piet Retief", lat: -27.0000, lng: 30.8000 },
          { name: "Bethal", lat: -26.4500, lng: 29.4667 },
        ]
      },
    }
  },
  
  // ===========================================================================
  // NORTH WEST - Mining Province
  // ===========================================================================
  "North West": {
    lat: -26.6638, lng: 25.2838,
    districts: {
      "Bojanala": {
        lat: -25.7000, lng: 27.2167,
        municipalities: ["Rustenburg", "Moses Kotane", "Madibeng", "Kgetlengrivier", "Moretele"],
        towns: [
          { name: "Rustenburg", lat: -25.6667, lng: 27.2500 },
          { name: "Brits", lat: -25.6333, lng: 27.7667 },
          { name: "Hartbeespoort", lat: -25.7333, lng: 27.8500 },
        ]
      },
      "Ngaka Modiri Molema": {
        lat: -25.8464, lng: 25.6408,
        municipalities: ["Mahikeng", "Ditsobotla", "Tswaing", "Ramotshere Moiloa", "Ratlou"],
        towns: [
          { name: "Mahikeng", lat: -25.8464, lng: 25.6408 },
          { name: "Lichtenburg", lat: -26.1500, lng: 26.1667 },
          { name: "Zeerust", lat: -25.5333, lng: 26.0833 },
        ]
      },
      "Dr Kenneth Kaunda": {
        lat: -26.7167, lng: 26.9833,
        municipalities: ["JB Marks", "Maquassi Hills", "Matlosana"],
        towns: [
          { name: "Klerksdorp", lat: -26.8667, lng: 26.6667 },
          { name: "Potchefstroom", lat: -26.7167, lng: 27.1000 },
          { name: "Orkney", lat: -26.9833, lng: 26.6667 },
        ]
      },
      "Dr Ruth Segomotsi Mompati": {
        lat: -27.1667, lng: 24.5000,
        municipalities: ["Naledi", "Greater Taung", "Lekwa-Teemane", "Kagisano-Molopo", "Mamusa"],
        towns: [
          { name: "Vryburg", lat: -26.9500, lng: 24.7333 },
          { name: "Schweizer-Reneke", lat: -27.1833, lng: 25.3333 },
          { name: "Christiana", lat: -27.9167, lng: 25.1667 },
        ]
      },
    }
  },
  
  // ===========================================================================
  // NORTHERN CAPE - Largest, Least Populated
  // ===========================================================================
  "Northern Cape": {
    lat: -29.0467, lng: 22.9375,
    districts: {
      "Frances Baard": {
        lat: -28.7282, lng: 24.7499,
        municipalities: ["Sol Plaatje", "Dikgatlong", "Magareng", "Phokwane"],
        towns: [
          { name: "Kimberley", lat: -28.7282, lng: 24.7499 },
          { name: "Barkly West", lat: -28.5333, lng: 24.5167 },
          { name: "Warrenton", lat: -28.1167, lng: 24.8667 },
          { name: "Hartswater", lat: -27.7667, lng: 24.8167 },
        ]
      },
      "ZF Mgcawu": {
        lat: -28.4478, lng: 21.2561,
        municipalities: ["Dawid Kruiper", "Kai !Garib", "!Kheis", "Tsantsabane", "Kgatelopele"],
        towns: [
          { name: "Upington", lat: -28.4478, lng: 21.2561 },
          { name: "Kakamas", lat: -28.7667, lng: 20.6167 },
          { name: "Groblershoop", lat: -28.8833, lng: 22.0000 },
          { name: "Postmasburg", lat: -28.3500, lng: 23.0833 },
          { name: "Daniëlskuil", lat: -28.2000, lng: 23.5500 },
        ]
      },
      "Namakwa": {
        lat: -29.6642, lng: 17.8836,
        municipalities: ["Richtersveld", "Nama Khoi", "Kamiesberg", "Hantam", "Karoo Hoogland", "Khai-Ma"],
        towns: [
          { name: "Springbok", lat: -29.6642, lng: 17.8836 },
          { name: "Port Nolloth", lat: -29.2500, lng: 16.8667 },
          { name: "Garies", lat: -30.5667, lng: 17.9833 },
          { name: "Calvinia", lat: -31.4667, lng: 19.7667 },
          { name: "Sutherland", lat: -32.4000, lng: 20.6667 },
          { name: "Pofadder", lat: -29.1333, lng: 19.4000 },
          { name: "Aggeneys", lat: -29.2000, lng: 18.8500 },
        ]
      },
      "Pixley ka Seme": {
        lat: -30.6462, lng: 23.9942,
        municipalities: ["Ubuntu", "Umsobomvu", "Emthanjeni", "Kareeberg", "Renosterberg", "Thembelihle", "Siyathemba", "Siyancuma"],
        towns: [
          { name: "De Aar", lat: -30.6462, lng: 23.9942 },
          { name: "Colesberg", lat: -30.7167, lng: 25.1000 },
          { name: "Victoria West", lat: -31.4000, lng: 23.1333 },
          { name: "Carnarvon", lat: -30.9667, lng: 22.1333 },
          { name: "Petrusville", lat: -30.0833, lng: 24.6833 },
          { name: "Hopetown", lat: -29.6167, lng: 24.0833 },
          { name: "Prieska", lat: -29.6667, lng: 22.7500 },
          { name: "Douglas", lat: -29.0500, lng: 23.7667 },
          { name: "Marydale", lat: -29.4000, lng: 22.1000 },
        ]
      },
      "John Taolo Gaetsewe": {
        lat: -27.4542, lng: 23.0478,
        municipalities: ["Joe Morolong", "Gamagara", "Ga-Segonyana"],
        towns: [
          { name: "Kuruman", lat: -27.4542, lng: 23.4334 },
          { name: "Kathu", lat: -27.6952, lng: 23.0478 },
          { name: "Hotazel", lat: -27.2000, lng: 22.9500 },
          { name: "Olifantshoek", lat: -27.9333, lng: 22.7333 },
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
        return { 
          ...town, 
          province, 
          district, 
          municipality: dData.municipalities[0] 
        }
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
// DISTANCE CALCULATION (Haversine Formula)
// =============================================================================

function haversine(lat1, lng1, lat2, lng2) {
  const R = 6371
  const dLat = (lat2 - lat1) * Math.PI / 180
  const dLng = (lng2 - lng1) * Math.PI / 180
  const a = Math.sin(dLat/2)**2 + 
            Math.cos(lat1*Math.PI/180) * Math.cos(lat2*Math.PI/180) * 
            Math.sin(dLng/2)**2
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a))
  return R * c
}

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
  return [...new Set(result)]
}

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

// =============================================================================
// TENDER LOCATION PIN FUNCTIONS (NEW)
// =============================================================================

/**
 * Get coordinates for a tender based on its town, municipality, or province
 * 
 * Priority order:
 *   1. Exact town match (most precise)
 *   2. Municipality match (district center)
 *   3. Province center (fallback)
 * 
 * @param {Object} tender - Tender object with town, municipality, province
 * @returns {Object|null} - { lat, lng, name, type } or null if not found
 */
export function getTenderCoordinates(tender) {
  if (!tender) return null
  
  // Priority 1: Try to find by town name (most precise)
  if (tender.town) {
    const town = findTown(tender.town)
    if (town) {
      return { 
        lat: town.lat, 
        lng: town.lng, 
        name: town.name,
        type: 'town'
      }
    }
  }
  
  // Priority 2: Try to find by municipality (district center)
  if (tender.municipality) {
    for (const [province, pData] of Object.entries(SA_LOCATIONS)) {
      for (const [district, dData] of Object.entries(pData.districts)) {
        const matches = dData.municipalities.some(m => 
          m.toLowerCase() === tender.municipality.toLowerCase() ||
          m.toLowerCase().includes(tender.municipality.toLowerCase()) ||
          tender.municipality.toLowerCase().includes(m.toLowerCase())
        )
        
        if (matches) {
          return { 
            lat: dData.lat, 
            lng: dData.lng, 
            name: tender.municipality,
            type: 'municipality'
          }
        }
      }
    }
  }
  
  // Priority 3: Fall back to province center
  if (tender.province && SA_LOCATIONS[tender.province]) {
    const p = SA_LOCATIONS[tender.province]
    return { 
      lat: p.lat, 
      lng: p.lng, 
      name: tender.province,
      type: 'province'
    }
  }
  
  return null
}

/**
 * Create a custom marker icon for individual tenders
 * 
 * Color coding by precision level:
 *   - Green (#1D9E75): Exact town match (most precise)
 *   - Amber (#F59E0B): Municipality match (medium precision)
 *   - Gray (#6B7280): Province center (least precise)
 * 
 * @param {string} type - 'town', 'municipality', or 'province'
 * @returns {Object} - Leaflet divIcon configuration
 */
export function createTenderMarkerIcon(type = 'town') {
  const colors = {
    town: '#1D9E75',         // Green - most precise
    municipality: '#F59E0B',  // Amber - medium precision
    province: '#6B7280'       // Gray - least precise
  }
  
  const bgColor = colors[type] || colors.province
  const size = type === 'town' ? 12 : type === 'municipality' ? 10 : 8
  
  // Return a plain object that Leaflet can use (not an L.divIcon directly)
  // This allows the component to call L.divIcon with this configuration
  return {
    html: `<div style="
      width: ${size}px;
      height: ${size}px;
      background: ${bgColor};
      border: 2px solid white;
      border-radius: 50%;
      box-shadow: 0 2px 6px rgba(0,0,0,0.35);
      cursor: pointer;
      transition: transform 0.15s ease;
    "></div>`,
    iconSize: [size, size],
    iconAnchor: [size/2, size/2],
    popupAnchor: [0, -size/2 - 4],
    className: ''
  }
}