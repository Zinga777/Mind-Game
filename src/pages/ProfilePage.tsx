import { useEffect, useState } from 'react'
import { Card, StatTile, Badge } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Skeleton } from '../components/ui/Skeleton'
import { LightningBolt } from '../components/brand/LightningMark'
import { usePlayer } from '../state/PlayerContext'
import { useThunder } from '../state/ThunderContext'
import { useSettings } from '../state/SettingsContext'
import { GameHistoryRepository } from '../repositories/GameHistoryRepository'
import { AchievementRepository } from '../repositories/AchievementRepository'
import { ThunderRepository } from '../repositories/ThunderRepository'
import { PlayerRepository } from '../repositories/PlayerRepository'
import { analyzeMindDna, METRIC_LABEL, type AttemptSample, type MindDnaResult } from '../game-engine/performance'
import { computeProgressionScore, levelForScore, nextLevelThreshold } from '../game-engine/progression'
import { ACHIEVEMENTS } from '../game-engine/achievements'
import type { ThunderTransactionRecord } from '../data/db'

export function ProfilePage() {
  const { profile, updateUsername, updateAvatar } = usePlayer()
  const { balance } = useThunder()
  const { settings, update: updateSettings } = useSettings()

  const [dna, setDna] = useState<MindDnaResult | null>(null)
  const [progression, setProgression] = useState<{ level: string; score: number; next: { next: string; pointsToGo: number } | null } | null>(
    null,
  )
  const [unlocked, setUnlocked] = useState<Set<string>>(new Set())
  const [ledger, setLedger] = useState<ThunderTransactionRecord[]>([])
  const [totalGames, setTotalGames] = useState(0)
  const [streak, setStreak] = useState({ current: 0, longest: 0 })
  const [loading, setLoading] = useState(true)
  const [editingName, setEditingName] = useState(false)
  const [nameDraft, setNameDraft] = useState('')

  const load = async () => {
    setLoading(true)
    const [history, pbs, streakRec, unlockedSet, ledgerRows] = await Promise.all([
      GameHistoryRepository.getAll(),
      GameHistoryRepository.getAllPersonalBests(),
      GameHistoryRepository.getStreak(),
      AchievementRepository.getUnlocked(),
      ThunderRepository.getHistory(20),
    ])

    const samples: AttemptSample[] = history
      .sort((a, b) => b.playedAt - a.playedAt)
      .map((a) => ({ objective: a.config.objective, difficulty: a.config.difficulty, mutators: a.config.mutators, score: a.score, playedAt: a.playedAt }))

    setDna(analyzeMindDna(samples))
    setTotalGames(history.length)
    setStreak({ current: streakRec.current, longest: streakRec.longest })
    setUnlocked(unlockedSet)
    setLedger(ledgerRows)

    const avgAccuracy = history.length === 0 ? 0 : history.reduce((s, a) => s + a.score.accuracy, 0) / history.length
    const score = computeProgressionScore({ totalGames: history.length, personalBestCount: pbs.length, averageAccuracy: avgAccuracy })
    setProgression({ level: levelForScore(score), score, next: nextLevelThreshold(score) })

    setLoading(false)
  }

  useEffect(() => {
    load()
  }, [])

  const saveName = async () => {
    if (nameDraft.trim().length >= 2) await updateUsername(nameDraft.trim())
    setEditingName(false)
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <button className="flex items-center gap-2 text-left" onClick={() => setEditingName(true)}>
          <AvatarBadge avatarId={profile?.avatarId} />
          <h1 className="text-xl font-bold text-ink-50">{profile?.username ?? 'Athlete'}</h1>
        </button>
        {progression && <Badge tone="thunder">{progression.level}</Badge>}
      </div>

      {editingName && (
        <Card>
          <div className="flex gap-2">
            <input
              autoFocus
              defaultValue={profile?.username}
              onChange={(e) => setNameDraft(e.target.value)}
              className="flex-1 rounded-lg border border-ink-700 bg-ink-900 px-3 py-2 text-sm text-ink-50 outline-none focus:border-volt-500"
            />
            <Button onClick={saveName}>SAVE</Button>
          </div>
          <div className="mt-3 flex gap-2">
            {PlayerRepository.AVATAR_IDS.map((id) => (
              <button
                key={id}
                onClick={() => updateAvatar(id)}
                className={`h-8 w-8 rounded-full border-2 ${profile?.avatarId === id ? 'border-volt-500' : 'border-ink-700'}`}
              >
                <AvatarBadge avatarId={id} bare />
              </button>
            ))}
          </div>
        </Card>
      )}

      <Card>
        <div className="grid grid-cols-3 gap-3">
          <StatTile label="Thunder" value={<span className="inline-flex items-center gap-1"><LightningBolt className="h-4 w-4" />{balance}</span>} accent />
          <StatTile label="Streak" value={`${streak.current}d`} />
          <StatTile label="Games" value={totalGames} />
        </div>
        {progression?.next && (
          <p className="mt-3 text-xs text-ink-400">
            {progression.next.pointsToGo} points to <span className="font-semibold text-ink-200">{progression.next.next}</span>
          </p>
        )}
      </Card>

      <Card>
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-ink-300">Mind DNA</h2>
        {loading ? (
          <Skeleton className="h-32" />
        ) : dna && dna.sampleSize > 0 ? (
          <>
            <div className="mb-3 flex items-center justify-between text-xs text-ink-400">
              <span>
                Archetype <span className="font-bold text-volt-400">{dna.archetype}</span>
              </span>
              <span>
                Strongest <span className="font-bold text-ink-200 capitalize">{dna.strongest}</span>
              </span>
            </div>
            <div className="flex flex-col gap-2">
              {(Object.entries(dna.metrics) as [keyof typeof dna.metrics, number][]).map(([key, value]) => (
                <div key={key} className="flex items-center gap-3">
                  <span className="w-24 shrink-0 text-xs text-ink-300">{METRIC_LABEL[key]}</span>
                  <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-ink-800">
                    <div className="h-full rounded-full bg-volt-500" style={{ width: `${value}%` }} />
                  </div>
                  <span className="w-8 shrink-0 text-right text-xs tabular-nums text-ink-400">{value}</span>
                </div>
              ))}
            </div>
            <p className="mt-3 text-[11px] text-ink-500">
              Game-performance stats computed from your runs — not a medical or psychological assessment.
            </p>
          </>
        ) : (
          <p className="text-sm text-ink-400">Play a few Mind Grids to reveal your Mind DNA.</p>
        )}
      </Card>

      <Card>
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-ink-300">Achievements</h2>
        <div className="grid grid-cols-2 gap-2">
          {ACHIEVEMENTS.map((a) => {
            const isUnlocked = unlocked.has(a.id)
            return (
              <div
                key={a.id}
                className={`rounded-lg border p-2.5 ${isUnlocked ? 'border-thunder-500/40 bg-thunder-500/5' : 'border-ink-800 bg-ink-900/40 opacity-60'}`}
              >
                <div className={`text-xs font-bold ${isUnlocked ? 'text-thunder-400' : 'text-ink-400'}`}>{a.title}</div>
                <div className="mt-1 text-[10px] text-ink-500">{a.description}</div>
              </div>
            )
          })}
        </div>
      </Card>

      <Card>
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-ink-300">Thunder History</h2>
        {ledger.length === 0 ? (
          <p className="text-sm text-ink-400">No Thunder activity yet.</p>
        ) : (
          <div className="flex flex-col gap-1.5">
            {ledger.slice(0, 8).map((tx) => (
              <div key={tx.transactionId} className="flex justify-between text-xs">
                <span className="capitalize text-ink-300">{tx.source.replace(/_/g, ' ')}</span>
                <span className={tx.amount >= 0 ? 'text-volt-400' : 'text-danger-500'}>
                  {tx.amount >= 0 ? '+' : ''}
                  {tx.amount}
                </span>
              </div>
            ))}
          </div>
        )}
      </Card>

      <Card>
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-ink-300">Settings</h2>
        <div className="flex flex-col gap-3">
          <SettingRow label="Sound Effects" checked={settings?.sfxEnabled ?? true} onChange={(v) => updateSettings({ sfxEnabled: v })} />
          <SettingRow label="Music" checked={settings?.musicEnabled ?? true} onChange={(v) => updateSettings({ musicEnabled: v })} />
          <SettingRow label="Haptic Feedback" checked={settings?.hapticsEnabled ?? true} onChange={(v) => updateSettings({ hapticsEnabled: v })} />
          <SettingRow label="Reduce Motion" checked={settings?.reduceMotion ?? false} onChange={(v) => updateSettings({ reduceMotion: v })} />
        </div>
      </Card>
    </div>
  )
}

function AvatarBadge({ avatarId, bare }: { avatarId?: string; bare?: boolean }) {
  const seed = avatarId ?? 'bolt-01'
  const hue = (seed.charCodeAt(seed.length - 1) * 37) % 360
  return (
    <div
      className={bare ? 'flex h-full w-full items-center justify-center rounded-full' : 'flex h-10 w-10 items-center justify-center rounded-full'}
      style={{ background: `hsl(${hue} 70% 20%)` }}
    >
      <LightningBolt className="h-4 w-4" monochrome style={{ color: `hsl(${hue} 90% 65%)` }} />
    </div>
  )
}

function SettingRow({ label, checked, onChange }: { label: string; checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <label className="flex items-center justify-between text-sm text-ink-200">
      {label}
      <button
        onClick={() => onChange(!checked)}
        className={`h-6 w-11 rounded-full transition-colors ${checked ? 'bg-volt-500' : 'bg-ink-700'}`}
      >
        <span className={`block h-5 w-5 translate-y-0.5 rounded-full bg-ink-50 transition-transform ${checked ? 'translate-x-5' : 'translate-x-0.5'}`} />
      </button>
    </label>
  )
}
