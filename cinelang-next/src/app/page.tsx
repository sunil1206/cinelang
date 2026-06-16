'use client'
import { signIn, useSession } from 'next-auth/react'
import { useRouter } from 'next/navigation'
import { useEffect, useState } from 'react'
import { Film, Search, BookOpen, Layers, ArrowRight, Loader2, Eye, EyeOff } from 'lucide-react'

const FEATURES = [
  { icon: Search,   title: 'Search Subtitles',  desc: 'Find subtitles for any movie or series in your target language via OpenSubtitles.' },
  { icon: BookOpen, title: 'Mine Vocabulary',    desc: 'AI automatically extracts, translates, and categorises words worth learning.' },
  { icon: Layers,   title: 'Study & Master',     desc: 'Spaced-repetition flip cards move words from New → Learning → Mastered.' },
]

const FLAGS = ['🇫🇷','🇩🇪','🇪🇸','🇮🇹','🇯🇵','🇰🇷','🇷🇺','🇵🇹','🇨🇳','🇳🇱','🇸🇦','🇵🇱']

type AuthMode = 'login' | 'register'

export default function LandingPage() {
  const { data: session, status } = useSession()
  const router = useRouter()

  const [authMode, setAuthMode]     = useState<AuthMode>('login')
  const [email, setEmail]           = useState('')
  const [password, setPassword]     = useState('')
  const [name, setName]             = useState('')
  const [showPw, setShowPw]         = useState(false)
  const [loading, setLoading]       = useState(false)
  const [error, setError]           = useState('')

  useEffect(() => {
    if (status === 'authenticated') router.push('/dashboard')
  }, [status, router])

  if (status === 'loading') {
    return (
      <div className="min-h-screen bg-cream-100 flex items-center justify-center">
        <Loader2 className="w-6 h-6 animate-spin text-cinema-500" />
      </div>
    )
  }

  async function handleEmailAuth(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    setLoading(true)
    const res = await signIn('credentials', {
      redirect:  false,
      email,
      password,
      mode: authMode,
      name: authMode === 'register' ? name : '',
      callbackUrl: '/dashboard',
    })
    setLoading(false)
    if (res?.error) {
      setError(res.error === 'CredentialsSignin' ? 'Invalid email or password' : res.error)
    } else if (res?.ok) {
      router.push('/dashboard')
    }
  }

  function switchMode(m: AuthMode) {
    setAuthMode(m)
    setError('')
  }

  return (
    <main className="min-h-screen bg-cream-100 flex flex-col">
      {/* Nav */}
      <nav className="px-6 py-4 flex items-center justify-between max-w-6xl mx-auto w-full">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-cinema-500 flex items-center justify-center">
            <Film className="w-4 h-4 text-white" />
          </div>
          <span className="font-heading font-bold text-warm-900 text-lg">
            Cine<span className="text-cinema-500">Lang</span>
          </span>
        </div>
      </nav>

      {/* Hero */}
      <section className="flex-1 flex flex-col items-center justify-center px-6 py-16 text-center">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-cinema-50 border border-cinema-100 text-cinema-600 text-xs font-mono mb-8">
          <span className="w-1.5 h-1.5 rounded-full bg-cinema-400 animate-pulse-dot" />
          Powered by Gemini 2.5 Flash · OpenSubtitles
        </div>

        <h1 className="text-5xl sm:text-6xl md:text-7xl font-heading font-bold text-warm-900 max-w-3xl leading-tight mb-6">
          Learn Languages<br />
          <span className="text-cinema-500 italic">Through Cinema</span>
        </h1>

        <p className="text-warm-500 text-lg max-w-xl mb-10 leading-relaxed">
          Upload or search real movie subtitles, extract vocabulary with AI,
          and study with beautiful flashcards — in any language.
        </p>

        {/* Language flags */}
        <div className="flex flex-wrap gap-3 justify-center mb-12">
          {FLAGS.map((f) => (
            <span key={f} className="text-2xl hover:scale-125 transition-transform cursor-default select-none">{f}</span>
          ))}
        </div>

        {/* Auth card */}
        <div className="card p-8 w-full max-w-sm text-left">
          {/* Tab switcher */}
          <div className="flex rounded-xl bg-cream-100 p-1 mb-6">
            <button
              onClick={() => switchMode('login')}
              className={`flex-1 py-2 rounded-lg text-sm font-medium transition-all ${
                authMode === 'login'
                  ? 'bg-white text-warm-900 shadow-sm'
                  : 'text-warm-500 hover:text-warm-700'
              }`}
            >
              Sign In
            </button>
            <button
              onClick={() => switchMode('register')}
              className={`flex-1 py-2 rounded-lg text-sm font-medium transition-all ${
                authMode === 'register'
                  ? 'bg-white text-warm-900 shadow-sm'
                  : 'text-warm-500 hover:text-warm-700'
              }`}
            >
              Register
            </button>
          </div>

          {/* Email/password form */}
          <form onSubmit={handleEmailAuth} className="space-y-3">
            {authMode === 'register' && (
              <input
                type="text"
                placeholder="Your name"
                value={name}
                onChange={e => setName(e.target.value)}
                required
                className="w-full px-4 py-2.5 rounded-xl border border-warm-200 bg-white text-warm-900 text-sm placeholder:text-warm-400 focus:outline-none focus:ring-2 focus:ring-cinema-300"
              />
            )}
            <input
              type="email"
              placeholder="Email address"
              value={email}
              onChange={e => setEmail(e.target.value)}
              required
              className="w-full px-4 py-2.5 rounded-xl border border-warm-200 bg-white text-warm-900 text-sm placeholder:text-warm-400 focus:outline-none focus:ring-2 focus:ring-cinema-300"
            />
            <div className="relative">
              <input
                type={showPw ? 'text' : 'password'}
                placeholder="Password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                required
                minLength={8}
                className="w-full px-4 py-2.5 pr-10 rounded-xl border border-warm-200 bg-white text-warm-900 text-sm placeholder:text-warm-400 focus:outline-none focus:ring-2 focus:ring-cinema-300"
              />
              <button
                type="button"
                onClick={() => setShowPw(p => !p)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-warm-400 hover:text-warm-600"
              >
                {showPw ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>

            {error && (
              <p className="text-red-500 text-xs px-1">{error}</p>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full flex items-center justify-center gap-2 py-2.5 rounded-xl bg-cinema-500 text-white text-sm font-medium hover:bg-cinema-600 transition-all active:scale-95 disabled:opacity-60"
            >
              {loading
                ? <Loader2 className="w-4 h-4 animate-spin" />
                : authMode === 'login' ? 'Sign In' : 'Create Account'
              }
              {!loading && <ArrowRight className="w-3.5 h-3.5" />}
            </button>
          </form>

          <div className="flex items-center gap-3 my-4">
            <div className="flex-1 h-px bg-warm-200" />
            <span className="text-xs text-warm-400">or</span>
            <div className="flex-1 h-px bg-warm-200" />
          </div>

          {/* Google */}
          <button
            onClick={() => { setLoading(true); signIn('google', { callbackUrl: '/dashboard' }) }}
            disabled={loading}
            className="w-full flex items-center justify-center gap-3 px-5 py-2.5 rounded-xl border border-warm-200 bg-white text-warm-700 font-medium text-sm hover:bg-cream-100 transition-all active:scale-95 disabled:opacity-60 mb-3"
          >
            <svg className="w-4 h-4" viewBox="0 0 24 24">
              <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
              <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
              <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l3.66-2.84z" fill="#FBBC05"/>
              <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
            </svg>
            Continue with Google
          </button>

          {/* Demo */}
          <button
            onClick={() => router.push('/dashboard?demo=1')}
            className="w-full py-2.5 rounded-xl border border-warm-200 text-warm-600 text-sm font-medium hover:bg-cream-100 transition-all active:scale-95"
          >
            🎬 Try Demo Mode
          </button>

          <p className="text-xs text-warm-400 text-center mt-4 leading-relaxed">
            Sign in to save vocabulary across sessions.
          </p>
        </div>
      </section>

      {/* Features */}
      <section className="px-6 py-16 max-w-5xl mx-auto w-full">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-5">
          {FEATURES.map((f) => (
            <div key={f.title} className="card-sm p-6">
              <div className="w-10 h-10 rounded-xl bg-cinema-50 flex items-center justify-center mb-4">
                <f.icon className="w-5 h-5 text-cinema-500" />
              </div>
              <h3 className="font-heading font-semibold text-warm-900 mb-2">{f.title}</h3>
              <p className="text-warm-500 text-sm leading-relaxed">{f.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-warm-200 px-6 py-4 text-center text-xs text-warm-400 font-mono">
        CineLang · Gemini 2.5 Flash · OpenSubtitles API
      </footer>
    </main>
  )
}
