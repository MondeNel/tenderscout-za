/**
 * File: src/components/TenderCard.jsx
 * Purpose: Individual Tender Display Card Component
 * 
 * This component renders a single tender in a card format.
 * It supports two display modes:
 *   - Full card: Detailed view with all metadata (used in Dashboard, Search results)
 *   - Compact: Minimal row view (used in lists, map popups)
 * 
 * Features:
 *   - Industry-specific color coding
 *   - Closing date formatting and "expiring soon" warning
 *   - Document/PDF link detection
 *   - Click to open detail drawer (TenderDrawer)
 *   - Responsive design
 * 
 * Usage:
 *   <TenderCard tender={tenderObject} />
 *   <TenderCard tender={tenderObject} compact />
 *   <TenderCard tender={tenderObject} showBadgeColor={false} />
 */

import { useState } from 'react'
import { 
  ExternalLink,   // External link icon
  MapPin,         // Location icon
  Building2,      // Building/issuing body icon
  AlertCircle,    // Warning icon (no link)
  FileText,       // Document icon (PDF)
  Calendar        // Calendar icon (closing date)
} from 'lucide-react'
import TenderDrawer from './TenderDrawer'

// =============================================================================
// INDUSTRY COLOR MAPPING
// =============================================================================
/**
 * Maps industry categories to Tailwind color classes for badges.
 * Each industry has a distinct color combination for visual recognition.
 * 
 * Format: "bg-{color}-50 text-{color}-700"
 * This creates a subtle background with darker text for readability.
 */
const INDUSTRY_COLORS = {
  // Current industry categories (from updated utils.py)
  "Accounting, Banking & Legal":     "bg-blue-50 text-blue-700",
  "Building & Trades":               "bg-amber-50 text-amber-700",
  "Civil":                           "bg-stone-50 text-stone-700",
  "Cleaning & Facility Management":  "bg-teal-50 text-teal-700",
  "Consultants":                     "bg-purple-50 text-purple-700",
  "Electrical & Automation":         "bg-yellow-50 text-yellow-700",
  "Engineering Consultants":         "bg-orange-50 text-orange-700",
  "General, Property & Auctions":    "bg-gray-100 text-gray-600",
  "HR & Training":                   "bg-pink-50 text-pink-700",
  "IT & Telecoms":                   "bg-sky-50 text-sky-700",
  "Materials, Supply & Services":    "bg-lime-50 text-lime-700",
  "Mechanical, Plant & Equipment":   "bg-zinc-50 text-zinc-700",
  "Media & Marketing":               "bg-rose-50 text-rose-700",
  "Medical & Healthcare":            "bg-red-50 text-red-700",
  "Plumbing & Water":                "bg-cyan-50 text-cyan-700",
  "Security, Access, Alarms & Fire": "bg-indigo-50 text-indigo-700",
  "Transport & Logistics":           "bg-slate-50 text-slate-700",
  "Travel, Tourism & Hospitality":   "bg-emerald-50 text-emerald-700",
  "Waste Management":                "bg-lime-50 text-lime-700",
  
  // Legacy fallbacks (for older tenders with old category names)
  "General":                         "bg-gray-100 text-gray-600",
  "Construction":                    "bg-amber-50 text-amber-700",
  "ICT / Technology":                "bg-sky-50 text-sky-700",
  "Security Services":               "bg-indigo-50 text-indigo-700",
  "Catering":                        "bg-orange-50 text-orange-700",
}

// =============================================================================
// DATE FORMATTING UTILITIES
// =============================================================================

/**
 * Format a date string for display
 * 
 * South African tender sites use various date formats.
 * This function handles:
 *   - DD/MM/YYYY (most common)
 *   - ISO format (YYYY-MM-DD)
 *   - Other parseable formats
 * 
 * Output format: "15 Apr 2026" (en-ZA locale)
 * 
 * @param {string} dateStr - Raw date string from tender
 * @returns {string|null} Formatted date or null if invalid
 */
