'use client'
import { useState } from 'react'
import { useSession } from 'next-auth/react'
import { GraduationCap, Play } from 'lucide-react'
import StudyMode from '@/components/StudyMode'
import WordModal from '@/components/WordModal'
import { PosBadge, StatusBadge } from '@/components/ui/Badge'
import { useCineLang } from '@/lib/store'
import { setVocabStatus, enrichWord } from '@/lib/api'
import { STATUS_CYCLE, type VocabEntry, type VocabStatus } from '@/lib/types'
import clsx from 'clsx'

export default function LearnPage() {
  const { data: session } = useSession()
  const { vocab, updateVocabStatus, patchVocabEntry, targetLang, sourceLang, backendToken, showToast } = useCineLang()
  const token = (session as any)?.backendToken ?? backendToken

  const [studying,     setStudying]     = useState(false)
  const [selectedWord, setSelectedWord] = useState<VocabEntry | null>(null)
  const [enriching,    setEnriching]    = useState(false)

  const learningWords = vocab.filter((w) => w.status === 'learning' || w.status === 'new')
  const readyCount    = learningWords.filter((w) => w.status === 'learning').length

  async function changeStatus(word: VocabEntry, status: VocabStatus) {
    updateVocabStatus(word.id, word.word, word.target_lang, status)
    if (selectedWord?.word === word.word) setSelectedWord((p) => p ? { ...p, status } : p)
    if (token && word.id > 0) {
      try { await setVocabStatus(word.id, status, token) } catch {}
    }
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

  if (studying) {
    const deck = learningWords.filter((w) => w.status === 'learning')
    return (
      <StudyMode
        words={deck.length ? deck : learningWords}
        targetLang={targetLang}
        onClose={() => setStudying(false)}
        onGotIt={(w) => changeStatus(w, 'mastered')}
        onKeepLearning={(w) => changeStatus(w, 'learning')}
      />
    )
  }

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 py-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="font-heading font-bold text-warm-900 text-2xl mb-1">Learning List</h1>
          <p className="text-sm text-warm-400">
            {learningWords.length} words queued · {readyCount} in active study
          </p>
        </div>
        <button
          onClick={() => {
            if (!learningWords.length) { showToast('No words in your learning list yet', 'warn'); return }
            setStudying(true)
          }}
          className="btn-primary">
          <Play className="w-4 h-4" /> Start Study Session
        </button>
      </div>

      {learningWords.length === 0 ? (
        <div className="card p-12 text-center">
          <GraduationCap className="w-12 h-12 text-warm-300 mx-auto mb-3" />
          <p className="font-heading font-semibold text-warm-700 text-lg mb-1">Nothing to study yet</p>
          <p className="text-sm text-warm-400">
            Go to the Dashboard, click any word in the vocabulary table, and mark it as "Learning".
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {learningWords.map((word) => (
            <button key={`${word.id}-${word.word}`}
              onClick={() => setSelectedWord(word)}
              className="card-sm p-5 text-left hover:shadow-warm transition-all group active:scale-[.99]">
              <div className="flex items-start justify-between mb-3">
                <PosBadge pos={word.pos} />
                <StatusBadge status={word.status}
                  onClick={(e) => { e?.stopPropagation(); changeStatus(word, STATUS_CYCLE[word.status]) }} />
              </div>
              <p className="font-heading font-bold text-warm-900 text-xl mb-0.5 group-hover:text-cinema-600 transition-colors">
                {word.word}
              </p>
              {word.phonetic && (
                <p className="text-xs text-warm-400 font-mono mb-2">{word.phonetic}</p>
              )}
              {word.translation ? (
                <p className="text-sm text-cinema-600 font-medium">{word.translation}</p>
              ) : (
                <p className="text-xs text-warm-300 italic">Tap to enrich with AI</p>
              )}
              {word.contexts?.[0] && (
                <p className="text-xs text-warm-400 italic mt-3 border-t border-warm-100 pt-3 line-clamp-2">
                  "{word.contexts[0]}"
                </p>
              )}
              <div className="flex items-center justify-between mt-3">
                <span className="text-xs font-mono text-warm-300">×{word.count} seen</span>
                {word.status === 'new' && (
                  <span className="text-[10px] bg-violet-100 text-violet-600 rounded px-1.5 py-0.5 font-mono">NEW</span>
                )}
              </div>
            </button>
          ))}
        </div>
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
