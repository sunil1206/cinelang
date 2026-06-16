export interface User {
  id: number
  email: string
  name: string
  picture?: string | null
}

export interface Subtitle {
  index: number
  start: string
  end: string
  text: string
}

export interface TranslatedSubtitle extends Subtitle {
  original: string
}

export type VocabStatus = 'new' | 'learning' | 'mastered'

export interface VocabEntry {
  id: number
  word: string
  source_lang: string
  target_lang: string
  translation?: string | null
  pos?: string | null
  phonetic?: string | null
  explanation?: string | null
  status: VocabStatus
  count: number
  contexts: string[]
  timestamps: string[]
  created_at?: string | null
  updated_at?: string | null
}

export interface SubtitleSearchResult {
  subtitle_id: string
  title: string
  year: number | null
  language: string
  download_count: number
  file_id: number
  file_name: string
  feature_type: string
  imdb_id?: number | null
  poster?: string | null
}

export interface TranslateResult {
  translated: TranslatedSubtitle[]
  vocabulary: VocabEntry[]
  source_lang: string
  target_lang: string
  subtitle_count: number
  vocab_count: number
}

export interface Language {
  code: string
  label: string
  flag: string
}

export const LANGUAGES: Language[] = [
  { code: 'en', label: 'English',    flag: '🇬🇧' },
  { code: 'fr', label: 'French',     flag: '🇫🇷' },
  { code: 'de', label: 'German',     flag: '🇩🇪' },
  { code: 'es', label: 'Spanish',    flag: '🇪🇸' },
  { code: 'it', label: 'Italian',    flag: '🇮🇹' },
  { code: 'pt', label: 'Portuguese', flag: '🇵🇹' },
  { code: 'ja', label: 'Japanese',   flag: '🇯🇵' },
  { code: 'ko', label: 'Korean',     flag: '🇰🇷' },
  { code: 'zh', label: 'Mandarin',   flag: '🇨🇳' },
  { code: 'ru', label: 'Russian',    flag: '🇷🇺' },
  { code: 'ar', label: 'Arabic',     flag: '🇸🇦' },
  { code: 'nl', label: 'Dutch',      flag: '🇳🇱' },
  { code: 'pl', label: 'Polish',     flag: '🇵🇱' },
  { code: 'sv', label: 'Swedish',    flag: '🇸🇪' },
  { code: 'tr', label: 'Turkish',    flag: '🇹🇷' },
  { code: 'hi', label: 'Hindi',      flag: '🇮🇳' },
]

export function langMeta(code: string): Language {
  return LANGUAGES.find((l) => l.code === code) ?? { code, label: code, flag: '🌐' }
}

export const POS_COLORS: Record<string, string> = {
  Verb:      'bg-violet-100 text-violet-700 border-violet-200',
  Noun:      'bg-teal-100  text-teal-700  border-teal-200',
  Adjective: 'bg-amber-100 text-amber-700 border-amber-200',
  Adverb:    'bg-orange-100 text-orange-700 border-orange-200',
  Idiom:     'bg-cinema-50 text-cinema-600 border-cinema-200',
  Slang:     'bg-pink-100  text-pink-600  border-pink-200',
  Phrase:    'bg-sky-100   text-sky-600   border-sky-200',
}

export const STATUS_META = {
  new:      { label: 'New',      classes: 'bg-warm-100 text-warm-600 border-warm-200' },
  learning: { label: 'Learning', classes: 'bg-emerald-50 text-emerald-700 border-emerald-200' },
  mastered: { label: 'Mastered', classes: 'bg-amber-50  text-amber-700  border-amber-200' },
}

export const STATUS_CYCLE: Record<VocabStatus, VocabStatus> = {
  new: 'learning', learning: 'mastered', mastered: 'new',
}
