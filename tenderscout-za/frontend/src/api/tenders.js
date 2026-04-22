/**
 * File: src/api/tenders.js
 * Purpose: Tender Search and Retrieval API Service
 * 
 * This module provides functions for all tender-related API calls:
 *   - Advanced search with filtering and location-based ranking
 *   - Fetching recently added tenders
 *   - Retrieving a single tender by ID
 *   - Viewing search history
 * 
 * All functions use the pre-configured Axios client from client.js,
 * which automatically handles token injection and 401 redirects.
 * 
 * Note: Search operations consume credits from the user's balance.
 */

import client from './client'

// =============================================================================
// ADVANCED SEARCH
// =============================================================================

/**
 * Search tenders with full filtering and location-aware parameters
 * 
 * Endpoint: POST /search/tenders
 * 
 * Requires Authentication: Yes (JWT token required)
 * Consumes Credits: Yes (1 credit per result returned)
 * 
 * Request Body:
 *   - industries: string[] - Filter by industry categories
 *   - provinces: string[] - Filter by provinces
 *   - municipalities: string[] - Filter by municipalities
 *   - towns: string[] - Filter by towns/cities
 *   - keyword: string - Free-text search across title, description, issuing body
 *   - user_lat: number - Latitude of user's business location (optional)
 *   - user_lng: number - Longitude of user's business location (optional)
 *   - radius_km: number - Search radius in kilometers (requires lat/lng)
 *   - page: number - Page number for pagination (1-based, default: 1)
 *   - page_size: number - Results per page (default: 20)
 * 
 * Response:
 *   {
 *     "total": 156,                    // Total matching tenders
 *     "page": 1,                       // Current page
 *     "page_size": 20,                 // Results per page
 *     "results": [                     // Array of tender objects
 *       {
 *         "id": 123,
 *         "title": "IT Support Services",
 *         "description": "...",
 *         "issuing_body": "City of Johannesburg",
 *         "province": "Gauteng",
 *         "municipality": "City of Johannesburg",
 *         "town": "Johannesburg",
 *         "industry_category": "IT & Telecoms",
 *         "closing_date": "15/05/2026",
 *         "source_url": "https://...",
 *         "document_url": "https://.../tender.pdf",
 *         ...
 *       }
 *     ],
 *     "credits_charged": 20            // Credits deducted for this search
 *   }
 * 
 * Location-Based Ranking (when lat/lng provided):
 *   - Tenders with coordinates are ranked by distance from user
 *   - Tenders without coordinates appear at the end
 *   - Radius filter excludes tenders beyond radius_km
 * 
 * Error Responses:
 *   - 402: Insufficient credits
 *   - 400: Invalid parameters
 * 
 * @param {Object} params - Search parameters
 * @returns {Promise} Axios promise resolving to search results
 */
export const searchTenders = (params) => client.post('/search/tenders', params)

// =============================================================================
// LATEST TENDERS (Dashboard Feed)
// =============================================================================

/**
 * Get recently added tenders with optional filtering
 * 
 * Endpoint: GET /tenders/latest
 * 
 * Requires Authentication: Yes (JWT token required)
 * Does NOT consume credits (free dashboard view)
 * 
 * Query Parameters:
 *   - since: ISO datetime string - Only tenders added after this time
 *   - industries: string (comma-separated) - Filter by industries
 *   - provinces: string (comma-separated) - Filter by provinces
 *   - municipalities: string (comma-separated) - Filter by municipalities
 * 
 * Response:
 *   {
 *     "new_count": 12,                 // Number of new tenders returned
 *     "tenders": [...]                 // Array of tender objects (max 50)
 *   }
 * 
 * Usage:
 *   - Dashboard: Show tenders matching user's preferences
 *   - Polling: Check for new tenders since last visit
 *   - Filtered feeds: Industry-specific or province-specific views
 * 
 * Example:
 *   // Get all latest tenders
 *   await getLatest()
 * 
 *   // Get tenders since yesterday
 *   const yesterday = new Date(Date.now() - 86400000).toISOString()
 *   await getLatest(yesterday)
 * 
 *   // Get IT tenders in Gauteng
 *   await getLatest(null, ['IT & Telecoms'], ['Gauteng'])
 * 
 * @param {string} since - ISO datetime for incremental updates (optional)
 * @param {string[]} industries - Industry categories to filter by (optional)
 * @param {string[]} provinces - Provinces to filter by (optional)
 * @param {string[]} municipalities - Municipalities to filter by (optional)
 * @returns {Promise} Axios promise resolving to latest tenders response
 */
export const getLatest = (since, industries, provinces, municipalities) => {
  // Build query string from provided parameters
  const params = new URLSearchParams()
  
  // Only add parameters that have values
  if (since) {
    params.append('since', since)
  }
  
  // Convert arrays to comma-separated strings for query params
  if (industries?.length) {
    params.append('industries', industries.join(','))
  }
  
  if (provinces?.length) {
    params.append('provinces', provinces.join(','))
  }
  
  if (municipalities?.length) {
    params.append('municipalities', municipalities.join(','))
  }
  
  // Build final URL with query string
  const queryString = params.toString()
  return client.get(`/tenders/latest${queryString ? `?${queryString}` : ''}`)
}

// =============================================================================
// SINGLE TENDER RETRIEVAL
// =============================================================================

/**
 * Get a single tender by ID
 * 
 * Endpoint: GET /tenders/{id}
 * 
 * Requires Authentication: Yes (JWT token required)
 * Does NOT consume credits (viewing details is free)
 * 
 * Response:
 *   Returns the full tender object with all details:
 *   - id, title, description
 *   - issuing_body, province, municipality, town
 *   - industry_category
 *   - closing_date, posted_date
 *   - source_url, document_url
 *   - reference_number, contact_info
 *   - is_active, scraped_at
 * 
 * Usage:
 *   - Tender detail modal/drawer
 *   - Document viewing page
 *   - Bookmark/save functionality
 * 
 * Example:
 *   const tender = await getTender(123)
 *   console.log(tender.data.title)
 * 
 * @param {number|string} id - The tender ID to retrieve
 * @returns {Promise} Axios promise resolving to tender object
 */
export const getTender = (id) => client.get(`/tenders/${id}`)

// =============================================================================
// SEARCH HISTORY
// =============================================================================

/**
 * Get the current user's search history
 * 
 * Endpoint: GET /search/history
 * 
 * Requires Authentication: Yes (JWT token required)
 * Does NOT consume credits
 * 
 * Response:
 *   Array of search log entries (most recent first, max 20):
 *   [
 *     {
 *       "id": 456,
 *       "user_id": 1,
 *       "query_params": {
 *         "industries": ["IT & Telecoms"],
 *         "provinces": ["Gauteng"],
 *         "keyword": "security"
 *       },
 *       "result_count": 15,
 *       "credits_charged": 15,
 *       "searched_at": "2026-04-22T10:30:00Z"
 *     }
 *   ]
 * 
 * Usage:
 *   - Display recent searches for quick re-run
 *   - Analytics for user behavior
 *   - Credit usage tracking
 * 
 * @returns {Promise} Axios promise resolving to search history array
 */
export const getSearchHistory = () => client.get('/search/history')