import { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { api } from '../api/client'

interface Props {
  claimId: string
  cached?: any
  onSummarized: (result: any) => void
}

const AGENTS = [
  { key: 'facts',    icon: '🔍', label: 'Facts Agent',    model: 'Haiku' },
  { key: 'coverage', icon: '📋', label: 'Coverage Agent', model: 'Haiku' },
  { key: 'risk',     icon: '⚠️', label: 'Risk Agent',     model: 'Haiku' },
  { key: 'timeline', icon: '📅', label: 'Timeline Agent', model: 'Haiku' },
  { key: 'synthesis',icon: '✍️', label: 'Synthesis Agent',model: 'Sonnet' },
]

export default function SummaryTab({ claimId, cached, onSummarized }: Props) {
  const [running, setRunning]   = useState(false)
  const [fired, setFired]       = useState<Set<string>>(new Set())
  const [result, setResult]     = useState<any>(cached ?? null)
  const [error, setError]       = useState<string | null>(null)
  const [openPanel, setOpenPanel] = useState<string | null>(null)

  const run = async () => {
    setRunning(true); setFired(new Set()); setError(null)
    try {
      const res = await api.streamSummarize(claimId)
      const reader = res.body!.getReader()
      const dec = new TextDecoder()
      let buf = ''
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buf += dec.decode(value, { stream: true })
        const lines = buf.split('\n')
        buf = lines.pop() ?? ''
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          const raw = line.slice(6)
          if (raw === '[DONE]') { setRunning(false); return }
          const evt = JSON.parse(raw)
          if (evt.type === 'status') setFired(f => new Set([...f, evt.agent]))
          if (evt.type === 'result') { setResult(evt.data); onSummarized(evt.data) }
          if (evt.type === 'error')  { setError(evt.message); setRunning(false) }
        }
      }
    } catch (e: any) { setError(String(e)) }
    setRunning(false)
  }

  const riskColor: Record<string, string> = {
    High: 'text-red-400', Medium: 'text-orange', Low: 'text-teal'
  }

  return (
    <div className="space-y-5 max-w-4xl">
      {/* Header row */}
      <div className="flex items-center justify-between">
        <h2 className="text-hi font-bold text-lg">Claim Intelligence Report</h2>
        <button
          onClick={run}
          disabled={running}
          className="flex items-center gap-2 px-5 py-2 bg-teal text-bg-deep font-bold text-sm rounded-lg hover:bg-teal-light disabled:opacity-50 transition-colors"
        >
          {running ? '⏳ Running...' : '▶ Summarize Claim'}
        </button>
      </div>

      {/* Agent pipeline */}
      {(running || result) && (
        <div className="bg-bg-card border border-border rounded-lg p-4 space-y-2">
          {AGENTS.map(a => {
            const done = fired.has(a.key) || !!result
            return (
              <div key={a.key} className="flex items-center gap-3 text-sm">
                <span className={done ? 'opacity-100' : 'opacity-30'}>{a.icon}</span>
                <span className={done ? 'text-mid' : 'text-muted'}>
                  <span className="font-semibold text-hi">{a.label}</span>
                  <span className="text-xs ml-1 text-muted">({a.model})</span>
                </span>
                {done && <span className="ml-auto text-teal text-xs">✓</span>}
              </div>
            )
          })}
          {result && <div className="text-teal text-xs font-bold mt-2">✅ Analysis complete!</div>}
        </div>
      )}

      {error && <div className="bg-red-900/20 border border-red-500/30 text-red-400 rounded-lg p-3 text-sm">{error}</div>}

      {!result && !running && (
        <div className="bg-bg-card border border-border rounded-lg p-5 text-muted text-sm">
          Click <strong className="text-teal">▶ Summarize Claim</strong> to run the multi-agent analysis.
        </div>
      )}

      {result && (
        <>
          {/* Synthesis markdown — fully styled */}
          <div className="bg-bg-card border border-border rounded-xl p-7">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                h1: ({children}) => (
                  <h1 className="text-hi text-2xl font-extrabold tracking-tight mb-4 pb-2 border-b border-border">{children}</h1>
                ),
                h2: ({children}) => (
                  <h2 className="text-teal text-base font-bold uppercase tracking-widest mt-6 mb-3 flex items-center gap-2">
                    <span className="w-1 h-4 bg-teal rounded-full inline-block" />
                    {children}
                  </h2>
                ),
                h3: ({children}) => (
                  <h3 className="text-hi text-sm font-bold mt-4 mb-2">{children}</h3>
                ),
                p: ({children}) => (
                  <p className="text-mid text-sm leading-relaxed mb-3">{children}</p>
                ),
                strong: ({children}) => (
                  <strong className="text-hi font-semibold">{children}</strong>
                ),
                em: ({children}) => (
                  <em className="text-mid italic">{children}</em>
                ),
                ul: ({children}) => (
                  <ul className="space-y-1.5 mb-4 ml-2">{children}</ul>
                ),
                ol: ({children}) => (
                  <ol className="list-decimal list-inside space-y-1.5 mb-4 ml-2 text-mid text-sm">{children}</ol>
                ),
                li: ({children}) => (
                  <li className="flex items-start gap-2 text-sm text-mid">
                    <span className="text-teal mt-1 flex-shrink-0">▸</span>
                    <span>{children}</span>
                  </li>
                ),
                blockquote: ({children}) => (
                  <blockquote className="border-l-2 border-teal/40 pl-4 py-1 my-3 text-muted text-sm italic">{children}</blockquote>
                ),
                code: ({inline, children}: any) => inline
                  ? <code className="bg-bg-deep text-teal font-mono text-xs px-1.5 py-0.5 rounded">{children}</code>
                  : <pre className="bg-bg-deep border border-border rounded-lg p-4 overflow-x-auto my-3"><code className="text-teal font-mono text-xs leading-relaxed">{children}</code></pre>,
                table: ({children}) => (
                  <div className="overflow-x-auto my-4 rounded-lg border border-border">
                    <table className="w-full text-sm">{children}</table>
                  </div>
                ),
                thead: ({children}) => (
                  <thead className="bg-bg-hover">{children}</thead>
                ),
                th: ({children}) => (
                  <th className="text-left px-4 py-2.5 text-xs font-bold uppercase tracking-wider text-teal border-b border-border">{children}</th>
                ),
                tr: ({children}) => (
                  <tr className="border-b border-border/50 hover:bg-bg-hover/50 transition-colors">{children}</tr>
                ),
                td: ({children}) => (
                  <td className="px-4 py-2.5 text-mid text-xs">{children}</td>
                ),
                hr: () => <hr className="border-border my-5" />,
              }}
            >
              {result.summary}
            </ReactMarkdown>
          </div>

          {/* Sources row */}
          <div className="flex flex-wrap gap-2 text-xs">
            <span className="text-muted font-semibold uppercase tracking-wider">Sources analysed:</span>
            {Object.keys(result.facts || {}).length > 0 &&
              (result.facts.document_types || []).map((dt: string) => (
                <span key={dt} className="bg-teal/10 border border-teal/25 text-teal px-2 py-0.5 rounded">
                  📄 {claimId} — {dt}
                </span>
              ))}
          </div>

          {/* Agent output panels */}
          <div className="grid grid-cols-2 gap-3">
            {[
              { key: 'facts',    label: '🔍 Facts Agent',    data: result.facts },
              { key: 'coverage', label: '📋 Coverage Agent', data: result.coverage },
              { key: 'risk',     label: '⚠️ Risk Agent',     data: result.risk },
              { key: 'timeline', label: '📅 Timeline Agent', data: result.timeline },
            ].map(({ key, label, data }) => (
              <div key={key} className="bg-bg-card border border-border rounded-lg overflow-hidden">
                <button
                  onClick={() => setOpenPanel(openPanel === key ? null : key)}
                  className="w-full flex items-center justify-between px-4 py-3 text-xs font-bold uppercase tracking-wider text-mid hover:text-hi"
                >
                  <span>{label}</span>
                  <span className="text-muted">{openPanel === key ? '▲' : '▼'}</span>
                </button>
                {openPanel === key && (
                  <div className="px-4 pb-4 border-t border-border">
                    {key === 'risk' && (
                      <div className={`font-bold text-sm mt-3 mb-2 ${riskColor[data?.overall_risk] ?? 'text-mid'}`}>
                        Risk: {data?.overall_risk ?? 'Unknown'}
                      </div>
                    )}
                    {key === 'timeline'
                      ? (data?.events ?? []).map((e: any, i: number) => (
                          <div key={i} className="flex gap-2 text-xs text-mid mt-2">
                            <span className="text-teal font-mono">{e.date ?? '?'}</span>
                            <span>{e.event}</span>
                          </div>
                        ))
                      : Object.entries(data ?? {}).map(([k, v]) =>
                          v && k !== 'document_types' && (
                            <div key={k} className="flex gap-2 text-xs mt-2">
                              <span className="text-muted capitalize">{k.replace(/_/g, ' ')}:</span>
                              <span className="text-mid">{Array.isArray(v) ? (v as string[]).join(', ') : String(v)}</span>
                            </div>
                          )
                        )
                    }
                  </div>
                )}
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  )
}
