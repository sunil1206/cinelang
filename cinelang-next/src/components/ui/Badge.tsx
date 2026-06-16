import clsx from 'clsx'
import { POS_COLORS, STATUS_META, type VocabStatus } from '@/lib/types'

export function PosBadge({ pos }: { pos?: string | null }) {
  const cls = pos ? (POS_COLORS[pos] ?? 'bg-warm-100 text-warm-600 border-warm-200') : 'bg-warm-100 text-warm-400 border-warm-200'
  return <span className={clsx('badge', cls)}>{pos ?? '?'}</span>
}

export function StatusBadge({
  status, onClick,
}: { status: VocabStatus; onClick?: () => void }) {
  const { label, classes } = STATUS_META[status] ?? STATUS_META.new
  return (
    <button
      onClick={onClick}
      className={clsx('badge transition-all', classes, onClick && 'cursor-pointer hover:opacity-80')}
    >
      {label}
    </button>
  )
}
