import { useEffect, useState } from 'react'
import { Document, Page, pdfjs } from 'react-pdf'
import { X, Download, ExternalLink, ChevronLeft, ChevronRight, ZoomIn, ZoomOut, Loader } from 'lucide-react'
import 'react-pdf/dist/Page/AnnotationLayer.css'
import 'react-pdf/dist/Page/TextLayer.css'

// Point pdfjs worker to the correct version
pdfjs.GlobalWorkerOptions.workerSrc = `https://cdnjs.cloudflare.com/ajax/libs/pdf.js/${pdfjs.version}/pdf.worker.min.js`

export default function TenderDrawer({ tender, onClose }) {
  const [numPages, setNumPages] = useState(null)
  const [page, setPage] = useState(1)
  const [scale, setScale] = useState(1.0)
  const [pdfError, setPdfError] = useState(false)
  const [loading, setLoading] = useState(true)

  const docUrl = tender?.document_url || tender?.source_url
  const isPdf = docUrl?.toLowerCase().includes('.pdf') ||
                docUrl?.toLowerCase().includes('phocadownload')

  // Close on Escape key
  useEffect(() => {
    const handler = (e) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [onClose])

  // Reset state when tender changes
  useEffect(() => {
    setPage(1)
    setScale(1.0)
    setPdfError(false)
    setLoading(true)
    setNumPages(null)
  }, [tender?.id])

  const handleDownload = () => {
    const a = document.createElement('a')
    a.href = docUrl
    a.download = tender.title.slice(0, 60).replace(/[^a-zA-Z0-9 ]/g, '') + '.pdf'
    a.target = '_blank'
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
  }

  if (!tender) return null

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black bg-opacity-40 z-40 transition-opacity"
        onClick={onClose}
      />

      {/* Drawer */}
      <div className="fixed top-0 right-0 bottom-0 z-50 w-full max-w-3xl bg-white shadow-2xl flex flex-col">

        {/* Header */}
        <div className="flex items-start justify-between gap-3 px-5 py-4 border-b border-gray-200 bg-white flex-shrink-0">
          <div className="min-w-0">
            <h2 className="text-base font-semibold text-gray-900 leading-snug truncate">
              {tender.title}
            </h2>
            <p className="text-sm text-gray-500 mt-0.5">
              {tender.issuing_body}
              {tender.province ? ` · ${tender.town ? tender.town + ', ' : ''}${tender.province}` : ''}
              {tender.closing_date ? ` · Closes ${tender.closing_date}` : ''}
            </p>
          </div>
          <button
            onClick={onClose}
            className="flex-shrink-0 p-1.5 rounded-lg hover:bg-gray-100 text-gray-500"
          >
            <X size={18} />
          </button>
        </div>

        {/* PDF Toolbar */}
        {isPdf && !pdfError && numPages && (
          <div className="flex items-center justify-between px-5 py-2.5 border-b border-gray-100 bg-gray-50 flex-shrink-0">
            {/* Page controls */}
            <div className="flex items-center gap-2">
              <button
                onClick={() => setPage(p => Math.max(1, p - 1))}
                disabled={page <= 1}
                className="p-1 rounded hover:bg-gray-200 disabled:opacity-30"
              >
                <ChevronLeft size={16} />
              </button>
              <span className="text-sm text-gray-600 min-w-[80px] text-center">
                {page} / {numPages}
              </span>
              <button
                onClick={() => setPage(p => Math.min(numPages, p + 1))}
                disabled={page >= numPages}
                className="p-1 rounded hover:bg-gray-200 disabled:opacity-30"
              >
                <ChevronRight size={16} />
              </button>
            </div>

            {/* Zoom controls */}
            <div className="flex items-center gap-2">
              <button
                onClick={() => setScale(s => Math.max(0.5, s - 0.2))}
                className="p-1 rounded hover:bg-gray-200"
              >
                <ZoomOut size={16} />
              </button>
              <span className="text-sm text-gray-600 w-12 text-center">
                {Math.round(scale * 100)}%
              </span>
              <button
                onClick={() => setScale(s => Math.min(2.5, s + 0.2))}
                className="p-1 rounded hover:bg-gray-200"
              >
                <ZoomIn size={16} />
              </button>
            </div>

            {/* Actions */}
            <div className="flex items-center gap-2">
              <button
                onClick={handleDownload}
                className="flex items-center gap-1.5 text-sm text-gray-600 hover:text-gray-900 px-2.5 py-1.5 rounded-lg hover:bg-gray-200"
              >
                <Download size={14} /> Download
              </button>
              
                href={docUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1.5 text-sm text-brand-600 hover:text-brand-800 px-2.5 py-1.5 rounded-lg hover:bg-brand-50"
              >
                <ExternalLink size={14} /> Open in browser
              </a>
            </div>
          </div>
        )}

        {/* Content area */}
        <div className="flex-1 overflow-auto bg-gray-100">
          {isPdf && !pdfError ? (
            <div className="flex flex-col items-center py-6 px-4 min-h-full">
              {loading && (
                <div className="flex flex-col items-center justify-center py-20 gap-3 text-gray-400">
                  <Loader size={28} className="animate-spin text-brand-400" />
                  <p className="text-sm">Loading document...</p>
                </div>
              )}
              <Document
                file={docUrl}
                onLoadSuccess={({ numPages }) => {
                  setNumPages(numPages)
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
            /* Fallback — non-PDF or PDF load failed */
            <div className="flex flex-col items-center justify-center h-full gap-6 p-8 text-center">
              {pdfError ? (
                <>
                  <div className="w-14 h-14 bg-red-50 rounded-full flex items-center justify-center">
                    <X size={24} className="text-red-400" />
                  </div>
                  <div>
                    <p className="text-base font-medium text-gray-900 mb-1">
                      Unable to load document
                    </p>
                    <p className="text-sm text-gray-500 mb-6">
                      The document may require authentication or isn't publicly accessible as a direct embed.
                    </p>
                  </div>
                </>
              ) : (
                <>
                  <div className="w-14 h-14 bg-brand-50 rounded-full flex items-center justify-center">
                    <ExternalLink size={24} className="text-brand-400" />
                  </div>
                  <div>
                    <p className="text-base font-medium text-gray-900 mb-1">
                      Tender listing page
                    </p>
                    <p className="text-sm text-gray-500 mb-6">
                      This tender links to a listing page. Open it to find and download the tender documents.
                    </p>
                  </div>
                </>
              )}

              {/* Tender details summary */}
              <div className="w-full max-w-md bg-white rounded-xl border border-gray-200 p-5 text-left space-y-3">
                <div>
                  <p className="text-xs text-gray-400 uppercase tracking-wide mb-1">Title</p>
                  <p className="text-sm font-medium text-gray-900">{tender.title}</p>
                </div>
                {tender.description && tender.description.length > 20 && (
                  <div>
                    <p className="text-xs text-gray-400 uppercase tracking-wide mb-1">Description</p>
                    <p className="text-sm text-gray-600">{tender.description}</p>
                  </div>
                )}
                {tender.issuing_body && (
                  <div>
                    <p className="text-xs text-gray-400 uppercase tracking-wide mb-1">Issuing body</p>
                    <p className="text-sm text-gray-600">{tender.issuing_body}</p>
                  </div>
                )}
                {tender.closing_date && (
                  <div>
                    <p className="text-xs text-gray-400 uppercase tracking-wide mb-1">Closing date</p>
                    <p className="text-sm text-red-500 font-medium">{tender.closing_date}</p>
                  </div>
                )}
                {tender.reference_number && (
                  <div>
                    <p className="text-xs text-gray-400 uppercase tracking-wide mb-1">Reference</p>
                    <p className="text-sm text-gray-600 font-mono">{tender.reference_number}</p>
                  </div>
                )}
              </div>

              <div className="flex gap-3">
                <button
                  onClick={handleDownload}
                  className="flex items-center gap-2 px-4 py-2.5 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-lg text-sm font-medium"
                >
                  <Download size={15} /> Download
                </button>
                
                  href={docUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-2 px-4 py-2.5 bg-brand-400 hover:bg-brand-600 text-white rounded-lg text-sm font-medium"
                >
                  <ExternalLink size={15} /> Open tender page
                </a>
              </div>
            </div>
          )}
        </div>
      </div>
    </>
  )
}
