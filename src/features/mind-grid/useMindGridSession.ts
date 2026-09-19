import { useCallback, useEffect, useRef, useState } from 'react'
import { createSession, remainingTimeMs, selectCell, tick } from '../../game-engine/core/session'
import type { GameConfig, GameSessionState, SelectionEvent } from '../../game-engine/types'

export function useMindGridSession(config: GameConfig, onSelection?: (event: SelectionEvent, comboAfter: number) => void) {
  const [session, setSession] = useState<GameSessionState>(() => createSession(config, performance.now()))
  const [remainingMs, setRemainingMs] = useState(() => config.durationSeconds * 1000)
  const lastFrameRef = useRef(performance.now())
  const rafRef = useRef<number>(0)
  const onSelectionRef = useRef(onSelection)
  onSelectionRef.current = onSelection

  useEffect(() => {
    setSession(createSession(config, performance.now()))
    lastFrameRef.current = performance.now()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [config])

  useEffect(() => {
    const loop = (now: number) => {
      const deltaMs = now - lastFrameRef.current
      lastFrameRef.current = now
      setSession((prev) => {
        if (prev.status !== 'active') return prev
        return tick(prev, now, deltaMs)
      })
      rafRef.current = requestAnimationFrame(loop)
    }
    rafRef.current = requestAnimationFrame(loop)
    return () => cancelAnimationFrame(rafRef.current)
  }, [])

  useEffect(() => {
    const id = setInterval(() => {
      setSession((prev) => {
        setRemainingMs(remainingTimeMs(prev, performance.now()))
        return prev
      })
    }, 100)
    return () => clearInterval(id)
  }, [])

  const select = useCallback((cellId: string) => {
    setSession((prev) => {
      const next = selectCell(prev, cellId, performance.now())
      if (next.events.length > prev.events.length) {
        onSelectionRef.current?.(next.events[next.events.length - 1], next.combo)
      }
      return next
    })
  }, [])

  const elapsedMs = config.durationSeconds * 1000 - remainingMs

  return { session, remainingMs, elapsedMs, select }
}
