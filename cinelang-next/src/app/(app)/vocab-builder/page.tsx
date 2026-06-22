'use client'
import { useState, useRef, useCallback } from 'react'
import {
  Upload, FileText, BookOpen, Search, Loader2, X, Check,
  Pencil, ChevronDown, ChevronUp, Languages, Sparkles, RefreshCw,
} from 'lucide-react'
import { LANGUAGES } from '@/lib/types'
import clsx from 'clsx'

// ── Types ──────────────────────────────────────────────────────────────────────

interface WordItem {
  word:        string
  lemma:       string
  pos:         string
  cefr:        string
  count:       number
  example:     string
  translation: string
  phonetic:    string
  explanation: string
  // local state
  _editing:    boolean
  _draft:      string
  _loading:    boolean
  _saved:      boolean
}

const BASE = process.env.NEXT_PUBLIC_API_URL || ''

// ── Free-dictionary lookup (calls our no-auth backend) ────────────────────────
async function lookupWord(word: string, src: string, tgt: string): Promise<Partial<WordItem>> {
  const res = await fetch(`${BASE}/api/extract/lookup?word=${encodeURIComponent(word)}&source_lang=${src}&target_lang=${tgt}`)
  if (!res.ok) throw new Error('Lookup failed')
  return res.json()
}

// ── POS colour badge ──────────────────────────────────────────────────────────
const POS_CLS: Record<string, string> = {
  Verb:      'bg-violet-100 text-violet-700',
  Noun:      'bg-teal-100 text-teal-700',
  Adjective: 'bg-amber-100 text-amber-700',
  Adverb:    'bg-orange-100 text-orange-700',
}
const CEFR_CLS: Record<string, string> = {
  A1: 'bg-green-100 text-green-700',
  A2: 'bg-emerald-100 text-emerald-700',
  B1: 'bg-sky-100 text-sky-700',
  B2: 'bg-blue-100 text-blue-700',
  C1: 'bg-purple-100 text-purple-700',
}

function PosBadge({ pos }: { pos: string }) {
  return <span className={clsx('text-[10px] font-mono px-1.5 py-0.5 rounded font-medium', POS_CLS[pos] ?? 'bg-warm-100 text-warm-500')}>{pos || '?'}</span>
}
function CefrBadge({ cefr }: { cefr: string }) {
  return <span className={clsx('text-[10px] font-mono px-1.5 py-0.5 rounded font-bold', CEFR_CLS[cefr] ?? 'bg-warm-100 text-warm-500')}>{cefr}</span>
}

