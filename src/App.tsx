import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { AppShell } from './components/layout/AppShell'
import { SplashGate } from './components/layout/SplashGate'
import { SessionProvider } from './state/SessionContext'
import { ToastProvider } from './components/ui/Toast'
import { HomePage } from './pages/HomePage'
import { PreGamePage } from './pages/PreGamePage'
import { PlayPage } from './pages/PlayPage'
import { ResultsPage } from './pages/ResultsPage'
import { LeaderboardPage } from './pages/LeaderboardPage'
import { ProfilePage } from './pages/ProfilePage'
import { TournamentsPage } from './pages/TournamentsPage'

export default function App() {
  return (
    <SessionProvider>
      <SplashGate>
        <ToastProvider>
          <BrowserRouter>
            <AppShell>
              <Routes>
                <Route path="/" element={<HomePage />} />
                <Route path="/pre-game" element={<PreGamePage />} />
                <Route path="/play" element={<PlayPage />} />
                <Route path="/results" element={<ResultsPage />} />
                <Route path="/leaderboard" element={<LeaderboardPage />} />
                <Route path="/profile" element={<ProfilePage />} />
                <Route path="/tournaments" element={<TournamentsPage />} />
              </Routes>
            </AppShell>
          </BrowserRouter>
        </ToastProvider>
      </SplashGate>
    </SessionProvider>
  )
}
