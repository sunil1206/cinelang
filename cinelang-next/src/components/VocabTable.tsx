'use client'
import { useState } from 'react'
import { Search, Volume2, Trash2, ChevronUp, ChevronDown } from 'lucide-react'
import { PosBadge, StatusBadge } from './ui/Badge'
import type { VocabEntry, VocabStatus } from '@/lib/types'
import { STATUS_CYCLE } from '@/lib/types'
import clsx from 'clsx'

function speak(word: string, lang: string) {
  if (typeof window === 'undefined' || !window.speechSynthesis) return
  window.speechSynthesis.cancel()
  const u = new SpeechSynthesisUtterance(word)
  u.lang = lang === 'zh' ? 'zh-CN' : `${lang}-${lang.toUpperCase()}`
  u.rate = 0.85
  window.speechSynthesis.speak(u)
}

type SortKey = 'count' | 'word' | 'status'

interface Props {
  vocab:          VocabEntry[]
  targetLang:     string
  onWordClick:    (w: VocabEntry) => void
  onStatusChange: (w: VocabEntry, status: VocabStatus) => void
  onDelete?:      (w: VocabEntry) => void
}

export default function VocabTable({ vocab, targetLang, onWordClick, onStatusChange, onDelete }: Props) {
  const [query,     setQuery]  = useState('')
  const [posFilter, setPosF]   = useState('All')
  const [stFilter,  setStF]    = useState('All')
  const [sortKey,   setSortK]  = useState<SortKey>('count')
  const [sortAsc,   setSortA]  = useState(false)

  const posOptions = ['All', 'Noun', 'Verb', 'Adjective', 'Adverb', 'Idiom', 'Slang', 'Phrase']
  const stOptions  = ['All', 'new', 'learning', 'mastered']

  function toggleSort(k: SortKey) {
    if (sortKey === k) setSortA((a) => !a)
    else { setSortK(k); setSortA(k === 'word') }
  }

  const filtered = vocab
    .filter((w) => {
      const q = query.toLowerCase()
      return (
        (!q || w.word.includes(q) || (w.translation ?? '').toLowerCase().includes(q)) &&
        (posFilter === 'All' || w.pos === posFilter) &&
        (stFilter  === 'All' || w.status === stFilter)
      )
    })
    .sort((a, b) => {
      let cmp = 0
      if (sortKey === 'count')  cmp = b.count - a.count
      if (sortKey === 'word')   cmp = a.word.localeCompare(b.word)
      if (sortKey === 'status') cmp = a.status.localeCompare(b.status)
      return sortAsc ? -cmp : cmp
    })

  const SortIcon = ({ k }: { k: SortKey }) =>
    sortKey === k
      ? (sortAsc ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />)
      : <ChevronDown className="w-3 h-3 opacity-30" />

  const sel = "select text-xs py-1.5"

  return (
    <div className="space-y-3">
      {/* Filters */}
      <div className="flex flex-wrap gap-2">
        <div className="relative flex-1 min-w-48">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-warm-400" />
          <input value={query} onChange={(e) => setQuery(e.target.value)}
            placeholder="Search words or translations…"
            className="input pl-9 py-2 text-sm" />
        </div>
        <select value={posFilter} onChange={(e) => setPosF(e.target.value)} className={sel}>
          {posOptions.map((p) => <option key={p}>{p}</option>)}
        </select>
        <select value={stFilter} onChange={(e) => setStF(e.target.value)} className={sel}>
          {stOptions.map((s) => <option key={s}>{s}</option>)}
        </select>
      </div>

      <p className="text-xs text-warm-400 font-mono">{filtered.length} words matched</p>

      {/* Table */}
      <div className="card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-warm-200 bg-cream-100 text-warm-500 text-xs font-mono uppercase tracking-wide">
                <th className="px-4 py-3 text-left">
                  <button onClick={() => toggleSort('word')} className="flex items-center gap-1 hover:text-warm-700">
                    Word <SortIcon k="word" />
                  </button>
                </th>
                <th className="px-4 py-3 text-left">Type</th>
                <th className="px-4 py-3 text-left">Translation</th>
                <th className="px-4 py-3 text-center">
                  <button onClick={() => toggleSort('count')} className="flex items-center gap-1 hover:text-warm-700 mx-auto">
                    Freq <SortIcon k="count" />
                  </button>
                </th>
                <th className="px-4 py-3 text-center">
                  <button onClick={() => toggleSort('status')} className="flex items-center gap-1 hover:text-warm-700 mx-auto">
                    Status <SortIcon k="status" />
                  </button>
                </th>
                <th className="px-4 py-3 text-center">TTS</th>
                {onDelete && <th className="px-4 py-3" />}
              </tr>
            </thead>
            <tbody>
              {filtered.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-4 py-10 text-center text-warm-400 text-xs font-mono">
                    No words match your filters
                  </td>
                </tr>
              )}
              {filtered.map((w) => (
                <tr key={`${w.id}-${w.word}`}
                  onClick={() => onWordClick(w)}
                  className="border-b border-warm-100 cursor-pointer hover:bg-cream-100 transition-all group">
                  <td className="px-4 py-3">
                    <span className="font-heading font-semibold text-warm-900">{w.word}</span>
                    {w.phonetic && <span className="block text-xs text-warm-400 font-mono">{w.phonetic}</span>}
                  </td>
                  <td className="px-4 py-3"><PosBadge pos={w.pos} /></td>
                  <td className="px-4 py-3 max-w-48">
                    {w.translation
                      ? <span className="text-cinema-600 font-medium">{w.translation}</span>
                      : <span className="text-warm-300 italic text-xs">Not enriched</span>
                    }
                  </td>
                  <td className="px-4 py-3 text-center">
                    <span className="font-mono text-xs text-warm-400">×{w.count}</span>
                  </td>
                  <td className="px-4 py-3 text-center" onClick={(e) => e.stopPropagation()}>
                    <StatusBadge status={w.status} onClick={() => onStatusChange(w, STATUS_CYCLE[w.status])} />
                  </td>
                  <td className="px-4 py-3 text-center" onClick={(e) => e.stopPropagation()}>
                    <button onClick={() => speak(w.word, targetLang)}
                      className="btn-icon p-1.5 mx-auto opacity-0 group-hover:opacity-100 transition-opacity">
                      <Volume2 className="w-3.5 h-3.5" />
                    </button>
                  </td>
                  {onDelete && (
                    <td className="px-3 py-3 text-center" onClick={(e) => e.stopPropagation()}>
                      <button onClick={() => onDelete(w)}
                        className="btn-icon p-1.5 mx-auto opacity-0 group-hover:opacity-100 text-red-400 hover:text-red-600 hover:border-red-200 transition-all">
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