function formatDate(dateStr) {
  if (!dateStr) return null
  
  // Handle DD/MM/YYYY format (most common in SA)
  const ddmm = dateStr.match(/^(\d{2})\/(\d{2})\/(\d{4})$/)
  if (ddmm) {
    const [, d, m, y] = ddmm
    const date = new Date(`${y}-${m}-${d}`)
    if (!isNaN(date.getTime())) {
      return date.toLocaleDateString('en-ZA', { 
        day: '2-digit', 
        month: 'short', 
        year: 'numeric' 
      })
    }
  }
  
  // Try standard date parsing
  try {
    const d = new Date(dateStr)
    if (!isNaN(d.getTime())) {
      return d.toLocaleDateString('en-ZA', { 
        day: '2-digit', 
        month: 'short', 
        year: 'numeric' 
      })
    }
  } catch {
    return null
  }
  
  return null
}

/**
 * Check if a tender is expiring within the next 7 days
 * 
 * Used to show a warning icon and orange text for urgent tenders.
 * 
 * @param {string} dateStr - Closing date string
 * @returns {boolean} True if closing within 7 days
 */
function isExpiringSoon(dateStr) {
  if (!dateStr) return false
  
  const ddmm = dateStr.match(/^(\d{2})\/(\d{2})\/(\d{4})$/)
  let d
  
  if (ddmm) {
    d = new Date(`${ddmm[3]}-${ddmm[2]}-${ddmm[1]}`)
  } else {
    d = new Date(dateStr)
  }
  
  if (isNaN(d.getTime())) return false
  
  // Calculate days until closing
  const diffDays = (d - new Date()) / (1000 * 60 * 60 * 24)
  return diffDays >= 0 && diffDays <= 7
}

// =============================================================================
// URL VALIDATION
// =============================================================================

/**
 * Validate if a string is a proper URL
 * 
 * @param {string} url - URL string to validate
 * @returns {boolean} True if valid URL
 */
function isValidUrl(url) {
  try { 
    return Boolean(new URL(url)) 
  } catch { 
    return false 
  }
}

// =============================================================================
// MAIN COMPONENT
// =============================================================================

/**
 * TenderCard Component
 * 
 * @param {Object} props
 * @param {Object} props.tender - Tender object from API
 * @param {boolean} props.showBadgeColor - Whether to show industry color badge
 * @param {boolean} props.compact - Use compact row layout instead of full card
 */
