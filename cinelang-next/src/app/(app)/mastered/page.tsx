'use client'
import { useState } from 'react'
import { useSession } from 'next-auth/react'
import { Star, Download, Volume2, RotateCcw } from 'lucide-react'
import WordModal from '@/components/WordModal'
import { PosBadge } from '@/components/ui/Badge'
import { useCineLang } from '@/lib/store'
import { setVocabStatus, enrichWord } from '@/lib/api'
import { langMeta, type VocabEntry, type VocabStatus } from '@/lib/types'
import clsx from 'clsx'

function speak(word: string, lang: string) {
  if (typeof window === 'undefined' || !window.speechSynthesis) return
  window.speechSynthesis.cancel()
  const u = new SpeechSynthesisUtterance(word)
  u.lang = lang === 'zh' ? 'zh-CN' : `${lang}-${lang.toUpperCase()}`
  u.rate = 0.85
  window.speechSynthesis.speak(u)
}

export default function MasteredPage() {
  const { data: session } = useSession()
  const { vocab, updateVocabStatus, patchVocabEntry, targetLang, sourceLang, backendToken, showToast } = useCineLang()
  const token = (session as any)?.backendToken ?? backendToken

  const [selectedWord, setSelectedWord] = useState<VocabEntry | null>(null)
  const [enriching,    setEnriching]    = useState(false)

  const mastered = vocab.filter((w) => w.status === 'mastered')

  async function changeStatus(word: VocabEntry, status: VocabStatus) {
    updateVocabStatus(word.id, word.word, word.target_lang, status)
    if (selectedWord?.word === word.word) setSelectedWord((p) => p ? { ...p, status } : p)
    if (token && word.id > 0) {
      try { await setVocabStatus(word.id, status, token) } catch {}
    }
    if (status !== 'mastered') showToast(`"${word.word}" moved back to ${status}`)
  }

  async function handleEnrich(word: VocabEntry) {
    if (!token) { showToast('Sign in to enrich words with AI', 'warn'); return }
    setEnriching(true)
    try {
      const res = await enrichWord(word.word, word.contexts?.[0] ?? '', sourceLang, targetLang, token)
      patchVocabEntry(word.id, res as Partial<VocabEntry>)
      setSelectedWord((p) => p ? { ...p, ...res } : p)
      showToast(`✨ "${word.word}" enriched`)
    } catch (e: any) { showToast(e.message, 'err') }
    finally { setEnriching(false) }
  }

  function exportAnki() {
    const lines = mastered.map((w) =>
      [w.word, w.translation ?? '', w.pos ?? '', w.phonetic ?? '', w.explanation ?? '', (w.contexts ?? []).join(' | ')].join('\t')
    )
    const blob = new Blob(['#separator:tab\n#deck:CineLang Mastered\n' + lines.join('\n')], { type: 'text/plain' })
    const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = 'cinelang-mastered.txt'; a.click()
  }

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 py-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="font-heading font-bold text-warm-900 text-2xl mb-1">Mastered Words</h1>
          <p className="text-sm text-warm-400">
            {mastered.length} words mastered in {langMeta(targetLang).flag} {langMeta(targetLang).label}
          </p>
        </div>
        {mastered.length > 0 && (
          <button onClick={exportAnki} className="btn-ghost text-sm">
            <Download className="w-4 h-4" /> Export Anki Deck
          </button>
        )}
      </div>

      {mastered.length === 0 ? (
        <div className="card p-12 text-center">
          <Star className="w-12 h-12 text-warm-300 mx-auto mb-3" />
          <p className="font-heading font-semibold text-warm-700 text-lg mb-1">No mastered words yet</p>
          <p className="text-sm text-warm-400">
            Study words on the Learning page and tap "Got it! ✓" to move them here.
          </p>
        </div>
      ) : (
        <>
          {/* Achievement banner */}
          <div className="card-sm p-4 bg-amber-50 border border-amber-100 flex items-center gap-4">
            <div className="text-3xl">🏆</div>
            <div>
              <p className="font-heading font-semibold text-amber-800">{mastered.length} words mastered!</p>
              <p className="text-xs text-amber-600">Keep going — fluency is built one word at a time.</p>
            </div>
          </div>

          {/* Gallery grid */}
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
            {mastered.map((word) => (
              <div key={`${word.id}-${word.word}`}
                className="card-sm p-4 flex flex-col gap-2 group hover:shadow-warm-lg transition-all">
                <div className="flex items-center justify-between">
                  <PosBadge pos={word.pos} />
                  <span className="text-amber-400">
                    <Star className="w-3.5 h-3.5 fill-amber-400" />
                  </span>
                </div>
                <button onClick={() => setSelectedWord(word)}
                  className="text-left">
                  <p className="font-heading font-bold text-warm-900 text-lg leading-tight group-hover:text-cinema-600 transition-colors">
                    {word.word}
                  </p>
                  {word.phonetic && (
                    <p className="text-xs text-warm-400 font-mono">{word.phonetic}</p>
                  )}
                </button>
                {word.translation && (
                  <p className="text-sm text-cinema-600 font-medium line-clamp-2">{word.translation}</p>
                )}
                <div className="flex items-center gap-1 mt-auto pt-2 border-t border-warm-100">
                  <button onClick={() => speak(word.word, targetLang)}
                    className="btn-icon p-1 text-warm-400 hover:text-cinema-500">
                    <Volume2 className="w-3 h-3" />
                  </button>
                  <button
                    title="Move back to Learning"
                    onClick={() => changeStatus(word, 'learning')}
                    className="btn-icon p-1 text-warm-400 hover:text-violet-500 ml-auto">
                    <RotateCcw className="w-3 h-3" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      {selectedWord && (
        <WordModal word={selectedWord} targetLang={targetLang} enriching={enriching}
          onClose={() => setSelectedWord(null)}
          onEnrich={handleEnrich}
          onStatusChange={changeStatus} />
      )}
    </div>
  )
}
