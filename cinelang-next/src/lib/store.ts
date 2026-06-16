'use client'
import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { Subtitle, TranslatedSubtitle, VocabEntry, VocabStatus } from './types'

interface Toast { msg: string; type: 'ok' | 'warn' | 'err' }

interface CineLangStore {
  // Language prefs
  sourceLang: string
  targetLang: string
  setSourceLang: (l: string) => void
  setTargetLang: (l: string) => void

  // Backend token (from FastAPI)
  backendToken: string | null
  setBackendToken: (t: string | null) => void

  // Subtitles
  subtitles: Subtitle[]
  translatedSubs: TranslatedSubtitle[]
  allSubtitleLogs: TranslatedSubtitle[]   // accumulated across all loads
  currentSubIdx: number
  setSubtitles: (s: Subtitle[]) => void
  setTranslatedSubs: (s: TranslatedSubtitle[]) => void
  appendSubtitleLogs: (s: TranslatedSubtitle[]) => void
  clearSubtitleLogs: () => void
  setCurrentSubIdx: (i: number) => void

  // Vocabulary (client cache)
  vocab: VocabEntry[]
  setVocab: (v: VocabEntry[]) => void
  mergeVocab: (incoming: VocabEntry[]) => void
  updateVocabStatus: (id: number, word: string, lang: string, status: VocabStatus) => void
  patchVocabEntry: (id: number, patch: Partial<VocabEntry>) => void

  // Toast
  toast: Toast | null
  showToast: (msg: string, type?: Toast['type']) => void
  clearToast: () => void
}

export const useCineLang = create<CineLangStore>()(
  persist(
    (set) => ({
      sourceLang: 'en',
      targetLang: 'fr',
      setSourceLang: (l) => set({ sourceLang: l }),
      setTargetLang: (l) => set({ targetLang: l }),

      backendToken: null,
      setBackendToken: (t) => set({ backendToken: t }),

      subtitles: [],
      translatedSubs: [],
      allSubtitleLogs: [],
      currentSubIdx: 0,
      // Loading new subtitles resets the player but keeps vocab + logs intact
      setSubtitles: (s) => set({ subtitles: s, translatedSubs: [], currentSubIdx: 0 }),
      setTranslatedSubs: (s) => set({ translatedSubs: s, currentSubIdx: 0 }),
      appendSubtitleLogs: (s) =>
        set((state) => {
          const existing = new Set(state.allSubtitleLogs.map((x) => `${x.start}|${x.original ?? x.text}`))
          const fresh = s.filter((x) => !existing.has(`${x.start}|${x.original ?? x.text}`))
          return { allSubtitleLogs: [...state.allSubtitleLogs, ...fresh] }
        }),
      clearSubtitleLogs: () => set({ allSubtitleLogs: [] }),
      setCurrentSubIdx: (i) => set({ currentSubIdx: i }),

      vocab: [],
      setVocab: (v) => set({ vocab: v }),
      mergeVocab: (incoming) =>
        set((state) => {
          const map = new Map(state.vocab.map((w) => [`${w.word}|${w.target_lang}`, w]))
          incoming.forEach((v) => {
            const key = `${v.word}|${v.target_lang}`
            if (!map.has(key)) map.set(key, v)
          })
          return { vocab: Array.from(map.values()) }
        }),
      updateVocabStatus: (id, word, lang, status) =>
        set((state) => ({
          vocab: state.vocab.map((v) =>
            (v.id === id || (v.word === word && v.target_lang === lang)) ? { ...v, status } : v,
          ),
        })),
      patchVocabEntry: (id, patch) =>
        set((state) => ({
          vocab: state.vocab.map((v) => (v.id === id ? { ...v, ...patch } : v)),
        })),

      toast: null,
      showToast: (msg, type = 'ok') => {
        set({ toast: { msg, type } })
        setTimeout(() => set({ toast: null }), 3500)
      },
      clearToast: () => set({ toast: null }),
    }),
    {
      name: 'cinelang-store',
      partialize: (s) => ({
        sourceLang: s.sourceLang,
        targetLang: s.targetLang,
        backendToken: s.backendToken,
      }),
    },
  ),
)
