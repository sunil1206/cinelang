'use client'
import { X, Volume2, Loader2, Sparkles } from 'lucide-react'
import { PosBadge, StatusBadge } from './ui/Badge'
import type { VocabEntry, VocabStatus } from '@/lib/types'
import { STATUS_CYCLE } from '@/lib/types'

function speak(word: string, lang: string) {
  if (typeof window === 'undefined' || !window.speechSynthesis) return
  window.speechSynthesis.cancel()
  const u = new SpeechSynthesisUtterance(word)
  u.lang = lang === 'zh' ? 'zh-CN' : `${lang}-${lang.toUpperCase()}`
  u.rate = 0.85
  window.speechSynthesis.speak(u)
}

interface Props {
  word:           VocabEntry
  targetLang:     string
  enriching:      boolean
  onClose:        () => void
  onEnrich:       (w: VocabEntry) => void
  onStatusChange: (w: VocabEntry, s: VocabStatus) => void
}

export default function WordModal({ word, targetLang, enriching, onClose, onEnrich, onStatusChange }: Props) {
  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-0 sm:p-4"
      style={{ background: 'rgba(28,25,23,0.5)', backdropFilter: 'blur(4px)' }}
      onClick={onClose}>
      <div
        className="bg-white w-full sm:max-w-md rounded-t-2xl sm:rounded-2xl shadow-warm-xl border border-warm-200 p-6 animate-slide-up"
        onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="flex items-start justify-between mb-5">
          <div>
            <div className="flex items-center gap-2 mb-2">
              <h2 className="font-heading font-bold text-warm-900 text-3xl">{word.word}</h2>
              <button onClick={() => speak(word.word, targetLang)} className="btn-icon p-1.5">
                <Volume2 className="w-4 h-4" />
              </button>
            </div>
            <div className="flex items-center gap-2 flex-wrap">
              <PosBadge pos={word.pos} />
              {word.phonetic && <span className="text-xs font-mono text-warm-400">{word.phonetic}</span>}
              <StatusBadge status={word.status} onClick={() => onStatusChange(word, STATUS_CYCLE[word.status])} />
            </div>
          </div>
          <button onClick={onClose} className="btn-icon p-1.5 shrink-0"><X className="w-4 h-4" /></button>
        </div>

        {/* Translation */}
        <div className="space-y-3 mb-5">
          <div className="p-3 rounded-xl bg-cinema-50 border border-cinema-100">
            <p className="text-xs font-mono text-cinema-400 uppercase tracking-wider mb-1">Translation</p>
            <p className="font-heading font-semibold text-cinema-700 text-lg">
              {word.translation ?? <span className="text-warm-300 italic font-body font-normal text-base">Not enriched yet</span>}
            </p>
          </div>

          {word.explanation && (
            <div className="p-3 rounded-xl bg-cream-100 border border-warm-200">
              <p className="text-xs font-mono text-warm-400 uppercase tracking-wider mb-1">Usage</p>
              <p className="text-sm text-warm-700 leading-relaxed">{word.explanation}</p>
            </div>
          )}

          {word.contexts && word.contexts.length > 0 && (
            <div className="p-3 rounded-xl bg-cream-100 border border-warm-200">
              <p className="text-xs font-mono text-warm-400 uppercase tracking-wider mb-2">Example Contexts</p>
              {word.contexts.slice(0, 3).map((ctx, i) => (
                <p key={i} className="text-sm text-warm-600 italic border-l-2 border-cinema-200 pl-3 mb-1.5 last:mb-0">
                  "{ctx}"
                </p>
              ))}
            </div>
          )}
        </div>

        {/* Actions */}
        <div className="flex gap-2">
          <button onClick={() => onEnrich(word)} disabled={enriching}
            className="flex-1 btn-primary justify-center">
            {enriching
              ? <><Loader2 className="w-4 h-4 animate-spin" /> Enriching…</>
              : <><Sparkles className="w-4 h-4" /> Enrich with AI</>
            }
          </button>
          <button onClick={() => onStatusChange(word, STATUS_CYCLE[word.status])} className="btn-ghost">
            Next Status
          </button>
        </div>
      </div>
    </div>
  )
}
