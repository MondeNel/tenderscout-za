import { useEffect, useState } from 'react'
import { Document, Page, pdfjs } from 'react-pdf'
import { X, Download, ExternalLink, ChevronLeft, ChevronRight, ZoomIn, ZoomOut, Loader } from 'lucide-react'
import 'react-pdf/dist/Page/AnnotationLayer.css'
import 'react-pdf/dist/Page/TextLayer.css'

pdfjs.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js'

function DetailRow({ label, value, valueClass }) {
  if (!value) return null
  return (
    <div>
      <p className="text-xs text-gray-400 uppercase tracking-wide mb-1">{label}</p>
      <p className={valueClass || "text-sm text-gray-600"}>{value}</p>
    </div>
  )
}

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

function FallbackView({ tender, docUrl, pdfError, onDownload, isDirectDoc }) {
  const province = tender.province
    ? ((tender.town ? tender.town + ', ' : '') + tender.province)
    : null

  const description = tender.description && tender.description.length > 20
    ? tender.description
    : null

  const title = pdfError ? 'Unable to load document' : 'Tender listing page'
  const subtitle = pdfError
    ? 'The document may require authentication or cannot be embedded directly.'
    : 'This tender links to a listing page. Open it to find and download the tender documents.'

  return (
    <div className="flex flex-col items-center justify-center h-full gap-6 p-8 text-center">
      <FallbackIcon pdfError={pdfError} />

      <div>
        <p className="text-base font-medium text-gray-900 mb-1">{title}</p>
        <p className="text-sm text-gray-500 mb-2">{subtitle}</p>
      </div>

      <div className="w-full max-w-md bg-white rounded-xl border border-gray-200 p-5 text-left space-y-3">
        <DetailRow label="Title" value={tender.title} valueClass="text-sm text-gray-900 font-medium" />
        <DetailRow label="Description" value={description} valueClass="text-sm text-gray-600" />
        <DetailRow label="Issuing body" value={tender.issuing_body} valueClass="text-sm text-gray-600" />
        <DetailRow label="Closing date" value={tender.closing_date} valueClass="text-sm text-red-500 font-medium" />
        <DetailRow label="Reference" value={tender.reference_number} valueClass="text-sm text-gray-600 font-mono" />
        <DetailRow label="Province" value={province} valueClass="text-sm text-gray-600" />
      </div>

      <div className="flex gap-3">
        <button
          onClick={onDownload}
          className="flex items-center gap-2 px-4 py-2.5 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-lg text-sm font-medium"
        >
          <Download size={15} /> Download
        </button>
        
        <a href={docUrl} target="_blank" rel="noopener noreferrer" className="flex items-center gap-2 px-4 py-2.5 bg-brand-400 hover:bg-brand-600 text-white rounded-lg text-sm font-medium">
          <ExternalLink size={15} /> Open tender page
        </a>
      </div>
    </div>
  )
}

function PdfToolbar({ page, numPages, scale, docUrl, onPrev, onNext, onZoomIn, onZoomOut, onDownload }) {
  return (
    <div className="flex items-center justify-between px-4 py-2 border-b border-gray-100 bg-gray-50 flex-shrink-0 flex-wrap gap-2">
      <div className="flex items-center gap-1">
        <button onClick={onPrev} disabled={page <= 1} className="p-1.5 rounded hover:bg-gray-200 disabled:opacity-30">
          <ChevronLeft size={15} />
        </button>
        <span className="text-sm text-gray-600 px-1">{page} / {numPages}</span>
        <button onClick={onNext} disabled={page >= numPages} className="p-1.5 rounded hover:bg-gray-200 disabled:opacity-30">
          <ChevronRight size={15} />
        </button>
      </div>

      <div className="flex items-center gap-1">
        <button onClick={onZoomOut} className="p-1.5 rounded hover:bg-gray-200">
          <ZoomOut size={15} />
        </button>
        <span className="text-sm text-gray-600 w-12 text-center">{Math.round(scale * 100)}%</span>
        <button onClick={onZoomIn} className="p-1.5 rounded hover:bg-gray-200">
          <ZoomIn size={15} />
        </button>
      </div>

      <div className="flex items-center gap-2">
        <button
          onClick={onDownload}
          className="flex items-center gap-1.5 text-sm text-gray-600 hover:text-gray-900 px-2.5 py-1.5 rounded-lg hover:bg-gray-200"
        >
          <Download size={14} /> Download
        </button>
        
        <a href={docUrl} target="_blank" rel="noopener noreferrer" className="flex items-center gap-1.5 text-sm text-brand-600 hover:text-brand-800 px-2.5 py-1.5 rounded-lg hover:bg-brand-50">
          <ExternalLink size={14} /> Open in browser
        </a>
      </div>
    </div>
  )
}

