'use client'
import { useState, useEffect, useRef } from 'react'
import { Play, Pause, SkipBack, SkipForward, Volume2 } from 'lucide-react'
import { useCineLang } from '@/lib/store'
import clsx from 'clsx'

function speak(text: string, lang: string) {
  if (typeof window === 'undefined' || !window.speechSynthesis) return
  window.speechSynthesis.cancel()
  const u = new SpeechSynthesisUtterance(text)
  u.lang = lang === 'zh' ? 'zh-CN' : `${lang}-${lang.toUpperCase()}`
  u.rate = 0.85
  window.speechSynthesis.speak(u)
}

interface Props {
  onWordClick?: (word: string) => void
}

export default function SubtitlePlayer({ onWordClick }: Props) {
  const {
    subtitles, translatedSubs, currentSubIdx, setCurrentSubIdx,
    vocab, targetLang, sourceLang,
  } = useCineLang()

  const [playing, setPlaying] = useState(false)
  const timer = useRef<ReturnType<typeof setInterval> | null>(null)

  const hasTranslations = translatedSubs.length > 0
  const displaySubs = hasTranslations
    ? translatedSubs
    : subtitles.map((s) => ({ ...s, original: s.text }))
  const current     = displaySubs[currentSubIdx]
  const wordSet     = new Set(vocab.map((v) => v.word))

  // Only show the translation line when it actually differs from the original
  const isReallyTranslated =
    current &&
    'original' in current &&
    current.original !== current.text

  useEffect(() => {
    if (playing) {
      timer.current = setInterval(() => {
        setCurrentSubIdx(Math.min(displaySubs.length - 1, currentSubIdx + 1))
        if (currentSubIdx >= displaySubs.length - 1) setPlaying(false)
      }, 3200)
    } else if (timer.current) clearInterval(timer.current)
    return () => { if (timer.current) clearInterval(timer.current) }
  }, [playing, currentSubIdx, displaySubs.length])

  function highlight(text: string, isTranslation = false) {
    return text.split(/(\s+)/).map((part, i) => {
      const clean = part.toLowerCase().replace(/[^a-zàâäéèêëïîôùûüÿæœçñßäöü]/g, '')
      const isKw = isTranslation && wordSet.has(clean)
      return isKw ? (
        <button key={i}
          onClick={() => { onWordClick?.(clean); speak(clean, targetLang) }}
          className="text-cinema-500 font-medium hover:text-cinema-600 hover:underline decoration-dotted transition-all">
          {part}
        </button>
      ) : <span key={i}>{part}</span>
    })
  }

  return (
    <div className="card overflow-hidden">
      {/* Screen */}
      <div className="relative bg-warm-900 min-h-44 flex flex-col items-center justify-center px-6 py-6 text-center">
        {current ? (
          <>
            <p className="text-xs font-mono text-warm-400 mb-3">
              {current.start?.slice(0, 8)} — {current.end?.slice(0, 8)}
            </p>

            {/* When real translation exists: show original (dim) + translated (bright) */}
            {isReallyTranslated ? (
              <>
                <div className="mb-2 w-full">
                  <span className="text-[10px] font-mono text-warm-500 uppercase tracking-wider">
                    {sourceLang?.toUpperCase()}
                  </span>
                  <p className="text-warm-400 text-sm italic leading-relaxed mt-0.5">
                    {('original' in current) ? current.original : current.text}
                  </p>
                </div>
                <div className="w-12 h-px bg-warm-700 mb-2" />
                <div className="w-full">
                  <span className="text-[10px] font-mono text-cinema-400 uppercase tracking-wider">
                    {targetLang?.toUpperCase()}
                  </span>
                  <p className="text-white text-xl font-heading leading-relaxed mt-0.5">
                    {highlight(current.text, true)}
                  </p>
                </div>
              </>
            ) : (
              /* No translation yet — show single line in source language */
              <div className="w-full">
                <span className="text-[10px] font-mono text-warm-500 uppercase tracking-wider">
                  {sourceLang?.toUpperCase()}
                </span>
                <p className="text-white text-xl font-heading leading-relaxed mt-0.5">
                  {highlight(current.text, false)}
                </p>
              </div>
            )}

            <p className="text-xs font-mono text-warm-500 mt-3">
              {currentSubIdx + 1} / {displaySubs.length}
            </p>
          </>
        ) : (
          <div className="text-center">
            <p className="text-warm-400 text-sm">No subtitles loaded</p>
            <p className="text-warm-500 text-xs mt-1">Go to Search to find & import subtitles</p>
          </div>
        )}

        {/* Equalizer */}
        {playing && (
          <div className="absolute top-3 right-3 flex items-end h-5 gap-0.5">
            {[1,2,3,4,5].map((n) => (
              <span key={n} className="eq-bar" style={{ animationDelay: `${n * 0.1}s`, height: 8 }} />
            ))}
          </div>
        )}
      </div>

      {/* Controls */}
      <div className="px-4 py-3 flex items-center gap-2 border-t border-warm-200">
        <button onClick={() => setCurrentSubIdx(Math.max(0, currentSubIdx - 1))} className="btn-icon p-1.5">
          <SkipBack className="w-3.5 h-3.5" />
        </button>

        <button onClick={() => setPlaying((p) => !p)}
          className={clsx(
            'flex-1 flex items-center justify-center gap-2 py-2 rounded-xl text-sm font-medium transition-all',
            playing
              ? 'bg-cinema-50 text-cinema-600 border border-cinema-200'
              : 'bg-cinema-500 text-white hover:bg-cinema-600',
          )}>
          {playing ? <><Pause className="w-4 h-4" /> Pause</> : <><Play className="w-4 h-4" /> Play Scene</>}
        </button>

        <button onClick={() => setCurrentSubIdx(Math.min(displaySubs.length - 1, currentSubIdx + 1))} className="btn-icon p-1.5">
          <SkipForward className="w-3.5 h-3.5" />
        </button>

        <button onClick={() => current && speak(current.text, targetLang)} className="btn-icon p-1.5">
          <Volume2 className="w-3.5 h-3.5" />
        </button>
      </div>

      {/* Timeline */}
      {displaySubs.length > 1 && (
        <div className="px-4 pb-3">
          <div className="flex gap-px h-1.5 rounded-full overflow-hidden">
            {displaySubs.map((_, i) => (
              <button key={i} onClick={() => setCurrentSubIdx(i)}
                className={clsx(
                  'flex-1 rounded-full transition-all',
                  i === currentSubIdx ? 'bg-cinema-500' : i < currentSubIdx ? 'bg-cinema-200' : 'bg-warm-200',
                )} />
            ))}
          </div>
          <div className="flex justify-between text-xs text-warm-400 font-mono mt-1">
            <span>{displaySubs[0]?.start?.slice(0, 8)}</span>
            <span>{displaySubs[displaySubs.length - 1]?.end?.slice(0, 8)}</span>
          </div>
        </div>
      )}
    </div>
  )
}
