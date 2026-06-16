'use client'
import { useState, useCallback, useRef } from 'react'
import { Search, Download, Film, Upload, Link2, Loader2, AlertCircle, Languages, Zap } from 'lucide-react'
import { useCineLang } from '@/lib/store'
import { searchSubtitles, downloadSubtitle, parseSRT, translateSubtitles } from '@/lib/api'
import { LANGUAGES, type SubtitleSearchResult } from '@/lib/types'
import clsx from 'clsx'

export default function SubtitleSearch() {
  const {
    backendToken, sourceLang, targetLang,
    setSourceLang, setTargetLang,
    setSubtitles, setTranslatedSubs, appendSubtitleLogs, mergeVocab, showToast,
  } = useCineLang()

  const [query,      setQuery]      = useState('')
  const [searchLang, setSearchLang] = useState(sourceLang)
  const [results,    setResults]    = useState<SubtitleSearchResult[]>([])
  const [searching,  setSearching]  = useState(false)
  const [importing,  setImporting]  = useState<number | null>(null)
  const [urlInput,   setUrlInput]   = useState('')
  const [urlLoading, setUrlLoading] = useState(false)
  const [translating,setTranslating]= useState(false)
  const [error,      setError]      = useState<string | null>(null)
  const [dragOver,   setDragOver]   = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)

  // ── Search OpenSubtitles ──────────────────────────────────────────────────
  async function handleSearch(e: React.FormEvent) {
    e.preventDefault()
    if (!query.trim()) return
    setSearching(true); setError(null); setResults([])
    try {
      const data = await searchSubtitles(query.trim(), searchLang, backendToken)
      setResults(data.results)
      if (!data.results.length) setError('No subtitles found. Try a different title or language.')
    } catch (err: any) {
      setError(err.message?.includes('503') ? 'OpenSubtitles API key not configured in backend.' : err.message)
    } finally { setSearching(false) }
  }

  // ── Import a result ───────────────────────────────────────────────────────
  async function handleImport(r: SubtitleSearchResult) {
    setImporting(r.file_id)
    try {
      const { content, filename } = await downloadSubtitle(r.file_id, backendToken)
      const lang = r.language?.slice(0, 2).toLowerCase() || searchLang
      await loadSRT(content, filename, lang, r.title)
    } catch (err: any) {
      showToast(err.message, 'err')
    } finally { setImporting(null) }
  }

  // ── Core load + auto-translate ────────────────────────────────────────────
  async function loadSRT(content: string, filename: string, subLang?: string, movieTitle?: string) {
    const srcLang = subLang || sourceLang
    if (subLang && subLang !== sourceLang) setSourceLang(subLang)

    const data = await parseSRT(content, backendToken)
    setSubtitles(data.subtitles)
    showToast(`✓ Loaded "${filename}" — ${data.subtitle_count} frames`)

    // Auto-translate if source ≠ target
    if (srcLang !== targetLang) {
      setTranslating(true)
      try {
        const title = movieTitle || filename.replace(/\.[^.]+$/, '').replace(/[._-]/g, ' ').trim()
        const res = await translateSubtitles(data.subtitles, srcLang, targetLang, backendToken, title)
        setTranslatedSubs(res.translated)
        appendSubtitleLogs(res.translated)
        if (res.vocabulary.length) {
          mergeVocab(res.vocabulary)
          showToast(`✨ Translated + ${res.vocab_count} words mined`)
        } else {
          showToast(`✓ Translated (no vocab extracted — add Gemini API key for AI mining)`, 'warn')
        }
      } catch (e: any) {
        showToast('Translation failed: ' + e.message, 'err')
      } finally { setTranslating(false) }
    }
  }

  // ── File upload ───────────────────────────────────────────────────────────
  async function handleFile(file: File | null | undefined) {
    if (!file) return
    if (!file.name.endsWith('.srt')) { showToast('Please upload a .srt file', 'err'); return }
    const content = await file.text()
    await loadSRT(content, file.name)
  }

  // ── URL import ────────────────────────────────────────────────────────────
  async function handleUrl() {
    if (!urlInput.trim()) return
    setUrlLoading(true)
    try {
      const res = await fetch(urlInput.trim())
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const content = await res.text()
      await loadSRT(content, 'subtitle.srt')
      setUrlInput('')
    } catch (err: any) {
      showToast('URL fetch failed: ' + err.message, 'err')
    } finally { setUrlLoading(false) }
  }

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault(); setDragOver(false)
    handleFile(e.dataTransfer.files?.[0])
  }, [sourceLang, targetLang, backendToken])

  const isLoading = translating || urlLoading || searching

  return (
    <div className="max-w-3xl mx-auto space-y-6">

      {/* Language pair selector */}
      <div className="card-sm p-4">
        <div className="flex items-center gap-2 mb-3">
          <Languages className="w-4 h-4 text-cinema-500" />
          <span className="text-sm font-medium text-warm-700">Language Setup</span>
        </div>
        <div className="grid sm:grid-cols-2 gap-3">
          <div>
            <label className="text-xs font-mono text-warm-500 uppercase tracking-wide mb-1 block">
              Subtitle language (source)
            </label>
            <select
              value={sourceLang}
              onChange={(e) => { setSourceLang(e.target.value); setSearchLang(e.target.value) }}
              className="select w-full"
            >
              {LANGUAGES.map((l) => <option key={l.code} value={l.code}>{l.flag} {l.label}</option>)}
            </select>
            <p className="text-xs text-warm-400 mt-1">The language your subtitle file is written in</p>
          </div>
          <div>
            <label className="text-xs font-mono text-warm-500 uppercase tracking-wide mb-1 block">
              Language you&apos;re learning (target)
            </label>
            <select
              value={targetLang}
              onChange={(e) => setTargetLang(e.target.value)}
              className="select w-full border-cinema-200 focus:border-cinema-400"
            >
              {LANGUAGES.filter((l) => l.code !== sourceLang).map((l) => (
                <option key={l.code} value={l.code}>{l.flag} {l.label}</option>
              ))}
            </select>
            <p className="text-xs text-warm-400 mt-1">Vocabulary will be extracted in this language</p>
          </div>
        </div>
        {sourceLang !== targetLang && (
          <div className="mt-3 flex items-center gap-2 px-3 py-2 rounded-lg bg-cinema-50 border border-cinema-100">
            <Zap className="w-3.5 h-3.5 text-cinema-500 shrink-0" />
            <span className="text-xs text-cinema-700">
              Subtitles will be auto-translated from{' '}
              <strong>{LANGUAGES.find(l => l.code === sourceLang)?.label}</strong> →{' '}
              <strong>{LANGUAGES.find(l => l.code === targetLang)?.label}</strong> after loading
            </span>
          </div>
        )}
      </div>

      {/* Upload / URL section */}
      <div className="grid sm:grid-cols-2 gap-4">
        {/* Drag & drop */}
        <div
          onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
          onDragLeave={() => setDragOver(false)}
          onDrop={onDrop}
          onClick={() => fileRef.current?.click()}
          className={clsx(
            'card-sm p-6 flex flex-col items-center justify-center gap-3 cursor-pointer transition-all min-h-36',
            dragOver ? 'border-cinema-400 bg-cinema-50' : 'border-dashed hover:border-cinema-300 hover:bg-cinema-50/40',
            isLoading && 'pointer-events-none opacity-60',
          )}>
          {translating
            ? <><Loader2 className="w-7 h-7 text-cinema-400 animate-spin" /><p className="text-sm text-warm-600">Translating…</p></>
            : <>
                <Upload className="w-7 h-7 text-warm-400" />
                <div className="text-center">
                  <p className="text-sm font-medium text-warm-700">Upload .srt file</p>
                  <p className="text-xs text-warm-400 mt-0.5">Drag & drop or click to browse</p>
                </div>
              </>
          }
          <input ref={fileRef} type="file" accept=".srt" className="hidden"
            onChange={(e) => handleFile(e.target.files?.[0])} />
        </div>

        {/* URL import */}
        <div className="card-sm p-6 flex flex-col gap-3">
          <div className="flex items-center gap-2 text-warm-600">
            <Link2 className="w-4 h-4" />
            <span className="text-sm font-medium">Import from URL</span>
          </div>
          <p className="text-xs text-warm-400">Paste a direct link to any .srt file</p>
          <div className="flex gap-2">
            <input value={urlInput} onChange={(e) => setUrlInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleUrl()}
              placeholder="https://…/subtitle.srt"
              className="input text-xs py-2 flex-1" />
            <button onClick={handleUrl} disabled={urlLoading || !urlInput.trim()} className="btn-primary py-2 px-3">
              {urlLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Download className="w-3.5 h-3.5" />}
            </button>
          </div>
        </div>
      </div>

      {/* OpenSubtitles search */}
      <div className="card p-6 space-y-4">
        <div>
          <h2 className="font-heading font-semibold text-warm-900 mb-1">Search OpenSubtitles</h2>
          <p className="text-xs text-warm-400">Search by movie/series title. Select the subtitle language to search for.</p>
        </div>

        <form onSubmit={handleSearch} className="flex flex-col sm:flex-row gap-2">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-warm-400" />
            <input value={query} onChange={(e) => setQuery(e.target.value)}
              placeholder="Movie or series title…"
              className="input pl-9" />
          </div>
          <select value={searchLang} onChange={(e) => setSearchLang(e.target.value)}
            className="select shrink-0">
            {LANGUAGES.map((l) => (
              <option key={l.code} value={l.code}>{l.flag} {l.label}</option>
            ))}
          </select>
          <button type="submit" disabled={searching || !query.trim()} className="btn-primary shrink-0">
            {searching ? <Loader2 className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
            Search
          </button>
        </form>

        {error && (
          <div className="flex items-start gap-2 p-3 rounded-lg bg-red-50 border border-red-100 text-red-600 text-sm">
            <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
            {error}
          </div>
        )}

        {results.length > 0 && (
          <div className="space-y-2 max-h-[480px] overflow-y-auto -mx-2 px-2">
            {results.map((r) => (
              <div key={r.file_id}
                className="flex items-center gap-4 p-4 rounded-xl border border-warm-200 hover:border-cinema-200 hover:bg-cinema-50/30 transition-all group">
                <div className="w-10 h-10 rounded-lg bg-warm-100 flex items-center justify-center shrink-0">
                  <Film className="w-5 h-5 text-warm-400" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-warm-900 text-sm truncate">
                    {r.title} {r.year ? <span className="text-warm-400 font-normal">({r.year})</span> : null}
                  </p>
                  <div className="flex items-center gap-2 mt-0.5 flex-wrap">
                    <span className="text-xs font-mono text-warm-500 capitalize">{r.language}</span>
                    <span className="w-1 h-1 rounded-full bg-warm-300" />
                    <span className="text-xs text-warm-400">{r.download_count.toLocaleString()} downloads</span>
                    {r.feature_type && (
                      <><span className="w-1 h-1 rounded-full bg-warm-300" />
                      <span className="text-xs text-warm-400 capitalize">{r.feature_type}</span></>
                    )}
                  </div>
                </div>
                <button
                  onClick={() => handleImport(r)}
                  disabled={!!importing}
                  className="btn-primary text-xs py-1.5 px-3 shrink-0 opacity-0 group-hover:opacity-100 transition-opacity">
                  {importing === r.file_id
                    ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    : <><Download className="w-3.5 h-3.5" /> Import</>
                  }
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
