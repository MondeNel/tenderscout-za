import { useState } from 'react'
import { ExternalLink, MapPin, Clock, Building2, AlertCircle, FileText } from 'lucide-react'
import TenderDrawer from './TenderDrawer'

const BADGE_COLORS = {
  'ICT / Technology':     'bg-blue-50 text-blue-700',
  'Construction':         'bg-amber-50 text-amber-700',
  'Security Services':    'bg-indigo-50 text-indigo-700',
  'Electrical Services':  'bg-yellow-50 text-yellow-700',
  'Waste Management':     'bg-green-50 text-green-700',
  'Plumbing':             'bg-cyan-50 text-cyan-700',
  'Maintenance':          'bg-orange-50 text-orange-700',
  'Mining Services':      'bg-stone-50 text-stone-700',
  'Cleaning Services':    'bg-teal-50 text-teal-700',
  'Catering':             'bg-rose-50 text-rose-700',
  'Healthcare':           'bg-red-50 text-red-700',
  'Consulting':           'bg-purple-50 text-purple-700',
  'General':              'bg-gray-100 text-gray-600',
}

function formatDate(dateStr) {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  return d.toLocaleString('en-ZA', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
}

function isValidUrl(url) {
  try { return Boolean(new URL(url)) } catch { return false }
}

export default function TenderCard({ tender, showBadgeColor = true }) {
  const [drawerOpen, setDrawerOpen] = useState(false)

  const color = showBadgeColor
    ? (BADGE_COLORS[tender.industry_category] || BADGE_COLORS['General'])
    : 'bg-gray-100 text-gray-600'

  const linkUrl = tender.document_url || tender.source_url
  const validUrl = isValidUrl(linkUrl)
  const isPdf = linkUrl?.toLowerCase().includes('.pdf') ||
                linkUrl?.toLowerCase().includes('phocadownload')

  return (
    <>
      <div
        className="card hover:border-gray-300 transition-colors cursor-pointer"
        onClick={() => validUrl && setDrawerOpen(true)}
      >
        <div className="flex items-start justify-between gap-3 mb-2">
          <h3 className="text-base font-medium text-gray-900 leading-snug">{tender.title}</h3>
          <span className={'badge flex-shrink-0 ' + color}>{tender.industry_category}</span>
        </div>

        {tender.description && tender.description.length > 20 && (
          <p className="text-sm text-gray-500 mb-2 line-clamp-2">{tender.description}</p>
        )}

        <div className="flex flex-wrap gap-x-4 gap-y-1 mb-3">
          {tender.issuing_body && (
            <span className="flex items-center gap-1 text-sm text-gray-500">
              <Building2 size={12} />{tender.issuing_body}
            </span>
          )}
          {/* Municipality (new) */}
          {tender.municipality && (
            <span className="flex items-center gap-1 text-sm text-gray-500">
              <Building2 size={12} />{tender.municipality}
            </span>
          )}
          {tender.province && (
            <span className="flex items-center gap-1 text-sm text-gray-500">
              <MapPin size={12} />{tender.town ? tender.town + ', ' : ''}{tender.province}
            </span>
          )}
          <span className="flex items-center gap-1 text-sm text-gray-500">
            <Clock size={12} />{formatDate(tender.scraped_at)}
          </span>
        </div>

        <div className="flex items-center justify-between pt-2 border-t border-gray-100">
          {tender.closing_date
            ? <span className="text-sm text-red-500">Closes {tender.closing_date}</span>
            : <span className="text-sm text-gray-400">{tender.source_site}</span>
          }
          {validUrl ? (
            <button
              onClick={e => { e.stopPropagation(); setDrawerOpen(true) }}
              className="flex items-center gap-1 text-sm text-brand-600 hover:text-brand-800 font-medium"
            >
              {isPdf ? <><FileText size={13} /> View document</> : <><ExternalLink size={13} /> View tender</>}
            </button>
          ) : (
            <span className="flex items-center gap-1 text-sm text-gray-400">
              <AlertCircle size={13} /> Link unavailable
            </span>
          )}
        </div>
      </div>

      {drawerOpen && (
        <TenderDrawer
          tender={tender}
          onClose={() => setDrawerOpen(false)}
        />
      )}
    </>
  )
}