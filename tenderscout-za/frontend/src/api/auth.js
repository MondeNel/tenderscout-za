// src/api/auth.js
import client from './client'

export const register          = (data) => client.post('/auth/register', data)
export const login             = (data) => client.post('/auth/login', data)
export const getProfile        = ()     => client.get('/user/profile')

/**
 * Update user preferences.
 * New fields accepted by backend:
 *   business_location, business_lat, business_lng,
 *   search_radius_km, municipality_preferences
 */
export const updatePreferences = (data) => client.put('/user/preferences', data)