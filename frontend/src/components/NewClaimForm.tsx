import { useState, useEffect } from 'react'
import { X, Upload } from 'lucide-react'
import { api } from '../api/client'

const CAUSES = ['Fire', 'Flood', 'Theft', 'Liability', 'Wind/Hail', 'Water Damage', 'Other']

interface Props { onClose: () => void; onCreated: () => void }

export default function NewClaimForm({ onClose, onCreated }: Props) {
  const [claimId, setClaimId]       = useState('')
  const [insured, setInsured]       = useState('')
  const [policy, setPolicy]         = useState('')
  const [dol, setDol]               = useState(new Date().toISOString().split('T')[0])
  const [cause, setCause]           = useState('Fire')
  const [files, setFiles]           = useState<File[]>([])
  const [loading, setLoading]       = useState(false)
  const [error, setError]           = useState('')

  useEffect(() => {
    api.getNextId().then(r => setClaimId(r.id))
  }, [])

  const submit = async () => {
    if (!claimId || files.length === 0) { setError('Claim ID and at least one PDF required.'); return }
    setLoading(true); setError('')
    const fd = new FormData()
    fd.append('claim_id', claimId)
    fd.append('insured_name', insured)
    fd.append('policy_id', policy)
    fd.append('date_of_loss', dol)
    fd.append('cause_of_loss', cause)
    files.forEach(f => fd.append('files', f))
    try {
      await api.createClaim(fd)
      onCreated()
    } catch (e) { setError(String(e)) }
    setLoading(false)
  }

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-bg-card border border-border rounded-xl w-full max-w-md shadow-2xl">
        <div className="flex items-center justify-between px-6 py-4 border-b border-border">
          <h2 className="text-hi font-bold text-base">➕ Create New Claim</h2>
          <button onClick={onClose} className="text-muted hover:text-hi transition-colors"><X size={18} /></button>
        </div>

        <div className="px-6 py-5 space-y-4">
          <div>
            <label className="text-xs text-muted uppercase tracking-wider block mb-1">Claim ID</label>
            <input value={claimId} onChange={e => setClaimId(e.target.value.toUpperCase())}
              className="w-full bg-bg-hover border border-border rounded-lg px-3 py-2 text-hi text-sm font-mono focus:outline-none focus:border-teal" />
          </div>
          <div>
            <label className="text-xs text-muted uppercase tracking-wider block mb-1">Insured Name</label>
            <input value={insured} onChange={e => setInsured(e.target.value)} placeholder="e.g. Acme Corporation"
              className="w-full bg-bg-hover border border-border rounded-lg px-3 py-2 text-hi text-sm focus:outline-none focus:border-teal" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-muted uppercase tracking-wider block mb-1">Policy Number</label>
              <input value={policy} onChange={e => setPolicy(e.target.value)} placeholder="POL-2025-001"
                className="w-full bg-bg-hover border border-border rounded-lg px-3 py-2 text-hi text-sm focus:outline-none focus:border-teal" />
            </div>
            <div>
              <label className="text-xs text-muted uppercase tracking-wider block mb-1">Date of Loss</label>
              <input type="date" value={dol} onChange={e => setDol(e.target.value)}
                className="w-full bg-bg-hover border border-border rounded-lg px-3 py-2 text-hi text-sm focus:outline-none focus:border-teal" />
            </div>
          </div>
          <div>
            <label className="text-xs text-muted uppercase tracking-wider block mb-1">Cause of Loss</label>
            <select value={cause} onChange={e => setCause(e.target.value)}
              className="w-full bg-bg-hover border border-border rounded-lg px-3 py-2 text-hi text-sm focus:outline-none focus:border-teal">
              {CAUSES.map(c => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
          <div>
            <label className="text-xs text-muted uppercase tracking-wider block mb-1">Upload PDFs</label>
            <label className="flex flex-col items-center gap-2 border border-dashed border-border rounded-lg px-4 py-5 cursor-pointer hover:border-teal/50 transition-colors">
              <Upload size={20} className="text-muted" />
              <span className="text-muted text-xs">Drop PDFs or click to browse</span>
              <input type="file" multiple accept=".pdf" className="hidden"
                onChange={e => setFiles(Array.from(e.target.files ?? []))} />
            </label>
            {files.length > 0 && (
              <div className="mt-2 space-y-1">
                {files.map(f => (
                  <div key={f.name} className="flex items-center gap-2 text-xs text-mid bg-bg-hover px-2 py-1 rounded">
                    📄 {f.name}
                  </div>
                ))}
              </div>
            )}
          </div>
          {error && <div className="text-red-400 text-xs">{error}</div>}
        </div>

        <div className="px-6 pb-5 flex gap-3">
          <button onClick={onClose} className="flex-1 py-2.5 border border-border rounded-lg text-mid text-sm hover:text-hi transition-colors">
            Cancel
          </button>
          <button onClick={submit} disabled={loading}
            className="flex-1 py-2.5 bg-teal text-bg-deep font-bold text-sm rounded-lg hover:bg-teal-light disabled:opacity-50 transition-colors">
            {loading ? 'Creating…' : '✅ Create Claim'}
          </button>
        </div>
      </div>
    </div>
  )
}
