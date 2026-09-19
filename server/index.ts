import express from 'express'
import cors from 'cors'
import './db' // ensures schema is initialized before routes touch it
import { authRouter } from './routes/auth'
import { gameAttemptsRouter } from './routes/gameAttempts'
import { leaderboardRouter } from './routes/leaderboard'
import { adsRouter } from './routes/ads'
import { profileRouter } from './routes/profile'

const app = express()
const PORT = Number(process.env.PORT ?? 8787)

app.use(cors())
app.use(express.json())

app.get('/api/health', (_req, res) => res.json({ ok: true }))
app.use('/api/auth', authRouter)
app.use('/api/game-attempts', gameAttemptsRouter)
app.use('/api/leaderboard', leaderboardRouter)
app.use('/api/ads', adsRouter)
app.use('/api/profile', profileRouter)

app.use((err: unknown, _req: express.Request, res: express.Response, _next: express.NextFunction) => {
  console.error(err)
  res.status(500).json({ error: 'Internal server error' })
})

app.listen(PORT, () => {
  console.log(`Mind Athlete API listening on http://localhost:${PORT}`)
})
