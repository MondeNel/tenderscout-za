// src/context/AuthContext.jsx
import { createContext, useContext, useState, useEffect } from 'react'
import { getProfile } from '../api/auth'

const AuthContext = createContext(null)

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

function loadLastSearch() {
  try {
    const saved = localStorage.getItem('lastSearch')
    return saved ? { ...DEFAULT_LAST_SEARCH, ...JSON.parse(saved) } : DEFAULT_LAST_SEARCH
  } catch {
    return DEFAULT_LAST_SEARCH
  }
}

export function AuthProvider({ children }) {
  const [user,    setUser]    = useState(null)
  const [loading, setLoading] = useState(true)
  const [lastSearch, setLastSearch] = useState(loadLastSearch)

  useEffect(() => {
    const token = localStorage.getItem('token')
    if (token) {
      getProfile()
        .then(res => setUser(res.data))
        .catch(() => {
          localStorage.removeItem('token')
          localStorage.removeItem('user')
        })
        .finally(() => setLoading(false))
    } else {
      setLoading(false)
    }
  }, [])

  const loginUser = (token, userData) => {
    localStorage.setItem('token', token)
    setUser(userData)
  }

  const logoutUser = () => {
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    localStorage.removeItem('lastSearch')
    setUser(null)
    setLastSearch(DEFAULT_LAST_SEARCH)
  }

  const refreshUser = async () => {
    const res = await getProfile()
    setUser(res.data)
    return res.data
  }

  const saveLastSearch = (filters) => {
    const merged = { ...DEFAULT_LAST_SEARCH, ...filters }
    setLastSearch(merged)
    localStorage.setItem('lastSearch', JSON.stringify(merged))
  }

  return (
    <AuthContext.Provider value={{
      user, loading,
      loginUser, logoutUser, refreshUser,
      lastSearch, saveLastSearch,
    }}>
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => useContext(AuthContext)/**
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
// Create the AuthContext with null as initial value.
// The actual value is provided by AuthProvider at runtime.

const AuthContext = createContext(null)

// =============================================================================
// DEFAULT SEARCH FILTERS
// =============================================================================
/**
 * Default structure for last search filters.
 * Used when no saved search exists or after logout.
 * 
 * This ensures the search page always has a valid initial state.
 */
const DEFAULT_LAST_SEARCH = {
  industries: [],           // Selected industry categories
  provinces: [],            // Selected provinces
  municipalities: [],       // Selected municipalities
  towns: [],               // Selected towns/cities
  keyword: '',             // Free-text search query
  userLat: null,           // User's business latitude
  userLng: null,           // User's business longitude
  radiusKm: 100,           // Search radius in kilometers
  useMyLocation: false,    // Whether to use location-based ranking
}

// =============================================================================
// LOCALSTORAGE HELPERS
// =============================================================================

/**
 * Load saved search filters from localStorage
 * 
 * Returns the default search object merged with any saved values.
 * This allows returning users to see their last search when they come back.
 * 
 * @returns {Object} Merged search filters object
 */
function loadLastSearch() {
  try {
    const saved = localStorage.getItem('lastSearch')
    // Merge saved values with defaults (saved values override defaults)
    return saved ? { ...DEFAULT_LAST_SEARCH, ...JSON.parse(saved) } : DEFAULT_LAST_SEARCH
  } catch {
    // If localStorage is corrupted or unavailable, return defaults
    return DEFAULT_LAST_SEARCH
  }
}

// =============================================================================
// AUTH PROVIDER COMPONENT
// =============================================================================

/**
 * AuthProvider - Global authentication state provider
 * 
 * Wraps the application and provides authentication state and methods
 * to all child components via Context.
 * 
 * State:
 *   - user: Current user object (null if not logged in)
 *   - loading: True while checking initial authentication
 *   - lastSearch: Saved search filters for returning users
 * 
 * Methods:
 *   - loginUser: Store token and set user after successful login
 *   - logoutUser: Clear all auth data
 *   - refreshUser: Fetch latest user data from API
 *   - saveLastSearch: Persist search filters to localStorage
 * 
 * @param {React.ReactNode} children - Child components to render
 */
export function AuthProvider({ children }) {
  // ===========================================================================
  // STATE
  // ===========================================================================
  
  // Current authenticated user (null = not logged in)
  const [user, setUser] = useState(null)
  
  // Loading flag for initial auth check (true = checking, false = ready)
  const [loading, setLoading] = useState(true)
  
  // Saved search filters (persisted in localStorage)
  const [lastSearch, setLastSearch] = useState(loadLastSearch)

  // ===========================================================================
  // INITIAL AUTHENTICATION CHECK
  // ===========================================================================
  /**
   * On component mount, check if the user has a valid token.
   * If token exists, attempt to fetch the user profile.
   * If token is invalid/expired, clear it and proceed as logged out.
   */
  useEffect(() => {
    const token = localStorage.getItem('token')
    
    if (token) {
      // Token exists — try to fetch user profile
      getProfile()
        .then(res => {
          // Success! User is authenticated
          setUser(res.data)
        })
        .catch(() => {
          // Token is invalid or expired — clean up
          localStorage.removeItem('token')
          localStorage.removeItem('user')
          // User remains null (logged out)
        })
        .finally(() => {
          // Auth check complete — ready to render
          setLoading(false)
        })
    } else {
      // No token — user is not logged in
      setLoading(false)
    }
  }, []) // Empty dependency array = runs once on mount

  // ===========================================================================
  // AUTHENTICATION METHODS
  // ===========================================================================

  /**
   * Log in a user
   * 
   * Called after successful login or registration.
   * Stores the JWT token and sets the user state.
   * 
   * @param {string} token - JWT access token from backend
   * @param {Object} userData - User profile object
   */
  const loginUser = (token, userData) => {
    localStorage.setItem('token', token)
    setUser(userData)
  }

  /**
   * Log out the current user
   * 
   * Clears all authentication data from localStorage and resets state.
   * Also clears saved search to prevent data leakage between users.
   */
  const logoutUser = () => {
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    localStorage.removeItem('lastSearch')
    setUser(null)
    setLastSearch(DEFAULT_LAST_SEARCH)
  }

  /**
   * Refresh the current user's profile
   * 
   * Fetches the latest user data from the API and updates state.
   * Useful after:
   *   - Updating preferences
   *   - Purchasing credits
   *   - Changing account settings
   * 
   * @returns {Promise<Object>} Updated user object
   */
  const refreshUser = async () => {
    const res = await getProfile()
    setUser(res.data)
    return res.data
  }

  // ===========================================================================
  // SEARCH PERSISTENCE
  // ===========================================================================

  /**
   * Save search filters for returning users
   * 
   * Persists the current search filters to localStorage so that
   * when the user returns, they can continue where they left off.
   * 
   * This creates a seamless experience — the search page remembers
   * the user's last query, filters, and location settings.
   * 
   * @param {Object} filters - Search filters to save (partial object)
   */
  const saveLastSearch = (filters) => {
    // Merge incoming filters with defaults (filters override defaults)
    const merged = { ...DEFAULT_LAST_SEARCH, ...filters }
    setLastSearch(merged)
    localStorage.setItem('lastSearch', JSON.stringify(merged))
  }

  // ===========================================================================
  // CONTEXT VALUE
  // ===========================================================================
  /**
   * The value provided to all consumers of this context.
   * Includes both state and methods for managing authentication.
   */
  const contextValue = {
    // State
    user,           // Current user (null if not logged in)
    loading,        // True during initial auth check
    
    // Auth methods
    loginUser,      // Log in with token and user data
    logoutUser,     // Log out and clear all data
    refreshUser,    // Fetch fresh user data from API
    
    // Search persistence
    lastSearch,     // Current saved search filters
    saveLastSearch, // Save search filters to localStorage
  }

  return (
    <AuthContext.Provider value={contextValue}>
      {children}
    </AuthContext.Provider>
  )
}

// =============================================================================
// CUSTOM HOOK
// =============================================================================

/**
 * useAuth - Custom hook to access authentication context
 * 
 * Provides a convenient way for components to access authentication
 * state and methods without manually importing useContext.
 * 
 * Usage:
 *   const { user, loginUser, logoutUser } = useAuth()
 * 
 * @returns {Object} The authentication context value
 * @throws {Error} If used outside of AuthProvider
 */
export const useAuth = () => {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}