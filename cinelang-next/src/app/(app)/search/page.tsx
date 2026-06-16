'use client'
import SubtitleSearch from '@/components/SubtitleSearch'

export default function SearchPage() {
  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 py-6">
      <div className="mb-6">
        <h1 className="font-heading font-bold text-warm-900 text-2xl mb-1">Find Subtitles</h1>
        <p className="text-sm text-warm-400">Upload an SRT file, paste a URL, or search OpenSubtitles to load subtitles for vocabulary mining.</p>
      </div>
      <SubtitleSearch />
    </div>
  )
}
