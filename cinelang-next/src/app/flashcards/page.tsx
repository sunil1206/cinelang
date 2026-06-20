'use client'
import { useState, useEffect, useCallback, useRef } from 'react'
import { useSession } from 'next-auth/react'
import { useRouter } from 'next/navigation'
import {
  Layers, CheckCircle, XCircle, Clock, Zap, Trophy,
  RotateCcw, ChevronRight, Volume2, Eye, EyeOff,
} from 'lucide-react'
import clsx from 'clsx'

// ── Types ──────────────────────────────────────────────────────────────────────
interface VocabCard {
  id: number
  word: string
  lemma: string
  pos: string
  cefr: string
  translation: string
  ipa: string
  definition: string
  example: string
  context_sentence: string
  mastery_score: number
  interval_days: number
  status: string
}

interface SessionSummary {
  session_id: number
  words_reviewed: number
  correct: number
  accuracy: number
  xp_earned: number
  duration_s: number
}

const CEFR_COLOR: Record<string, string> = {
  A1: 'bg-emerald-500', A2: 'bg-green-500',
  B1: 'bg-yellow-500',  B2: 'bg-amber-500',
  C1: 'bg-orange-500',  C2: 'bg-red-500',
}

const RESPONSE_BUTTONS = [
  { key: 'again', label: 'Again',  sub: '< 1 min',  color: 'bg-red-600 hover:bg-red-500'    },
  { key: 'hard',  label: 'Hard',   sub: '< 10 min', color: 'bg-orange-600 hover:bg-orange-500' },
  { key: 'good',  label: 'Good',   sub: '1 day',    color: 'bg-blue-600 hover:bg-blue-500'   },
  { key: 'easy',  label: 'Easy',   sub: '4 days',   color: 'bg-emerald-600 hover:bg-emerald-500' },
]

function speak(text: string, lang: string) {
  if (typeof window === 'undefined' || !window.speechSynthesis) return
  window.speechSynthesis.cancel()
  const u = new SpeechSynthesisUtterance(text)
  u.lang = `${lang}-${lang.toUpperCase()}`
  u.rate = 0.85
  window.speechSynthesis.speak(u)
}

// ── Setup screen ───────────────────────────────────────────────────────────────
function SetupScreen({ onStart, loading, error }: {
  onStart: (lang: string, limit: number) => void
  loading: boolean
  error: string
}) {
  const [lang, setLang]   = useState('fr')
  const [limit, setLimit] = useState(20)

  return (
    <div className="min-h-screen bg-cinema-950 flex items-center justify-center p-4">
      <div className="w-full max-w-md bg-cinema-900 rounded-2xl p-8 border border-cinema-700 shadow-2xl">
        <div className="flex items-center gap-3 mb-8">
          <Layers className="text-cinema-400" size={28} />
          <h1 className="text-2xl font-heading text-white">Flashcards</h1>
        </div>

        <div className="space-y-5">
          <div>
            <label className="block text-sm text-warm-400 mb-2">Language</label>
            <select value={lang} onChange={e => setLang(e.target.value)}
              className="w-full bg-cinema-800 border border-cinema-600 rounded-lg px-4 py-2.5 text-white focus:outline-none focus:border-cinema-400">
              <option value="fr">🇫🇷 French</option>
              <option value="de">🇩🇪 German</option>
              <option value="es">🇪🇸 Spanish</option>
              <option value="it">🇮🇹 Italian</option>
              <option value="pt">🇵🇹 Portuguese</option>
              <option value="ja">🇯🇵 Japanese</option>
            </select>
          </div>

          <div>
            <label className="block text-sm text-warm-400 mb-2">Cards per session: {limit}</label>
            <input type="range" min={5} max={50} step={5} value={limit}
              onChange={e => setLimit(+e.target.value)}
              className="w-full accent-cinema-400" />
            <div className="flex justify-between text-xs text-warm-500 mt-1">
              <span>5</span><span>10</span><span>20</span><span>30</span><span>40</span><span>50</span>
            </div>
          </div>

          {error && <p className="text-red-400 text-sm bg-red-900/20 rounded-lg px-4 py-3">{error}</p>}

          <button onClick={() => onStart(lang, limit)} disabled={loading}
            className="w-full btn-primary py-3 rounded-xl font-semibold text-lg disabled:opacity-50">
            {loading ? 'Loading cards…' : 'Start Session'}
          </button>
        </div>

        <p className="text-warm-600 text-xs text-center mt-6">
          Due cards come first, then new words. Uses SM-2 spaced repetition.
        </p>
      </div>
    </div>
  )
}

