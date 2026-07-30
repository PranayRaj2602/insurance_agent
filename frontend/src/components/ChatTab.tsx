import { useState, useRef, useEffect } from 'react'
import { Send } from 'lucide-react'
import { api } from '../api/client'

interface Message { role: 'user' | 'assistant'; content: string }

export default function ChatTab({ claimId }: { claimId: string }) {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput]       = useState('')
  const [streaming, setStreaming] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages])

  const send = async () => {
    const text = input.trim()
    if (!text || streaming) return
    setInput('')
    const userMsg: Message = { role: 'user', content: text }
    setMessages(m => [...m, userMsg])
    setStreaming(true)

    const history = messages.map(m => ({
      role: m.role, content: m.content,
    }))

    let assistantText = ''
    setMessages(m => [...m, { role: 'assistant', content: '' }])

    try {
      const res = await api.streamChat(text, history, claimId)
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
          if (raw === '[DONE]') break
          const evt = JSON.parse(raw)
          assistantText += evt.text ?? ''
          setMessages(m => [
            ...m.slice(0, -1),
            { role: 'assistant', content: assistantText },
          ])
        }
      }
    } catch (e) {
      setMessages(m => [...m.slice(0, -1), { role: 'assistant', content: `Error: ${e}` }])
    }
    setStreaming(false)
  }

  return (
    <div className="flex flex-col h-full max-w-3xl">
      <h2 className="text-hi font-bold text-lg mb-1">Chat with your claim documents</h2>
      <p className="text-muted text-xs mb-4">
        Context: <span className="text-teal font-mono">{claimId}</span> — ask about this claim or any claim in the corpus.
      </p>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto space-y-4 mb-4 pr-1">
        {messages.length === 0 && (
          <div className="text-muted text-sm">Ask anything about this claim…</div>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`flex gap-3 ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            {m.role === 'assistant' && (
              <div className="w-7 h-7 rounded-full bg-teal/20 border border-teal/30 flex items-center justify-center text-teal text-xs flex-shrink-0 mt-0.5">
                🤖
              </div>
            )}
            <div className={[
              'max-w-[85%] rounded-xl px-4 py-3 text-sm leading-relaxed',
              m.role === 'user'
                ? 'bg-teal/10 border border-teal/20 text-hi ml-auto'
                : 'bg-bg-card border border-border text-mid',
            ].join(' ')}>
              <pre className="whitespace-pre-wrap font-sans">
                {m.content}
                {streaming && i === messages.length - 1 && m.role === 'assistant' && (
                  <span className="animate-pulse text-teal">▌</span>
                )}
              </pre>
            </div>
            {m.role === 'user' && (
              <div className="w-7 h-7 rounded-full bg-bg-hover border border-border flex items-center justify-center text-xs flex-shrink-0 mt-0.5">
                👤
              </div>
            )}
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="flex gap-2">
        <input
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && !e.shiftKey && send()}
          placeholder="Ask about claims, coverage, or any document..."
          disabled={streaming}
          className="flex-1 bg-bg-card border border-border rounded-lg px-4 py-3 text-sm text-hi placeholder-muted focus:outline-none focus:border-teal transition-colors disabled:opacity-50"
        />
        <button
          onClick={send}
          disabled={streaming || !input.trim()}
          className="w-11 h-11 flex items-center justify-center bg-teal text-bg-deep rounded-lg hover:bg-teal-light disabled:opacity-40 transition-colors"
        >
          <Send size={16} />
        </button>
      </div>

      {messages.length > 0 && !streaming && (
        <button
          onClick={() => setMessages([])}
          className="text-muted text-xs mt-2 hover:text-mid text-center transition-colors"
        >
          🗑 Clear chat
        </button>
      )}
    </div>
  )
}
