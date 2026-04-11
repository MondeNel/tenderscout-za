import client from './client'

export const register = (data) => client.post('/auth/register', data)
export const login = (data) => client.post('/auth/login', data)
export const getProfile = () => client.get('/user/profile')
export const updatePreferences = (data) => client.put('/user/preferences', data)
