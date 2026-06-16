'use client'
import { X } from 'lucide-react'
import clsx from 'clsx'

const STYLES = {
  ok:   'bg-emerald-50 border-emerald-200 text-emerald-700',
  warn: 'bg-amber-50  border-amber-200  text-amber-700',
  err:  'bg-red-50    border-red-200    text-red-700',
}

export default function Toast({ msg, type = 'ok', onClose }: {
  msg: string; type?: 'ok' | 'warn' | 'err'; onClose: () => void
}) {
  return (
    <div className={clsx(
      'fixed bottom-6 right-6 z-50 flex items-start gap-3 px-4 py-3 rounded-xl border shadow-warm-lg max-w-sm animate-slide-up text-sm font-medium',
      STYLES[type],
    )}>
      <span className="flex-1">{msg}</span>
      <button onClick={onClose} className="shrink-0 opacity-60 hover:opacity-100 transition-opacity mt-0.5">
        <X className="w-3.5 h-3.5" />
      </button>
    </div>
  )
}
