import client from './client'

export const searchTenders = (params) => client.post('/search/tenders', params)
export const getLatest = (since, industries, provinces) => {
  const params = new URLSearchParams()
  if (since) params.append('since', since)
  if (industries?.length) params.append('industries', industries.join(','))
  if (provinces?.length) params.append('provinces', provinces.join(','))
  return client.get(`/tenders/latest?${params.toString()}`)
}
export const getTender = (id) => client.get(`/tenders/${id}`)
export const getSearchHistory = () => client.get('/search/history')