// ── Word row component ────────────────────────────────────────────────────────
function WordRow({
  item, index, srcLang, tgtLang,
  onUpdate,
}: {
  item: WordItem; index: number; srcLang: string; tgtLang: string
  onUpdate: (index: number, patch: Partial<WordItem>) => void
}) {
  const [showDetail, setShowDetail] = useState(false)

  async function handleAutoLookup() {
    onUpdate(index, { _loading: true })
    try {
      const result = await lookupWord(item.word, srcLang, tgtLang)
      onUpdate(index, {
        translation: result.translation || item.translation,
        phonetic:    result.phonetic    || item.phonetic,
        explanation: result.explanation || item.explanation,
        pos:         result.pos         || item.pos,
        _loading: false, _saved: true,
      })
    } catch {
      onUpdate(index, { _loading: false })
    }
  }

  function saveManual() {
    onUpdate(index, { translation: item._draft, _editing: false, _saved: true })
  }

  return (
    <div className={clsx(
      'border border-warm-200 rounded-xl bg-white transition-all',
      item._saved && 'border-l-4 border-l-emerald-400',
    )}>
      {/* Main row */}
      <div className="flex items-center gap-3 px-4 py-3">
        {/* Word */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-heading font-bold text-warm-900">{item.word}</span>
            {item.phonetic && <span className="text-xs text-warm-400 font-mono">{item.phonetic}</span>}
            <PosBadge pos={item.pos} />
            <CefrBadge cefr={item.cefr} />
            {item.count > 1 && <span className="text-[10px] text-warm-300 font-mono">×{item.count}</span>}
          </div>
        </div>

        {/* Translation / edit */}
        <div className="w-48 shrink-0">
          {item._editing ? (
            <div className="flex items-center gap-1">
              <input
                autoFocus
                value={item._draft}
                onChange={e => onUpdate(index, { _draft: e.target.value })}
                onKeyDown={e => { if (e.key === 'Enter') saveManual(); if (e.key === 'Escape') onUpdate(index, { _editing: false, _draft: item.translation }) }}
                placeholder="Type translation…"
                className="flex-1 text-sm px-2 py-1 rounded-lg border border-cinema-300 focus:outline-none focus:ring-2 focus:ring-cinema-300 min-w-0"
              />
              <button onClick={saveManual} className="text-emerald-600 hover:text-emerald-700"><Check className="w-3.5 h-3.5" /></button>
              <button onClick={() => onUpdate(index, { _editing: false, _draft: item.translation })} className="text-warm-400"><X className="w-3.5 h-3.5" /></button>
            </div>
          ) : (
            <div className="flex items-center gap-1 group">
              <span className={clsx('text-sm flex-1 truncate', item.translation ? 'text-cinema-600 font-medium' : 'text-warm-300 italic')}>
                {item.translation || 'No meaning yet'}
              </span>
              <button
                onClick={() => onUpdate(index, { _editing: true, _draft: item.translation })}
                className="opacity-0 group-hover:opacity-100 text-warm-400 hover:text-cinema-500 transition-opacity"
              >
                <Pencil className="w-3 h-3" />
              </button>
            </div>
          )}
        </div>

        {/* Actions */}
        <div className="flex items-center gap-1 shrink-0">
          <button
            onClick={handleAutoLookup}
            disabled={item._loading}
            title="Auto-lookup meaning (free dictionary)"
            className="flex items-center gap-1 px-2 py-1 rounded-lg bg-violet-50 border border-violet-200 text-violet-700 text-xs hover:bg-violet-100 transition-all disabled:opacity-50"
          >
            {item._loading
              ? <Loader2 className="w-3 h-3 animate-spin" />
              : <Sparkles className="w-3 h-3" />}
            {item._loading ? '' : 'Lookup'}
          </button>
          <button
            onClick={() => setShowDetail(d => !d)}
            className="p-1 text-warm-400 hover:text-warm-700"
          >
            {showDetail ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </button>
        </div>
      </div>

      {/* Expandable detail */}
      {showDetail && (
        <div className="px-4 pb-4 pt-0 space-y-2 border-t border-warm-100">
          {item.explanation && (
            <p className="text-xs text-warm-600 leading-relaxed">{item.explanation}</p>
          )}
          {item.example && (
            <p className="text-xs text-warm-400 italic">"{item.example}"</p>
          )}
          {/* Manual explanation */}
          <div>
            <label className="text-[10px] font-medium text-warm-500 uppercase tracking-wide">Note / Example</label>
            <textarea
              rows={2}
              value={item.explanation}
              onChange={e => onUpdate(index, { explanation: e.target.value })}
              placeholder="Add your own note or example sentence…"
              className="w-full mt-1 text-xs px-2 py-1.5 rounded-lg border border-warm-200 focus:outline-none focus:ring-2 focus:ring-cinema-300 resize-none bg-cream-50"
            />
          </div>
        </div>
      )}
    </div>
  )
}

// ── Main Page ─────────────────────────────────────────────────────────────────
type InputMode = 'srt' | 'pdf' | 'text'
type FilterMode = 'all' | 'missing' | 'done'

export default function VocabBuilderPage() {
  const [srcLang,   setSrcLang]   = useState('fr')
  const [tgtLang,   setTgtLang]   = useState('en')
  const [mode,      setMode]      = useState<InputMode>('srt')
  const [rawText,   setRawText]   = useState('')
  const [loading,   setLoading]   = useState(false)
  const [error,     setError]     = useState('')
  const [words,     setWords]     = useState<WordItem[]>([])
  const [filter,    setFilter]    = useState<FilterMode>('all')
  const [search,    setSearch]    = useState('')
  const [lookingAll, setLookingAll] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)

  function updateWord(index: number, patch: Partial<WordItem>) {
    setWords(prev => prev.map((w, i) => i === index ? { ...w, ...patch } : w))
  }

  function toWordItems(raw: any[]): WordItem[] {
    return raw.map(w => ({
      ...w,
      _editing: false,
      _draft:   w.translation || '',
      _loading: false,
      _saved:   !!w.translation,
    }))
  }

  async function handleSRTSubmit() {
    if (!rawText.trim()) { setError('Paste SRT content first'); return }
    setLoading(true); setError('')
    try {
      const res = await fetch(`${BASE}/api/extract/srt`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: rawText, source_lang: srcLang, target_lang: tgtLang }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data?.detail || 'Extraction failed')
      setWords(toWordItems(data.words))
    } catch (e: any) {
      setError(e.message)
    } finally { setLoading(false) }
  }

  async function handleTextSubmit() {
    if (!rawText.trim()) { setError('Enter some text first'); return }
    setLoading(true); setError('')
    try {
      const res = await fetch(`${BASE}/api/extract/text`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: rawText, source_lang: srcLang, target_lang: tgtLang }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data?.detail || 'Extraction failed')
      setWords(toWordItems(data.words))
    } catch (e: any) {
      setError(e.message)
    } finally { setLoading(false) }
  }

  async function handlePDFUpload(file: File) {
    setLoading(true); setError('')
    const form = new FormData()
    form.append('file', file)
    try {
      const res = await fetch(`${BASE}/api/extract/pdf?source_lang=${srcLang}&target_lang=${tgtLang}`, {
        method: 'POST',
        body: form,
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data?.detail || 'PDF extraction failed')
      setWords(toWordItems(data.words))
    } catch (e: any) {
      setError(e.message)
    } finally { setLoading(false) }
  }

  async function lookupAll() {
    const missing = words.map((w, i) => ({ w, i })).filter(({ w }) => !w.translation)
    if (!missing.length) return
    setLookingAll(true)
    for (const { w, i } of missing) {
      updateWord(i, { _loading: true })
      try {
        const result = await lookupWord(w.word, srcLang, tgtLang)
        updateWord(i, {
          translation: result.translation || '',
          phonetic:    result.phonetic    || '',
          explanation: result.explanation || '',
          _loading: false, _saved: !!result.translation,
        })
      } catch {
        updateWord(i, { _loading: false })
      }
      await new Promise(r => setTimeout(r, 250)) // polite rate limit
    }
    setLookingAll(false)
  }

  function exportCSV() {
    const rows = [['Word', 'Translation', 'Phonetic', 'POS', 'CEFR', 'Example', 'Note']]
    words.forEach(w => rows.push([w.word, w.translation, w.phonetic, w.pos, w.cefr, w.example, w.explanation]))
    const csv = rows.map(r => r.map(c => `"${(c || '').replace(/"/g, '""')}"`).join(',')).join('\n')
    const a = document.createElement('a')
    a.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv' }))
    a.download = 'vocabulary.csv'
    a.click()
  }

  const filtered = words.filter(w => {
    if (filter === 'missing' && w.translation) return false
    if (filter === 'done'    && !w.translation) return false
    if (search && !w.word.toLowerCase().includes(search.toLowerCase()) && !(w.translation ?? '').toLowerCase().includes(search.toLowerCase())) return false
    return true
  })

  const doneCount    = words.filter(w => w.translation).length
  const missingCount = words.length - doneCount

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 py-6 space-y-6">
      {/* Header */}
      <div>
        <h1 className="font-heading font-bold text-warm-900 text-2xl mb-1">Vocabulary Builder</h1>
        <p className="text-sm text-warm-400">Upload SRT subtitles or a PDF book — no login needed. NLP extracts words, dictionary fills meanings.</p>
      </div>

      {/* Input section */}
      <div className="card p-5 space-y-4">
        {/* Language pair */}
        <div className="flex items-center gap-3 flex-wrap">
          <div className="flex items-center gap-2">
            <Languages className="w-4 h-4 text-warm-400" />
            <select value={srcLang} onChange={e => setSrcLang(e.target.value)}
              className="text-sm px-3 py-1.5 rounded-xl border border-warm-200 bg-cream-50 text-warm-900 focus:outline-none focus:ring-2 focus:ring-cinema-300">
              {LANGUAGES.map(l => <option key={l.code} value={l.code}>{l.flag} {l.label}</option>)}
            </select>
            <span className="text-warm-400 text-sm">→</span>
            <select value={tgtLang} onChange={e => setTgtLang(e.target.value)}
              className="text-sm px-3 py-1.5 rounded-xl border border-warm-200 bg-cream-50 text-warm-900 focus:outline-none focus:ring-2 focus:ring-cinema-300">
              {LANGUAGES.map(l => <option key={l.code} value={l.code}>{l.flag} {l.label}</option>)}
            </select>
          </div>
        </div>

        {/* Mode tabs */}
        <div className="flex rounded-xl bg-cream-100 p-1 gap-1 w-fit">
          {([['srt', FileText, 'SRT File'], ['pdf', BookOpen, 'PDF Book'], ['text', FileText, 'Plain Text']] as const).map(([m, Icon, label]) => (
            <button key={m} onClick={() => { setMode(m); setRawText(''); setError('') }}
              className={clsx('flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-all',
                mode === m ? 'bg-white text-warm-900 shadow-sm' : 'text-warm-500 hover:text-warm-700')}>
              <Icon className="w-3.5 h-3.5" /> {label}
            </button>
          ))}
        </div>

        {/* Input area */}
        {mode === 'pdf' ? (
          <div
            onClick={() => fileRef.current?.click()}
            onDragOver={e => e.preventDefault()}
            onDrop={e => { e.preventDefault(); const f = e.dataTransfer.files[0]; if (f) handlePDFUpload(f) }}
            className="border-2 border-dashed border-warm-200 rounded-xl p-10 text-center cursor-pointer hover:border-cinema-300 hover:bg-cinema-50/20 transition-all">
            {loading
              ? <Loader2 className="w-8 h-8 text-cinema-500 animate-spin mx-auto mb-2" />
              : <Upload className="w-8 h-8 text-warm-300 mx-auto mb-2" />}
            <p className="text-sm font-medium text-warm-700">{loading ? 'Extracting vocabulary…' : 'Drop PDF here or click to browse'}</p>
            <p className="text-xs text-warm-400 mt-1">Max 20 MB · up to 80 pages</p>
            <input ref={fileRef} type="file" accept=".pdf" className="hidden"
              onChange={e => { const f = e.target.files?.[0]; if (f) handlePDFUpload(f) }} />
          </div>
        ) : (
          <div className="space-y-2">
            <textarea
              rows={6}
              value={rawText}
              onChange={e => setRawText(e.target.value)}
              placeholder={mode === 'srt'
                ? '1\n00:00:01,000 --> 00:00:03,000\nBonjour, comment ça va?\n\n2\n00:00:04,000 → 00:00:06,000\nJe suis très heureux…'
                : 'Paste your text here…'}
              className="w-full px-3 py-2.5 rounded-xl border border-warm-200 bg-cream-50 text-warm-900 text-sm font-mono placeholder:text-warm-300 focus:outline-none focus:ring-2 focus:ring-cinema-300 resize-none"
            />
            {error && <p className="text-red-500 text-xs">{error}</p>}
            <button
              onClick={mode === 'srt' ? handleSRTSubmit : handleTextSubmit}
              disabled={loading || !rawText.trim()}
              className="btn-primary w-full justify-center">
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
              {loading ? 'Extracting with NLP…' : 'Extract Vocabulary'}
            </button>
          </div>
        )}
      </div>

      {/* Results */}
      {words.length > 0 && (
        <div className="space-y-4">
          {/* Stats + actions bar */}
          <div className="flex items-center justify-between flex-wrap gap-3">
            <div className="flex items-center gap-3">
              <span className="text-sm font-medium text-warm-700">{words.length} words extracted</span>
              <span className="text-xs text-emerald-600 font-mono">{doneCount} with meaning</span>
              {missingCount > 0 && <span className="text-xs text-warm-400 font-mono">{missingCount} missing</span>}
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={lookupAll}
                disabled={lookingAll || missingCount === 0}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-violet-50 border border-violet-200 text-violet-700 text-xs font-medium hover:bg-violet-100 transition-all disabled:opacity-50">
                {lookingAll ? <Loader2 className="w-3 h-3 animate-spin" /> : <RefreshCw className="w-3 h-3" />}
                {lookingAll ? 'Looking up…' : `Auto-lookup all (${missingCount})`}
              </button>
              <button onClick={exportCSV}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-warm-200 text-warm-600 text-xs font-medium hover:bg-cream-100 transition-all">
                Export CSV
              </button>
            </div>
          </div>

          {/* Filter + search */}
          <div className="flex items-center gap-2 flex-wrap">
            <div className="flex rounded-xl bg-cream-100 p-0.5 gap-0.5">
              {(['all', 'missing', 'done'] as FilterMode[]).map(f => (
                <button key={f} onClick={() => setFilter(f)}
                  className={clsx('px-3 py-1 rounded-lg text-xs font-medium capitalize transition-all',
                    filter === f ? 'bg-white text-warm-900 shadow-sm' : 'text-warm-500 hover:text-warm-700')}>
                  {f === 'all' ? `All (${words.length})` : f === 'missing' ? `Missing (${missingCount})` : `Done (${doneCount})`}
                </button>
              ))}
            </div>
            <div className="flex items-center gap-2 flex-1 min-w-[160px]">
              <Search className="w-3.5 h-3.5 text-warm-400 shrink-0" />
              <input
                type="text"
                placeholder="Search words…"
                value={search}
                onChange={e => setSearch(e.target.value)}
                className="flex-1 text-sm py-1 bg-transparent border-b border-warm-200 focus:outline-none focus:border-cinema-400 placeholder:text-warm-300"
              />
            </div>
          </div>

          {/* Word list */}
          <div className="space-y-2">
            {filtered.map((item, i) => {
              const realIdx = words.indexOf(item)
              return (
                <WordRow
                  key={`${item.word}-${realIdx}`}
                  item={item}
                  index={realIdx}
                  srcLang={srcLang}
                  tgtLang={tgtLang}
                  onUpdate={updateWord}
                />
              )
            })}
            {filtered.length === 0 && (
              <p className="text-center text-warm-400 text-sm py-8">No words match your filter.</p>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
