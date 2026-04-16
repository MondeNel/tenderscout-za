import client from './client'

export const searchTenders = (params) => {
  // Clean up empty arrays to avoid sending them
  const cleaned = { ...params }
  if (!cleaned.industries?.length) delete cleaned.industries
  if (!cleaned.provinces?.length) delete cleaned.provinces
  if (!cleaned.municipalities?.length) delete cleaned.municipalities
  if (!cleaned.towns?.length) delete cleaned.towns
  if (!cleaned.keyword) delete cleaned.keyword
  
  return client.post('/search/tenders', cleaned)
}

export const getLatest = (since, industries, provinces) => {
  const params = new URLSearchParams()
  if (since) params.append('since', since)
  if (industries?.length) params.append('industries', industries.join(','))
  if (provinces?.length) params.append('provinces', provinces.join(','))
  return client.get(`/tenders/latest?${params.toString()}`)
}

export const getTender = (id) => client.get(`/tenders/${id}`)

export const getSearchHistory = () => client.get('/search/history')