'use client'
import { useState, useEffect, useCallback, useRef } from 'react'
import {
  Film, Loader2, ChevronDown, ChevronUp, Volume2, Pencil, Check, X,
  Trash2, Search, ArrowLeft, Clapperboard, Plus, GraduationCap, Brain,
} from 'lucide-react'
import { useCineLang } from '@/lib/store'
import { useSession } from 'next-auth/react'
import clsx from 'clsx'
import Link from 'next/link'

// ── Types ─────────────────────────────────────────────────────────────────────

interface MovieOut {
  id: number; title: string; year: number | null
  language: string; target_lang: string
  subtitle_count: number; vocab_count: number
  cefr_breakdown: Record<string, number>; created_at: string
}

interface WordEntry {
  id: number; word: string; lemma: string; pos: string; cefr: string
  count: number; example: string; translation: string; ipa: string; explanation: string
}

interface QuizQuestion {
  type: string; prompt: string; answer: string
  options: string[]; hint: string; word: string; cefr: string
}

// ── Constants ─────────────────────────────────────────────────────────────────

const CEFR_COLORS: Record<string, string> = {
  A1: 'bg-emerald-100 text-emerald-700 border-emerald-200',
  A2: 'bg-teal-100 text-teal-700 border-teal-200',
  B1: 'bg-blue-100 text-blue-700 border-blue-200',
  B2: 'bg-violet-100 text-violet-700 border-violet-200',
  C1: 'bg-red-100 text-red-700 border-red-200',
}
const CEFR_BAR: Record<string, string> = {
  A1: 'bg-emerald-400', A2: 'bg-teal-400',
  B1: 'bg-blue-400', B2: 'bg-violet-400', C1: 'bg-red-400',
}

function speak(word: string, lang: string) {
  if (typeof window === 'undefined' || !window.speechSynthesis) return
  window.speechSynthesis.cancel()
  const u = new SpeechSynthesisUtterance(word)
  u.lang = `${lang}-${lang.toUpperCase()}`; u.rate = 0.85
  window.speechSynthesis.speak(u)
}

// ── CEFR bar ──────────────────────────────────────────────────────────────────

function CefrBar({ breakdown }: { breakdown: Record<string, number> }) {
  const total = Object.values(breakdown).reduce((a, b) => a + b, 0) || 1
  return (
    <div className="space-y-1.5">
      {['A1','A2','B1','B2','C1'].map(lvl => {
        const n = breakdown[lvl] || 0
        const pct = Math.round((n / total) * 100)
        return (
          <div key={lvl} className="flex items-center gap-2 text-xs">
            <span className={clsx('badge text-[10px] w-6 text-center', CEFR_COLORS[lvl])}>{lvl}</span>
            <div className="flex-1 h-2 bg-warm-100 rounded-full overflow-hidden">
              <div className={clsx('h-full rounded-full', CEFR_BAR[lvl])} style={{ width: `${pct}%` }} />
            </div>
            <span className="text-warm-500 w-16">{n} words ({pct}%)</span>
          </div>
        )
      })}
    </div>
  )
}

// ── Movie card ────────────────────────────────────────────────────────────────

function MovieCard({
  movie, active, onClick, onDelete,
}: { movie: MovieOut; active: boolean; onClick: () => void; onDelete: () => void }) {
  const total = Object.values(movie.cefr_breakdown).reduce((a, b) => a + b, 0) || 1
  return (
    <div
      onClick={onClick}
      className={clsx(
        'p-3 rounded-xl border cursor-pointer transition-all group relative',
        active
          ? 'bg-cinema-50 border-cinema-300 shadow-sm'
          : 'bg-white border-warm-200 hover:border-cinema-200 hover:bg-cream-50',
      )}
    >
      <div className="flex items-start gap-2">
        <div className={clsx('w-8 h-8 rounded-lg flex items-center justify-center shrink-0', active ? 'bg-cinema-500' : 'bg-warm-100')}>
          <Film className={clsx('w-4 h-4', active ? 'text-white' : 'text-warm-500')} />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-warm-900 truncate">{movie.title}</p>
          {movie.year && <p className="text-xs text-warm-400">{movie.year}</p>}
          <div className="flex gap-2 mt-1 text-[10px] text-warm-500">
            <span>{movie.vocab_count} words</span>
            <span>·</span>
            <span className="uppercase font-mono">{movie.language}</span>
          </div>
          <div className="flex gap-0.5 mt-1.5">
            {['A1','A2','B1','B2','C1'].map(lvl => {
              const pct = Math.round(((movie.cefr_breakdown[lvl] || 0) / total) * 100)
              return pct > 0 ? (
                <div key={lvl} title={`${lvl}: ${pct}%`}
                  className={clsx('h-1 rounded-full', CEFR_BAR[lvl])}
                  style={{ width: `${Math.max(pct, 4)}%` }} />
              ) : null
            })}
          </div>
        </div>
      </div>
      <button
        onClick={e => { e.stopPropagation(); onDelete() }}
        className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-red-50 text-warm-300 hover:text-red-500 transition-all"
      >
        <Trash2 className="w-3 h-3" />
      </button>
    </div>
  )
}

