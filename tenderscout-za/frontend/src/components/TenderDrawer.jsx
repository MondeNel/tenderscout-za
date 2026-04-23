/**
 * File: src/components/TenderDrawer.jsx
 * Purpose: Slide-out Tender Detail Panel with PDF Viewer
 * 
 * This component renders a slide-out drawer from the right side of the screen
 * that displays detailed information about a tender and its associated document.
 * 
 * Features:
 *   - PDF document viewer using react-pdf
 *   - Page navigation (prev/next)
 *   - Zoom controls (in/out)
 *   - Download document via backend proxy
 *   - Fallback view for non-PDF documents or errors
 *   - Keyboard support (ESC to close)
 *   - Responsive design (full-width on mobile, max-width on desktop)
 * 
 * Document Handling:
 *   - PDFs: Embedded viewer with controls
 *   - DOCs/ZIPs: Fallback view with download option
 *   - Listing pages: Fallback view with link to source
 * 
 * Usage:
 *   <TenderDrawer tender={tenderObject} onClose={() => setOpen(false)} />
 */

import { useEffect, useState } from 'react'
import { Document, Page, pdfjs } from 'react-pdf'
import { 
  X,              // Close icon
  Download,       // Download icon
  ExternalLink,   // External link icon
  ChevronLeft,    // Previous page
  ChevronRight,   // Next page
  ZoomIn,         // Zoom in
  ZoomOut,        // Zoom out
  Loader          // Loading spinner
} from 'lucide-react'

// PDF.js styles for annotation and text layers
import 'react-pdf/dist/Page/AnnotationLayer.css'
import 'react-pdf/dist/Page/TextLayer.css'

// =============================================================================
// PDF.JS WORKER CONFIGURATION
// =============================================================================
// The worker is loaded from CDN to avoid bundling issues.
// This is required for PDF parsing in the browser.

pdfjs.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js'

// =============================================================================
// API CONFIGURATION
// =============================================================================
// Backend URL for proxy endpoint (handles CORS and authentication)

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

// =============================================================================
// HELPER COMPONENT: DetailRow
// =============================================================================

/**
 * Renders a labeled detail row in the fallback view
 * 
 * @param {string} label - Label text (e.g., "Title")
 * @param {string} value - Value to display
 * @param {string} valueClass - Additional CSS classes for value
 */
function DetailRow({ label, value, valueClass }) {
  if (!value) return null
  return (
    <div>
      <p className="text-xs text-gray-400 uppercase tracking-wide mb-1">{label}</p>
      <p className={valueClass || "text-sm text-gray-600"}>{value}</p>
    </div>
  )
}

// =============================================================================
// HELPER COMPONENT: FallbackIcon
// =============================================================================

/**
 * Renders an icon for the fallback view
 * Shows red X for errors, green external link for normal fallback
 * 
 * @param {boolean} pdfError - Whether there was a PDF loading error
 */
function FallbackIcon({ pdfError }) {
  if (pdfError) {
    return (
      <div className="w-14 h-14 rounded-full flex items-center justify-center bg-red-50">
        <X size={24} className="text-red-400" />
      </div>
    )
  }
  return (
    <div className="w-14 h-14 rounded-full flex items-center justify-center bg-brand-50">
      <ExternalLink size={24} className="text-brand-400" />
    </div>
  )
}

// =============================================================================
// HELPER COMPONENT: FallbackView
// =============================================================================

/**
 * Renders a fallback view when PDF cannot be displayed
 * 
 * Shown when:
 *   - Document is not a PDF (DOC, ZIP, etc.)
 *   - PDF failed to load (authentication required, CORS, etc.)
 *   - Tender only has a listing page URL (no direct document)
 * 
 * @param {Object} tender - Tender object
 * @param {string} docUrl - Document or source URL
 * @param {boolean} pdfError - Whether there was a PDF error
 * @param {Function} onDownload - Download handler
 * @param {boolean} isDirectDoc - Whether URL points to a document
 */
