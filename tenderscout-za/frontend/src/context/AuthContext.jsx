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

export const useAuth = () => useContext(AuthContext)