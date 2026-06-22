'use client'
import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { signOut } from 'next-auth/react'
import Image from 'next/image'
import {
  Film, Search, LayoutDashboard, BookMarked, Trophy, LogOut,
  ChevronDown, BookOpen, Clapperboard, Layers, Brain,
  GalleryVertical, Menu, X,
} from 'lucide-react'
import { useCineLang } from '@/lib/store'
import { LANGUAGES } from '@/lib/types'
import { useState } from 'react'
import type { Session } from 'next-auth'
import clsx from 'clsx'

const NAV = [
  { href: '/dashboard',    label: 'Dashboard',  icon: LayoutDashboard },
  { href: '/search',       label: 'Films',      icon: Search },
  { href: '/cinema',       label: 'Cinema',     icon: Clapperboard },
  { href: '/books',        label: 'Books',      icon: BookOpen },
  { href: '/learn',        label: 'Learning',   icon: BookMarked },
  { href: '/vocab-builder',label: 'Builder',    icon: Layers },
  { href: '/flashcards',   label: 'Flashcards', icon: GalleryVertical },
  { href: '/quiz',         label: 'Quiz',       icon: Brain },
  { href: '/mastered',     label: 'Mastered',   icon: Trophy },
]

export default function Header({ demo, session }: { demo: boolean; session: Session | null }) {
  const pathname = usePathname()
  const router   = useRouter()
  const { sourceLang, targetLang, setSourceLang, setTargetLang } = useCineLang()
  const [userOpen,   setUserOpen]   = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)

  const user   = session?.user
  const avatar = user?.image

  return (
    <>
      <header className="bg-white/90 backdrop-blur border-b border-warm-200 sticky top-0 z-30">
        <div className="max-w-7xl mx-auto px-4 sm:px-6">
          <div className="flex items-center h-14 gap-3">

            {/* Hamburger — mobile only */}
            <button
              onClick={() => setMobileOpen(o => !o)}
              className="md:hidden p-2 rounded-lg text-warm-600 hover:bg-cream-200 transition-all"
              aria-label="Menu"
            >
              {mobileOpen ? <X size={20} /> : <Menu size={20} />}
            </button>

            {/* Logo */}
            <Link href="/dashboard" className="flex items-center gap-2 shrink-0">
              <div className="w-7 h-7 rounded-lg bg-cinema-500 flex items-center justify-center">
                <Film className="w-3.5 h-3.5 text-white" />
              </div>
              <span className="font-heading font-bold text-warm-900 text-base">
                Cine<span className="text-cinema-500">Lang</span>
              </span>
            </Link>

            {/* Nav — desktop */}
            <nav className="hidden md:flex items-center gap-0.5 ml-2 flex-wrap">
              {NAV.map((n) => {
                const active = pathname === n.href
                return (
                  <Link key={n.href} href={n.href}
                    className={clsx(
                      'flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium transition-all',
                      active ? 'bg-cinema-50 text-cinema-600' : 'text-warm-600 hover:bg-cream-200 hover:text-warm-900',
                    )}>
                    <n.icon className="w-3.5 h-3.5" />
                    {n.label}
                  </Link>
                )
              })}
            </nav>

            <div className="flex-1" />

            {/* Language selectors */}
            <div className="flex items-center gap-1.5 text-sm">
              <select value={sourceLang} onChange={e => setSourceLang(e.target.value)}
                className="select text-xs py-1.5 pr-7 max-w-[90px]">
                {LANGUAGES.map(l => <option key={l.code} value={l.code}>{l.flag} {l.label}</option>)}
              </select>
              <span className="text-warm-400 text-xs font-mono">→</span>
              <select value={targetLang} onChange={e => setTargetLang(e.target.value)}
                className="select text-xs py-1.5 pr-7 border-cinema-200 focus:border-cinema-400 max-w-[90px]">
                {LANGUAGES.filter(l => l.code !== sourceLang).map(l => (
                  <option key={l.code} value={l.code}>{l.flag} {l.label}</option>
                ))}
              </select>
            </div>

            {demo && (
              <span className="badge bg-amber-50 text-amber-700 border-amber-200 text-xs shrink-0 hidden sm:inline">Demo</span>
            )}

            {/* User menu */}
            {user ? (
              <div className="relative">
                <button onClick={() => setUserOpen(p => !p)}
                  className="flex items-center gap-2 px-2 py-1 rounded-lg hover:bg-cream-200 transition-all">
                  {avatar
                    ? <Image src={avatar} alt="" width={28} height={28} className="rounded-full" />
                    : <div className="w-7 h-7 rounded-full bg-cinema-500 flex items-center justify-center text-white text-xs font-bold">
                        {user.name?.[0]}
                      </div>
                  }
                  <ChevronDown className="w-3 h-3 text-warm-400 hidden sm:block" />
                </button>
                {userOpen && (
                  <div className="absolute right-0 top-full mt-1 w-48 card-sm py-1 z-50 animate-fade-in">
                    <div className="px-3 py-2 border-b border-warm-100">
                      <p className="text-xs font-medium text-warm-900 truncate">{user.name}</p>
                      <p className="text-xs text-warm-400 truncate">{user.email}</p>
                    </div>
                    <button onClick={() => signOut({ callbackUrl: '/' })}
                      className="w-full flex items-center gap-2 px-3 py-2 text-sm text-warm-600 hover:bg-cream-100 transition-all">
                      <LogOut className="w-3.5 h-3.5" /> Sign out
                    </button>
                  </div>
                )}
              </div>
            ) : (
              <button onClick={() => router.push('/')} className="btn-ghost text-xs py-1.5">Sign in</button>
            )}
          </div>
        </div>
      </header>

      {/* Mobile drawer */}
      {mobileOpen && (
        <>
          <div
            className="fixed inset-0 bg-black/40 z-40 md:hidden"
            onClick={() => setMobileOpen(false)}
          />
          <nav className="fixed top-0 left-0 bottom-0 w-72 bg-white z-50 flex flex-col shadow-2xl md:hidden animate-slide-in-left">
            <div className="flex items-center justify-between px-4 h-14 border-b border-warm-200">
              <Link href="/dashboard" onClick={() => setMobileOpen(false)}
                className="flex items-center gap-2">
                <div className="w-7 h-7 rounded-lg bg-cinema-500 flex items-center justify-center">
                  <Film className="w-3.5 h-3.5 text-white" />
                </div>
                <span className="font-heading font-bold text-warm-900">CineLang</span>
              </Link>
              <button onClick={() => setMobileOpen(false)} className="p-2 rounded-lg text-warm-500 hover:bg-cream-200">
                <X size={20} />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto py-3 px-3">
              {NAV.map(n => {
                const active = pathname === n.href
                return (
                  <Link key={n.href} href={n.href}
                    onClick={() => setMobileOpen(false)}
                    className={clsx(
                      'flex items-center gap-3 px-4 py-3 rounded-xl mb-1 text-sm font-medium transition-all',
                      active ? 'bg-cinema-50 text-cinema-600' : 'text-warm-700 hover:bg-cream-100',
                    )}>
                    <n.icon className="w-4 h-4 shrink-0" />
                    {n.label}
                  </Link>
                )
              })}
            </div>

            {/* Language picker in drawer */}
            <div className="border-t border-warm-200 px-4 py-4 space-y-3">
              <p className="text-xs text-warm-400 font-medium uppercase tracking-wider">Language</p>
              <div className="flex items-center gap-2">
                <select value={sourceLang} onChange={e => setSourceLang(e.target.value)}
                  className="select text-sm py-2 flex-1">
                  {LANGUAGES.map(l => <option key={l.code} value={l.code}>{l.flag} {l.label}</option>)}
                </select>
                <span className="text-warm-400 text-xs">→</span>
                <select value={targetLang} onChange={e => setTargetLang(e.target.value)}
                  className="select text-sm py-2 flex-1">
                  {LANGUAGES.filter(l => l.code !== sourceLang).map(l => (
                    <option key={l.code} value={l.code}>{l.flag} {l.label}</option>
                  ))}
                </select>
              </div>
            </div>

            {user && (
              <div className="border-t border-warm-200 px-4 py-4">
                <div className="flex items-center gap-3 mb-3">
                  {avatar
                    ? <Image src={avatar} alt="" width={32} height={32} className="rounded-full" />
                    : <div className="w-8 h-8 rounded-full bg-cinema-500 flex items-center justify-center text-white text-sm font-bold">
                        {user.name?.[0]}
                      </div>
                  }
                  <div>
                    <p className="text-sm font-medium text-warm-900 truncate">{user.name}</p>
                    <p className="text-xs text-warm-400 truncate">{user.email}</p>
                  </div>
                </div>
                <button onClick={() => signOut({ callbackUrl: '/' })}
                  className="w-full flex items-center gap-2 px-3 py-2 text-sm text-warm-600 hover:bg-cream-100 rounded-lg transition-all">
                  <LogOut className="w-4 h-4" /> Sign out
                </button>
              </div>
            )}
          </nav>
        </>
      )}
    </>
  )
}