function FallbackView({ tender, docUrl, pdfError, onDownload, isDirectDoc }) {
  // Build location string
  const province = tender.province
    ? ((tender.town ? tender.town + ', ' : '') + tender.province)
    : null

  // Only show description if it's substantial
  const description = tender.description && tender.description.length > 20
    ? tender.description
    : null

  // Detect URL type for better messaging
  const isHtmlDetailPage = docUrl && !isDirectDoc && !docUrl.match(/\.(pdf|doc|docx|zip)$/i)
  const sourceSite = tender.source_site || 'the source website'

  // Customize message based on what we know about the URL
  let title, subtitle, showDownload

  if (pdfError) {
    title = 'Unable to load document'
    subtitle = 'The document may require authentication or cannot be embedded directly. Try opening it in your browser.'
    showDownload = true
  } else if (isDirectDoc) {
    title = 'Document available'
    subtitle = `This tender links to a document. Open it directly or download a copy.`
    showDownload = true
  } else if (isHtmlDetailPage) {
    title = 'Tender detail page'
    subtitle = `This tender has a dedicated page on ${sourceSite}. Open it to view full details and download the tender documents.`
    showDownload = false
  } else {
    title = 'Tender listing page'
    subtitle = `This tender is listed on ${sourceSite}. Visit the page to find and download the tender documents.`
    showDownload = false
  }

  return (
    <div className="flex flex-col items-center justify-center h-full gap-6 p-8 text-center">
      {/* Icon */}
      <FallbackIcon pdfError={pdfError} />

      {/* Message */}
      <div>
        <p className="text-base font-medium text-gray-900 mb-1">{title}</p>
        <p className="text-sm text-gray-500 mb-2">{subtitle}</p>
      </div>

      {/* Tender details card */}
      <div className="w-full max-w-md bg-white rounded-xl border border-gray-200 p-5 text-left space-y-3">
        <DetailRow label="Title" value={tender.title} valueClass="text-sm text-gray-900 font-medium" />
        <DetailRow label="Description" value={description} valueClass="text-sm text-gray-600" />
        <DetailRow label="Issuing body" value={tender.issuing_body} valueClass="text-sm text-gray-600" />
        <DetailRow label="Closing date" value={tender.closing_date} valueClass="text-sm text-red-500 font-medium" />
        <DetailRow label="Reference" value={tender.reference_number} valueClass="text-sm text-gray-600 font-mono" />
        <DetailRow label="Province" value={province} valueClass="text-sm text-gray-600" />
        <DetailRow label="Municipality" value={tender.municipality} valueClass="text-sm text-gray-600" />
        <DetailRow label="Town" value={tender.town} valueClass="text-sm text-gray-600" />
      </div>

      {/* Action buttons */}
      <div className="flex gap-3">
        {showDownload && (
          <button
            onClick={onDownload}
            className="flex items-center gap-2 px-4 py-2.5 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-lg text-sm font-medium transition-colors"
          >
            <Download size={15} /> Download
          </button>
        )}
        
        <a 
          href={docUrl} 
          target="_blank" 
          rel="noopener noreferrer" 
          className="flex items-center gap-2 px-4 py-2.5 bg-brand-400 hover:bg-brand-600 text-white rounded-lg text-sm font-medium transition-colors"
        >
          <ExternalLink size={15} /> {isHtmlDetailPage ? 'Open tender page' : 'Open in browser'}
        </a>
      </div>
    </div>
  )
}

// =============================================================================
// HELPER COMPONENT: PdfToolbar
// =============================================================================

/**
 * Renders the PDF viewer toolbar with navigation and zoom controls
 * 
 * @param {number} page - Current page number
 * @param {number} numPages - Total number of pages
 * @param {number} scale - Current zoom scale (1.0 = 100%)
 * @param {string} docUrl - Document URL
 * @param {Function} onPrev - Previous page handler
 * @param {Function} onNext - Next page handler
 * @param {Function} onZoomIn - Zoom in handler
 * @param {Function} onZoomOut - Zoom out handler
 * @param {Function} onDownload - Download handler
 */
