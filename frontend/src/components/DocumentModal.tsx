import { useEffect, useRef, useState } from 'react'
import { X, Download, ChevronLeft, ChevronRight, ZoomIn, ZoomOut } from 'lucide-react'
import * as pdfjsLib from 'pdfjs-dist'
import { api, Document } from '../api/client'

// Point PDF.js worker at its own bundled copy
pdfjsLib.GlobalWorkerOptions.workerSrc = new URL(
  'pdfjs-dist/build/pdf.worker.mjs',
  import.meta.url,
).toString()

interface Props { doc: Document; onClose: () => void }

export default function DocumentModal({ doc, onClose }: Props) {
  const pdfUrl   = api.pdfUrl(doc.claim_id, doc.path)
  const canvasRef = useRef<HTMLDivElement>(null)

  const [numPages, setNumPages]   = useState(0)
  const [page, setPage]           = useState(1)
  const [scale, setScale]         = useState(1.4)
  const [loading, setLoading]     = useState(true)
  const [error, setError]         = useState('')
  const [pdfDoc, setPdfDoc]       = useState<any>(null)

  // Load PDF document once
  useEffect(() => {
    setLoading(true); setError('')
    pdfjsLib.getDocument({ url: pdfUrl }).promise
      .then(pdf => { setPdfDoc(pdf); setNumPages(pdf.numPages); setLoading(false) })
      .catch(e => { setError(String(e)); setLoading(false) })
  }, [pdfUrl])

  // Render current page whenever page or scale changes
  useEffect(() => {
    if (!pdfDoc || !canvasRef.current) return
    const container = canvasRef.current
    container.innerHTML = ''
    pdfDoc.getPage(page).then((pg: any) => {
      const viewport = pg.getViewport({ scale })
      const canvas   = document.createElement('canvas')
      canvas.width   = viewport.width
      canvas.height  = viewport.height
      canvas.style.borderRadius = '6px'
      canvas.style.boxShadow    = '0 4px 24px rgba(0,0,0,0.4)'
      container.appendChild(canvas)
      pg.render({ canvasContext: canvas.getContext('2d')!, viewport })
    })
  }, [pdfDoc, page, scale])

  const download = async () => {
    const blob = await fetch(pdfUrl).then(r => r.blob())
    const a    = document.createElement('a')
    a.href     = URL.createObjectURL(blob)
    a.download = doc.path
    a.click()
    URL.revokeObjectURL(a.href)
  }

  return (
    <div
      className="fixed inset-0 bg-black/75 backdrop-blur-sm z-50 flex items-center justify-center p-4"
      onClick={e => e.target === e.currentTarget && onClose()}
    >
      <div className="bg-bg-card border border-border rounded-2xl w-full max-w-4xl h-[92vh] flex flex-col shadow-2xl overflow-hidden">

        {/* ── Header ─────────────────────────────────────────────────────── */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-border flex-shrink-0">
          <div className="flex items-center gap-3 min-w-0">
            <span className="text-2xl">📄</span>
            <div className="min-w-0">
              <h2 className="text-hi font-bold text-sm truncate">
                {doc.claim_id} — {doc.file_type}
              </h2>
              <p className="text-muted text-xs font-mono truncate">{doc.path}</p>
            </div>
          </div>
          <div className="flex items-center gap-2 flex-shrink-0">
            {/* Zoom controls */}
            <button onClick={() => setScale(s => Math.max(0.6, s - 0.2))}
              className="w-8 h-8 flex items-center justify-center rounded-lg border border-border text-muted hover:text-hi hover:border-teal/40 transition-colors">
              <ZoomOut size={14} />
            </button>
            <span className="text-muted text-xs w-10 text-center">{Math.round(scale * 100)}%</span>
            <button onClick={() => setScale(s => Math.min(2.8, s + 0.2))}
              className="w-8 h-8 flex items-center justify-center rounded-lg border border-border text-muted hover:text-hi hover:border-teal/40 transition-colors">
              <ZoomIn size={14} />
            </button>
            {/* Download — manual, no auto-trigger */}
            <button onClick={download}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-border text-mid text-xs hover:text-teal hover:border-teal/40 transition-colors ml-1">
              <Download size={13} /> Download
            </button>
            <button onClick={onClose} className="w-8 h-8 flex items-center justify-center rounded-lg text-muted hover:text-hi transition-colors ml-1">
              <X size={16} />
            </button>
          </div>
        </div>

        {/* ── PDF Canvas ──────────────────────────────────────────────────── */}
        <div className="flex-1 overflow-auto bg-[#111320] flex justify-center py-6 px-4">
          {loading && (
            <div className="flex items-center justify-center h-full text-muted text-sm">
              <span className="animate-pulse">Loading PDF…</span>
            </div>
          )}
          {error && (
            <div className="flex items-center justify-center h-full text-red-400 text-sm">{error}</div>
          )}
          <div ref={canvasRef} className="flex flex-col items-center" />
        </div>

        {/* ── Page navigation ─────────────────────────────────────────────── */}
        {numPages > 1 && (
          <div className="flex items-center justify-center gap-4 px-6 py-3 border-t border-border bg-bg-card flex-shrink-0">
            <button
              onClick={() => setPage(p => Math.max(1, p - 1))}
              disabled={page === 1}
              className="w-8 h-8 flex items-center justify-center rounded-lg border border-border text-mid hover:text-hi hover:border-teal/40 disabled:opacity-30 transition-colors"
            >
              <ChevronLeft size={16} />
            </button>
            <span className="text-mid text-sm font-medium">
              Page <span className="text-hi font-bold">{page}</span> of <span className="text-hi font-bold">{numPages}</span>
            </span>
            <button
              onClick={() => setPage(p => Math.min(numPages, p + 1))}
              disabled={page === numPages}
              className="w-8 h-8 flex items-center justify-center rounded-lg border border-border text-mid hover:text-hi hover:border-teal/40 disabled:opacity-30 transition-colors"
            >
              <ChevronRight size={16} />
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
