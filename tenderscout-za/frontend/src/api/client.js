/**
 * File: src/api/client.js
 * Purpose: Axios HTTP Client Configuration
 */

import axios from 'axios'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const client = axios.create({
  baseURL: API_URL,
  headers: { 'Content-Type': 'application/json' },
})

// =============================================================================
// REQUEST INTERCEPTOR — Inject JWT token
// =============================================================================
client.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

// =============================================================================
// RESPONSE INTERCEPTOR — Global error handling
// =============================================================================
client.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status

    // 401 — token expired or invalid → force logout
    if (status === 401) {
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      window.location.href = '/login'
    }

    // FIX: 402 — insufficient credits
    // Previously this fell through with no special handling, causing a raw
    // AxiosError to surface. Now we attach a clean human-readable message
    // so callers can do: error.response.data.detail or error.creditError
    if (status === 402) {
      error.creditError = true
      error.creditMessage =
        error.response?.data?.error ||
        error.response?.data?.detail ||
        'Insufficient credits. Please top up to continue searching.'
    }

    return Promise.reject(error)
  }
)

export default client