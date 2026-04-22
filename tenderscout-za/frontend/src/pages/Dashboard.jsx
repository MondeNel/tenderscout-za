/**
 * File: src/pages/Dashboard.jsx
 * Purpose: Main User Dashboard / Home Page
 * 
 * This is the primary landing page for authenticated users.
 * It displays:
 *   - Personalized greeting with user's name
 *   - Tender statistics (total, credits, filters)
 *   - List of tenders matching user's preferences or last search
 *   - Real-time polling for new tenders (every 60 seconds)
 *   - Quick access to refresh data
 * 
 * Features:
 *   - Loads tenders based on user preferences (from onboarding)
 *   - Respects last search filters (from Search page)
 *   - Location-aware filtering using user's business address
 *   - Live polling for new tenders with notification banner
 *   - One-click refresh button
 * 
 * The dashboard persists search context: if you search on /search,
 * those filters are applied here automatically.
 */

import { useState, useEffect, useRef } from 'react'
import { useAuth } from '../context/AuthContext'
import { searchTenders, getLatest } from '../api/tenders'
import { RefreshCw, MapPin } from 'lucide-react'
import TenderCard from '../components/TenderCard'
import toast from 'react-hot-toast'

export default function Dashboard() {
  // ===========================================================================
  // HOOKS & CONTEXT
  // ===========================================================================
  
  const { user, refreshUser, lastSearch } = useAuth()
  
  // ===========================================================================
  // STATE
  // ===========================================================================
  
  // Current tenders displayed in the list
  const [tenders, setTenders] = useState([])
  
  // Loading state for initial/full refresh
  const [loading, setLoading] = useState(true)
  
  // Total number of tenders matching current filters
  const [total, setTotal] = useState(0)
  
  // Number of new tenders found since last poll
  const [newCount, setNewCount] = useState(0)
  
  // New tenders waiting to be loaded (from polling)
  const [pendingTenders, setPendingTenders] = useState([])
  
  // ===========================================================================
  // REFS
  // ===========================================================================
  
  // Timestamp for incremental updates (polling)
  const lastScrapeRef = useRef(new Date().toISOString())
  
  // Polling interval reference for cleanup
  const pollRef = useRef(null)
  
  // Track if initial load has completed (prevents duplicate loads)
  const initialLoadDone = useRef(false)

  // ===========================================================================
  // SEARCH PAYLOAD BUILDER
  // ===========================================================================
  
  /**
   * Build the search payload based on current context
   * 
   * Priority order:
   *   1. Last search filters (if user searched on /search page)
   *   2. User preferences (from onboarding)
   *   3. Empty/default values
   * 
   * Location handling:
   *   - If last search used "My Location", use those coordinates
   *   - Otherwise, fall back to user's saved business location
   * 
   * @returns {Object} { payload, ind, prov, muni }
   */
  const getPayload = () => {
    // Industries: lastSearch > user preferences > empty
    const ind = lastSearch?.industries?.length 
      ? lastSearch.industries 
      : (user?.industry_preferences || [])
    
    // Provinces: lastSearch > user preferences > empty
    const prov = lastSearch?.provinces?.length 
      ? lastSearch.provinces 
      : (user?.province_preferences || [])
    
    // Municipalities: only from lastSearch (not stored in user preferences)
    const muni = lastSearch?.municipalities?.length 
      ? lastSearch.municipalities 
      : []

    // Base payload
    const payload = { 
      industries: ind, 
      provinces: prov, 
      municipalities: muni, 
      page: 1, 
      page_size: 20 
    }

    // Attach location if available
    if (lastSearch?.userLat && lastSearch?.userLng && lastSearch?.useMyLocation) {
      // User explicitly used "My Location" in search
      payload.user_lat = lastSearch.userLat
      payload.user_lng = lastSearch.userLng
      payload.radius_km = lastSearch.radiusKm || 100
    } else if (user?.business_lat && user?.business_lng && !lastSearch?.industries?.length) {
      // First load with no search — use user's saved business location
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
   * Load tenders with current filters (full refresh)
   * 
   * Called on:
   *   - Initial page load
   *   - Manual refresh button click
   *   - When lastSearch changes
   */
  const loadTenders = async () => {
    setLoading(true)
    const { payload } = getPayload()
    
    try {
      const res = await searchTenders(payload)
      setTenders(res.data.results)
      setTotal(res.data.total)
      
      // Refresh user to get updated credit balance
      await refreshUser()
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to load tenders')
    } finally {
      setLoading(false)
    }
  }

  /**
   * Poll for new tenders (incremental update)
   * 
   * Called every 60 seconds via setInterval.
   * Uses the 'since' parameter to only fetch tenders added after last check.
   * New tenders are stored in pendingTenders and displayed as a notification.
   */
  const pollForNew = async () => {
    const { payload } = getPayload()
    
    try {
      const ind = payload.industries || []
      const prov = payload.provinces || []
      const muni = payload.municipalities || []
      
      // Fetch only tenders added since last check
      const res = await getLatest(lastScrapeRef.current, ind, prov, muni)
      
      if (res.data.new_count > 0) {
        // Store new tenders and show notification
        setPendingTenders(res.data.tenders)
        setNewCount(res.data.new_count)
        
        // Update timestamp for next poll
        lastScrapeRef.current = new Date().toISOString()
      }
    } catch {
      // Silently fail on polling errors (don't spam user with toasts)
    }
  }

  /**
   * Load new tenders from the notification banner
   * 
   * Prepends pending tenders to the current list and clears notification.
   */
  const loadNewTenders = () => {
    setTenders(prev => [...pendingTenders, ...prev])
    setTotal(prev => prev + pendingTenders.length)
    setPendingTenders([])
    setNewCount(0)
    refreshUser()
  }

  // ===========================================================================
  // EFFECTS
  // ===========================================================================
  
  /**
   * Initial load — runs once when user is available
   */
  useEffect(() => {
    if (user && !initialLoadDone.current) {
      initialLoadDone.current = true
      loadTenders()
    }
  }, [user])

  /**
   * Reload when lastSearch changes
   * 
   * This handles the flow: Search page → Dashboard
   * When user performs a search and navigates back, the dashboard
   * automatically shows those filtered results.
   */
  const lastSearchKey = JSON.stringify(lastSearch)
  const prevSearchKey = useRef(lastSearchKey)
  
  useEffect(() => {
    if (!initialLoadDone.current) return  // Don't reload before initial load
    
    if (prevSearchKey.current !== lastSearchKey) {
      prevSearchKey.current = lastSearchKey
      loadTenders()
    }
  }, [lastSearchKey])

  /**
   * Set up polling for new tenders
   * 
   * Polls every 60 seconds. Cleanup clears the interval.
   */
  useEffect(() => {
    pollRef.current = setInterval(pollForNew, 60000)  // 60 seconds
    return () => clearInterval(pollRef.current)
  }, [user, lastSearch])  // Re-create when user or search changes

  // ===========================================================================
  // COMPUTED DISPLAY VALUES
  // ===========================================================================
  
  const { ind, prov, muni } = getPayload()
  
  // Check if results come from an explicit search (vs. default preferences)
  const isFromSearch = lastSearch?.industries?.length > 0 || lastSearch?.provinces?.length > 0
  
  // Check if location-based filtering is active
  const hasLocation = (lastSearch?.useMyLocation && lastSearch?.userLat) || 
                      (user?.business_lat && !isFromSearch)
  
  // Human-readable location description
  const locationName = lastSearch?.userLat
    ? `${lastSearch.radiusKm || 100}km radius`
    : user?.business_location
      ? `near ${user.business_location}`
      : null

  // Time-based greeting
  const greeting = new Date().getHours() < 12 
    ? 'Good morning' 
    : new Date().getHours() < 17 
      ? 'Good afternoon' 
      : 'Good evening'

  // ===========================================================================
  // RENDER
  // ===========================================================================
  
  return (
    <div className="p-4 md:p-6 max-w-4xl mx-auto">
      {/* =====================================================================
          HEADER SECTION
          ===================================================================== */}
      <div className="flex items-start justify-between mb-4 md:mb-6">
        <div>
          {/* Greeting with user's first name */}
          <h1 className="text-lg md:text-xl font-semibold text-gray-900">
            {greeting}, {user?.full_name?.split(' ')[0]}
          </h1>
          
          {/* Tender count and filter context */}
          <p className="text-sm text-gray-500 mt-0.5">
            {total} tenders{isFromSearch ? ' — filtered by your last search' : ' matching your preferences'}
          </p>
          
          {/* Location indicator */}
          {hasLocation && locationName && (
            <div className="flex items-center gap-1 mt-1 text-xs text-brand-600">
              <MapPin size={11} />
              <span>{locationName}</span>
            </div>
          )}
        </div>
        
        {/* Right side: Live indicator + Refresh button */}
        <div className="flex items-center gap-2">
          <span className="hidden md:flex items-center gap-1.5 text-xs text-gray-400">
            <span className="w-1.5 h-1.5 rounded-full bg-brand-400 animate-pulse" />
            Live
          </span>
          <button 
            onClick={loadTenders} 
            className="p-1.5 rounded-lg hover:bg-gray-100 border border-gray-200 transition-colors"
            aria-label="Refresh tenders"
          >
            <RefreshCw size={14} />
          </button>
        </div>
      </div>

      {/* =====================================================================
          ACTIVE FILTER CHIPS
          =====================================================================
          Shows which filters are currently applied
      */}
      {(isFromSearch || muni.length > 0) && (
        <div className="mb-4 flex flex-wrap gap-1.5">
          {/* Industry chips */}
          {ind.map(i => (
            <span key={i} className="px-2 py-0.5 bg-brand-50 text-brand-700 text-xs rounded-full border border-brand-200">
              {i}
            </span>
          ))}
          
          {/* Province chips */}
          {prov.map(p => (
            <span key={p} className="px-2 py-0.5 bg-gray-100 text-gray-600 text-xs rounded-full border border-gray-200">
              {p}
            </span>
          ))}
          
          {/* Municipality chips */}
          {muni.map(m => (
            <span key={m} className="px-2 py-0.5 bg-purple-50 text-purple-700 text-xs rounded-full border border-purple-200">
              {m}
            </span>
          ))}
        </div>
      )}

      {/* =====================================================================
          NEW TENDERS NOTIFICATION
          =====================================================================
          Appears when polling discovers new tenders
      */}
      {newCount > 0 && (
        <div className="mb-4 flex items-center justify-between bg-brand-50 border border-brand-200 rounded-xl px-4 py-3 animate-in slide-in-from-top-2">
          <span className="text-sm text-brand-600">
            {newCount} new tender{newCount > 1 ? 's' : ''} found
          </span>
          <button 
            onClick={loadNewTenders} 
            className="text-sm font-medium text-brand-600 hover:text-brand-800 transition-colors"
          >
            Load
          </button>
        </div>
      )}

      {/* =====================================================================
          STATISTICS CARDS
          ===================================================================== */}
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

      {/* =====================================================================
          TENDER LIST
          ===================================================================== */}
      {loading ? (
        /* Loading spinner */
        <div className="flex justify-center py-16">
          <div className="w-6 h-6 border-2 border-brand-400 border-t-transparent rounded-full animate-spin" />
        </div>
      ) : tenders.length === 0 ? (
        /* Empty state */
        <div className="text-center py-16 text-gray-400 text-sm">
          No tenders found. Try adjusting your filters or location on the Search page.
        </div>
      ) : (
        /* Tender cards grid */
        <div className="grid grid-cols-1 gap-3">
          {tenders.map(t => (
            <TenderCard key={t.id} tender={t} showBadgeColor />
          ))}
        </div>
      )}
    </div>
  )
}