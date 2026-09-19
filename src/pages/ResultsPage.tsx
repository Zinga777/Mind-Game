import { useLocation, useNavigate } from 'react-router-dom'
import { Button } from '../components/ui/Button'
import { Card, StatTile } from '../components/ui/Card'
import type { GameConfig, ScoreBreakdown } from '../game-engine/types'

interface ResultsState {
  score: ScoreBreakdown
  isNewPersonalBest: boolean
  previousBest: number | null
  config: GameConfig
}

export function ResultsPage() {
  const location = useLocation()
  const navigate = useNavigate()
  const state = location.state as ResultsState | null

  if (!state) {
    navigate('/', { replace: true })
    return null
  }

  const { score, isNewPersonalBest, config } = state

  return (
    <div className="flex flex-col items-center gap-6 text-center">
      {isNewPersonalBest && (
        <div className="rounded-full bg-ember-500/15 px-4 py-1 text-xs font-bold uppercase tracking-wider text-ember-400">
          New Personal Best
        </div>
      )}

      <div className="text-6xl font-black tabular-nums text-ink-50">{score.finalScore.toLocaleString()}</div>

      <Card className="w-full text-left">
        <div className="grid grid-cols-2 gap-3">
          <StatTile label="Accuracy" value={`${Math.round(score.accuracy * 100)}%`} />
          <StatTile label="Avg Reaction" value={`${(score.avgReactionMs / 1000).toFixed(2)}s`} />
          <StatTile label="Correct" value={score.correctCount} />
          <StatTile label="Mistakes" value={score.incorrectCount} />
          <StatTile label="Best Combo" value={`×${score.bestCombo}`} />
          <StatTile label="Final Score" value={score.finalScore.toLocaleString()} accent />
        </div>
      </Card>

      <Card className="w-full text-left font-mono text-sm">
        <Row label="BASE SCORE" value={score.baseScore} />
        <Row label="SPEED BONUS" value={score.speedBonus} sign />
        <Row label="COMBO BONUS" value={score.comboBonus} sign />
        <Row label="TIME BONUS" value={score.timeBonus} sign />
        <Row label="PENALTIES" value={-score.penalties} sign />
        <div className="my-2 border-t border-ink-700" />
        <Row label="FINAL SCORE" value={score.finalScore} bold />
      </Card>

      <div className="flex w-full gap-3">
        <Button
          variant="secondary"
          className="flex-1"
          onClick={() => navigate(`/pre-game?objective=${config.objective}&difficulty=${config.difficulty}`)}
        >
          RETRY
        </Button>
        <Button className="flex-1" onClick={() => navigate('/')}>
          HOME
        </Button>
      </div>
    </div>
  )
}

function Row({ label, value, sign, bold }: { label: string; value: number; sign?: boolean; bold?: boolean }) {
  const display = sign && value >= 0 ? `+${value}` : `${value}`
  return (
    <div className={`flex items-center justify-between py-1 ${bold ? 'font-bold text-focus-400' : 'text-ink-300'}`}>
      <span>{label}</span>
      <span className="tabular-nums">{display}</span>
    </div>
  )
}
