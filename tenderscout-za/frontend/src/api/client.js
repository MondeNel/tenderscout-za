/**
 * File: src/api/client.js
 * Purpose: Axios HTTP Client Configuration
 * 
 * This file creates and configures a centralized Axios instance for all API calls.
 * It handles:
 *   - Base URL configuration from environment variables
 *   - Automatic JWT token injection in request headers
 *   - Global error handling (401 unauthorized redirects)
 *   - Consistent JSON content type
 * 
 * All other API modules (auth.js, tenders.js, credits.js) import this client
 * to make HTTP requests to the FastAPI backend.
 */

import axios from 'axios'

// =============================================================================
// API BASE URL CONFIGURATION
// =============================================================================
/**
 * The base URL for all API requests.
 * 
 * In development: http://localhost:8000 (default)
 * In production: Set via VITE_API_URL environment variable
 * 
 * Example .env file:
 *   VITE_API_URL=https://api.tenderscout.co.za
 */
const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

// =============================================================================
// AXIOS CLIENT INSTANCE
// =============================================================================
/**
 * Create a configured Axios instance with default settings.
 * 
 * This instance is shared across all API modules, ensuring consistent:
 *   - Base URL
 *   - Headers
 *   - Interceptor behavior
 * 
 * Using a single instance improves performance through connection reuse.
 */
const client = axios.create({
  baseURL: API_URL,
  headers: { 'Content-Type': 'application/json' },
})

// =============================================================================
// REQUEST INTERCEPTOR - Automatic Token Injection
// =============================================================================
/**
 * Request Interceptor
 * 
 * Runs BEFORE every API request is sent.
 * Automatically attaches the JWT token from localStorage to the Authorization header.
 * 
 * This means API calls don't need to manually include the token:
 * 
 *   // Instead of this:
 *   client.get('/tenders', { headers: { Authorization: `Bearer ${token}` } })
 * 
 *   // You can just do this:
 *   client.get('/tenders')
 * 
 * Flow:
 *   1. User logs in → token saved to localStorage
 *   2. Interceptor reads token and adds to request headers
 *   3. Backend validates token and returns protected data
 */
client.interceptors.request.use(
  (config) => {
    // Get the JWT token from browser storage
    // This is set in auth.js after successful login/register
    const token = localStorage.getItem('token')
    
    // If token exists, add it to the Authorization header
    // Format: "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    
    // Return the modified config so the request proceeds
    return config
  },
  (error) => {
    // If there's an error in the interceptor itself, reject the promise
    return Promise.reject(error)
  }
)

// =============================================================================
// RESPONSE INTERCEPTOR - Global Error Handling
// =============================================================================
/**
 * Response Interceptor
 * 
 * Runs AFTER every API response is received.
 * Handles global error cases, particularly authentication failures.
 * 
 * 401 Unauthorized Handling:
 *   - Token expired or invalid
 *   - User logged out on another device
 *   - Backend rejected the token
 * 
 * When 401 occurs:
 *   1. Clear authentication data from localStorage
 *   2. Redirect user to login page
 *   3. Reject the promise so the calling code knows it failed
 * 
 * This prevents users from seeing broken pages with "Unauthorized" errors.
 */
client.interceptors.response.use(
  // ===========================================================================
  // Success Handler
  // ===========================================================================
  // For successful responses (2xx status codes), simply pass through the response.
  (response) => {
    return response
  },
  
  // ===========================================================================
  // Error Handler
  // ===========================================================================
  (error) => {
    // Check if the error is a 401 Unauthorized response
    // This happens when:
    //   - Token is expired
    //   - Token is malformed
    //   - User account was deactivated
    //   - Backend secret key changed
    if (error.response?.status === 401) {
      // Clear all authentication data from localStorage
      // This ensures the user cannot access protected routes
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      
      // Redirect to login page
      // Using window.location.href forces a full page reload,
      // which clears any stale React state
      window.location.href = '/login'
    }
    
    // Reject the promise so the calling code can handle the error if needed
    // For example, showing a toast notification for other error types
    return Promise.reject(error)
  }
)

// =============================================================================
// EXPORT
// =============================================================================
/**
 * Export the configured client instance.
 * 
 * Usage in other files:
 * 
 *   import client from './api/client'
 * 
 *   // GET request
 *   const response = await client.get('/tenders')
 * 
 *   // POST request with data
 *   const response = await client.post('/auth/login', { email, password })
 * 
 *   // PUT request
 *   const response = await client.put('/user/preferences', preferences)
 * 
 * The response data is available as response.data
 */
export default client