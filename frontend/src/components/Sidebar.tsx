import { useState, useEffect } from 'react'
import { FileText, Plus, Upload, ChevronDown, ChevronRight } from 'lucide-react'
import { api, Claim, Document } from '../api/client'
import NewClaimForm from './NewClaimForm'
import DocumentModal from './DocumentModal'

interface Props {
  claims: Claim[]
  selectedId: string | null
  onSelect: (id: string) => void
  onRefresh: () => void
}

export default function Sidebar({ claims, selectedId, onSelect, onRefresh }: Props) {
  const [docs, setDocs]             = useState<Document[]>([])
  const [showNewClaim, setShowNewClaim] = useState(false)
  const [viewDoc, setViewDoc]       = useState<Document | null>(null)

  useEffect(() => {
    if (selectedId) api.getDocuments(selectedId).then(setDocs)
  }, [selectedId])

  const selected = claims.find(c => c.id === selectedId)

  return (
    <>
      <aside className="w-60 flex-shrink-0 bg-bg-card border-r border-border flex flex-col overflow-hidden">
        {/* Logo */}
        <div className="px-5 py-5 border-b border-border">
          <div className="text-hi font-extrabold text-base tracking-wide leading-tight">🏥 Insurance<br/>Intelligence</div>
          <div className="text-muted text-xs mt-0.5 uppercase tracking-widest">P&C Claims System</div>
        </div>

        {/* Claims list */}
        <div className="flex-1 overflow-y-auto px-3 py-3 space-y-0.5">
          <div className="text-muted text-xs font-bold uppercase tracking-widest px-2 mb-2">Claims</div>
          {claims.map(c => (
            <button
              key={c.id}
              onClick={() => onSelect(c.id)}
              className={[
                'w-full text-left px-3 py-2 rounded text-xs font-medium transition-colors',
                c.id === selectedId
                  ? 'bg-teal/10 text-teal border border-teal/30'
                  : 'text-mid hover:bg-bg-hover hover:text-hi',
              ].join(' ')}
            >
              <div className="flex items-center gap-1.5">
                {c.is_new && <span className="text-teal text-xs">🆕</span>}
                <span className="font-mono">{c.id}</span>
              </div>
              {c.insured_name && (
                <div className="text-muted text-xs truncate mt-0.5">{c.insured_name}</div>
              )}
            </button>
          ))}
        </div>

        {/* Selected claim docs */}
        {selected && docs.length > 0 && (
          <div className="border-t border-border px-3 py-3 max-h-56 overflow-y-auto">
            <div className="text-muted text-xs font-bold uppercase tracking-widest px-1 mb-2">
              {docs.length} Documents
            </div>
            {docs.map(d => (
              <button
                key={d.file_type}
                onClick={() => setViewDoc(d)}
                className="w-full text-left flex items-center gap-2 px-2 py-1.5 rounded text-xs text-mid hover:text-teal hover:bg-teal/5 transition-colors"
              >
                <FileText size={12} className="flex-shrink-0" />
                <span className="truncate">{d.file_type}</span>
              </button>
            ))}
          </div>
        )}

        {/* New Claim + Upload */}
        <div className="border-t border-border p-3 space-y-2">
          <button
            onClick={() => setShowNewClaim(true)}
            className="w-full flex items-center gap-2 px-3 py-2 rounded text-xs font-semibold text-teal border border-teal/30 hover:bg-teal/10 transition-colors"
          >
            <Plus size={13} /> New Claim
          </button>
          <div className="text-muted text-xs text-center">
            {claims.length} claims · {claims.reduce((a, c) => a + c.doc_count, 0)} docs
          </div>
        </div>
      </aside>

      {showNewClaim && (
        <NewClaimForm
          onClose={() => setShowNewClaim(false)}
          onCreated={() => { setShowNewClaim(false); onRefresh() }}
        />
      )}
      {viewDoc && (
        <DocumentModal doc={viewDoc} onClose={() => setViewDoc(null)} />
      )}
    </>
  )
}
