/**
 * File: src/context/AuthContext.jsx
 * Purpose: Global Authentication State Management
 *
 * This module provides a React Context for managing authentication state
 * across the entire application. It handles:
 *   - User login/logout state
 *   - Token persistence in localStorage
 *   - Automatic profile loading on app start
 *   - Last search persistence for returning users
 *
 * The AuthProvider wraps the entire app in App.jsx, making authentication
 * state available to any component via the useAuth() hook.
 */

import { createContext, useContext, useState, useEffect } from 'react'
import { getProfile } from '../api/auth'

// =============================================================================
// CONTEXT CREATION
// =============================================================================

// The context object – initially null to detect when a consumer is not
// wrapped in an AuthProvider (see useAuth hook).
const AuthContext = createContext(null)

// =============================================================================
// DEFAULT SEARCH FILTERS
// =============================================================================

// Structure used when the user has no saved search in localStorage, or after
// logout. `useMyLocation` is a boolean that the search page can toggle
// independently; it doesn't affect the backend directly.
const DEFAULT_LAST_SEARCH = {
  industries: [],
  provinces: [],
  municipalities: [],
  towns: [],
  keyword: '',
  userLat: null,
  userLng: null,
  radiusKm: 100,
  useMyLocation: false,
}

// =============================================================================
// LOCALSTORAGE HELPERS
// =============================================================================

// Load the last search filters from localStorage, merging with defaults.
// If the stored JSON is corrupt or missing, return the default object.
function loadLastSearch() {
  try {
    const saved = localStorage.getItem('lastSearch')
    return saved ? { ...DEFAULT_LAST_SEARCH, ...JSON.parse(saved) } : DEFAULT_LAST_SEARCH
  } catch {
    return DEFAULT_LAST_SEARCH
  }
}

// =============================================================================
// AUTH PROVIDER COMPONENT
// =============================================================================

export function AuthProvider({ children }) {
  // Current user object (from GET /user/profile) or null if not logged in
  const [user, setUser] = useState(null)
  // True while the initial session restoration is in progress
  const [loading, setLoading] = useState(true)
  // The last search filters used by the user, persisted across visits
  const [lastSearch, setLastSearch] = useState(loadLastSearch)

  // On first mount, check if a token exists and try to fetch the profile.
  // If the token is invalid/expired, clean up and proceed as unauthenticated.
  useEffect(() => {
    const token = localStorage.getItem('token')
    if (token) {
      getProfile()
        .then(res => setUser(res.data))
        .catch(() => {
          // Invalid token – clear storage so the user doesn't get stuck
          localStorage.removeItem('token')
          localStorage.removeItem('user')
        })
        .finally(() => setLoading(false))
    } else {
      setLoading(false)
    }
  }, [])

  // Called after a successful registration or login.
  // Stores the JWT and sets the user in state (causing a re-render).
  const loginUser = (token, userData) => {
    localStorage.setItem('token', token)
    setUser(userData)
  }

  // Clears all auth-related data and resets search filters to default.
  const logoutUser = () => {
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    localStorage.removeItem('lastSearch')
    setUser(null)
    setLastSearch(DEFAULT_LAST_SEARCH)
  }

  // Re-fetch the user profile from the server (e.g., after updating
  // preferences) and update local state. Returns the fresh user object.
  const refreshUser = async () => {
    const res = await getProfile()
    setUser(res.data)
    return res.data
  }

  // Persist a set of search filters to both state and localStorage.
  // Any missing keys are filled with DEFAULT_LAST_SEARCH values.
  const saveLastSearch = (filters) => {
    const merged = { ...DEFAULT_LAST_SEARCH, ...filters }
    setLastSearch(merged)
    localStorage.setItem('lastSearch', JSON.stringify(merged))
  }

  // Provide the entire auth state and action functions to the component tree.
  return (
    <AuthContext.Provider value={{
      user,
      loading,
      loginUser,
      logoutUser,
      refreshUser,
      lastSearch,
      saveLastSearch,
    }}>
      {children}
    </AuthContext.Provider>
  )
}

// =============================================================================
// CUSTOM HOOK
// =============================================================================

// Convenience hook – throws if used outside of an AuthProvider, which helps
// catch misconfiguration early during development.
export const useAuth = () => {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}