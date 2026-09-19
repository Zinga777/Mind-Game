import { useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Button } from '../components/ui/Button'
import { Card, StatTile } from '../components/ui/Card'
import { RewardedAdModal } from '../components/ads/RewardedAdModal'
import { useSession } from '../state/SessionContext'
import { useToast } from '../components/ui/Toast'
import type { GameConfig, ScoreBreakdown } from '../game-engine/types'

interface ResultsState {
  score: ScoreBreakdown
  isNewPersonalBest: boolean
  previousBest: number | null
  globalRank: number | null
  coins: number | null
  config: GameConfig
  savedLocally?: boolean
  submitError?: string
}

export function ResultsPage() {
  const location = useLocation()
  const navigate = useNavigate()
  const { refresh } = useSession()
  const { show } = useToast()
  const [adOpen, setAdOpen] = useState(false)
  const [adClaimed, setAdClaimed] = useState(false)
  const state = location.state as ResultsState | null

  if (!state) {
    navigate('/', { replace: true })
    return null
  }

  const { score, isNewPersonalBest, globalRank, config, savedLocally, submitError } = state

  return (
    <div className="flex flex-col items-center gap-6 text-center">
      {isNewPersonalBest && (
        <motion.div
          initial={{ opacity: 0, scale: 0.8, y: -8 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          transition={{ type: 'spring', stiffness: 260, damping: 16 }}
          className="rounded-full bg-ember-500/15 px-4 py-1 text-xs font-bold uppercase tracking-wider text-ember-400"
        >
          New Personal Best
        </motion.div>
      )}

      <motion.div
        initial={{ opacity: 0, scale: 0.9 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ delay: 0.1 }}
        className="text-6xl font-black tabular-nums text-ink-50"
      >
        {score.finalScore.toLocaleString()}
      </motion.div>

      {savedLocally && (
        <Card className="w-full border-ember-500/40 bg-ember-500/5 text-left">
          <p className="text-xs text-ember-400">
            {submitError === 'Server unreachable'
              ? "Couldn't reach the server — your result is saved on this device and will submit automatically once you're back online."
              : `Result not confirmed by the server yet (${submitError}). It's saved locally and will retry.`}
          </p>
        </Card>
      )}

      {globalRank != null && (
        <div className="flex gap-6 text-sm text-ink-300">
          <div>
            GLOBAL RANK <span className="font-bold text-ink-50">#{globalRank.toLocaleString()}</span>
          </div>
        </div>
      )}

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

      {!adClaimed && !savedLocally && (
        <Card className="w-full">
          <div className="flex items-center justify-between">
            <div className="text-left">
              <div className="text-sm font-semibold text-ink-50">Watch an ad</div>
              <div className="text-xs text-ink-400">Earn +30 coins</div>
            </div>
            <Button variant="secondary" onClick={() => setAdOpen(true)}>
              WATCH
            </Button>
          </div>
        </Card>
      )}

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

      <RewardedAdModal
        open={adOpen}
        onClose={() => setAdOpen(false)}
        onRewarded={(coins) => {
          setAdClaimed(true)
          refresh()
          show(`+${coins} coins`, 'success')
        }}
      />
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
