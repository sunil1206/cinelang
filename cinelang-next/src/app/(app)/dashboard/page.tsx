'use client'
import { useState, useEffect } from 'react'
import { useSession } from 'next-auth/react'
import { useSearchParams } from 'next/navigation'
import useSWR from 'swr'
import { BookOpen, Star, GraduationCap, TrendingUp, Languages, Zap, Loader2, Download } from 'lucide-react'
import SubtitlePlayer from '@/components/SubtitlePlayer'
import VocabTable from '@/components/VocabTable'
import WordModal from '@/components/WordModal'
import { useCineLang } from '@/lib/store'
import { makeFetcher, setVocabStatus, enrichWord, translateSubtitles, ping } from '@/lib/api'
import { STATUS_CYCLE, type VocabEntry, type VocabStatus, langMeta, LANGUAGES } from '@/lib/types'
import clsx from 'clsx'


function MetricCard({ label, value, icon: Icon, color, sub }: { label: string; value: string | number; icon: any; color: string; sub?: string }) {
  const colors: Record<string, string> = {
    cinema: 'bg-cinema-50 text-cinema-600 border-cinema-100',
    amber:  'bg-amber-50  text-amber-600  border-amber-100',
    violet: 'bg-violet-50 text-violet-600 border-violet-100',
    teal:   'bg-teal-50   text-teal-600   border-teal-100',
  }
  const iconColors: Record<string, string> = {
    cinema: 'bg-cinema-100 text-cinema-500',
    amber:  'bg-amber-100  text-amber-500',
    violet: 'bg-violet-100 text-violet-500',
    teal:   'bg-teal-100   text-teal-500',
  }
  return (
    <div className={clsx('card-sm p-5 border', colors[color])}>
      <div className="flex items-start justify-between mb-3">
        <div className={clsx('w-9 h-9 rounded-lg flex items-center justify-center', iconColors[color])}>
          <Icon className="w-4.5 h-4.5" />
        </div>
      </div>
      <p className="text-2xl font-heading font-bold text-warm-900">{value}</p>
      <p className="text-xs font-mono text-warm-500 uppercase tracking-wide mt-0.5">{label}</p>
      {sub && <p className="text-xs text-warm-400 mt-1">{sub}</p>}
    </div>
  )
}