// ── Word row with inline edit ─────────────────────────────────────────────────

function WordRow({
  w, lang, idx, token, API, onUpdated,
}: { w: WordEntry; lang: string; idx: number; token: string; API: string; onUpdated: (id: number, translation: string) => void }) {
  const [open,    setOpen]    = useState(false)
  const [editing, setEditing] = useState(false)
  const [draft,   setDraft]   = useState(w.translation)
  const [saving,  setSaving]  = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  async function saveMeaning() {
    if (!draft.trim()) return
    setSaving(true)
    try {
      const res = await fetch(`${API}/api/vocabulary/${w.id}/meaning`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ translation: draft.trim() }),
      })
      if (res.ok) {
        onUpdated(w.id, draft.trim())
        setEditing(false)
      }
    } finally { setSaving(false) }
  }

  return (
    <>
      <tr className={clsx('hover:bg-cream-50 transition-colors', open && 'bg-cream-50')}>
        <td className="px-3 py-2 text-xs text-warm-400 tabular-nums">{idx + 1}</td>
        <td className="px-3 py-2">
          <div className="flex items-center gap-2">
            <button onClick={() => speak(w.word, lang)} className="p-1 rounded hover:bg-cinema-50 text-warm-400 hover:text-cinema-500">
              <Volume2 className="w-3 h-3" />
            </button>
            <div>
              <span className="text-sm font-semibold text-warm-900">{w.word}</span>
              {w.ipa && <span className="ml-1.5 text-[11px] text-warm-400 font-mono">{w.ipa}</span>}
            </div>
          </div>
        </td>
        <td className="px-3 py-2 min-w-[140px]">
          {editing ? (
            <div className="flex items-center gap-1">
              <input
                ref={inputRef}
                value={draft}
                onChange={e => setDraft(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter') saveMeaning(); if (e.key === 'Escape') setEditing(false) }}
                className="input py-0.5 text-sm flex-1 min-w-0"
                autoFocus
              />
              <button onClick={saveMeaning} disabled={saving} className="p-1 text-emerald-600 hover:bg-emerald-50 rounded">
                {saving ? <Loader2 className="w-3 h-3 animate-spin" /> : <Check className="w-3 h-3" />}
              </button>
              <button onClick={() => { setEditing(false); setDraft(w.translation) }} className="p-1 text-warm-400 hover:bg-warm-100 rounded">
                <X className="w-3 h-3" />
              </button>
            </div>
          ) : (
            <div className="flex items-center gap-1.5 group/cell">
              <span className="text-sm text-warm-600">{w.translation || <span className="italic text-warm-300">no translation</span>}</span>
              <button
                onClick={() => { setEditing(true); setDraft(w.translation) }}
                className="opacity-0 group-hover/cell:opacity-100 p-0.5 rounded hover:bg-cinema-50 text-warm-300 hover:text-cinema-500 transition-all"
              >
                <Pencil className="w-2.5 h-2.5" />
              </button>
            </div>
          )}
        </td>
        <td className="px-3 py-2">
          <span className={clsx('badge text-[10px]', CEFR_COLORS[w.cefr] || 'bg-gray-100 text-gray-600')}>{w.cefr}</span>
        </td>
        <td className="px-3 py-2 text-xs text-warm-400">{w.pos}</td>
        <td className="px-3 py-2 text-xs text-warm-400 tabular-nums">{w.count}×</td>
        <td className="px-3 py-2">
          <button onClick={() => setOpen(o => !o)} className="text-warm-300 hover:text-warm-600">
            {open ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
          </button>
        </td>
      </tr>
      {open && (
        <tr className="bg-amber-50/40">
          <td />
          <td colSpan={6} className="px-4 pb-3 pt-1 space-y-1">
            {w.example && (
              <p className="text-xs italic text-warm-600">
                <span className="font-medium not-italic text-warm-800">Example: </span>{w.example}
              </p>
            )}
            {w.explanation && (
              <p className="text-xs text-amber-700 bg-amber-50 rounded px-2 py-1">💡 {w.explanation}</p>
            )}
            {!w.example && !w.explanation && (
              <p className="text-xs text-warm-300 italic">No example available. Edit translation above to enrich this word.</p>
            )}
          </td>
        </tr>
      )}
    </>
  )
}

// ── Add Word Modal ────────────────────────────────────────────────────────────

function AddWordModal({
  movie, token, API, onClose, onAdded,
}: { movie: MovieOut; token: string; API: string; onClose: () => void; onAdded: () => void }) {
  const [word,        setWord]        = useState('')
  const [translation, setTranslation] = useState('')
  const [phonetic,    setPhonetic]    = useState('')
  const [example,     setExample]     = useState('')
  const [saving,      setSaving]      = useState(false)
  const [enriching,   setEnriching]   = useState(false)
  const [msg,         setMsg]         = useState('')

  async function autoEnrich() {
    if (!word.trim()) return
    setEnriching(true); setMsg('')
    try {
      const res = await fetch(`${API}/api/vocabulary/enrich`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ word: word.trim(), sentence: '', source_lang: 'en', target_lang: movie.language }),
      })
      if (res.ok) {
        const d = await res.json()
        if (d.translation) setTranslation(d.translation)
        if (d.phonetic)    setPhonetic(d.phonetic)
        setMsg('Auto-filled from dictionary')
      } else {
        setMsg('Could not auto-fill — fill manually')
      }
    } finally { setEnriching(false) }
  }

  async function save() {
    if (!word.trim()) return
    setSaving(true)
    try {
      const res = await fetch(`${API}/api/vocabulary/manual-add`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          word: word.trim(),
          source_lang: movie.language,
          target_lang: movie.target_lang || 'en',
          translation, phonetic, example_sentence: example,
          movie_id: movie.id,
        }),
      })
      if (res.ok) { onAdded(); onClose() }
    } finally { setSaving(false) }
  }

  return (
    <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md p-6">
        <div className="flex items-center justify-between mb-5">
          <h3 className="font-heading font-bold text-warm-900 flex items-center gap-2">
            <Plus className="w-4 h-4 text-cinema-500" /> Add Word
          </h3>
          <button onClick={onClose} className="text-warm-400 hover:text-warm-700">✕</button>
        </div>
        <div className="space-y-3">
          <div>
            <label className="text-xs font-medium text-warm-600 block mb-1">Word ({movie.language.toUpperCase()})</label>
            <div className="flex gap-2">
              <input value={word} onChange={e => setWord(e.target.value)}
                placeholder={`e.g. magnifique`}
                className="input flex-1 text-sm" />
              <button onClick={autoEnrich} disabled={enriching || !word.trim()}
                className="btn-ghost text-xs px-3 py-1.5 whitespace-nowrap flex items-center gap-1">
                {enriching ? <Loader2 className="w-3 h-3 animate-spin" /> : '✨'} Auto-fill
              </button>
            </div>
            {msg && <p className="text-xs text-warm-400 mt-1">{msg}</p>}
          </div>
          <div>
            <label className="text-xs font-medium text-warm-600 block mb-1">Translation (English)</label>
            <input value={translation} onChange={e => setTranslation(e.target.value)}
              placeholder="e.g. magnificent"
              className="input w-full text-sm" />
          </div>
          <div>
            <label className="text-xs font-medium text-warm-600 block mb-1">IPA phonetics (optional)</label>
            <input value={phonetic} onChange={e => setPhonetic(e.target.value)}
              placeholder="e.g. /maɲifik/"
              className="input w-full text-sm font-mono" />
          </div>
          <div>
            <label className="text-xs font-medium text-warm-600 block mb-1">Example sentence (optional)</label>
            <textarea value={example} onChange={e => setExample(e.target.value)}
              placeholder="e.g. C'est une journée magnifique."
              className="input w-full text-sm resize-none" rows={2} />
          </div>
        </div>
        <div className="flex gap-2 mt-5">
          <button onClick={onClose} className="flex-1 btn-ghost text-sm py-2">Cancel</button>
          <button onClick={save} disabled={saving || !word.trim()}
            className="flex-1 btn-primary text-sm py-2 flex items-center justify-center gap-1">
            {saving ? <Loader2 className="w-3 h-3 animate-spin" /> : <Check className="w-3 h-3" />}
            Save Word
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Quiz Modal ────────────────────────────────────────────────────────────────

function QuizModal({
  movie, token, API, onClose,
}: { movie: MovieOut; token: string; API: string; onClose: () => void }) {
  const [questions, setQuestions]   = useState<QuizQuestion[]>([])
  const [idx,       setIdx]         = useState(0)
  const [answer,    setAnswer]      = useState('')
  const [selected,  setSelected]    = useState('')
  const [revealed,  setRevealed]    = useState(false)
  const [score,     setScore]       = useState(0)
  const [loading,   setLoading]     = useState(true)
  const [error,     setError]       = useState('')
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    async function load() {
      try {
        const res = await fetch(`${API}/api/quiz/movie/${movie.id}?size=10`, {
          headers: { Authorization: `Bearer ${token}` },
        })
        if (!res.ok) {
          const d = await res.json()
          setError(d.detail || 'Not enough vocabulary for a quiz yet.')
        } else {
          const d = await res.json()
          setQuestions(d.questions || [])
        }
      } catch { setError('Failed to load quiz.') }
      finally { setLoading(false) }
    }
    load()
  }, [API, token, movie.id])

  function submitAnswer(ans: string) {
    setRevealed(true)
    const q = questions[idx]
    const correct = ans.trim().toLowerCase() === q.answer.trim().toLowerCase()
    if (correct) setScore(s => s + 1)
    setSelected(ans)
  }

  function next() {
    setIdx(i => i + 1)
    setAnswer(''); setSelected(''); setRevealed(false)
    setTimeout(() => inputRef.current?.focus(), 50)
  }

  const q = questions[idx]
  const done = idx >= questions.length && questions.length > 0

  return (
    <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-heading font-bold text-warm-900 flex items-center gap-2">
            <Brain className="w-4 h-4 text-cinema-500" /> Quiz — {movie.title}
          </h3>
          <button onClick={onClose} className="text-warm-400 hover:text-warm-700">✕</button>
        </div>

        {loading && (
          <div className="flex items-center justify-center py-16">
            <Loader2 className="w-6 h-6 animate-spin text-warm-300" />
            <span className="ml-2 text-warm-400 text-sm">Generating quiz…</span>
          </div>
        )}

        {error && (
          <div className="py-8 text-center">
            <p className="text-warm-600 text-sm mb-4">{error}</p>
            <p className="text-warm-400 text-xs">Load and translate subtitles for this film first, then study some words before taking the quiz.</p>
            <button onClick={onClose} className="btn-primary mt-4">Got it</button>
          </div>
        )}

        {done && !loading && !error && (
          <div className="text-center py-8">
            <div className="text-5xl mb-3">{score >= questions.length * 0.8 ? '🏆' : score >= questions.length * 0.5 ? '👍' : '📚'}</div>
            <p className="font-bold text-warm-900 text-xl mb-1">Quiz complete!</p>
            <p className="text-warm-500 text-sm">{score} / {questions.length} correct</p>
            <div className="mt-4 h-3 bg-warm-100 rounded-full overflow-hidden">
              <div className="h-full bg-cinema-400 rounded-full transition-all"
                style={{ width: `${(score / questions.length) * 100}%` }} />
            </div>
            <div className="flex gap-2 mt-6">
              <button onClick={() => { setIdx(0); setScore(0); setAnswer(''); setSelected(''); setRevealed(false) }}
                className="flex-1 btn-ghost text-sm py-2">Try again</button>
              <button onClick={onClose} className="flex-1 btn-primary text-sm py-2">Done</button>
            </div>
          </div>
        )}

        {q && !done && !loading && !error && (
          <>
            {/* Progress */}
            <div className="flex items-center gap-2 mb-4">
              <div className="flex-1 h-2 bg-warm-100 rounded-full overflow-hidden">
                <div className="h-full bg-cinema-400 rounded-full transition-all"
                  style={{ width: `${(idx / questions.length) * 100}%` }} />
              </div>
              <span className="text-xs text-warm-400 tabular-nums">{idx + 1}/{questions.length}</span>
              <span className="text-xs text-emerald-600 font-medium">{score} ✓</span>
            </div>

            {/* CEFR + type badge */}
            <div className="flex gap-2 mb-3">
              <span className={clsx('badge text-[10px]', CEFR_COLORS[q.cefr] || 'bg-gray-100 text-gray-600')}>{q.cefr}</span>
              <span className="badge text-[10px] bg-warm-100 text-warm-600 capitalize">{q.type.replace('_', ' ')}</span>
            </div>

            {/* Question */}
            <div className="bg-cream-50 border border-warm-200 rounded-xl p-5 mb-4 whitespace-pre-line text-sm text-warm-800 font-medium">
              {q.prompt}
            </div>

            {/* Multiple choice */}
            {q.type === 'multiple_choice' && q.options.length > 0 && (
              <div className="grid grid-cols-2 gap-2">
                {q.options.map(opt => {
                  const isCorrect  = opt.toLowerCase() === q.answer.toLowerCase()
                  const isSelected = opt === selected
                  return (
                    <button
                      key={opt}
                      disabled={revealed}
                      onClick={() => submitAnswer(opt)}
                      className={clsx(
                        'rounded-lg border p-3 text-sm text-left transition-all',
                        !revealed && 'hover:border-cinema-300 hover:bg-cinema-50 border-warm-200 bg-white',
                        revealed && isCorrect  && 'border-emerald-400 bg-emerald-50 text-emerald-800',
                        revealed && isSelected && !isCorrect && 'border-red-300 bg-red-50 text-red-700',
                        revealed && !isSelected && !isCorrect && 'border-warm-100 bg-warm-50 text-warm-400',
                      )}
                    >
                      {opt}
                    </button>
                  )
                })}
              </div>
            )}

            {/* Translation / fill blank */}
            {(q.type === 'translation' || q.type === 'fill_blank') && (
              <div className="space-y-2">
                {q.hint && <p className="text-xs text-warm-400">Hint: {q.hint}</p>}
                <input
                  ref={inputRef}
                  value={answer}
                  onChange={e => setAnswer(e.target.value)}
                  onKeyDown={e => { if (e.key === 'Enter' && !revealed) submitAnswer(answer) }}
                  disabled={revealed}
                  placeholder="Type your answer…"
                  className={clsx(
                    'input w-full text-sm',
                    revealed && answer.trim().toLowerCase() === q.answer.trim().toLowerCase() && 'border-emerald-400 bg-emerald-50',
                    revealed && answer.trim().toLowerCase() !== q.answer.trim().toLowerCase() && 'border-red-300 bg-red-50',
                  )}
                  autoFocus
                />
                {revealed && (
                  <div className={clsx(
                    'rounded-lg px-3 py-2 text-sm',
                    answer.trim().toLowerCase() === q.answer.trim().toLowerCase()
                      ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                      : 'bg-red-50 text-red-700 border border-red-200',
                  )}>
                    {answer.trim().toLowerCase() === q.answer.trim().toLowerCase()
                      ? '✓ Correct!'
                      : <>✗ Answer: <strong>{q.answer}</strong></>}
                  </div>
                )}
                {!revealed && (
                  <button onClick={() => submitAnswer(answer)} disabled={!answer.trim()}
                    className="btn-primary w-full text-sm py-2">Check answer</button>
                )}
              </div>
            )}

            {/* Next button (after reveal) */}
            {revealed && (
              <button onClick={next} className="btn-primary w-full text-sm py-2 mt-3">
                {idx + 1 < questions.length ? 'Next question →' : 'See results'}
              </button>
            )}
          </>
        )}
      </div>
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function CinemaPage() {
  const { data: session } = useSession()
  const { backendToken } = useCineLang()
  const token = (session as any)?.backendToken ?? backendToken
  const API = process.env.NEXT_PUBLIC_API_URL || ''

  const [movies,       setMovies]      = useState<MovieOut[]>([])
  const [activeMovie,  setActiveMovie] = useState<MovieOut | null>(null)
  const [vocab,        setVocab]       = useState<WordEntry[]>([])
  const [loading,      setLoading]     = useState(false)
  const [vocabLoading, setVocabLoading]= useState(false)
  const [search,       setSearch]      = useState('')
  const [cefrFilter,   setCefrFilter]  = useState('All')
  const [posFilter,    setPosFilter]   = useState('All')

  // Study flashcard state
  const [studyQueue,   setStudyQueue]  = useState<any[]>([])
  const [studyIdx,     setStudyIdx]    = useState(0)
  const [showStudy,    setShowStudy]   = useState(false)
  const [studyLoading, setStudyLoading]= useState(false)
  const [flipped,      setFlipped]     = useState(false)

  // Modals
  const [showAddWord,  setShowAddWord] = useState(false)
  const [showQuiz,     setShowQuiz]    = useState(false)

  const loadMovies = useCallback(async () => {
    if (!token) return
    setLoading(true)
    try {
      const res = await fetch(`${API}/api/cinema`, { headers: { Authorization: `Bearer ${token}` } })
      if (res.ok) setMovies(await res.json())
    } catch { /* ignore */ } finally { setLoading(false) }
  }, [token, API])

  useEffect(() => { loadMovies() }, [loadMovies])

  async function loadVocab(movie: MovieOut) {
    setActiveMovie(movie); setVocab([]); setVocabLoading(true)
    try {
      const res = await fetch(`${API}/api/cinema/${movie.id}/vocab`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (res.ok) setVocab(await res.json())
    } catch { /* ignore */ } finally { setVocabLoading(false) }
  }

  async function startStudy(movie: MovieOut) {
    setStudyLoading(true)
    try {
      const res = await fetch(`${API}/api/cinema/${movie.id}/study?limit=20`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (res.ok) {
        const data = await res.json()
        setStudyQueue(data.words || [])
        setStudyIdx(0); setFlipped(false); setShowStudy(true)
      }
    } catch { /* ignore */ } finally { setStudyLoading(false) }
  }

  async function deleteMovie(movie: MovieOut) {
    if (!confirm(`Remove "${movie.title}"? Vocabulary stays in your learning list.`)) return
    await fetch(`${API}/api/cinema/${movie.id}`, {
      method: 'DELETE', headers: { Authorization: `Bearer ${token}` },
    })
    setMovies(prev => prev.filter(m => m.id !== movie.id))
    if (activeMovie?.id === movie.id) { setActiveMovie(null); setVocab([]) }
  }

  function handleMeaningUpdate(id: number, translation: string) {
    setVocab(prev => prev.map(w => w.id === id ? { ...w, translation } : w))
  }

  const filtered = vocab.filter(w => {
    if (cefrFilter !== 'All' && w.cefr !== cefrFilter) return false
    if (posFilter  !== 'All' && w.pos  !== posFilter)  return false
    if (search && !w.word.includes(search.toLowerCase()) && !w.translation.toLowerCase().includes(search.toLowerCase())) return false
    return true
  })
  const allPos = Array.from(new Set(vocab.map(w => w.pos).filter(Boolean)))

  return (
    <div className="flex h-[calc(100vh-56px)] overflow-hidden">

      {/* ── LEFT: Library sidebar ────────────────────────────────── */}
      <aside className="w-72 shrink-0 border-r border-warm-200 bg-cream-50 flex flex-col">
        <div className="p-4 border-b border-warm-200">
          <div className="flex items-center justify-between mb-3">
            <h2 className="font-heading font-bold text-warm-900 flex items-center gap-2 text-sm">
              <Clapperboard className="w-4 h-4 text-cinema-500" /> Cinema Library
            </h2>
            <Link href="/search" className="btn-primary py-1 px-2 text-xs flex items-center gap-1">
              <Plus className="w-3 h-3" /> Add Film
            </Link>
          </div>
          <p className="text-[11px] text-warm-400">
            {movies.length === 0
              ? 'No films yet — load a subtitle file to start'
              : `${movies.length} film${movies.length > 1 ? 's' : ''} · each is a vocabulary folder`}
          </p>
        </div>

        <div className="flex-1 overflow-y-auto p-3 space-y-2">
          {loading && (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="w-5 h-5 animate-spin text-warm-300" />
            </div>
          )}
          {!loading && movies.length === 0 && (
            <div className="text-center py-10 text-warm-400">
              <Film className="w-8 h-8 mx-auto mb-2 opacity-40" />
              <p className="text-xs">Load a subtitle file in<br />
                <Link href="/search" className="text-cinema-500 hover:underline">Films → Find Subtitles</Link><br />
                to build your library.
              </p>
            </div>
          )}
          {movies.map(movie => (
            <MovieCard
              key={movie.id}
              movie={movie}
              active={activeMovie?.id === movie.id}
              onClick={() => loadVocab(movie)}
              onDelete={() => deleteMovie(movie)}
            />
          ))}
        </div>
      </aside>

      {/* ── RIGHT: Vocabulary panel ───────────────────────────────── */}
      <main className="flex-1 overflow-y-auto flex flex-col">
        {!activeMovie ? (
          <div className="flex-1 flex flex-col items-center justify-center text-center p-8">
            <div className="w-16 h-16 rounded-2xl bg-cinema-50 flex items-center justify-center mb-4">
              <Clapperboard className="w-8 h-8 text-cinema-400" />
            </div>
            <h3 className="text-lg font-heading font-bold text-warm-800 mb-2">Cinema Vocabulary Library</h3>
            <p className="text-warm-500 text-sm max-w-sm mb-6">
              Every film you load subtitles for gets its own folder here.
              Click a film to browse, edit, and quiz its vocabulary.
            </p>
            <Link href="/search" className="btn-primary flex items-center gap-2">
              <Film className="w-4 h-4" /> Load subtitles
            </Link>
          </div>
        ) : (
          <>
            {/* Movie header */}
            <div className="p-4 border-b border-warm-200 bg-white">
              <div className="flex items-start gap-3">
                <button onClick={() => setActiveMovie(null)} className="btn-ghost p-1 mt-0.5">
                  <ArrowLeft className="w-4 h-4" />
                </button>
                <div className="flex-1">
                  <h1 className="text-lg font-heading font-bold text-warm-900">
                    {activeMovie.title}
                    {activeMovie.year && <span className="ml-2 text-warm-400 font-normal text-base">({activeMovie.year})</span>}
                  </h1>
                  <div className="flex gap-4 mt-1 text-xs text-warm-500">
                    <span>{activeMovie.subtitle_count} subtitle lines</span>
                    <span className="text-cinema-600 font-medium">{activeMovie.vocab_count} words mined</span>
                    <span className="uppercase font-mono">{activeMovie.language} → {activeMovie.target_lang}</span>
                  </div>
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => setShowAddWord(true)}
                    className="btn-ghost py-1.5 px-3 text-xs flex items-center gap-1.5"
                  >
                    <Plus className="w-3 h-3" /> Add Word
                  </button>
                  <button
                    onClick={() => setShowQuiz(true)}
                    className="btn-ghost py-1.5 px-3 text-xs flex items-center gap-1.5 text-amber-700 hover:bg-amber-50"
                  >
                    <Brain className="w-3 h-3" /> Quiz
                  </button>
                  <button
                    onClick={() => startStudy(activeMovie)}
                    disabled={studyLoading}
                    className="btn-primary py-1.5 px-3 text-xs flex items-center gap-1.5"
                  >
                    {studyLoading ? <Loader2 className="w-3 h-3 animate-spin" /> : <GraduationCap className="w-3 h-3" />}
                    Study
                  </button>
                </div>
              </div>
              <div className="mt-3 max-w-lg">
                <CefrBar breakdown={activeMovie.cefr_breakdown} />
              </div>
            </div>

            {/* Filters */}
            <div className="p-3 border-b border-warm-100 bg-white flex flex-wrap gap-2 items-center">
              <div className="relative flex-1 min-w-40">
                <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-warm-400" />
                <input value={search} onChange={e => setSearch(e.target.value)}
                  placeholder="Search word or translation…"
                  className="input pl-8 py-1.5 text-sm w-full" />
              </div>
              <select value={cefrFilter} onChange={e => setCefrFilter(e.target.value)} className="select py-1.5 text-sm">
                <option value="All">All levels</option>
                {['A1','A2','B1','B2','C1'].map(l => <option key={l}>{l}</option>)}
              </select>
              <select value={posFilter} onChange={e => setPosFilter(e.target.value)} className="select py-1.5 text-sm">
                <option value="All">All POS</option>
                {allPos.map(p => <option key={p}>{p}</option>)}
              </select>
              <span className="text-xs text-warm-400">{filtered.length} / {vocab.length} words</span>
            </div>

            {/* Vocab table */}
            {vocabLoading ? (
              <div className="flex-1 flex items-center justify-center">
                <Loader2 className="w-6 h-6 animate-spin text-warm-300" />
              </div>
            ) : (
              <div className="flex-1 overflow-auto">
                <table className="w-full text-left">
                  <thead className="sticky top-0 bg-white border-b border-warm-200 z-10">
                    <tr className="text-xs text-warm-500">
                      <th className="px-3 py-2 w-10">#</th>
                      <th className="px-3 py-2">Word / IPA</th>
                      <th className="px-3 py-2">Translation <span className="text-warm-300 font-normal">(hover to edit)</span></th>
                      <th className="px-3 py-2">Level</th>
                      <th className="px-3 py-2">POS</th>
                      <th className="px-3 py-2">Freq</th>
                      <th className="px-3 py-2 w-8" />
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-warm-100">
                    {filtered.length === 0 && (
                      <tr>
                        <td colSpan={7} className="text-center py-10 text-warm-400 text-sm">
                          {vocab.length === 0
                            ? 'No vocabulary yet. Load subtitles in Films → Find Subtitles, or click Add Word to add manually.'
                            : 'No words match the filter.'}
                        </td>
                      </tr>
                    )}
                    {filtered.map((w, i) => (
                      <WordRow
                        key={w.id}
                        w={w} lang={activeMovie.language} idx={i}
                        token={token} API={API}
                        onUpdated={handleMeaningUpdate}
                      />
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}
      </main>

      {/* ── Study flashcard modal ─────────────────────────────────── */}
      {showStudy && studyQueue.length > 0 && (() => {
        const card = studyQueue[studyIdx]
        const done = studyIdx >= studyQueue.length
        return (
          <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4">
            <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md p-6">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h3 className="font-heading font-bold text-warm-900 flex items-center gap-2">
                    <GraduationCap className="w-4 h-4 text-cinema-500" /> {activeMovie?.title}
                  </h3>
                  <p className="text-xs text-warm-400">{studyIdx + 1} / {studyQueue.length} cards</p>
                </div>
                <button onClick={() => setShowStudy(false)} className="text-warm-400 hover:text-warm-700 text-lg">✕</button>
              </div>
              <div className="h-1.5 bg-warm-100 rounded-full mb-5">
                <div className="h-full bg-cinema-400 rounded-full transition-all"
                  style={{ width: `${(studyIdx / studyQueue.length) * 100}%` }} />
              </div>
              {done ? (
                <div className="text-center py-8">
                  <div className="text-4xl mb-3">🎉</div>
                  <p className="font-bold text-warm-900 text-lg">Session complete!</p>
                  <p className="text-warm-500 text-sm mt-1">{studyQueue.length} cards reviewed</p>
                  <div className="flex gap-2 mt-4">
                    <button onClick={() => { setStudyIdx(0); setFlipped(false) }} className="flex-1 btn-ghost text-sm py-2">Start over</button>
                    <button onClick={() => setShowStudy(false)} className="flex-1 btn-primary text-sm py-2">Done</button>
                  </div>
                </div>
              ) : (
                <>
                  <div onClick={() => setFlipped(f => !f)}
                    className="cursor-pointer bg-cream-50 border border-warm-200 rounded-xl p-8 text-center min-h-[160px] flex flex-col items-center justify-center gap-3 hover:border-cinema-300 transition-all">
                    {!flipped ? (
                      <>
                        <p className="text-3xl font-bold text-warm-900">{card.word}</p>
                        {card.ipa && <p className="text-warm-400 font-mono text-sm">{card.ipa}</p>}
                        <p className="text-xs text-warm-400 mt-2">Tap to reveal</p>
                      </>
                    ) : (
                      <>
                        <p className="text-xl font-semibold text-cinema-600">{card.translation || '—'}</p>
                        {card.example && <p className="text-xs italic text-warm-500 mt-2 max-w-xs">{card.example}</p>}
                        {card.definition && <p className="text-xs text-amber-700 bg-amber-50 rounded px-2 py-1 mt-1">💡 {card.definition}</p>}
                      </>
                    )}
                  </div>
                  <div className="flex justify-center mt-3">
                    <button onClick={() => speak(card.word, activeMovie?.language || 'fr')}
                      className="btn-ghost text-xs flex items-center gap-1 py-1">
                      <Volume2 className="w-3 h-3" /> Listen
                    </button>
                  </div>
                  <div className="flex gap-2 mt-4">
                    <button onClick={() => { setStudyIdx(i => i + 1); setFlipped(false) }}
                      className="flex-1 btn-ghost text-sm py-2">Skip →</button>
                    <button onClick={() => { setStudyIdx(i => i + 1); setFlipped(false) }}
                      className="flex-1 btn-primary text-sm py-2">Got it ✓</button>
                  </div>
                </>
              )}
            </div>
          </div>
        )
      })()}

      {/* ── Add Word modal ────────────────────────────────────────── */}
      {showAddWord && activeMovie && (
        <AddWordModal
          movie={activeMovie}
          token={token} API={API}
          onClose={() => setShowAddWord(false)}
          onAdded={() => { loadVocab(activeMovie); loadMovies() }}
        />
      )}

      {/* ── Quiz modal ────────────────────────────────────────────── */}
      {showQuiz && activeMovie && (
        <QuizModal
          movie={activeMovie}
          token={token} API={API}
          onClose={() => setShowQuiz(false)}
        />
      )}
    </div>
  )
}
