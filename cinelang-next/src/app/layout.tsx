import type { Metadata, Viewport } from 'next'
import './globals.css'
import Providers from './providers'

export const metadata: Metadata = {
  title: 'CineLang — Learn Languages Through Cinema',
  description: 'Search real movie subtitles, extract vocabulary, and master new languages with AI-powered flashcards.',
  keywords: ['language learning', 'cinema', 'subtitles', 'vocabulary', 'french', 'german', 'spanish'],
  openGraph: {
    title: 'CineLang',
    description: 'Learn languages through cinema',
    type: 'website',
  },
}

export const viewport: Viewport = {
  themeColor: '#fafaf8',
  width: 'device-width',
  initialScale: 1,
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="h-full">
      <body className="h-full antialiased">
        <Providers>{children}</Providers>
      </body>
    </html>
  )
}