// ── Flashcard ──────────────────────────────────────────────────────────────────
function Flashcard({ card, lang, revealed, onReveal, onResponse }: {
  card: VocabCard
  lang: string
  revealed: boolean
  onReveal: () => void
  onResponse: (r: string) => void
}) {
  const mastery = Math.round(card.mastery_score * 100)

  return (
    <div className="w-full max-w-lg">
      {/* Card front/back */}
      <div className="bg-cinema-900 rounded-2xl border border-cinema-700 shadow-2xl overflow-hidden">

        {/* Header strip */}
        <div className="flex items-center justify-between px-5 py-3 border-b border-cinema-800">
          <div className="flex items-center gap-2">
            <span className={clsx('text-[10px] font-bold px-2 py-0.5 rounded text-white', CEFR_COLOR[card.cefr] || 'bg-cinema-600')}>
              {card.cefr}
            </span>
            <span className="text-xs text-warm-500">{card.pos}</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="text-xs text-warm-500">{mastery}% mastered</div>
            <div className="w-16 h-1 bg-cinema-800 rounded-full">
              <div className="h-1 bg-cinema-400 rounded-full" style={{ width: `${mastery}%` }} />
            </div>
          </div>
        </div>

        {/* Front — always visible */}
        <div className="p-8 text-center">
          <div className="flex items-center justify-center gap-3 mb-2">
            <h2 className="text-4xl font-heading text-white">{card.word}</h2>
            <button onClick={() => speak(card.word, lang)}
              className="text-warm-500 hover:text-cinema-400 transition-colors">
              <Volume2 size={20} />
            </button>
          </div>
          {card.ipa && <p className="text-warm-500 text-sm font-mono mb-1">/{card.ipa}/</p>}
          {card.context_sentence && (
            <p className="text-warm-400 text-sm italic mt-4 leading-relaxed">
              "{card.context_sentence}"
            </p>
          )}
        </div>

        {/* Back — revealed on click */}
        {!revealed ? (
          <div className="px-8 pb-8">
            <button onClick={onReveal}
              className="w-full py-3 rounded-xl border border-cinema-600 text-warm-400 hover:border-cinema-400 hover:text-white transition-all flex items-center justify-center gap-2">
              <Eye size={16} /> Show Answer
            </button>
          </div>
        ) : (
          <div className="border-t border-cinema-800 px-8 py-6 space-y-4">
            {/* Translation */}
            <div className="text-center">
              <p className="text-2xl text-cinema-300 font-semibold">{card.translation}</p>
              {card.definition && (
                <p className="text-warm-400 text-sm mt-2 leading-relaxed">{card.definition}</p>
              )}
            </div>

            {/* Example */}
            {card.example && (
              <div className="bg-cinema-800/50 rounded-xl px-4 py-3">
                <p className="text-warm-300 text-sm italic leading-relaxed">"{card.example}"</p>
              </div>
            )}

            {/* SM-2 response buttons */}
            <div className="grid grid-cols-4 gap-2 pt-2">
              {RESPONSE_BUTTONS.map(b => (
                <button key={b.key} onClick={() => onResponse(b.key)}
                  className={clsx('rounded-xl py-3 px-1 text-white transition-all', b.color)}>
                  <div className="text-sm font-semibold">{b.label}</div>
                  <div className="text-[10px] opacity-75 mt-0.5">{b.sub}</div>
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      <p className="text-center text-warm-600 text-xs mt-4">
        {revealed ? 'How well did you know it?' : 'Press Space to reveal'}
      </p>
    </div>
  )
}

// ── Results screen ─────────────────────────────────────────────────────────────
function ResultsScreen({ summary, onReset }: { summary: SessionSummary; onReset: () => void }) {
  const pct = Math.round(summary.accuracy * 100)
  return (
    <div className="min-h-screen bg-cinema-950 flex items-center justify-center p-4">
      <div className="w-full max-w-md bg-cinema-900 rounded-2xl p-8 border border-cinema-700 shadow-2xl text-center">
        <Trophy className={clsx('mx-auto mb-4', pct >= 80 ? 'text-yellow-400' : 'text-warm-500')} size={48} />
        <h2 className="text-3xl font-heading text-white mb-1">{pct}% accuracy</h2>
        <p className="text-warm-400 mb-8">
          {summary.correct} / {summary.words_reviewed} correct · {summary.xp_earned} XP · {summary.duration_s}s
        </p>

        <div className="grid grid-cols-3 gap-4 mb-8">
          {[
            { label: 'Reviewed', value: summary.words_reviewed, icon: Layers },
            { label: 'Correct',  value: summary.correct,        icon: CheckCircle },
            { label: 'XP',       value: `+${summary.xp_earned}`, icon: Zap },
          ].map(s => (
            <div key={s.label} className="bg-cinema-800 rounded-xl p-4">
              <s.icon size={20} className="mx-auto mb-2 text-cinema-400" />
              <div className="text-xl font-bold text-white">{s.value}</div>
              <div className="text-xs text-warm-500 mt-1">{s.label}</div>
            </div>
          ))}
        </div>

        <button onClick={onReset}
          className="w-full btn-primary py-3 rounded-xl font-semibold flex items-center justify-center gap-2">
          <RotateCcw size={16} /> New Session
        </button>
      </div>
    </div>
  )
}

// ── Main page ──────────────────────────────────────────────────────────────────
export default function FlashcardsPage() {
  const { data: session } = useSession()
  const router = useRouter()

  const [phase, setPhase]         = useState<'setup' | 'session' | 'results'>('setup')
  const [loading, setLoading]     = useState(false)
  const [error, setError]         = useState('')
  const [lang, setLang]           = useState('fr')
  const [sessionId, setSessionId] = useState(0)
  const [cards, setCards]         = useState<VocabCard[]>([])
  const [idx, setIdx]             = useState(0)
  const [revealed, setRevealed]   = useState(false)
  const [summary, setSummary]     = useState<SessionSummary | null>(null)
  const startTime                 = useRef<number>(0)

  const token = (session as any)?.backendToken

  const headers = useCallback(() => ({
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  }), [token])

  // Keyboard shortcuts
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (phase !== 'session') return
      if (e.key === ' ' || e.key === 'Enter') { e.preventDefault(); if (!revealed) setRevealed(true) }
      if (revealed) {
        if (e.key === '1') submitResponse('again')
        if (e.key === '2') submitResponse('hard')
        if (e.key === '3') submitResponse('good')
        if (e.key === '4') submitResponse('easy')
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  })

  const startSession = useCallback(async (langCode: string, limit: number) => {
    if (!session) { router.push('/'); return }
    setLoading(true); setError(''); setLang(langCode)
    try {
      const res = await fetch('/api/reviews/session/start', {
        method: 'POST',
        headers: headers(),
        body: JSON.stringify({ lang_code: langCode, limit, session_type: 'review' }),
      })
      if (!res.ok) {
        const d = await res.json()
        throw new Error(d?.detail || 'No words due for review — add vocabulary first')
      }
      const data = await res.json()
      setSessionId(data.session_id)
      setCards(data.words)
      setIdx(0); setRevealed(false)
      startTime.current = Date.now()
      setPhase('session')
    } catch (e: any) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [session, headers, router])

  const submitResponse = useCallback(async (response: string) => {
    const card = cards[idx]
    if (!card) return

    await fetch(`/api/reviews/session/${sessionId}/answer`, {
      method: 'POST',
      headers: headers(),
      body: JSON.stringify({ user_vocab_id: card.id, response, time_ms: Date.now() - startTime.current }),
    })

    const next = idx + 1
    if (next >= cards.length) {
      // Complete session
      const res = await fetch(`/api/reviews/session/${sessionId}/complete`, {
        method: 'POST', headers: headers(),
      })
      const data = await res.json()
      setSummary(data)
      setPhase('results')
    } else {
      setIdx(next)
      setRevealed(false)
      startTime.current = Date.now()
    }
  }, [cards, idx, sessionId, headers])

  if (phase === 'results' && summary) {
    return <ResultsScreen summary={summary} onReset={() => setPhase('setup')} />
  }

  if (phase === 'setup') {
    return <SetupScreen onStart={startSession} loading={loading} error={error} />
  }

  const card = cards[idx]
  if (!card) return null
  const progress = (idx / cards.length) * 100

  return (
    <div className="min-h-screen bg-cinema-950 flex flex-col items-center justify-center p-4">
      {/* Progress */}
      <div className="w-full max-w-lg mb-6">
        <div className="flex justify-between text-sm text-warm-400 mb-2">
          <span>{idx + 1} / {cards.length}</span>
          <div className="flex items-center gap-3 text-xs">
            <span className="flex items-center gap-1"><Clock size={12} /> {Math.round((Date.now() - (startTime.current || Date.now())) / 1000)}s</span>
          </div>
        </div>
        <div className="h-1 bg-cinema-800 rounded-full">
          <div className="h-1 bg-cinema-400 rounded-full transition-all duration-500" style={{ width: `${progress}%` }} />
        </div>
      </div>

      <Flashcard
        card={card}
        lang={lang}
        revealed={revealed}
        onReveal={() => setRevealed(true)}
        onResponse={submitResponse}
      />

      <p className="text-warm-700 text-xs mt-6">1=Again · 2=Hard · 3=Good · 4=Easy · Space=Reveal</p>
    </div>
  )
}
