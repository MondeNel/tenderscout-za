// src/components/TenderCard.jsx
import { useState } from 'react'
import { ExternalLink, MapPin, Building2, AlertCircle, FileText, Calendar } from 'lucide-react'
import TenderDrawer from './TenderDrawer'

const INDUSTRY_COLORS = {
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
  "Security, Access, Alarms & Fire": "bg-indigo-50 text-indigo-700",
  "Travel, Tourism & Hospitality":   "bg-emerald-50 text-emerald-700",
  // Legacy fallbacks
  "General":                         "bg-gray-100 text-gray-600",
  "Construction":                    "bg-amber-50 text-amber-700",
  "ICT / Technology":                "bg-sky-50 text-sky-700",
  "Security Services":               "bg-indigo-50 text-indigo-700",
}

function formatDate(dateStr) {
  if (!dateStr) return null
  // Handle dd/mm/yyyy format from SA sites
  const ddmm = dateStr.match(/^(\d{2})\/(\d{2})\/(\d{4})$/)
  if (ddmm) {
    const [, d, m, y] = ddmm
    const date = new Date(`${y}-${m}-${d}`)
    if (!isNaN(date.getTime())) {
      return date.toLocaleDateString('en-ZA', { day: '2-digit', month: 'short', year: 'numeric' })
    }
  }
  try {
    const d = new Date(dateStr)
    if (!isNaN(d.getTime())) {
      return d.toLocaleDateString('en-ZA', { day: '2-digit', month: 'short', year: 'numeric' })
    }
  } catch { return null }
  return null
}

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
  const diffDays = (d - new Date()) / (1000 * 60 * 60 * 24)
  return diffDays >= 0 && diffDays <= 7
}

function isValidUrl(url) {
  try { return Boolean(new URL(url)) } catch { return false }
}

export default function TenderCard({ tender, showBadgeColor = true, compact = false }) {
  const [drawerOpen, setDrawerOpen] = useState(false)

  const color = showBadgeColor
    ? (INDUSTRY_COLORS[tender.industry_category] || INDUSTRY_COLORS['General'])
    : 'bg-gray-100 text-gray-600'

  const linkUrl   = tender.document_url || tender.source_url
  const validUrl  = isValidUrl(linkUrl)
  const isPdf     = linkUrl?.toLowerCase().includes('.pdf') || linkUrl?.toLowerCase().includes('phocadownload')
  const expiring  = isExpiringSoon(tender.closing_date)
  const closingFmt = formatDate(tender.closing_date)

  const locationParts = [tender.town, tender.province].filter(Boolean)
  const location = locationParts.join(', ') || null

  if (compact) {
    return (
      <div
        className="flex items-start gap-3 px-4 py-3 hover:bg-gray-50 cursor-pointer border-b border-gray-100 last:border-0"
        onClick={() => validUrl && setDrawerOpen(true)}
      >
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-gray-900 truncate">{tender.title}</p>
          <p className="text-xs text-gray-400 mt-0.5">{tender.issuing_body} {location ? `· ${location}` : ''}</p>
        </div>
        <span className={`badge flex-shrink-0 text-xs ${color}`}>{tender.industry_category}</span>
        {drawerOpen && <TenderDrawer tender={tender} onClose={() => setDrawerOpen(false)} />}
      </div>
    )
  }

  return (
    <>
      <div
        className="card hover:border-gray-300 hover:shadow-sm transition-all cursor-pointer"
        onClick={() => validUrl && setDrawerOpen(true)}
      >
        <div className="flex items-start justify-between gap-3 mb-2">
          <h3 className="text-sm font-semibold text-gray-900 leading-snug">{tender.title}</h3>
          <span className={`badge flex-shrink-0 text-xs ${color}`}>{tender.industry_category || 'General'}</span>
        </div>

        <div className="flex flex-wrap gap-x-4 gap-y-1 mb-3">
          {tender.issuing_body && (
            <span className="flex items-center gap-1 text-xs text-gray-500">
              <Building2 size={11} className="flex-shrink-0" />{tender.issuing_body}
            </span>
          )}
          {location && (
            <span className="flex items-center gap-1 text-xs text-gray-500">
              <MapPin size={11} className="flex-shrink-0" />{location}
            </span>
          )}
          {tender.reference_number && (
            <span className="text-xs text-gray-400 font-mono">{tender.reference_number}</span>
          )}
        </div>

        <div className="flex items-center justify-between pt-2 border-t border-gray-100">
          {closingFmt ? (
            <span className={`flex items-center gap-1 text-xs font-medium ${
              expiring ? 'text-orange-600' : 'text-red-500'
            }`}>
              <Calendar size={11} />
              {expiring ? '⚠ ' : ''}Closes {closingFmt}
            </span>
          ) : (
            <span className="text-xs text-gray-400">{tender.source_site}</span>
          )}

          {validUrl ? (
            <button
              onClick={e => { e.stopPropagation(); setDrawerOpen(true) }}
              className="flex items-center gap-1 text-xs text-brand-600 hover:text-brand-800 font-medium"
            >
              {isPdf ? <><FileText size={12} /> View doc</> : <><ExternalLink size={12} /> View tender</>}
            </button>
          ) : (
            <span className="flex items-center gap-1 text-xs text-gray-400">
              <AlertCircle size={11} /> No link
            </span>
          )}
        </div>
      </div>

      {drawerOpen && <TenderDrawer tender={tender} onClose={() => setDrawerOpen(false)} />}
    </>
  )
}