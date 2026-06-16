'use client'
import { useState, useRef, useEffect, useCallback } from 'react'
import {
  BookOpen, Upload, Loader2, Sparkles, ChevronDown, ChevronUp,
  Volume2, Trash2, FileText, Plus, ArrowLeft, Search, GraduationCap,
} from 'lucide-react'
import { useCineLang } from '@/lib/store'
import { useSession } from 'next-auth/react'
import { LANGUAGES } from '@/lib/types'
import clsx from 'clsx'

// ── Types ────────────────────────────────────────────────────────────────────

interface WordEntry {
  word: string; lemma: string; pos: string; cefr: string
  zipf: number; count: number; example: string
  translation: string; ipa: string; mnemonic: string
}

interface BookOut {
  id: number; title: string; author: string; lang_code: string
  total_words: number; unique_words: number; saved_count: number
  cefr_breakdown: Record<string, number>; created_at: string
}

interface AnalyzeResult {
  book_id: number; title: string; total_words: number; unique_words: number
  cefr_breakdown: Record<string, number>
  vocabulary: WordEntry[]; saved_count: number; lang_code: string
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

const CEFR_DESC: Record<string, string> = {
  A1: 'Beginner', A2: 'Elementary', B1: 'Intermediate', B2: 'Upper-Int', C1: 'Advanced',
}

function speak(word: string, lang: string) {
  if (typeof window === 'undefined' || !window.speechSynthesis) return
  window.speechSynthesis.cancel()
  const u = new SpeechSynthesisUtterance(word)
  u.lang = `${lang}-${lang.toUpperCase()}`
  u.rate = 0.85
  window.speechSynthesis.speak(u)
}

// ── CEFR bar chart ────────────────────────────────────────────────────────────

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

// ── Book card (library sidebar) ───────────────────────────────────────────────

function BookCard({
  book, active, onClick, onDelete,
}: { book: BookOut; active: boolean; onClick: () => void; onDelete: () => void }) {
  const total = Object.values(book.cefr_breakdown).reduce((a, b) => a + b, 0) || 1
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
        <div className={clsx(
          'w-8 h-8 rounded-lg flex items-center justify-center shrink-0',
          active ? 'bg-cinema-500' : 'bg-warm-100',
        )}>
          <BookOpen className={clsx('w-4 h-4', active ? 'text-white' : 'text-warm-500')} />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-warm-900 truncate">{book.title}</p>
          {book.author && <p className="text-xs text-warm-400 truncate">{book.author}</p>}
          <div className="flex gap-2 mt-1 text-[10px] text-warm-500">
            <span>{book.saved_count} words saved</span>
            <span>·</span>
            <span className="uppercase">{book.lang_code}</span>
          </div>
          {/* Mini CEFR dots */}
          <div className="flex gap-0.5 mt-1.5">
            {['A1','A2','B1','B2','C1'].map(lvl => {
              const pct = Math.round(((book.cefr_breakdown[lvl] || 0) / total) * 100)
              return pct > 0 ? (
                <div key={lvl} title={`${lvl}: ${pct}%`}
                  className={clsx('h-1 rounded-full', CEFR_BAR[lvl])}
                  style={{ width: `${Math.max(pct, 4)}%` }}
                />
              ) : null
            })}
          </div>
        </div>
      </div>
      {/* Delete button */}
      <button
        onClick={e => { e.stopPropagation(); onDelete() }}
        className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-red-50 text-warm-300 hover:text-red-500 transition-all"
      >
        <Trash2 className="w-3 h-3" />
      </button>
    </div>
  )
}

// ── Word table row ────────────────────────────────────────────────────────────

