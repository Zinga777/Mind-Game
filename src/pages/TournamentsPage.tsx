import { Card, Badge } from '../components/ui/Card'

export function TournamentsPage() {
  return (
    <div className="flex flex-col gap-4">
      <div>
        <Badge tone="ember">Coming Soon</Badge>
        <h1 className="mt-2 text-2xl font-bold text-ink-50">Tournaments</h1>
      </div>
      <Card>
        <p className="text-sm text-ink-300">
          Competitive tournaments — bracket formats, coin entry with server-held escrow, and reward distribution —
          aren't built yet. The backend already reserves a <code className="text-ink-100">tournaments</code> table
          and every Mind Grid run is scored from a versioned, seeded config, which is what fair, reproducible
          tournament rounds need. When this ships, it plugs into that foundation rather than requiring a rebuild.
        </p>
      </Card>
      <Card>
        <h2 className="mb-2 text-sm font-semibold uppercase tracking-wider text-ink-300">What's already in place</h2>
        <ul className="list-inside list-disc space-y-1 text-sm text-ink-300">
          <li>Deterministic, seeded challenge configs — every participant can get an identical round</li>
          <li>Server-authoritative scoring and a coin ledger (needed for entry fees + payouts)</li>
          <li>Difficulty presets and mutator sets to define tournament formats from</li>
        </ul>
      </Card>
    </div>
  )
}