function PdfToolbar({ 
  page, numPages, scale, docUrl, 
  onPrev, onNext, onZoomIn, onZoomOut, onDownload 
}) {
  return (
    <div className="flex items-center justify-between px-4 py-2 border-b border-gray-100 bg-gray-50 flex-shrink-0 flex-wrap gap-2">
      {/* Page navigation */}
      <div className="flex items-center gap-1">
        <button 
          onClick={onPrev} 
          disabled={page <= 1} 
          className="p-1.5 rounded hover:bg-gray-200 disabled:opacity-30 transition-colors"
        >
          <ChevronLeft size={15} />
        </button>
        <span className="text-sm text-gray-600 px-1">{page} / {numPages}</span>
        <button 
          onClick={onNext} 
          disabled={page >= numPages} 
          className="p-1.5 rounded hover:bg-gray-200 disabled:opacity-30 transition-colors"
        >
          <ChevronRight size={15} />
        </button>
      </div>

      {/* Zoom controls */}
      <div className="flex items-center gap-1">
        <button 
          onClick={onZoomOut} 
          className="p-1.5 rounded hover:bg-gray-200 transition-colors"
        >
          <ZoomOut size={15} />
        </button>
        <span className="text-sm text-gray-600 w-12 text-center">
          {Math.round(scale * 100)}%
        </span>
        <button 
          onClick={onZoomIn} 
          className="p-1.5 rounded hover:bg-gray-200 transition-colors"
        >
          <ZoomIn size={15} />
        </button>
      </div>

      {/* Download and external link */}
      <div className="flex items-center gap-2">
        <button
          onClick={onDownload}
          className="flex items-center gap-1.5 text-sm text-gray-600 hover:text-gray-900 px-2.5 py-1.5 rounded-lg hover:bg-gray-200 transition-colors"
        >
          <Download size={14} /> Download
        </button>
        
        <a 
          href={docUrl} 
          target="_blank" 
          rel="noopener noreferrer" 
          className="flex items-center gap-1.5 text-sm text-brand-600 hover:text-brand-800 px-2.5 py-1.5 rounded-lg hover:bg-brand-50 transition-colors"
        >
          <ExternalLink size={14} /> Open in browser
        </a>
      </div>
    </div>
  )
}

// =============================================================================
// MAIN COMPONENT: TenderDrawer
// =============================================================================

/**
 * TenderDrawer - Slide-out panel with tender details and document viewer
 * 
 * @param {Object} props
 * @param {Object} props.tender - Tender object to display
 * @param {Function} props.onClose - Callback when drawer is closed
 */