function WordRow({ w, lang, idx }: { w: WordEntry; lang: string; idx: number }) {
  const [open, setOpen] = useState(false)
  return (
    <>
      <tr
        onClick={() => setOpen(o => !o)}
        className="cursor-pointer hover:bg-cream-50 transition-colors"
      >
        <td className="px-3 py-2 text-xs text-warm-400 tabular-nums">{idx + 1}</td>
        <td className="px-3 py-2">
          <div className="flex items-center gap-2">
            <button onClick={e => { e.stopPropagation(); speak(w.word, lang) }}
              className="p-1 rounded hover:bg-cinema-50 text-warm-400 hover:text-cinema-500">
              <Volume2 className="w-3 h-3" />
            </button>
            <div>
              <span className="text-sm font-semibold text-warm-900">{w.word}</span>
              {w.ipa && <span className="ml-1.5 text-[11px] text-warm-400 font-mono">{w.ipa}</span>}
            </div>
          </div>
        </td>
        <td className="px-3 py-2 text-sm text-warm-600">{w.translation || '—'}</td>
        <td className="px-3 py-2">
          <span className={clsx('badge text-[10px]', CEFR_COLORS[w.cefr] || 'bg-gray-100 text-gray-600')}>
            {w.cefr}
          </span>
        </td>
        <td className="px-3 py-2 text-xs text-warm-400">{w.pos}</td>
        <td className="px-3 py-2 text-xs text-warm-400 tabular-nums">{w.count}×</td>
        <td className="px-3 py-2">
          {open ? <ChevronUp className="w-3 h-3 text-warm-400" /> : <ChevronDown className="w-3 h-3 text-warm-400" />}
        </td>
      </tr>
      {open && (
        <tr className="bg-cream-50">
          <td />
          <td colSpan={6} className="px-4 pb-3 pt-1">
            {w.example && (
              <p className="text-xs italic text-warm-600 mb-1">
                <span className="font-medium text-warm-900">Example: </span>{w.example}
              </p>
            )}
            {w.mnemonic && (
              <p className="text-xs text-amber-700 bg-amber-50 rounded px-2 py-1">
                💡 {w.mnemonic}
              </p>
            )}
          </td>
        </tr>
      )}
    </>
  )
}

// ── Upload modal ──────────────────────────────────────────────────────────────

