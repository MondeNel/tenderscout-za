/**
 * File: src/pages/Dashboard.jsx
 * Purpose: Main User Dashboard / Home Page
 * 
 * This is the primary landing page for authenticated users.
 * It displays:
 *   - Personalized greeting with user's name
 *   - Tender statistics (total, credits, filters)
 *   - List of tenders matching user's preferences
 *   - Real-time polling for new tenders (every 60 seconds)
 * 
 * KEY FEATURE: The dashboard loads tenders based on the user's
 * saved location (province/town from registration) and
 * automatically applies their industry/province preferences
 * from the user profile (the backend enforces this when no
 * filters are explicitly provided).
 */

import { useState, useEffect, useRef } from 'react'
import { useAuth } from '../context/AuthContext'
import { searchTenders, getLatest } from '../api/tenders'
import { RefreshCw, MapPin } from 'lucide-react'
import TenderCard from '../components/TenderCard'
import toast from 'react-hot-toast'

export default function Dashboard() {
  // Access the current user, refresh function, and last search state
  const { user, refreshUser, lastSearch } = useAuth()
  
  // --- State ---
  const [tenders, setTenders] = useState([])       // tenders currently displayed
  const [loading, setLoading] = useState(true)
  const [total, setTotal] = useState(0)            // total matching tenders (for stats)
  const [newCount, setNewCount] = useState(0)      // count of tenders found since last poll
  const [pendingTenders, setPendingTenders] = useState([]) // new tenders not yet loaded into the view
  
  // Track the timestamp of the last successful scrape/poll so we only fetch new
  // tenders since that point. Initialised to now to avoid fetching old data on startup.
  const lastScrapeRef = useRef(new Date().toISOString())
  const pollRef = useRef(null)                     // interval reference for cleanup
  const initialLoadDone = useRef(false)            // ensures we only load on first user

  // ===========================================================================
  // SEARCH PAYLOAD BUILDER
  // ===========================================================================
  
  /**
   * Builds the payload for the search and latest-tender API calls.
   * 
   * Priority:
   * 1. If the user has a saved lastSearch (from the Search page), use those
   *    filters. This lets them return to the dashboard with the same filter set.
   * 2. Otherwise fall back to the user's saved preferences (industry, province).
   * 3. Always includes the user's business location for radius-based filtering
   *    when coordinates are available.
   */
  const getPayload = () => {
    // Determine industries: explicit search > user preferences
    const ind = lastSearch?.industries?.length 
      ? lastSearch.industries 
      : (user?.industry_preferences || [])
    
    // Determine provinces: explicit search > user preferences
    const prov = lastSearch?.provinces?.length 
      ? lastSearch.provinces 
      : (user?.province_preferences || [])
    
    // Municipalities are only set from an explicit search (no user preference fallback)
    const muni = lastSearch?.municipalities?.length 
      ? lastSearch.municipalities 
      : []

    const payload = { 
      industries: ind, 
      provinces: prov, 
      municipalities: muni, 
      page: 1, 
      page_size: 20 
    }

    // Attach the user's business location for distance-based sorting/filtering.
    // The backend uses this to order tenders by proximity when a radius is given.
    if (user?.business_lat && user?.business_lng) {
      payload.user_lat = user.business_lat
      payload.user_lng = user.business_lng
      payload.radius_km = user.search_radius_km || 100
    }

    return { payload, ind, prov, muni }
  }

  // ===========================================================================
  // DATA LOADING
  // ===========================================================================
  
  /**
   * Fetch the full list of tenders matching the current filters.
   * This is the initial load and is also called when the user clicks Refresh
   * or when the lastSearch changes.
   */
  const loadTenders = async () => {
    setLoading(true)
    const { payload } = getPayload()
    
    try {
      const res = await searchTenders(payload)
      setTenders(res.data.results)
      setTotal(res.data.total)
      // Refresh user data (credits may have been deducted, etc.)
      await refreshUser()
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to load tenders')
    } finally {
      setLoading(false)
    }
  }

  /**
   * Poll for new tenders since the last scrape timestamp.
   * Uses the GET /tenders/latest endpoint with 'since' parameter.
   * If new tenders are found, they are stored in pendingTenders and
   * the user is shown a notification bar rather than auto-inserting them.
   */
  const pollForNew = async () => {
    const { payload } = getPayload()
    try {
      const ind = payload.industries || []
      const prov = payload.provinces || []
      const muni = payload.municipalities || []
      const res = await getLatest(lastScrapeRef.current, ind, prov, muni)
      
      if (res.data.new_count > 0) {
        // Store the new tenders; they'll be merged when the user clicks "Load"
        setPendingTenders(res.data.tenders)
        setNewCount(res.data.new_count)
        lastScrapeRef.current = new Date().toISOString()
      }
    } catch {
      // Polling failures are silently ignored – not critical enough to disrupt the UI
    }
  }

  /**
   * Manually merge the pending new tenders into the visible list.
   * Triggered by the "Load" button in the notification bar.
   */
  const loadNewTenders = () => {
    // Prepend new tenders so they appear at the top of the list
    setTenders(prev => [...pendingTenders, ...prev])
    setTotal(prev => prev + pendingTenders.length)
    setPendingTenders([])
    setNewCount(0)
    // Refresh credits after the insert (optional, since loadTenders would also do it)
    refreshUser()
  }

  // ===========================================================================
  // EFFECTS
  // ===========================================================================
  
  /**
   * On initial mount (when user becomes available), load tenders once.
   * The guard `initialLoadDone` prevents re-fetching on subsequent renders
   * unless the user object itself changes (e.g., login/logout).
   */
  useEffect(() => {
    if (user && !initialLoadDone.current) {
      initialLoadDone.current = true
      loadTenders()
    }
  }, [user])

  /**
   * When the lastSearch object changes (e.g., user performed a new search
   * and navigated back to the dashboard), reload the tenders.
   * We compare the serialized search object to avoid deep comparison.
   */
  const lastSearchKey = JSON.stringify(lastSearch)
  const prevSearchKey = useRef(lastSearchKey)
  
  useEffect(() => {
    if (!initialLoadDone.current) return
    if (prevSearchKey.current !== lastSearchKey) {
      prevSearchKey.current = lastSearchKey
      loadTenders()
    }
  }, [lastSearchKey])

  /**
   * Start polling for new tenders every 60 seconds.
   * Cleanup the interval when the component unmounts or when the user/lastSearch
   * change (to avoid stale closures).
   */
  useEffect(() => {
    pollRef.current = setInterval(pollForNew, 60000)
    return () => clearInterval(pollRef.current)
  }, [user, lastSearch])

  // ===========================================================================
  // COMPUTED DISPLAY VALUES
  // ===========================================================================
  
  const { ind, prov, muni } = getPayload()
  const isFromSearch = lastSearch?.industries?.length > 0 || lastSearch?.provinces?.length > 0
  
  // Extract user location for the greeting line
  const userProvince = user?.province_preferences?.[0]
  const userTown = user?.business_location
  
  // Dynamically generate the time‑of‑day greeting
  const greeting = new Date().getHours() < 12 
    ? 'Good morning' 
    : new Date().getHours() < 17 
      ? 'Good afternoon' 
      : 'Good evening'

  return (
    <div className="p-4 md:p-6 max-w-4xl mx-auto">
      {/* ===================================================================
          HEADER – greeting, tender count, location badge, refresh button
          =================================================================== */}
      <div className="flex items-start justify-between mb-4 md:mb-6">
        <div>
          <h1 className="text-lg md:text-xl font-semibold text-gray-900">
            {greeting}, {user?.full_name?.split(' ')[0]}
          </h1>
          <p className="text-sm text-gray-500 mt-0.5">
            {total} tenders{isFromSearch ? ' — filtered by your last search' : ' matching your preferences'}
          </p>
          
          {/* Show the user's saved location from their profile */}
          {(userProvince || userTown) && (
            <div className="flex items-center gap-1 mt-1 text-xs text-brand-600">
              <MapPin size={11} />
              <span>
                {userTown ? `${userTown}, ${userProvince}` : userProvince}
                {user?.search_radius_km ? ` · ${user.search_radius_km}km radius` : ''}
              </span>
            </div>
          )}
        </div>
        
        <div className="flex items-center gap-2">
          {/* Live indicator (desktop only) – a subtle "pulse" dot */}
          <span className="hidden md:flex items-center gap-1.5 text-xs text-gray-400">
            <span className="w-1.5 h-1.5 rounded-full bg-brand-400 animate-pulse" />
            Live
          </span>
          {/* Manual refresh button – re-fetches the full tender list */}
          <button onClick={loadTenders} className="p-1.5 rounded-lg hover:bg-gray-100 border border-gray-200" aria-label="Refresh">
            <RefreshCw size={14} />
          </button>
        </div>
      </div>

      {/* ===================================================================
          FILTER CHIPS – show which filters are currently active
          =================================================================== */}
      {(isFromSearch || muni.length > 0) && (
        <div className="mb-4 flex flex-wrap gap-1.5">
          {ind.map(i => (
            <span key={i} className="px-2 py-0.5 bg-brand-50 text-brand-700 text-xs rounded-full border border-brand-200">{i}</span>
          ))}
          {prov.map(p => (
            <span key={p} className="px-2 py-0.5 bg-gray-100 text-gray-600 text-xs rounded-full border border-gray-200">{p}</span>
          ))}
          {muni.map(m => (
            <span key={m} className="px-2 py-0.5 bg-purple-50 text-purple-700 text-xs rounded-full border border-purple-200">{m}</span>
          ))}
        </div>
      )}

      {/* ===================================================================
          NEW TENDERS NOTIFICATION BAR – appears after polling finds new items
          =================================================================== */}
      {newCount > 0 && (
        <div className="mb-4 flex items-center justify-between bg-brand-50 border border-brand-200 rounded-xl px-4 py-3">
          <span className="text-sm text-brand-600">{newCount} new tender{newCount > 1 ? 's' : ''} found</span>
          <button onClick={loadNewTenders} className="text-sm font-medium text-brand-600 hover:text-brand-800">Load</button>
        </div>
      )}

      {/* ===================================================================
          STATS CARDS – quick overview of total tenders, credits, filters
          =================================================================== */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-2 md:gap-3 mb-4 md:mb-6">
        {[
          { label: 'Total tenders', val: total, sub: 'matching filters' },
          { label: 'Credits', val: user?.credit_balance ?? 0, sub: `R${(((user?.credit_balance ?? 0) * 10)).toFixed(0)} value` },
          { label: 'Industries', val: ind.length, sub: 'active filters' },
          { label: 'Provinces', val: prov.length, sub: 'active filters' },
        ].map(({ label, val, sub }) => (
          <div key={label} className="bg-gray-100 rounded-xl px-3 py-2.5 md:px-4 md:py-3">
            <p className="text-xs text-gray-500">{label}</p>
            <p className="text-2xl md:text-3xl font-semibold text-gray-900 mt-0.5">{val}</p>
            <p className="text-xs text-gray-400">{sub}</p>
          </div>
        ))}
      </div>

      {/* ===================================================================
          TENDER LIST – loading spinner, empty state, or the list of cards
          =================================================================== */}
      {loading ? (
        <div className="flex justify-center py-16">
          <div className="w-6 h-6 border-2 border-brand-400 border-t-transparent rounded-full animate-spin" />
        </div>
      ) : tenders.length === 0 ? (
        <div className="text-center py-16 text-gray-400 text-sm">
          No tenders found. Try adjusting your filters or location on the Search page.
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-3">
          {tenders.map(t => <TenderCard key={t.id} tender={t} showBadgeColor />)}
        </div>
      )}
    </div>
  )
}