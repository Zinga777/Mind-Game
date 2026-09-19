import { useEffect, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Button } from '../components/ui/Button'
import { Card, StatTile, Badge } from '../components/ui/Card'
import { LightningBolt } from '../components/brand/LightningMark'
import { RewardedAdModal } from '../components/ads/RewardedAdModal'
import { InterstitialModal } from '../components/ads/InterstitialModal'
import { useThunder } from '../state/ThunderContext'
import { useToast } from '../components/ui/Toast'
import { GameHistoryRepository } from '../repositories/GameHistoryRepository'
import { generateInsights, type AttemptSample } from '../game-engine/performance'
import { ACHIEVEMENTS } from '../game-engine/achievements'
import { AdFrequencyManager } from '../services/AdFrequencyManager'
import type { GameConfig, ScoreBreakdown } from '../game-engine/types'
import type { GhostRunRecord } from '../data/db'
import type { ThunderRewardBreakdown } from '../game-engine/thunder'

interface ResultsState {
  score: ScoreBreakdown
  isNewPersonalBest: boolean
  previousBest: number | null
  streak: { current: number; longest: number }
  thunderReward: ThunderRewardBreakdown
  newlyUnlockedAchievements: string[]
  progressionLevel: string
  config: GameConfig
  ghost: GhostRunRecord | null
}

export function ResultsPage() {
  const location = useLocation()
  const navigate = useNavigate()
  const { refresh: refreshThunder } = useThunder()
  const { show } = useToast()
  const [adOpen, setAdOpen] = useState(false)
  const [adClaimed, setAdClaimed] = useState(false)
  const [insights, setInsights] = useState<string[]>([])
  const [interstitialOpen, setInterstitialOpen] = useState(false)
  const state = location.state as ResultsState | null

  useEffect(() => {
    if (!state) return
    GameHistoryRepository.getRecent(15).then((attempts) => {
      const samples: AttemptSample[] = attempts.map((a) => ({
        objective: a.config.objective,
        difficulty: a.config.difficulty,
        mutators: a.config.mutators,
        score: a.score,
        playedAt: a.playedAt,
      }))
      setInsights(generateInsights(samples))
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  if (!state) {
    navigate('/', { replace: true })
    return null
  }

  const { score, isNewPersonalBest, thunderReward, newlyUnlockedAchievements, config, ghost } = state
  const ghostDelta = ghost ? score.finalScore - ghost.finalScore : null

  const handleHome = async () => {
    const eligible = await AdFrequencyManager.checkInterstitialEligibility()
    if (eligible) {
      setInterstitialOpen(true)
    } else {
      navigate('/')
    }
  }

  const dismissInterstitial = async () => {
    await AdFrequencyManager.recordInterstitialShown()
    setInterstitialOpen(false)
    navigate('/')
  }

  return (
    <div className="flex flex-col items-center gap-6 text-center">
      {isNewPersonalBest && (
        <motion.div
          initial={{ opacity: 0, scale: 0.8, y: -8 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          transition={{ type: 'spring', stiffness: 260, damping: 16 }}
          className="rounded-full bg-thunder-500/15 px-4 py-1 text-xs font-bold uppercase tracking-wider text-thunder-400"
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

      {ghostDelta != null && (
        <div className={`text-sm font-semibold ${ghostDelta >= 0 ? 'text-volt-400' : 'text-danger-500'}`}>
          {ghostDelta >= 0 ? `+${ghostDelta} ahead of your ghost` : `${ghostDelta} behind your ghost`}
        </div>
      )}

      {newlyUnlockedAchievements.length > 0 && (
        <div className="flex flex-wrap justify-center gap-2">
          {newlyUnlockedAchievements.map((id) => {
            const def = ACHIEVEMENTS.find((a) => a.id === id)
            return (
              <Badge key={id} tone="thunder">
                🏆 {def?.title ?? id}
              </Badge>
            )
          })}
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

      <Card className="w-full text-left">
        <div className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-thunder-400">
          <LightningBolt className="h-3.5 w-3.5" /> Thunder Earned
        </div>
        <Row label="Completion" value={thunderReward.completion} sign />
        {thunderReward.accuracy > 0 && <Row label="Accuracy Bonus" value={thunderReward.accuracy} sign />}
        {thunderReward.combo > 0 && <Row label="Combo Bonus" value={thunderReward.combo} sign />}
        {thunderReward.personalBest > 0 && <Row label="PB Bonus" value={thunderReward.personalBest} sign />}
        {thunderReward.achievements > 0 && <Row label="Achievements" value={thunderReward.achievements} sign />}
        <div className="my-2 border-t border-ink-700" />
        <Row label="TOTAL" value={thunderReward.total} bold />
      </Card>

      {insights.length > 0 && (
        <Card className="w-full text-left">
          <div className="mb-2 text-xs font-semibold uppercase tracking-wider text-ink-300">Performance Insight</div>
          {insights.map((line, i) => (
            <p key={i} className="text-sm text-ink-200">
              {line}
            </p>
          ))}
        </Card>
      )}

      {!adClaimed && (
        <Card className="w-full">
          <div className="flex items-center justify-between">
            <div className="text-left">
              <div className="text-sm font-semibold text-ink-50">Watch an ad</div>
              <div className="text-xs text-ink-400">Recharge your Thunder</div>
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
        <Button className="flex-1" onClick={handleHome}>
          HOME
        </Button>
      </div>

      <RewardedAdModal
        open={adOpen}
        onClose={() => setAdOpen(false)}
        onRewarded={(thunder) => {
          setAdClaimed(true)
          refreshThunder()
          show(`+${thunder} Thunder`, 'success')
        }}
      />
      <InterstitialModal open={interstitialOpen} onDismiss={dismissInterstitial} />
    </div>
  )
}

function Row({ label, value, sign, bold }: { label: string; value: number; sign?: boolean; bold?: boolean }) {
  const display = sign && value >= 0 ? `+${value}` : `${value}`
  return (
    <div className={`flex items-center justify-between py-1 ${bold ? 'font-bold text-volt-400' : 'text-ink-300'}`}>
      <span>{label}</span>
      <span className="tabular-nums">{display}</span>
    </div>
  )
}
