'use client'
import { useSession } from 'next-auth/react'
import { useRouter, useSearchParams } from 'next/navigation'
import { useEffect, Suspense } from 'react'
import { useCineLang } from '@/lib/store'
import Header from '@/components/Header'
import Toast from '@/components/ui/Toast'
import { Loader2 } from 'lucide-react'

function AppGuard({ children }: { children: React.ReactNode }) {
  const { data: session, status } = useSession()
  const router = useRouter()
  const searchParams = useSearchParams()
  const demo = searchParams.get('demo') === '1'
  const { showToast, toast } = useCineLang()

  useEffect(() => {
    if (status === 'unauthenticated' && !demo) {
      router.push('/')
    }
  }, [status, demo, router])

  if (status === 'loading') {
    return (
      <div className="min-h-screen bg-cream-100 flex items-center justify-center">
        <Loader2 className="w-6 h-6 animate-spin text-cinema-500" />
      </div>
    )
  }

  if (status === 'unauthenticated' && !demo) return null

  return (
    <div className="min-h-screen bg-cream-100 flex flex-col">
      <Header demo={demo} session={session} />
      <main className="flex-1 overflow-auto">
        {children}
      </main>
      {toast && <Toast msg={toast.msg} type={toast.type} onClose={() => useCineLang.getState().clearToast()} />}
    </div>
  )
}

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <Suspense>
      <AppGuard>{children}</AppGuard>
    </Suspense>
  )
}
