/**
 * File: src/api/auth.js
 * Purpose: Authentication and User Profile API Service
 * 
 * This module provides functions for all authentication-related API calls:
 *   - User registration
 *   - User login
 *   - Fetching user profile
 *   - Updating user preferences
 * 
 * All functions use the pre-configured Axios client from client.js,
 * which automatically handles token injection and 401 redirects.
 */

import client from './client'

// =============================================================================
// AUTHENTICATION ENDPOINTS
// =============================================================================

/**
 * Register a new user account
 * 
 * Endpoint: POST /auth/register
 * 
 * Request Body:
 *   - email: string (required) - User's email address
 *   - full_name: string (required) - User's full name
 *   - password: string (required) - Account password
 * 
 * Response (on success):
 *   {
 *     "access_token": "eyJhbGciOiJIUzI1NiIs...",
 *     "token_type": "bearer"
 *   }
 * 
 * After successful registration:
 *   - Token should be saved to localStorage (handled in Register.jsx)
 *   - User receives 5 free credits automatically
 *   - User is redirected to onboarding
 * 
 * @param {Object} data - Registration form data
 * @param {string} data.email - User's email
 * @param {string} data.full_name - User's full name
 * @param {string} data.password - User's password
 * @returns {Promise} Axios promise resolving to token response
 */
export const register = (data) => client.post('/auth/register', data)

/**
 * Log in an existing user
 * 
 * Endpoint: POST /auth/login
 * 
 * Request Body:
 *   - email: string (required) - User's email address
 *   - password: string (required) - Account password
 * 
 * Response (on success):
 *   {
 *     "access_token": "eyJhbGciOiJIUzI1NiIs...",
 *     "token_type": "bearer"
 *   }
 * 
 * Error Responses:
 *   - 401: Invalid email or password
 *   - 400: Malformed request
 * 
 * After successful login:
 *   - Token should be saved to localStorage (handled in Login.jsx)
 *   - User is redirected to dashboard (or onboarding if first time)
 * 
 * @param {Object} data - Login form data
 * @param {string} data.email - User's email
 * @param {string} data.password - User's password
 * @returns {Promise} Axios promise resolving to token response
 */
export const login = (data) => client.post('/auth/login', data)

// =============================================================================
// USER PROFILE ENDPOINTS
// =============================================================================

/**
 * Get the current user's profile
 * 
 * Endpoint: GET /user/profile
 * 
 * Requires Authentication: Yes (JWT token required)
 * 
 * Response:
 *   {
 *     "id": 1,
 *     "email": "user@example.com",
 *     "full_name": "John Doe",
 *     "credit_balance": 5.0,
 *     "industry_preferences": ["IT & Telecoms", "Building & Trades"],
 *     "province_preferences": ["Gauteng", "Western Cape"],
 *     "town_preferences": ["Johannesburg", "Cape Town"],
 *     "municipality_preferences": ["City of Johannesburg"],
 *     "business_location": "Sandton, Johannesburg",
 *     "business_lat": -26.107,
 *     "business_lng": 28.057,
 *     "search_radius_km": 100,
 *     "created_at": "2026-04-22T10:30:00Z"
 *   }
 * 
 * This endpoint is used to:
 *   - Populate the user's dashboard with personalized data
 *   - Pre-fill the account settings page
 *   - Restore user state after page refresh
 * 
 * Token is automatically added by the client interceptor.
 * If token is invalid/expired, the interceptor redirects to /login.
 * 
 * @returns {Promise} Axios promise resolving to user profile
 */
export const getProfile = () => client.get('/user/profile')

/**
 * Update user preferences
 * 
 * Endpoint: PUT /user/preferences
 * 
 * Requires Authentication: Yes (JWT token required)
 * 
 * Request Body (all fields optional - only send what needs updating):
 *   - industry_preferences: string[] - Preferred industries for tenders
 *   - province_preferences: string[] - Preferred provinces
 *   - town_preferences: string[] - Preferred towns/cities
 *   - municipality_preferences: string[] - Preferred municipalities
 *   - business_location: string - Human-readable business address
 *   - business_lat: number - Latitude coordinate for location-based search
 *   - business_lng: number - Longitude coordinate for location-based search
 *   - search_radius_km: number - Search radius in kilometers (default: 100)
 * 
 * Response:
 *   Returns the updated user object (same format as getProfile)
 * 
 * Usage contexts:
 *   - Onboarding page: Set initial preferences after registration
 *   - Account page: Update preferences anytime
 *   - Dashboard: Quick preference toggles
 * 
 * Example:
 *   await updatePreferences({
 *     industry_preferences: ["IT & Telecoms", "Security"],
 *     province_preferences: ["Gauteng", "Western Cape"],
 *     business_location: "Sandton, Johannesburg",
 *     business_lat: -26.107,
 *     business_lng: 28.057,
 *     search_radius_km: 50
 *   })
 * 
 * @param {Object} data - Preferences to update (partial user object)
 * @returns {Promise} Axios promise resolving to updated user profile
 */
export const updatePreferences = (data) => client.put('/user/preferences', data)