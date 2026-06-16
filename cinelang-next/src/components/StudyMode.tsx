'use client'
import { useState } from 'react'
import { X, Volume2, Check, RotateCcw } from 'lucide-react'
import { PosBadge } from './ui/Badge'
import type { VocabEntry } from '@/lib/types'

function speak(word: string, lang: string) {
  if (typeof window === 'undefined' || !window.speechSynthesis) return
  window.speechSynthesis.cancel()
  const u = new SpeechSynthesisUtterance(word)
  u.lang = lang === 'zh' ? 'zh-CN' : `${lang}-${lang.toUpperCase()}`
  u.rate = 0.85
  window.speechSynthesis.speak(u)
}

interface Props {
  words:           VocabEntry[]
  targetLang:      string
  onClose:         () => void
  onGotIt:         (w: VocabEntry) => void
  onKeepLearning:  (w: VocabEntry) => void
}

export default function StudyMode({ words, targetLang, onClose, onGotIt, onKeepLearning }: Props) {
  const [idx,     setIdx]     = useState(0)
  const [flipped, setFlipped] = useState(false)
  const [gotItIds, setGotItIds] = useState<Set<number>>(new Set())

  const word = words[idx]
  const done = idx >= words.length

  function next(action: 'got' | 'keep') {
    if (!word) return
    if (action === 'got') { onGotIt(word); setGotItIds((s) => new Set(s).add(word.id)) }
    else onKeepLearning(word)
    setFlipped(false)
    setTimeout(() => setIdx((i) => i + 1), 80)
  }

  if (done) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center p-6 animate-fade-in"
        style={{ background: 'rgba(250,250,248,0.97)' }}>
        <div className="text-center max-w-sm">
          <div className="text-6xl mb-4">🎉</div>
          <h2 className="font-heading font-bold text-warm-900 text-3xl mb-2">Session Complete!</h2>
          <p className="text-warm-500 mb-2">
            <span className="font-semibold text-warm-800">{gotItIds.size}</span> mastered ·{' '}
            <span className="font-semibold text-warm-800">{words.length - gotItIds.size}</span> still learning
          </p>
          <div className="w-full bg-warm-200 rounded-full h-2 mb-8">
            <div className="bg-cinema-500 h-2 rounded-full transition-all"
              style={{ width: `${(gotItIds.size / words.length) * 100}%` }} />
          </div>
          <button onClick={onClose} className="btn-primary px-8 py-3">Back to Dashboard</button>
        </div>
      </div>
    )
  }

  return (
    <div className="fixed inset-0 z-50 flex flex-col items-center justify-center p-6 bg-cream-100 animate-fade-in">
      {/* Top bar */}
      <div className="w-full max-w-md flex items-center justify-between mb-6">
        <div className="text-xs font-mono text-warm-400">{idx + 1} / {words.length} cards</div>
        <button onClick={onClose} className="btn-icon p-1.5"><X className="w-4 h-4" /></button>
      </div>

      {/* Progress */}
      <div className="w-full max-w-md mb-6">
        <div className="h-1.5 bg-warm-200 rounded-full overflow-hidden">
          <div className="h-full bg-cinema-500 rounded-full transition-all"
            style={{ width: `${(idx / words.length) * 100}%` }} />
        </div>
      </div>

      {/* Flip card */}
      <div className="w-full max-w-md flip-scene mb-6">
        <div className={`flip-inner w-full h-60 cursor-pointer ${flipped ? 'flip' : ''}`}
          onClick={() => { setFlipped((f) => !f); if (!flipped) speak(word.word, targetLang) }}>
          {/* Front */}
          <div className="flip-face absolute inset-0 card flex flex-col items-center justify-center p-8">
            <PosBadge pos={word.pos} />
            <p className="font-heading font-bold text-warm-900 text-4xl mt-4 mb-2 text-center">{word.word}</p>
            <p className="text-warm-400 font-mono text-sm">{word.phonetic ?? ''}</p>
            <div className="flex items-center gap-1.5 mt-6 text-xs text-warm-300">
              <span>Tap to reveal</span>
            </div>
          </div>
          {/* Back */}
          <div className="flip-back flip-face absolute inset-0 rounded-2xl border border-cinema-100 bg-cinema-50 flex flex-col items-center justify-center p-8 text-center">
            <p className="font-heading font-bold text-cinema-600 text-2xl mb-3">{word.translation ?? '—'}</p>
            {word.explanation && (
              <p className="text-warm-600 text-sm leading-relaxed max-w-xs">{word.explanation}</p>
            )}
            {word.contexts?.[0] && (
              <p className="text-warm-400 text-xs italic mt-4 border-t border-cinema-100 pt-4">
                "{word.contexts[0]}"
              </p>
            )}
            <button onClick={(e) => { e.stopPropagation(); speak(word.word, targetLang) }}
              className="mt-3 btn-icon p-1.5">
              <Volume2 className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </div>

      {/* Action buttons — only show after flip */}
      {flipped ? (
        <div className="flex gap-3 w-full max-w-md animate-slide-up">
          <button onClick={() => next('keep')}
            className="flex-1 flex items-center justify-center gap-2 py-3.5 rounded-xl border-2 border-warm-300 text-warm-600 font-medium hover:bg-warm-100 transition-all active:scale-95">
            <RotateCcw className="w-4 h-4" /> Still Learning
          </button>
          <button onClick={() => next('got')}
            className="flex-1 flex items-center justify-center gap-2 py-3.5 rounded-xl bg-amber-500 text-white font-medium hover:bg-amber-600 transition-all active:scale-95 shadow-warm-sm">
            <Check className="w-4 h-4" /> Got it! ✓
          </button>
        </div>
      ) : (
        <p className="text-warm-400 text-sm">Click the card to flip</p>
      )}
    </div>
  )
}