export default function TenderDrawer({ tender, onClose }) {
  // ===========================================================================
  // STATE
  // ===========================================================================
  
  const [numPages, setNumPages] = useState(null)    // Total PDF pages
  const [page, setPage] = useState(1)               // Current page
  const [scale, setScale] = useState(1.0)           // Zoom level
  const [pdfError, setPdfError] = useState(false)   // PDF loading error
  const [loading, setLoading] = useState(true)      // Loading state

  // ===========================================================================
  // COMPUTED VALUES
  // ===========================================================================
  
  // Use document URL if available, otherwise source URL
  const docUrl = tender ? (tender.document_url || tender.source_url) : null
  
  // Check if URL points to a direct document (PDF, DOC, etc.)
  const isDirectDoc = docUrl ? (
    docUrl.toLowerCase().includes('.pdf') ||
    docUrl.toLowerCase().includes('.doc') ||
    docUrl.toLowerCase().includes('.docx') ||
    docUrl.toLowerCase().includes('.zip') ||
    docUrl.toLowerCase().includes('phocadownload')
  ) : false
  
  // Check if it's specifically a PDF (for embedded viewer)
  const isPdf = isDirectDoc && (
    docUrl.toLowerCase().includes('.pdf') ||
    docUrl.toLowerCase().includes('phocadownload')
  )

  // ===========================================================================
  // KEYBOARD HANDLER (ESC to close)
  // ===========================================================================
  
  useEffect(() => {
    const handler = (e) => { 
      if (e.key === 'Escape') onClose() 
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [onClose])

  // ===========================================================================
  // RESET STATE WHEN TENDER CHANGES
  // ===========================================================================
  
  useEffect(() => {
    setPage(1)
    setScale(1.0)
    setPdfError(false)
    setLoading(true)
    setNumPages(null)
  }, [tender && tender.id])

  // ===========================================================================
  // DOWNLOAD HANDLER (via backend proxy)
  // ===========================================================================
  
  /**
   * Download the document through the backend proxy
   * 
   * The proxy handles:
   *   - CORS issues
   *   - Authentication requirements
   *   - Domain restrictions
   * 
   * Falls back to opening in new tab if download fails.
   */
  const handleDownload = async () => {
    if (!docUrl) return
    
    // Sanitize filename from title
    const safeName = tender.title.slice(0, 60).replace(/[^a-zA-Z0-9 ]/g, '') + '.pdf'
    
    try {
      // Use backend proxy endpoint
      const proxyUrl = `${API_URL}/proxy/pdf?url=${encodeURIComponent(docUrl)}`
      const response = await fetch(proxyUrl)

      console.log('[Download] status:', response.status)
      console.log('[Download] content-type:', response.headers.get('content-type'))

      if (!response.ok) throw new Error(`Proxy returned ${response.status}`)

      const blob = await response.blob()
      console.log('[Download] blob size:', blob.size, 'type:', blob.type)

      if (blob.size === 0) throw new Error('Empty response from proxy')

      // Create download link
      const pdfBlob = new Blob([blob], { type: 'application/pdf' })
      const objectUrl = URL.createObjectURL(pdfBlob)
      const a = document.createElement('a')
      a.href = objectUrl
      a.download = safeName
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      
      // Clean up object URL
      setTimeout(() => URL.revokeObjectURL(objectUrl), 1000)
    } catch (err) {
      console.error('[Download] failed:', err)
      // Fallback: open in new tab
      window.open(docUrl, '_blank')
    }
  }

  // ===========================================================================
  // GUARD: No tender
  // ===========================================================================
  
  if (!tender) return null

  // ===========================================================================
  // DISPLAY FLAGS
  // ===========================================================================
  
  const showPdf = isPdf && !pdfError
  const showToolbar = showPdf && numPages !== null

  // ===========================================================================
  // HEADER METADATA
  // ===========================================================================
  
  const headerMeta = [
    tender.issuing_body,
    tender.province
      ? ((tender.town ? tender.town + ', ' : '') + tender.province)
      : null,
    tender.closing_date ? ('Closes ' + tender.closing_date) : null,
  ].filter(Boolean).join(' • ')

  // ===========================================================================
  // RENDER
  // ===========================================================================
  
  return (
    <div>
      {/* =====================================================================
          BACKDROP (click to close)
          ===================================================================== */}
      <div
        className="fixed inset-0 bg-black bg-opacity-40 z-40"
        onClick={onClose}
      />

      {/* =====================================================================
          DRAWER PANEL
          =====================================================================
          Fixed to right side, full height, max width on desktop
      */}
      <div className="fixed top-0 right-0 bottom-0 z-50 w-full max-w-3xl bg-white shadow-2xl flex flex-col">

        {/* =================================================================
            HEADER
            ================================================================= */}
        <div className="flex items-start justify-between gap-3 px-5 py-4 border-b border-gray-200 bg-white flex-shrink-0">
          <div className="min-w-0">
            <h2 className="text-base font-semibold text-gray-900 leading-snug line-clamp-2">
              {tender.title}
            </h2>
            <p className="text-sm text-gray-500 mt-0.5">{headerMeta}</p>
          </div>
          <button
            onClick={onClose}
            className="flex-shrink-0 p-1.5 rounded-lg hover:bg-gray-100 text-gray-500 transition-colors"
          >
            <X size={18} />
          </button>
        </div>

        {/* =================================================================
            PDF TOOLBAR (only shown for PDFs)
            ================================================================= */}
        {showToolbar && (
          <PdfToolbar
            page={page}
            numPages={numPages}
            scale={scale}
            docUrl={docUrl}
            onPrev={() => setPage(p => Math.max(1, p - 1))}
            onNext={() => setPage(p => Math.min(numPages, p + 1))}
            onZoomIn={() => setScale(s => Math.min(2.5, parseFloat((s + 0.2).toFixed(1))))}
            onZoomOut={() => setScale(s => Math.max(0.5, parseFloat((s - 0.2).toFixed(1))))}
            onDownload={handleDownload}
          />
        )}

        {/* =================================================================
            CONTENT AREA (PDF Viewer or Fallback)
            ================================================================= */}
        <div className="flex-1 overflow-auto bg-gray-100">
          {showPdf ? (
            /* -------------------------------------------------------------
               PDF VIEWER
               ------------------------------------------------------------- */
            <div className="flex flex-col items-center py-6 px-4">
              {/* Loading indicator */}
              {loading && (
                <div className="flex flex-col items-center justify-center py-20 gap-3 text-gray-400">
                  <Loader size={28} className="animate-spin text-brand-400" />
                  <p className="text-sm">Loading document...</p>
                </div>
              )}
              
              {/* PDF Document */}
              <Document
                file={docUrl}
                onLoadSuccess={({ numPages: n }) => { 
                  setNumPages(n)
                  setLoading(false) 
                }}
                onLoadError={() => { 
                  setPdfError(true)
                  setLoading(false) 
                }}
                loading=""
              >
                <Page
                  pageNumber={page}
                  scale={scale}
                  className="shadow-lg rounded"
                  renderTextLayer={true}
                  renderAnnotationLayer={true}
                />
              </Document>
            </div>
          ) : (
            /* -------------------------------------------------------------
               FALLBACK VIEW (non-PDF or error)
               ------------------------------------------------------------- */
            <FallbackView
              tender={tender}
              docUrl={docUrl}
              pdfError={pdfError}
              onDownload={handleDownload}
              isDirectDoc={isDirectDoc}
            />
          )}
        </div>
      </div>
    </div>
  )
}