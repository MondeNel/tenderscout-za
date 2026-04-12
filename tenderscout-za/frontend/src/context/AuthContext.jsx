import { createContext, useContext, useState, useEffect } from 'react'
import { getProfile } from '../api/auth'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)
  const [lastSearch, setLastSearch] = useState(() => {
    try {
      const saved = localStorage.getItem('lastSearch')
      return saved ? JSON.parse(saved) : { industries: [], provinces: [], keyword: '' }
    } catch { return { industries: [], provinces: [], keyword: '' } }
  })

  useEffect(() => {
    const token = localStorage.getItem('token')
    if (token) {
      getProfile()
        .then((res) => setUser(res.data))
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
  }

  const refreshUser = async () => {
    const res = await getProfile()
    setUser(res.data)
    return res.data
  }

  const saveLastSearch = (filters) => {
    setLastSearch(filters)
    localStorage.setItem('lastSearch', JSON.stringify(filters))
  }

  return (
    <AuthContext.Provider value={{ user, loading, loginUser, logoutUser, refreshUser, lastSearch, saveLastSearch }}>
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => useContext(AuthContext)
