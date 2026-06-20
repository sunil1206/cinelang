'use client'
import { useState, useEffect, useCallback } from 'react'
import { useSession } from 'next-auth/react'
import { useRouter } from 'next/navigation'
import { CheckCircle, XCircle, Trophy, RotateCcw, ChevronRight, Brain } from 'lucide-react'
import clsx from 'clsx'

interface Question {
  type: 'fill_blank' | 'multiple_choice' | 'translation'
  prompt: string
  answer: string
  options: string[]
  hint: string
  word: string
  cefr: string
}

interface QuizResult {
  word: string
  correct: boolean
  userAnswer: string
  correctAnswer: string
  type: string
}

const CEFR_COLORS: Record<string, string> = {
  A1: 'bg-green-500', A2: 'bg-green-400',
  B1: 'bg-yellow-500', B2: 'bg-yellow-400',
  C1: 'bg-red-400', C2: 'bg-red-600',
}

export default function QuizPage() {
  const { data: session } = useSession()
  const router = useRouter()

  const [langCode, setLangCode]     = useState('fr')
  const [size, setSize]             = useState(10)
  const [questions, setQuestions]   = useState<Question[]>([])
  const [current, setCurrent]       = useState(0)
  const [userInput, setUserInput]   = useState('')
  const [selected, setSelected]     = useState<string | null>(null)
  const [revealed, setRevealed]     = useState(false)
  const [results, setResults]       = useState<QuizResult[]>([])
  const [loading, setLoading]       = useState(false)
  const [error, setError]           = useState('')
  const [phase, setPhase]           = useState<'setup' | 'quiz' | 'results'>('setup')

  const q = questions[current]

  const startQuiz = useCallback(async () => {
    if (!session) { router.push('/'); return }
    setLoading(true); setError('')
    try {
      const res = await fetch(`/api/quiz/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ lang_code: langCode, size }),
      })
      if (!res.ok) {
        const d = await res.json()
        throw new Error(d?.detail || d?.error?.message || 'Not enough vocabulary yet — add more words first')
      }
      const data = await res.json()
      setQuestions(data.questions)
      setCurrent(0); setResults([]); setRevealed(false); setUserInput(''); setSelected(null)
      setPhase('quiz')
    } catch (e: any) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [session, langCode, size, router])

  const submitAnswer = useCallback(() => {
    if (!q || revealed) return
    const answer = q.type === 'multiple_choice' ? (selected ?? '') : userInput.trim()
    const correct = answer.toLowerCase() === q.answer.toLowerCase()
    setResults(r => [...r, { word: q.word, correct, userAnswer: answer, correctAnswer: q.answer, type: q.type }])
    setRevealed(true)
  }, [q, revealed, selected, userInput])

  const next = useCallback(() => {
    if (current + 1 >= questions.length) {
      setPhase('results')
    } else {
      setCurrent(c => c + 1)
      setRevealed(false); setUserInput(''); setSelected(null)
    }
  }, [current, questions.length])

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Enter') revealed ? next() : submitAnswer()
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [revealed, next, submitAnswer])

  const score = results.filter(r => r.correct).length

  // ── Setup screen ────────────────────────────────────────────────────────────
  if (phase === 'setup') return (
    <div className="min-h-screen bg-cinema-950 flex items-center justify-center p-4">
      <div className="w-full max-w-md bg-cinema-900 rounded-2xl p-8 shadow-2xl border border-cinema-700">
        <div className="flex items-center gap-3 mb-8">
          <Brain className="text-cinema-400" size={28} />
          <h1 className="text-2xl font-heading text-white">Quiz</h1>
        </div>

        <div className="space-y-5">
          <div>
            <label className="block text-sm text-warm-400 mb-2">Language</label>
            <select
              value={langCode}
              onChange={e => setLangCode(e.target.value)}
              className="w-full bg-cinema-800 border border-cinema-600 rounded-lg px-4 py-2.5 text-white focus:outline-none focus:border-cinema-400"
            >
              <option value="fr">French</option>
              <option value="de">German</option>
              <option value="es">Spanish</option>
              <option value="it">Italian</option>
              <option value="pt">Portuguese</option>
              <option value="ja">Japanese</option>
            </select>
          </div>

          <div>
            <label className="block text-sm text-warm-400 mb-2">Questions: {size}</label>
            <input
              type="range" min={5} max={30} step={5}
              value={size} onChange={e => setSize(+e.target.value)}
              className="w-full accent-cinema-400"
            />
            <div className="flex justify-between text-xs text-warm-500 mt-1">
              <span>5</span><span>10</span><span>15</span><span>20</span><span>25</span><span>30</span>
            </div>
          </div>

          {error && <p className="text-red-400 text-sm bg-red-900/20 rounded-lg px-4 py-3">{error}</p>}

          <button
            onClick={startQuiz} disabled={loading}
            className="w-full btn-primary py-3 rounded-xl font-semibold text-lg disabled:opacity-50"
          >
            {loading ? 'Loading...' : 'Start Quiz'}
          </button>
        </div>
      </div>
    </div>
  )

  // ── Results screen ──────────────────────────────────────────────────────────
  if (phase === 'results') return (
    <div className="min-h-screen bg-cinema-950 flex items-center justify-center p-4">
      <div className="w-full max-w-lg bg-cinema-900 rounded-2xl p-8 shadow-2xl border border-cinema-700">
        <div className="text-center mb-8">
          <Trophy className={clsx('mx-auto mb-4', score / questions.length >= 0.8 ? 'text-yellow-400' : 'text-warm-500')} size={48} />
          <h2 className="text-3xl font-heading text-white mb-2">{score}/{questions.length}</h2>
          <p className="text-warm-400">
            {score / questions.length >= 0.8 ? 'Excellent work!' :
             score / questions.length >= 0.6 ? 'Good effort!' : 'Keep practising!'}
          </p>
        </div>

        <div className="space-y-2 max-h-80 overflow-y-auto mb-6">
          {results.map((r, i) => (
            <div key={i} className={clsx(
              'flex items-center justify-between rounded-lg px-4 py-2.5',
              r.correct ? 'bg-green-900/30 border border-green-800' : 'bg-red-900/20 border border-red-900'
            )}>
              <div className="flex items-center gap-3">
                {r.correct
                  ? <CheckCircle size={16} className="text-green-400 shrink-0" />
                  : <XCircle size={16} className="text-red-400 shrink-0" />}
                <span className="text-white font-mono text-sm">{r.word}</span>
              </div>
              {!r.correct && (
                <div className="text-right text-xs">
                  <span className="text-red-400 line-through mr-2">{r.userAnswer || '—'}</span>
                  <span className="text-green-400">{r.correctAnswer}</span>
                </div>
              )}
            </div>
          ))}
        </div>

        <div className="flex gap-3">
          <button onClick={() => setPhase('setup')} className="flex-1 btn-secondary py-3 rounded-xl flex items-center justify-center gap-2">
            <RotateCcw size={16} /> New Quiz
          </button>
          <button onClick={startQuiz} className="flex-1 btn-primary py-3 rounded-xl flex items-center justify-center gap-2">
            <RotateCcw size={16} /> Retry Same
          </button>
        </div>
      </div>
    </div>
  )

  // ── Quiz screen ─────────────────────────────────────────────────────────────
  if (!q) return null
  const progress = ((current) / questions.length) * 100

  return (
    <div className="min-h-screen bg-cinema-950 flex items-center justify-center p-4">
      <div className="w-full max-w-lg">
        {/* Progress */}
        <div className="mb-6">
          <div className="flex justify-between text-sm text-warm-400 mb-2">
            <span>{current + 1} / {questions.length}</span>
            <span>{results.filter(r => r.correct).length} correct</span>
          </div>
          <div className="h-1.5 bg-cinema-800 rounded-full">
            <div className="h-1.5 bg-cinema-400 rounded-full transition-all duration-300" style={{ width: `${progress}%` }} />
          </div>
        </div>

        {/* Card */}
        <div className="bg-cinema-900 rounded-2xl p-8 shadow-2xl border border-cinema-700">
          {/* CEFR + type badge */}
          <div className="flex items-center gap-2 mb-6">
            <span className={clsx('text-[10px] font-bold px-2 py-0.5 rounded text-white', CEFR_COLORS[q.cefr] || 'bg-cinema-600')}>
              {q.cefr}
            </span>
            <span className="text-[10px] text-warm-500 uppercase tracking-wider">
              {q.type === 'fill_blank' ? 'Fill in the blank' : q.type === 'multiple_choice' ? 'Multiple choice' : 'Translation'}
            </span>
          </div>

          {/* Prompt */}
          <p className="text-white text-lg leading-relaxed mb-8 whitespace-pre-wrap">{q.prompt}</p>

          {/* Input area */}
          {q.type === 'multiple_choice' ? (
            <div className="space-y-3 mb-6">
              {q.options.map(opt => (
                <button
                  key={opt}
                  onClick={() => !revealed && setSelected(opt)}
                  disabled={revealed}
                  className={clsx(
                    'w-full text-left px-4 py-3 rounded-xl border transition-all text-sm',
                    revealed
                      ? opt === q.answer
                        ? 'bg-green-900/40 border-green-500 text-green-300'
                        : opt === selected && opt !== q.answer
                          ? 'bg-red-900/30 border-red-500 text-red-300'
                          : 'bg-cinema-800 border-cinema-600 text-warm-400 opacity-50'
                      : selected === opt
                        ? 'bg-cinema-700 border-cinema-400 text-white'
                        : 'bg-cinema-800 border-cinema-700 text-warm-300 hover:border-cinema-500 hover:text-white'
                  )}
                >
                  {opt}
                </button>
              ))}
            </div>
          ) : (
            <div className="mb-6">
              <input
                autoFocus
                type="text"
                value={userInput}
                onChange={e => setUserInput(e.target.value)}
                disabled={revealed}
                placeholder={q.type === 'fill_blank' ? 'Type the missing word…' : 'Type the translation…'}
                className={clsx(
                  'w-full bg-cinema-800 border rounded-xl px-4 py-3 text-white placeholder-warm-600 focus:outline-none transition-colors',
                  revealed
                    ? userInput.toLowerCase() === q.answer.toLowerCase()
                      ? 'border-green-500'
                      : 'border-red-500'
                    : 'border-cinema-600 focus:border-cinema-400'
                )}
              />
              {revealed && userInput.toLowerCase() !== q.answer.toLowerCase() && (
                <p className="text-green-400 text-sm mt-2">Correct: <strong>{q.answer}</strong></p>
              )}
            </div>
          )}

          {/* Hint */}
          {q.hint && !revealed && (
            <p className="text-warm-500 text-xs mb-4">Hint: {q.hint}</p>
          )}

          {/* Feedback */}
          {revealed && (
            <div className={clsx(
              'rounded-xl px-4 py-3 mb-4 flex items-center gap-3',
              results[results.length - 1]?.correct ? 'bg-green-900/30 border border-green-800' : 'bg-red-900/20 border border-red-900'
            )}>
              {results[results.length - 1]?.correct
                ? <CheckCircle size={18} className="text-green-400 shrink-0" />
                : <XCircle size={18} className="text-red-400 shrink-0" />}
              <span className="text-sm text-warm-300">
                {results[results.length - 1]?.correct ? 'Correct!' : `The answer was: ${q.answer}`}
              </span>
            </div>
          )}

          {/* Actions */}
          {!revealed ? (
            <button
              onClick={submitAnswer}
              disabled={q.type === 'multiple_choice' ? !selected : !userInput.trim()}
              className="w-full btn-primary py-3 rounded-xl font-semibold disabled:opacity-40"
            >
              Check Answer
            </button>
          ) : (
            <button onClick={next} className="w-full btn-primary py-3 rounded-xl font-semibold flex items-center justify-center gap-2">
              {current + 1 >= questions.length ? 'See Results' : 'Next'} <ChevronRight size={18} />
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