export default function TenderDrawer({ tender, onClose }) {
  const [numPages, setNumPages] = useState(null)
  const [page, setPage] = useState(1)
  const [scale, setScale] = useState(1.0)
  const [pdfError, setPdfError] = useState(false)
  const [loading, setLoading] = useState(true)

  const docUrl = tender ? (tender.document_url || tender.source_url) : null
  const isDirectDoc = docUrl ? (
    docUrl.toLowerCase().includes('.pdf') ||
    docUrl.toLowerCase().includes('.doc') ||
    docUrl.toLowerCase().includes('.docx') ||
    docUrl.toLowerCase().includes('.zip') ||
    docUrl.toLowerCase().includes('phocadownload')
  ) : false
  const isPdf = isDirectDoc && (
    docUrl.toLowerCase().includes('.pdf') ||
    docUrl.toLowerCase().includes('phocadownload')
  )

  useEffect(() => {
    const handler = (e) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [onClose])

  useEffect(() => {
    setPage(1)
    setScale(1.0)
    setPdfError(false)
    setLoading(true)
    setNumPages(null)
  }, [tender && tender.id])

  const handleDownload = async () => {
    if (!docUrl) return
    const safeName = tender.title.slice(0, 60).replace(/[^a-zA-Z0-9 ]/g, '') + '.pdf'
    try {
      const proxyUrl = `http://localhost:8000/proxy/pdf?url=${encodeURIComponent(docUrl)}`
      const response = await fetch(proxyUrl)

      console.log('[Download] status:', response.status)
      console.log('[Download] content-type:', response.headers.get('content-type'))

      if (!response.ok) throw new Error(`Proxy returned ${response.status}`)

      const blob = await response.blob()
      console.log('[Download] blob size:', blob.size, 'type:', blob.type)

      if (blob.size === 0) throw new Error('Empty response from proxy')

      // Force PDF mime type if blob came back as octet-stream
      const pdfBlob = new Blob([blob], { type: 'application/pdf' })
      const objectUrl = URL.createObjectURL(pdfBlob)
      const a = document.createElement('a')
      a.href = objectUrl
      a.download = safeName
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      setTimeout(() => URL.revokeObjectURL(objectUrl), 1000)
    } catch (err) {
      console.error('[Download] failed:', err)
      // Fallback: open directly in new tab
      window.open(docUrl, '_blank')
    }
  }

  if (!tender) return null

  const showPdf = isPdf && !pdfError
  const showToolbar = showPdf && numPages !== null

  const headerMeta = [
    tender.issuing_body,
    tender.province
      ? ((tender.town ? tender.town + ', ' : '') + tender.province)
      : null,
    tender.closing_date ? ('Closes ' + tender.closing_date) : null,
  ].filter(Boolean).join(' · ')

  return (
    <div>
      <div
        className="fixed inset-0 bg-black bg-opacity-40 z-40"
        onClick={onClose}
      />

      <div className="fixed top-0 right-0 bottom-0 z-50 w-full max-w-3xl bg-white shadow-2xl flex flex-col">

        <div className="flex items-start justify-between gap-3 px-5 py-4 border-b border-gray-200 bg-white flex-shrink-0">
          <div className="min-w-0">
            <h2 className="text-base font-semibold text-gray-900 leading-snug line-clamp-2">
              {tender.title}
            </h2>
            <p className="text-sm text-gray-500 mt-0.5">{headerMeta}</p>
          </div>
          <button
            onClick={onClose}
            className="flex-shrink-0 p-1.5 rounded-lg hover:bg-gray-100 text-gray-500"
          >
            <X size={18} />
          </button>
        </div>

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

        <div className="flex-1 overflow-auto bg-gray-100">
          {showPdf ? (
            <div className="flex flex-col items-center py-6 px-4">
              {loading && (
                <div className="flex flex-col items-center justify-center py-20 gap-3 text-gray-400">
                  <Loader size={28} className="animate-spin text-brand-400" />
                  <p className="text-sm">Loading document...</p>
                </div>
              )}
              <Document
                file={docUrl}
                onLoadSuccess={({ numPages: n }) => { setNumPages(n); setLoading(false) }}
                onLoadError={() => { setPdfError(true); setLoading(false) }}
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