export default function DashboardPage() {
  const { data: session } = useSession()
  const searchParams = useSearchParams()
  const demo = searchParams.get('demo') === '1'

  const {
    backendToken, targetLang, sourceLang, setSourceLang, setTargetLang,
    vocab, setVocab, mergeVocab, updateVocabStatus, patchVocabEntry,
    subtitles, translatedSubs, setTranslatedSubs, allSubtitleLogs, appendSubtitleLogs, clearSubtitleLogs,
    showToast,
  } = useCineLang()

  const token = (session as any)?.backendToken ?? backendToken
  const [selectedWord, setSelectedWord] = useState<VocabEntry | null>(null)
  const [enriching,    setEnriching]    = useState(false)
  const [translating,  setTranslating]  = useState(false)
  const [online,       setOnline]       = useState(false)
  const [tab,          setTab]          = useState<'vocab'|'log'>('vocab')

  // Health check
  useEffect(() => { ping().then(setOnline) }, [])

  // Auto-translate when subtitles are loaded and not yet translated
  useEffect(() => {
    if (subtitles.length > 0 && translatedSubs.length === 0 && !translating) {
      handleTranslate()
    }
  }, [subtitles])

  // Load vocab from server
  const { data: serverVocab } = useSWR<VocabEntry[]>(
    token ? `/api/vocabulary?target_lang=${targetLang}` : null,
    makeFetcher(token),
  )

  useEffect(() => {
    if (serverVocab?.length) mergeVocab(serverVocab)
  }, [serverVocab])

  // Stats
  const total    = vocab.length
  const mastered = vocab.filter((w) => w.status === 'mastered').length
  const learning = vocab.filter((w) => w.status === 'learning').length
  const newW     = total - mastered - learning
  const fluency  = total > 0 ? Math.round((mastered * 100 + learning * 50) / total) : 0

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

  async function handleTranslate() {
    if (!subtitles.length) { showToast('Load subtitles first via the Search page', 'warn'); return }
    setTranslating(true)
    try {
      const res = await translateSubtitles(subtitles, sourceLang, targetLang, token)
      setTranslatedSubs(res.translated)
      appendSubtitleLogs(res.translated)
      mergeVocab(res.vocabulary)
      showToast(`✓ Translated ${res.subtitle_count} frames — ${res.vocab_count} words extracted`)
    } catch (e: any) { showToast(e.message, 'err') }
    finally { setTranslating(false) }
  }

  function exportAnki() {
    const lines = vocab.map((w) =>
      [w.word, w.translation ?? '', w.pos ?? '', w.phonetic ?? '', w.explanation ?? '', (w.contexts ?? []).join(' | ')].join('\t')
    )
    const blob = new Blob(['#separator:tab\n#deck:CineLang\n' + lines.join('\n')], { type: 'text/plain' })
    const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = 'cinelang.txt'; a.click()
  }

  // For the log: prefer accumulated history; fall back to current session raw subs
  const logSubs = allSubtitleLogs.length > 0
    ? allSubtitleLogs
    : subtitles.map((s) => ({ ...s, original: s.text, text: s.text }))

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 py-6 space-y-6">
      {/* Status + language bar */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className={clsx('flex items-center gap-1.5 text-xs font-mono px-3 py-1 rounded-full border',
          online ? 'bg-emerald-50 text-emerald-600 border-emerald-200' : 'bg-amber-50 text-amber-600 border-amber-200')}>
          <span className={clsx('w-1.5 h-1.5 rounded-full', online ? 'bg-emerald-400 animate-pulse-dot' : 'bg-amber-400')} />
          {online ? 'AI connected' : 'Offline — translations echo source'}
        </div>

        {/* Inline language selectors */}
        <div className="flex items-center gap-1.5 text-xs">
          <span className="text-warm-400 font-mono hidden sm:inline">Subtitles:</span>
          <select value={sourceLang} onChange={(e) => setSourceLang(e.target.value)}
            className="select text-xs py-1 pr-6">
            {LANGUAGES.map((l) => <option key={l.code} value={l.code}>{l.flag} {l.label}</option>)}
          </select>
          <span className="text-warm-400">→</span>
          <span className="text-warm-400 font-mono hidden sm:inline">Learning:</span>
          <select value={targetLang} onChange={(e) => setTargetLang(e.target.value)}
            className="select text-xs py-1 pr-6 border-cinema-200">
            {LANGUAGES.filter(l => l.code !== sourceLang).map((l) => (
              <option key={l.code} value={l.code}>{l.flag} {l.label}</option>
            ))}
          </select>
        </div>

        <div className="flex-1" />
        {subtitles.length > 0 && (
          <button onClick={handleTranslate} disabled={translating}
            className="btn-primary text-xs py-1.5 px-3">
            {translating ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Zap className="w-3.5 h-3.5" />}
            {translating ? 'Translating…' : 'Re-translate'}
          </button>
        )}
        <button onClick={exportAnki} className="btn-ghost text-xs py-1.5 px-3">
          <Download className="w-3.5 h-3.5" /> Anki Export
        </button>
      </div>

      {/* Metrics */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <MetricCard label="Mined Words" value={total}     icon={BookOpen}     color="cinema" sub={langMeta(targetLang).label} />
        <MetricCard label="Mastered"    value={mastered}  icon={Star}         color="amber" />
        <MetricCard label="Learning"    value={learning}  icon={GraduationCap}color="violet" />
        <MetricCard label="Fluency"     value={`${fluency}%`} icon={TrendingUp} color="teal" />
      </div>

      {/* Fluency bar */}
      <div className="card-sm p-4">
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs font-mono text-warm-500 uppercase tracking-wide">
            Fluency — {langMeta(targetLang).label}
          </span>
          <span className="text-xs font-mono text-teal-600">{fluency}%</span>
        </div>
        <div className="h-2 bg-warm-200 rounded-full overflow-hidden">
          <div className="h-full bg-teal-500 rounded-full transition-all duration-700" style={{ width: `${fluency}%` }} />
        </div>
        <div className="flex justify-between mt-1.5">
          {['Beginner', 'Intermediate', 'Advanced', 'Fluent'].map((l) => (
            <span key={l} className="text-xs text-warm-300 font-mono">{l}</span>
          ))}
        </div>
        {/* Stacked ratio */}
        {total > 0 && (
          <div className="flex gap-px mt-3 h-1.5 rounded-full overflow-hidden">
            <div className="transition-all" style={{ width: `${mastered/total*100}%`, background: '#f59e0b' }} />
            <div className="transition-all" style={{ width: `${learning/total*100}%`, background: '#10b981' }} />
            <div className="transition-all" style={{ width: `${newW/total*100}%`,    background: '#a78bfa' }} />
          </div>
        )}
        <div className="flex gap-4 mt-2 flex-wrap">
          {[{label:'Mastered',val:mastered,c:'#f59e0b'},{label:'Learning',val:learning,c:'#10b981'},{label:'New',val:newW,c:'#a78bfa'}].map((d)=>(
            <div key={d.label} className="flex items-center gap-1.5 text-xs font-mono">
              <span className="w-2 h-2 rounded-full" style={{background:d.c}} />{d.val} {d.label}
            </div>
          ))}
        </div>
      </div>

      {/* Main grid */}
      <div className="grid grid-cols-1 lg:grid-cols-[340px_1fr] gap-5">
        {/* Left — player */}
        <div className="space-y-4">
          <SubtitlePlayer onWordClick={(w) => { const found = vocab.find((v) => v.word === w); if (found) setSelectedWord(found) }} />
        </div>

        {/* Right — vocab */}
        <div className="space-y-4">
          {/* Tabs */}
          <div className="flex gap-4 border-b border-warm-200">
            {([['vocab','📖 Vocabulary'],['log','🎬 Subtitle Log']] as const).map(([id, label]) => (
              <button key={id} onClick={() => setTab(id)}
                className={clsx('tab', tab === id && 'tab-active')}>{label}</button>
            ))}
          </div>

          {tab === 'vocab' && (
            <VocabTable vocab={vocab} targetLang={targetLang}
              onWordClick={setSelectedWord} onStatusChange={changeStatus} />
          )}

          {tab === 'log' && (
            <div className="card overflow-hidden">
              {logSubs.length > 0 && (
                <div className="px-4 py-2.5 flex items-center justify-between border-b border-warm-100 bg-cream-100">
                  <span className="text-xs font-mono text-warm-500">
                    {logSubs.length} frames · {langMeta(sourceLang).flag}{langMeta(sourceLang).label} → {langMeta(targetLang).flag}{langMeta(targetLang).label}
                  </span>
                  <button onClick={clearSubtitleLogs}
                    className="text-xs text-warm-400 hover:text-red-500 transition-colors">
                    Clear log
                  </button>
                </div>
              )}
              <div className="overflow-x-auto max-h-[520px] overflow-y-auto">
                <table className="w-full text-sm">
                  <thead className="sticky top-0">
                    <tr className="border-b border-warm-200 bg-cream-100 text-warm-500 text-xs font-mono uppercase">
                      <th className="px-4 py-2 text-left w-10">#</th>
                      <th className="px-4 py-2 text-left">Time</th>
                      <th className="px-4 py-2 text-left">{langMeta(sourceLang).flag} Original</th>
                      <th className="px-4 py-2 text-left">{langMeta(targetLang).flag} Translation</th>
                    </tr>
                  </thead>
                  <tbody>
                    {logSubs.length === 0 && (
                      <tr><td colSpan={4} className="px-4 py-8 text-center text-warm-300 text-xs font-mono">
                        No subtitles loaded — go to Search to load an SRT file
                      </td></tr>
                    )}
                    {logSubs.map((s) => {
                      const original = ('original' in s && s.original) ? s.original : s.text
                      const translated = s.text
                      const isTranslated = original !== translated
                      return (
                        <tr key={`${s.index}-${s.start}`} className="border-b border-warm-100 hover:bg-cream-100 transition-all text-xs">
                          <td className="px-4 py-2.5 text-warm-400 font-mono">{s.index}</td>
                          <td className="px-4 py-2.5 text-violet-500 font-mono whitespace-nowrap">{s.start?.slice(0,8)}</td>
                          <td className="px-4 py-2.5 text-warm-600">{original}</td>
                          <td className={clsx('px-4 py-2.5', isTranslated ? 'text-warm-900' : 'text-warm-400 italic')}>
                            {isTranslated ? translated : '—'}
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Word modal */}
      {selectedWord && (
        <WordModal word={selectedWord} targetLang={targetLang} enriching={enriching}
          onClose={() => setSelectedWord(null)}
          onEnrich={handleEnrich}
          onStatusChange={changeStatus} />
      )}
    </div>
  )
}
