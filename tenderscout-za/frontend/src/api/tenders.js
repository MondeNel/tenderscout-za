// src/api/tenders.js
import client from './client'

/**
 * Search tenders with full location-aware parameters.
 *
 * Payload:
 *   industries[]     – industry filter
 *   provinces[]      – province filter
 *   municipalities[] – municipality filter
 *   towns[]          – town filter
 *   keyword          – free-text keyword
 *   user_lat         – latitude of user's business (optional)
 *   user_lng         – longitude of user's business (optional)
 *   radius_km        – search radius in km (optional, requires lat/lng)
 *   page             – page number (1-based)
 *   page_size        – results per page
 */
export const searchTenders = (params) => client.post('/search/tenders', params)

export const getLatest = (since, industries, provinces, municipalities) => {
  const params = new URLSearchParams()
  if (since)               params.append('since',          since)
  if (industries?.length)  params.append('industries',     industries.join(','))
  if (provinces?.length)   params.append('provinces',      provinces.join(','))
  if (municipalities?.length) params.append('municipalities', municipalities.join(','))
  return client.get(`/tenders/latest?${params.toString()}`)
}

export const getTender         = (id) => client.get(`/tenders/${id}`)
export const getSearchHistory  = ()  => client.get('/search/history')