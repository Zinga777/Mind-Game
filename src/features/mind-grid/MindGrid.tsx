import { memo, useCallback } from 'react'
import { clsx } from 'clsx'
import type { CellVisualState, GridCell } from '../../game-engine/types'

interface MindGridProps {
  cells: GridCell[]
  cellVisualState: Record<string, CellVisualState>
  gridSize: number
  hideValues?: boolean
  onSelect: (cellId: string) => void
}

const VISUAL_CLASS: Record<CellVisualState, string> = {
  idle: 'bg-ink-800 text-ink-100 border-ink-600 hover:bg-ink-700',
  selected: 'bg-ink-700 text-ink-50 border-focus-500',
  correct: 'bg-focus-500 text-ink-950 border-focus-400 scale-[0.96]',
  incorrect: 'bg-danger-500/80 text-ink-950 border-danger-500 animate-[shake_0.25s_ease-in-out]',
  vanished: 'bg-transparent border-transparent text-transparent pointer-events-none',
  locked: 'bg-ink-900 text-ink-500 border-ink-800 pointer-events-none',
}

function MindGridCellButton({
  cell,
  state,
  hideValue,
  onSelect,
}: {
  cell: GridCell
  state: CellVisualState
  hideValue: boolean
  onSelect: (id: string) => void
}) {
  const handleClick = useCallback(() => onSelect(cell.id), [cell.id, onSelect])
  return (
    <button
      type="button"
      onClick={handleClick}
      disabled={state === 'vanished' || state === 'locked'}
      className={clsx(
        'aspect-square w-full rounded-md border text-[clamp(10px,2.6vw,16px)] font-bold tabular-nums transition-colors duration-100',
        VISUAL_CLASS[state],
      )}
    >
      {hideValue ? '' : cell.value}
    </button>
  )
}

const MemoCell = memo(MindGridCellButton)

export function MindGrid({ cells, cellVisualState, gridSize, hideValues, onSelect }: MindGridProps) {
  return (
    <div
      className="gameplay-surface mx-auto grid w-full max-w-[560px] gap-1.5 sm:gap-2"
      style={{ gridTemplateColumns: `repeat(${gridSize}, minmax(0, 1fr))` }}
    >
      {cells.map((cell) => (
        <MemoCell
          key={cell.id}
          cell={cell}
          state={cellVisualState[cell.id] ?? 'idle'}
          hideValue={Boolean(hideValues)}
          onSelect={onSelect}
        />
      ))}
    </div>
  )
}
