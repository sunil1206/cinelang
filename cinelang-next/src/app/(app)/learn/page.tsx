'use client'
import { useState } from 'react'
import { useSession } from 'next-auth/react'
import { GraduationCap, Play, Plus, X, Loader2, Sparkles } from 'lucide-react'
import StudyMode from '@/components/StudyMode'
import WordModal from '@/components/WordModal'
import { PosBadge, StatusBadge } from '@/components/ui/Badge'
import { useCineLang } from '@/lib/store'
import { setVocabStatus, enrichWord, manualAddWord } from '@/lib/api'
import { STATUS_CYCLE, type VocabEntry, type VocabStatus, LANGUAGES } from '@/lib/types'
import clsx from 'clsx'

// ── Add Word Modal ─────────────────────────────────────────────────────────────
function AddWordModal({
  sourceLang, targetLang, token,
  onAdded, onClose,
}: {
  sourceLang: string; targetLang: string; token: string | null
  onAdded: (entry: VocabEntry) => void
  onClose: () => void
}) {
  const [word,        setWord]        = useState('')
  const [translation, setTranslation] = useState('')
  const [phonetic,    setPhonetic]    = useState('')
  const [explanation, setExplanation] = useState('')
  const [enriching,   setEnriching]   = useState(false)
  const [saving,      setSaving]      = useState(false)
  const [error,       setError]       = useState('')

  const srcLabel = LANGUAGES.find(l => l.code === sourceLang)?.label ?? sourceLang
  const tgtLabel = LANGUAGES.find(l => l.code === targetLang)?.label ?? targetLang

  async function handleAutoFill() {
    if (!word.trim()) { setError('Enter a word first'); return }
    if (!token)       { setError('Sign in to use auto-fill'); return }
    setEnriching(true); setError('')
    try {
      const res = await enrichWord(word.trim(), '', sourceLang, targetLang, token)
      if (res.translation)  setTranslation(res.translation)
      if (res.phonetic)     setPhonetic(res.phonetic)
      if (res.explanation)  setExplanation(res.explanation)
    } catch (e: any) {
      setError(e.message || 'Auto-fill failed')
    } finally {
      setEnriching(false)
    }
  }

  async function handleSave() {
    if (!word.trim())        { setError('Word is required'); return }
    if (!translation.trim()) { setError('Translation is required'); return }
    if (!token)              { setError('Sign in to save words'); return }
    setSaving(true); setError('')
    try {
      const res = await manualAddWord(
        word.trim(), translation.trim(),
        sourceLang, targetLang,
        phonetic.trim(), explanation.trim(), token,
      )
      // Set status to 'learning' immediately
      if (res.id > 0) {
        try { await setVocabStatus(res.id, 'learning', token) } catch {}
      }
      onAdded({
        id: res.id, word: res.word,
        source_lang: sourceLang, target_lang: targetLang,
        translation: translation.trim(),
        phonetic: phonetic.trim() || null,
        explanation: explanation.trim() || null,
        status: 'learning',
        pos: null, count: 1, contexts: [], timestamps: [],
      })
    } catch (e: any) {
      setError(e.message || 'Failed to save word')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: 'rgba(30,20,10,0.45)' }}>
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-md p-6 animate-fade-in">
        {/* Header */}
        <div className="flex items-center justify-between mb-5">
          <h2 className="font-heading font-bold text-warm-900 text-lg">Add Word to Learning</h2>
          <button onClick={onClose} className="btn-icon p-1.5"><X className="w-4 h-4" /></button>
        </div>

        <div className="space-y-3">
          {/* Language hint */}
          <p className="text-xs text-warm-400 font-mono">
            {srcLabel} → {tgtLabel}
          </p>

          {/* Word input + auto-fill */}
          <div>
            <label className="block text-xs font-medium text-warm-600 mb-1">Word *</label>
            <div className="flex gap-2">
              <input
                type="text"
                placeholder={`Word in ${srcLabel}`}
                value={word}
                onChange={e => setWord(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && handleAutoFill()}
                className="flex-1 px-3 py-2 rounded-xl border border-warm-200 bg-cream-50 text-warm-900 text-sm placeholder:text-warm-300 focus:outline-none focus:ring-2 focus:ring-cinema-300"
              />
              <button
                onClick={handleAutoFill}
                disabled={enriching || !word.trim()}
                className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-violet-50 border border-violet-200 text-violet-700 text-xs font-medium hover:bg-violet-100 transition-all disabled:opacity-50"
              >
                {enriching
                  ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  : <Sparkles className="w-3.5 h-3.5" />}
                {enriching ? 'Filling…' : 'Auto-fill'}
              </button>
            </div>
          </div>

          {/* Translation */}
          <div>
            <label className="block text-xs font-medium text-warm-600 mb-1">
              Translation * <span className="text-warm-300">(in {tgtLabel})</span>
            </label>
            <input
              type="text"
              placeholder={`Meaning in ${tgtLabel}`}
              value={translation}
              onChange={e => setTranslation(e.target.value)}
              className="w-full px-3 py-2 rounded-xl border border-warm-200 bg-cream-50 text-warm-900 text-sm placeholder:text-warm-300 focus:outline-none focus:ring-2 focus:ring-cinema-300"
            />
          </div>

          {/* Phonetic */}
          <div>
            <label className="block text-xs font-medium text-warm-600 mb-1">Pronunciation <span className="text-warm-300">(IPA, optional)</span></label>
            <input
              type="text"
              placeholder="e.g. /bɔ̃ʒuʁ/"
              value={phonetic}
              onChange={e => setPhonetic(e.target.value)}
              className="w-full px-3 py-2 rounded-xl border border-warm-200 bg-cream-50 text-warm-900 text-sm font-mono placeholder:text-warm-300 focus:outline-none focus:ring-2 focus:ring-cinema-300"
            />
          </div>

          {/* Explanation */}
          <div>
            <label className="block text-xs font-medium text-warm-600 mb-1">Note / Example <span className="text-warm-300">(optional)</span></label>
            <textarea
              rows={2}
              placeholder="Usage note or example sentence…"
              value={explanation}
              onChange={e => setExplanation(e.target.value)}
              className="w-full px-3 py-2 rounded-xl border border-warm-200 bg-cream-50 text-warm-900 text-sm placeholder:text-warm-300 focus:outline-none focus:ring-2 focus:ring-cinema-300 resize-none"
            />
          </div>

          {error && <p className="text-red-500 text-xs px-1">{error}</p>}

          {/* Actions */}
          <div className="flex gap-2 pt-1">
            <button onClick={onClose}
              className="flex-1 py-2.5 rounded-xl border border-warm-200 text-warm-600 text-sm font-medium hover:bg-cream-100 transition-all">
              Cancel
            </button>
            <button
              onClick={handleSave}
              disabled={saving || !word.trim() || !translation.trim()}
              className="flex-1 flex items-center justify-center gap-2 py-2.5 rounded-xl bg-cinema-500 text-white text-sm font-medium hover:bg-cinema-600 transition-all disabled:opacity-50"
            >
              {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
              {saving ? 'Saving…' : 'Add to Learning'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

// ── Learn Page ─────────────────────────────────────────────────────────────────
export default function LearnPage() {
  const { data: session } = useSession()
  const { vocab, updateVocabStatus, patchVocabEntry, mergeVocab, targetLang, sourceLang, backendToken, showToast } = useCineLang()
  const token = (session as any)?.backendToken ?? backendToken

  const [studying,     setStudying]     = useState(false)
  const [selectedWord, setSelectedWord] = useState<VocabEntry | null>(null)
  const [enriching,    setEnriching]    = useState(false)
  const [showAdd,      setShowAdd]      = useState(false)

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

  function handleWordAdded(entry: VocabEntry) {
    mergeVocab([entry])
    setShowAdd(false)
    showToast(`✓ "${entry.word}" added to Learning`)
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
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowAdd(true)}
            className="flex items-center gap-1.5 px-4 py-2 rounded-xl border border-warm-200 bg-white text-warm-700 text-sm font-medium hover:bg-cream-100 transition-all">
            <Plus className="w-4 h-4" /> Add Word
          </button>
          <button
            onClick={() => {
              if (!learningWords.length) { showToast('No words in your learning list yet', 'warn'); return }
              setStudying(true)
            }}
            className="btn-primary">
            <Play className="w-4 h-4" /> Start Study Session
          </button>
        </div>
      </div>

      {learningWords.length === 0 ? (
        <div className="card p-12 text-center">
          <GraduationCap className="w-12 h-12 text-warm-300 mx-auto mb-3" />
          <p className="font-heading font-semibold text-warm-700 text-lg mb-1">Nothing to study yet</p>
          <p className="text-sm text-warm-400 mb-5">
            Add a word manually or mark any vocabulary word as "Learning" from the Dashboard.
          </p>
          <button onClick={() => setShowAdd(true)}
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-cinema-500 text-white text-sm font-medium hover:bg-cinema-600 transition-all">
            <Plus className="w-4 h-4" /> Add Your First Word
          </button>
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
                  onClick={() => changeStatus(word, STATUS_CYCLE[word.status])} />
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

          {/* Inline add card */}
          <button
            onClick={() => setShowAdd(true)}
            className="card-sm p-5 border-2 border-dashed border-warm-200 flex flex-col items-center justify-center gap-2 text-warm-400 hover:border-cinema-300 hover:text-cinema-500 hover:bg-cinema-50/30 transition-all min-h-[140px]">
            <Plus className="w-6 h-6" />
            <span className="text-sm font-medium">Add word</span>
          </button>
        </div>
      )}

      {selectedWord && (
        <WordModal word={selectedWord} targetLang={targetLang} enriching={enriching}
          onClose={() => setSelectedWord(null)}
          onEnrich={handleEnrich}
          onStatusChange={changeStatus} />
      )}

      {showAdd && (
        <AddWordModal
          sourceLang={sourceLang}
          targetLang={targetLang}
          token={token}
          onAdded={handleWordAdded}
          onClose={() => setShowAdd(false)}
        />
      )}
    </div>
  )
}
