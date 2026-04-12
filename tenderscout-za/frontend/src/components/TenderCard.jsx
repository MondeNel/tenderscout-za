import { ExternalLink, MapPin, Clock, Building2, AlertCircle } from 'lucide-react'

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

function timeAgo(dateStr) {
  const diff = Date.now() - new Date(dateStr).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 60) return mins + 'm ago'
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return hrs + 'h ago'
  return Math.floor(hrs / 24) + 'd ago'
}

function isValidUrl(url) {
  try { return Boolean(new URL(url)) } catch { return false }
}

export default function TenderCard({ tender, showBadgeColor = true }) {
  const color = showBadgeColor
    ? (BADGE_COLORS[tender.industry_category] || BADGE_COLORS['General'])
    : 'bg-gray-100 text-gray-600'
  const validUrl = isValidUrl(tender.source_url)

  return (
    <div className="card hover:border-gray-300 transition-colors">
      <div className="flex items-start justify-between gap-3 mb-2">
        <h3 className="text-sm font-medium text-gray-900 leading-snug">{tender.title}</h3>
        <span className={'badge flex-shrink-0 ' + color}>{tender.industry_category}</span>
      </div>
      {tender.description && tender.description.length > 20 && (
        <p className="text-xs text-gray-500 mb-2 line-clamp-2">{tender.description}</p>
      )}
      <div className="flex flex-wrap gap-x-4 gap-y-1 mb-3">
        {tender.issuing_body && (
          <span className="flex items-center gap-1 text-xs text-gray-500">
            <Building2 size={11} />{tender.issuing_body}
          </span>
        )}
        {tender.province && (
          <span className="flex items-center gap-1 text-xs text-gray-500">
            <MapPin size={11} />{tender.town ? tender.town + ', ' : ''}{tender.province}
          </span>
        )}
        <span className="flex items-center gap-1 text-xs text-gray-500">
          <Clock size={11} />{timeAgo(tender.scraped_at)}
        </span>
      </div>
      <div className="flex items-center justify-between pt-2 border-t border-gray-100">
        {tender.closing_date
          ? <span className="text-xs text-red-500">Closes {tender.closing_date}</span>
          : <span className="text-xs text-gray-400">{tender.source_site}</span>
        }
        {validUrl ? (
          <a href={tender.source_url} target="_blank" rel="noopener noreferrer"
            className="flex items-center gap-1 text-xs text-brand-600 hover:text-brand-800">
            View tender <ExternalLink size={11} />
          </a>
        ) : (
          <span className="flex items-center gap-1 text-xs text-gray-400">
            <AlertCircle size={11} /> Link unavailable
          </span>
        )}
      </div>
    </div>
  )
}
