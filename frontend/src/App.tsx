import { useState, useEffect } from 'react'
import Sidebar from './components/Sidebar'
import SummaryTab from './components/SummaryTab'
import ChatTab from './components/ChatTab'
import { api, Claim } from './api/client'

type Tab = 'summary' | 'chat'

export default function App() {
  const [claims, setClaims]           = useState<Claim[]>([])
  const [selectedId, setSelectedId]   = useState<string | null>(null)
  const [activeTab, setActiveTab]     = useState<Tab>('summary')
  const [summaryCache, setSummaryCache] = useState<Record<string, any>>({})

  useEffect(() => {
    api.getClaims().then(data => {
      setClaims(data)
      if (data.length > 0 && !selectedId) setSelectedId(data[0].id)
    })
  }, [])

  const selected = claims.find(c => c.id === selectedId) ?? null

  const refreshClaims = () =>
    api.getClaims().then(data => { setClaims(data) })

  return (
    <div className="flex h-screen overflow-hidden bg-bg-deep text-mid font-sans">
      <Sidebar
        claims={claims}
        selectedId={selectedId}
        onSelect={id => { setSelectedId(id); setActiveTab('summary') }}
        onRefresh={refreshClaims}
      />

      {/* ── Main ──────────────────────────────────────────────────────── */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Header */}
        <div className="px-8 pt-6 pb-0 border-b border-border">
          <div className="flex items-baseline gap-3 mb-4">
            <h1 className="text-2xl font-bold text-hi tracking-tight">
              {selectedId
                ? <>Claim: <span className="font-mono text-teal bg-bg-card px-3 py-0.5 rounded text-xl">{selectedId}</span></>
                : 'Insurance Intelligence'}
            </h1>
          </div>
          {/* Tabs */}
          <div className="flex gap-1">
            {(['summary', 'chat'] as Tab[]).map(tab => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={[
                  'px-5 py-2.5 text-xs font-bold uppercase tracking-widest border-b-2 transition-colors',
                  activeTab === tab
                    ? 'border-teal text-teal'
                    : 'border-transparent text-muted hover:text-mid',
                ].join(' ')}
              >
                {tab === 'summary' ? '📊 Summary' : '💬 Chat'}
              </button>
            ))}
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-auto p-8">
          {!selectedId && (
            <p className="text-muted">Select a claim from the sidebar.</p>
          )}
          {selectedId && activeTab === 'summary' && (
            <SummaryTab
              claimId={selectedId}
              cached={summaryCache[selectedId]}
              onSummarized={result =>
                setSummaryCache(c => ({ ...c, [selectedId]: result }))
              }
            />
          )}
          {selectedId && activeTab === 'chat' && (
            <ChatTab claimId={selectedId} />
          )}
        </div>
      </div>
    </div>
  )
}