export default function TenderCard({ 
  tender, 
  showBadgeColor = true, 
  compact = false 
}) {
  // ===========================================================================
  // STATE
  // ===========================================================================
  
  // Controls the detail drawer visibility
  const [drawerOpen, setDrawerOpen] = useState(false)

  // ===========================================================================
  // COMPUTED VALUES
  // ===========================================================================
  
  // Get industry color or fallback to General
  const color = showBadgeColor
    ? (INDUSTRY_COLORS[tender.industry_category] || INDUSTRY_COLORS['General'])
    : 'bg-gray-100 text-gray-600'
  
  // Determine which URL to use (document URL preferred over source URL)
  const linkUrl = tender.document_url || tender.source_url
  const validUrl = isValidUrl(linkUrl)
  
  // Check if the link is a PDF document
  const isPdf = linkUrl?.toLowerCase().includes('.pdf') || 
                linkUrl?.toLowerCase().includes('phocadownload')
  
  // Check if tender is expiring soon
  const expiring = isExpiringSoon(tender.closing_date)
  
  // Format the closing date
  const closingFmt = formatDate(tender.closing_date)
  
  // Build location string from town and province
  const locationParts = [tender.town, tender.province].filter(Boolean)
  const location = locationParts.join(', ') || null

  // ===========================================================================
  // COMPACT LAYOUT (Row style)
  // ===========================================================================
  // Used in lists, map popups, and recent tenders sections
  
  if (compact) {
    return (
      <>
        <div
          className="flex items-start gap-3 px-4 py-3 hover:bg-gray-50 cursor-pointer border-b border-gray-100 last:border-0 transition-colors"
          onClick={() => validUrl && setDrawerOpen(true)}
        >
          {/* Content */}
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-gray-900 truncate">
              {tender.title}
            </p>
            <p className="text-xs text-gray-400 mt-0.5">
              {tender.issuing_body} {location ? `· ${location}` : ''}
            </p>
          </div>
          
          {/* Industry badge */}
          <span className={`badge flex-shrink-0 text-xs ${color}`}>
            {tender.industry_category || 'General'}
          </span>
        </div>
        
        {/* Detail drawer */}
        {drawerOpen && (
          <TenderDrawer 
            tender={tender} 
            onClose={() => setDrawerOpen(false)} 
          />
        )}
      </>
    )
  }

  // ===========================================================================
  // FULL CARD LAYOUT
  // ===========================================================================
  // Used in dashboard and search results
  
  return (
    <>
      <div
        className="card hover:border-gray-300 hover:shadow-sm transition-all cursor-pointer"
        onClick={() => validUrl && setDrawerOpen(true)}
      >
        {/* =====================================================================
            HEADER: Title and Industry Badge
            ===================================================================== */}
        <div className="flex items-start justify-between gap-3 mb-2">
          <h3 className="text-sm font-semibold text-gray-900 leading-snug">
            {tender.title}
          </h3>
          <span className={`badge flex-shrink-0 text-xs ${color}`}>
            {tender.industry_category || 'General'}
          </span>
        </div>

        {/* =====================================================================
            METADATA: Issuing Body, Location, Reference Number
            ===================================================================== */}
        <div className="flex flex-wrap gap-x-4 gap-y-1 mb-3">
          {/* Issuing body */}
          {tender.issuing_body && (
            <span className="flex items-center gap-1 text-xs text-gray-500">
              <Building2 size={11} className="flex-shrink-0" />
              {tender.issuing_body}
            </span>
          )}
          
          {/* Location (town + province) */}
          {location && (
            <span className="flex items-center gap-1 text-xs text-gray-500">
              <MapPin size={11} className="flex-shrink-0" />
              {location}
            </span>
          )}
          
          {/* Reference number */}
          {tender.reference_number && (
            <span className="text-xs text-gray-400 font-mono">
              {tender.reference_number}
            </span>
          )}
        </div>

        {/* =====================================================================
            FOOTER: Closing Date and Action Button
            ===================================================================== */}
        <div className="flex items-center justify-between pt-2 border-t border-gray-100">
          {/* Closing date (with expiring soon warning) */}
          {closingFmt ? (
            <span className={`flex items-center gap-1 text-xs font-medium ${
              expiring ? 'text-orange-600' : 'text-red-500'
            }`}>
              <Calendar size={11} />
              {expiring ? '⚠ ' : ''}Closes {closingFmt}
            </span>
          ) : (
            // Fallback: show source site if no closing date
            <span className="text-xs text-gray-400">{tender.source_site}</span>
          )}

          {/* Action button (View document / View tender / No link) */}
          {validUrl ? (
            <button
              onClick={e => { 
                e.stopPropagation()  // Prevent card click from firing twice
                setDrawerOpen(true) 
              }}
              className="flex items-center gap-1 text-xs text-brand-600 hover:text-brand-800 font-medium transition-colors"
            >
              {isPdf ? (
                <>
                  <FileText size={12} /> View doc
                </>
              ) : (
                <>
                  <ExternalLink size={12} /> View tender
                </>
              )}
            </button>
          ) : (
            <span className="flex items-center gap-1 text-xs text-gray-400">
              <AlertCircle size={11} /> No link
            </span>
          )}
        </div>
      </div>

      {/* =====================================================================
          DETAIL DRAWER (Modal)
          ===================================================================== */}
      {drawerOpen && (
        <TenderDrawer 
          tender={tender} 
          onClose={() => setDrawerOpen(false)} 
        />
      )}
    </>
  )
}