function UploadModal({
  onClose, onDone, token, API,
}: { onClose: () => void; onDone: (r: AnalyzeResult) => void; token: string; API: string }) {
  const [mode,     setMode]     = useState<'paste'|'file'>('paste')
  const [text,     setText]     = useState('')
  const [title,    setTitle]    = useState('')
  const [author,   setAuthor]   = useState('')
  const [lang,     setLang]     = useState('fr')
  const [loading,  setLoading]  = useState(false)
  const [error,    setError]    = useState('')
  const fileRef = useRef<HTMLInputElement>(null)

  async function submit() {
    setError(''); setLoading(true)
    try {
      let res: Response
      if (mode === 'paste') {
        res = await fetch(`${API}/api/books/analyze`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
          body: JSON.stringify({ text, title: title || 'Untitled Book', author, lang_code: lang, enrich_top: 50 }),
        })
      } else {
        const file = fileRef.current?.files?.[0]
        if (!file) { setError('Select a file first'); setLoading(false); return }
        const fd = new FormData()
        fd.append('file', file)
        fd.append('title', title || file.name.replace(/\.[^.]+$/, ''))
        fd.append('author', author)
        fd.append('lang_code', lang)
        fd.append('enrich_top', '50')
        res = await fetch(`${API}/api/books/upload`, {
          method: 'POST',
          headers: { Authorization: `Bearer ${token}` },
          body: fd,
        })
      }
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Analysis failed')
      onDone(data)
    } catch (e: any) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg p-6 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-heading font-bold text-warm-900 flex items-center gap-2">
            <BookOpen className="w-5 h-5 text-cinema-500" /> Add Book
          </h2>
          <button onClick={onClose} className="text-warm-400 hover:text-warm-700">✕</button>
        </div>

        {/* Mode tabs */}
        <div className="flex gap-1 bg-cream-100 p-1 rounded-lg">
          {(['paste','file'] as const).map(m => (
            <button key={m} onClick={() => setMode(m)}
              className={clsx('flex-1 py-1.5 rounded-md text-sm font-medium transition-all',
                mode === m ? 'bg-white shadow text-warm-900' : 'text-warm-500 hover:text-warm-700'
              )}>
              {m === 'paste' ? '📋 Paste Text' : '📄 Upload PDF / TXT'}
            </button>
          ))}
        </div>

        {/* Meta fields */}
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="label">Book Title</label>
            <input value={title} onChange={e => setTitle(e.target.value)}
              placeholder="Le Petit Prince" className="input" />
          </div>
          <div>
            <label className="label">Author (optional)</label>
            <input value={author} onChange={e => setAuthor(e.target.value)}
              placeholder="Antoine de Saint-Exupéry" className="input" />
          </div>
        </div>
        <div>
          <label className="label">Book Language</label>
          <select value={lang} onChange={e => setLang(e.target.value)} className="select w-full">
            {LANGUAGES.map(l => <option key={l.code} value={l.code}>{l.flag} {l.label}</option>)}
          </select>
        </div>

        {mode === 'paste' ? (
          <div>
            <label className="label">Paste book text</label>
            <textarea value={text} onChange={e => setText(e.target.value)}
              className="input h-36 resize-none font-mono text-xs"
              placeholder="Paste a chapter or the full text here…" />
          </div>
        ) : (
          <div
            onClick={() => fileRef.current?.click()}
            className="border-2 border-dashed border-warm-200 rounded-xl p-8 text-center cursor-pointer hover:border-cinema-300 hover:bg-cream-50 transition-all"
          >
            <Upload className="w-8 h-8 text-warm-300 mx-auto mb-2" />
            <p className="text-sm text-warm-600">Click to select a <strong>.pdf</strong> or <strong>.txt</strong> file</p>
            <p className="text-xs text-warm-400 mt-1">PDF and plain text supported. Max ~500k characters.</p>
            <input ref={fileRef} type="file" accept=".pdf,.txt" className="hidden"
              onChange={() => {
                const f = fileRef.current?.files?.[0]
                if (f && !title) setTitle(f.name.replace(/\.[^.]+$/, '').replace(/[_-]/g, ' '))
              }}
            />
          </div>
        )}

        {error && (
          <p className="text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">{error}</p>
        )}

        <button onClick={submit} disabled={loading}
          className="btn-primary w-full flex items-center justify-center gap-2">
          {loading ? <><Loader2 className="w-4 h-4 animate-spin" /> Analyzing with AI…</> : <><Sparkles className="w-4 h-4" /> Analyze & Save</>}
        </button>
      </div>
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function BooksPage() {
  const { data: session } = useSession()
  const { backendToken, sourceLang, targetLang } = useCineLang()
  const token = (session as any)?.backendToken ?? backendToken

  const API = process.env.NEXT_PUBLIC_API_URL || ''

  const [books,        setBooks]       = useState<BookOut[]>([])
  const [activeBook,   setActiveBook]  = useState<BookOut | null>(null)
  const [bookVocab,    setBookVocab]   = useState<WordEntry[]>([])
  const [showUpload,   setShowUpload]  = useState(false)
  const [loading,      setLoading]     = useState(false)
  const [vocabLoading, setVocabLoading]= useState(false)
  const [search,       setSearch]      = useState('')
  const [cefrFilter,   setCefrFilter]  = useState('All')
  const [posFilter,    setPosFilter]   = useState('All')
  const [studyQueue,   setStudyQueue]  = useState<any[]>([])
  const [studyIdx,     setStudyIdx]    = useState(0)
  const [showStudy,    setShowStudy]   = useState(false)
  const [studyLoading, setStudyLoading]= useState(false)
  const [flipped,      setFlipped]     = useState(false)

  // Load book library
  const loadBooks = useCallback(async () => {
    if (!token) return
    setLoading(true)
    try {
      const res = await fetch(`${API}/api/books`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (res.ok) setBooks(await res.json())
    } catch { /* ignore */ } finally { setLoading(false) }
  }, [token, API])

  useEffect(() => { loadBooks() }, [loadBooks])

  async function startStudy(book: BookOut) {
    setStudyLoading(true)
    try {
      const res = await fetch(`${API}/api/books/${book.id}/study?limit=20`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (res.ok) {
        const data = await res.json()
        setStudyQueue(data.words || [])
        setStudyIdx(0); setFlipped(false); setShowStudy(true)
      }
    } catch { /* ignore */ } finally { setStudyLoading(false) }
  }

  // Load vocab for selected book
  async function loadBookVocab(book: BookOut) {
    setActiveBook(book)
    setBookVocab([])
    setVocabLoading(true)
    try {
      const res = await fetch(`${API}/api/books/${book.id}/vocab`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (res.ok) setBookVocab(await res.json())
    } catch { /* ignore */ } finally { setVocabLoading(false) }
  }

  async function deleteBook(book: BookOut) {
    if (!confirm(`Delete "${book.title}"? Vocabulary is kept in your learning library.`)) return
    await fetch(`${API}/api/books/${book.id}`, {
      method: 'DELETE', headers: { Authorization: `Bearer ${token}` },
    })
    setBooks(prev => prev.filter(b => b.id !== book.id))
    if (activeBook?.id === book.id) { setActiveBook(null); setBookVocab([]) }
  }

  function onUploadDone(result: AnalyzeResult) {
    setShowUpload(false)
    loadBooks()
    // Auto-select the new book
    const newBook: BookOut = {
      id: result.book_id, title: result.title, author: '',
      lang_code: result.lang_code,
      total_words: result.total_words, unique_words: result.unique_words,
      saved_count: result.saved_count, cefr_breakdown: result.cefr_breakdown,
      created_at: new Date().toISOString(),
    }
    setActiveBook(newBook)
    setBookVocab(result.vocabulary)
  }

  // Filter vocab
  const filtered = bookVocab.filter(w => {
    if (cefrFilter !== 'All' && w.cefr !== cefrFilter) return false
    if (posFilter  !== 'All' && w.pos  !== posFilter)  return false
    if (search && !w.word.includes(search.toLowerCase()) && !w.translation.toLowerCase().includes(search.toLowerCase())) return false
    return true
  })

  const allPos = Array.from(new Set(bookVocab.map(w => w.pos).filter(Boolean)))

  return (
    <div className="flex h-[calc(100vh-56px)] overflow-hidden">
      {/* ── LEFT: Library sidebar ─────────────────────────────── */}
      <aside className="w-72 shrink-0 border-r border-warm-200 bg-cream-50 flex flex-col">
        <div className="p-4 border-b border-warm-200">
          <div className="flex items-center justify-between mb-3">
            <h2 className="font-heading font-bold text-warm-900 flex items-center gap-2 text-sm">
              <BookOpen className="w-4 h-4 text-cinema-500" /> Book Library
            </h2>
            <button
              onClick={() => setShowUpload(true)}
              className="btn-primary py-1 px-2 text-xs flex items-center gap-1"
            >
              <Plus className="w-3 h-3" /> Add
            </button>
          </div>
          <p className="text-[11px] text-warm-400">
            {books.length === 0 ? 'No books yet — add your first!' : `${books.length} book${books.length > 1 ? 's' : ''}`}
          </p>
        </div>

        <div className="flex-1 overflow-y-auto p-3 space-y-2">
          {loading && (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="w-5 h-5 animate-spin text-warm-300" />
            </div>
          )}
          {!loading && books.length === 0 && (
            <div className="text-center py-10 text-warm-400">
              <FileText className="w-8 h-8 mx-auto mb-2 opacity-40" />
              <p className="text-xs">Upload a PDF or paste text to<br />start building your vocabulary.</p>
            </div>
          )}
          {books.map(book => (
            <BookCard
              key={book.id}
              book={book}
              active={activeBook?.id === book.id}
              onClick={() => loadBookVocab(book)}
              onDelete={() => deleteBook(book)}
            />
          ))}
        </div>
      </aside>

      {/* ── RIGHT: Vocabulary view ────────────────────────────── */}
      <main className="flex-1 overflow-y-auto flex flex-col">
        {!activeBook ? (
          /* Empty state */
          <div className="flex-1 flex flex-col items-center justify-center text-center p-8">
            <div className="w-16 h-16 rounded-2xl bg-cinema-50 flex items-center justify-center mb-4">
              <BookOpen className="w-8 h-8 text-cinema-400" />
            </div>
            <h3 className="text-lg font-heading font-bold text-warm-800 mb-2">Book Vocabulary Miner</h3>
            <p className="text-warm-500 text-sm max-w-sm mb-6">
              Upload a PDF or paste text from any French book.
              AI extracts vocabulary, classifies by CEFR level, and saves to your learning library.
            </p>
            <button onClick={() => setShowUpload(true)}
              className="btn-primary flex items-center gap-2">
              <Upload className="w-4 h-4" /> Add your first book
            </button>
          </div>
        ) : (
          <>
            {/* Book header */}
            <div className="p-4 border-b border-warm-200 bg-white">
              <div className="flex items-start gap-3">
                <button onClick={() => setActiveBook(null)} className="btn-ghost p-1 mt-0.5">
                  <ArrowLeft className="w-4 h-4" />
                </button>
                <div className="flex-1">
                  <h1 className="text-lg font-heading font-bold text-warm-900">{activeBook.title}</h1>
                  {activeBook.author && <p className="text-sm text-warm-500">{activeBook.author}</p>}
                  <div className="flex gap-4 mt-2 text-xs text-warm-500">
                    <span>{activeBook.total_words.toLocaleString()} total words</span>
                    <span>{activeBook.unique_words} unique</span>
                    <span className="text-cinema-600 font-medium">{activeBook.saved_count} saved to library</span>
                    <span className="uppercase font-mono">{activeBook.lang_code}</span>
                  </div>
                </div>
                <button
                  onClick={() => startStudy(activeBook)}
                  disabled={studyLoading}
                  className="btn-primary py-1.5 px-3 text-xs flex items-center gap-1.5 shrink-0"
                >
                  {studyLoading
                    ? <Loader2 className="w-3 h-3 animate-spin" />
                    : <GraduationCap className="w-3 h-3" />}
                  Study
                </button>
              </div>
              {/* CEFR bars */}
              <div className="mt-3 max-w-lg">
                <CefrBar breakdown={activeBook.cefr_breakdown} />
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
              <span className="text-xs text-warm-400">{filtered.length} words</span>
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
                      <th className="px-3 py-2">Word</th>
                      <th className="px-3 py-2">Translation</th>
                      <th className="px-3 py-2">Level</th>
                      <th className="px-3 py-2">POS</th>
                      <th className="px-3 py-2">Freq</th>
                      <th className="px-3 py-2 w-6" />
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-warm-100">
                    {filtered.length === 0 && (
                      <tr>
                        <td colSpan={7} className="text-center py-10 text-warm-400 text-sm">
                          No words match the filter.
                        </td>
                      </tr>
                    )}
                    {filtered.map((w, i) => (
                      <WordRow key={w.lemma + i} w={w} lang={activeBook.lang_code} idx={i} />
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}
      </main>

      {/* Upload modal */}
      {showUpload && (
        <UploadModal
          onClose={() => setShowUpload(false)}
          onDone={onUploadDone}
          token={token || ''}
          API={API}
        />
      )}

      {/* Study flashcard modal */}
      {showStudy && studyQueue.length > 0 && (() => {
        const card = studyQueue[studyIdx]
        const done = studyIdx >= studyQueue.length
        return (
          <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4">
            <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md p-6">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h3 className="font-heading font-bold text-warm-900 flex items-center gap-2">
                    <GraduationCap className="w-4 h-4 text-cinema-500" />
                    {activeBook?.title}
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
                  <button onClick={() => { setStudyIdx(0); setFlipped(false) }}
                    className="btn-primary mt-4">Start over</button>
                </div>
              ) : (
                <>
                  <div
                    onClick={() => setFlipped(f => !f)}
                    className="cursor-pointer bg-cream-50 border border-warm-200 rounded-xl p-8 text-center min-h-[160px] flex flex-col items-center justify-center gap-3 hover:border-cinema-300 transition-all"
                  >
                    {!flipped ? (
                      <>
                        <p className="text-3xl font-bold text-warm-900">{card.word}</p>
                        {card.ipa && <p className="text-warm-400 font-mono text-sm">{card.ipa}</p>}
                        <p className="text-xs text-warm-400 mt-2">Tap to reveal</p>
                      </>
                    ) : (
                      <>
                        <p className="text-xl font-semibold text-cinema-600">{card.translation || '—'}</p>
                        {card.example && (
                          <p className="text-xs italic text-warm-500 mt-2 max-w-xs">{card.example}</p>
                        )}
                        {card.definition && (
                          <p className="text-xs text-amber-700 bg-amber-50 rounded px-2 py-1 mt-1">💡 {card.definition}</p>
                        )}
                      </>
                    )}
                  </div>

                  <div className="flex justify-center mt-3">
                    <button onClick={() => speak(card.word, activeBook?.lang_code || 'fr')}
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
    </div>
  )
}
