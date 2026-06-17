import type { VocabEntry, VocabStatus } from './types'

// In development Next.js proxies /api/* to FastAPI via next.config.mjs rewrites,
// so we use the same origin (empty string). In production NEXT_PUBLIC_API_URL is
// the full domain and Nginx routes /api/ to FastAPI.
const BASE = process.env.NEXT_PUBLIC_API_URL || ''

function headers(token?: string | null): HeadersInit {
  const h: HeadersInit = { 'Content-Type': 'application/json' }
  if (token) (h as Record<string, string>)['Authorization'] = `Bearer ${token}`
  return h
}

async function handle<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let msg = `HTTP ${res.status}`
    try {
      const body = await res.json()
      msg = body?.error?.message || body?.detail || msg
    } catch {}
    throw new Error(msg)
  }
  return res.json() as Promise<T>
}

// ── Health ─────────────────────────────────────────────────────────────────────
export async function ping(): Promise<boolean> {
  try {
    const res = await fetch(`${BASE}/api/health`, { signal: AbortSignal.timeout(2500) })
    return res.ok
  } catch {
    return false
  }
}

// ── Auth ───────────────────────────────────────────────────────────────────────
// Called by NextAuth jwt callback (server-side) — exchanges Google id_token for CineLang tokens
export async function loginWithGoogle(idToken: string) {
  const res = await fetch(`${BASE}/api/auth/google`, {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify({ id_token: idToken }),
  })
  return handle<{
    tokens: { access_token: string; refresh_token: string; expires_in: number }
    user: { id: number; email: string; name: string; picture?: string }
  }>(res)
}

export async function refreshToken(refreshToken: string) {
  const res = await fetch(`${BASE}/api/auth/refresh`, {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify({ refresh_token: refreshToken }),
  })
  return handle<{
    tokens: { access_token: string; refresh_token: string; expires_in: number }
    user: { id: number; email: string; name: string; picture?: string }
  }>(res)
}

// ── SRT parsing ────────────────────────────────────────────────────────────────
export async function parseSRT(content: string, token?: string | null) {
  const res = await fetch(`${BASE}/api/subtitles/parse`, {
    method: 'POST',
    headers: headers(token),
    body: JSON.stringify({ content }),
  })
  return handle<{ subtitle_count: number; subtitles: { index: number; start: string; end: string; text: string }[] }>(res)
}

// ── Language detection ─────────────────────────────────────────────────────────
export async function detectLanguage(content: string, token?: string | null) {
  const res = await fetch(`${BASE}/api/subtitles/detect-language`, {
    method: 'POST',
    headers: headers(token),
    body: JSON.stringify({ content }),
  })
  return handle<{ language_code: string; language_name: string; confidence: number }>(res)
}

// ── Translation ────────────────────────────────────────────────────────────────
export async function translateSubtitles(
  subtitles: object[],
  source_lang: string,
  target_lang: string,
  token?: string | null,
  movie_title?: string,
) {
  const res = await fetch(`${BASE}/api/translations`, {
    method: 'POST',
    headers: headers(token),
    body: JSON.stringify({ subtitles, source_lang, target_lang, movie_title: movie_title || '' }),
  })
  return handle<{
    translated: { index: number; start: string; end: string; original: string; text: string }[]
    vocabulary: VocabEntry[]
    source_lang: string
    target_lang: string
    subtitle_count: number
    vocab_count: number
  }>(res)
}

// ── OpenSubtitles ──────────────────────────────────────────────────────────────
export async function searchSubtitles(query: string, language: string, token?: string | null) {
  const res = await fetch(`${BASE}/api/subtitles/search`, {
    method: 'POST',
    headers: headers(token),
    body: JSON.stringify({ query, language }),
  })
  return handle<{ results: import('./types').SubtitleSearchResult[]; total_pages: number; mock: boolean }>(res)
}

export async function downloadSubtitle(file_id: number, token?: string | null) {
  const res = await fetch(`${BASE}/api/subtitles/download`, {
    method: 'POST',
    headers: headers(token),
    body: JSON.stringify({ file_id }),
  })
  return handle<{ content: string; filename: string; mock: boolean }>(res)
}

// ── Vocabulary CRUD ────────────────────────────────────────────────────────────
export async function getVocabulary(target_lang: string, token: string) {
  const res = await fetch(`${BASE}/api/vocabulary?target_lang=${target_lang}`, { headers: headers(token) })
  return handle<VocabEntry[]>(res)
}

export async function setVocabStatus(id: number, status: VocabStatus, token: string) {
  const res = await fetch(`${BASE}/api/vocabulary/${id}/status`, {
    method: 'PATCH',
    headers: headers(token),
    body: JSON.stringify({ status }),
  })
  return handle<{ id: number; status: string }>(res)
}

export async function enrichWord(
  word: string,
  sentence: string,
  source_lang: string,
  target_lang: string,
  token: string,
) {
  const res = await fetch(`${BASE}/api/vocabulary/enrich`, {
    method: 'POST',
    headers: headers(token),
    body: JSON.stringify({ word, sentence, source_lang, target_lang }),
  })
  return handle<{
    translation: string; pos: string; phonetic: string;
    explanation: string; sentence_translation: string
  }>(res)
}

export async function manualAddWord(
  word: string,
  translation: string,
  source_lang: string,
  target_lang: string,
  phonetic: string,
  explanation: string,
  token: string,
) {
  const res = await fetch(`${BASE}/api/vocabulary/manual-add`, {
    method: 'POST',
    headers: headers(token),
    body: JSON.stringify({ word, translation, source_lang, target_lang, phonetic, explanation }),
  })
  return handle<{ id: number; word: string; translation: string; status: string }>(res)
}

export async function deleteVocab(id: number, token: string) {
  const res = await fetch(`${BASE}/api/vocabulary/${id}`, {
    method: 'DELETE',
    headers: headers(token),
  })
  if (res.status === 204) return { deleted: true }
  return handle<{ deleted: boolean }>(res)
}

// ── SWR fetcher ────────────────────────────────────────────────────────────────
export function makeFetcher(token?: string | null) {
  return (url: string) =>
    fetch(url.startsWith('http') ? url : `${BASE}${url}`, { headers: headers(token) }).then(async (r) => {
      if (!r.ok) {
        let msg = `HTTP ${r.status}`
        try { const b = await r.json(); msg = b?.error?.message || msg } catch {}
        throw new Error(msg)
      }
      return r.json()
    })
}
