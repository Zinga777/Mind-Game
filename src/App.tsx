import { useEffect, type ReactNode } from 'react'
import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { MotionConfig } from 'framer-motion'
import { AppShell } from './components/layout/AppShell'
import { SplashGate } from './components/layout/SplashGate'
import { PlayerProvider } from './state/PlayerContext'
import { ThunderProvider } from './state/ThunderContext'
import { SettingsProvider, useSettings } from './state/SettingsContext'
import { ToastProvider } from './components/ui/Toast'
import { configureSound } from './services/SoundService'
import { configureHaptics } from './services/HapticsService'
import { HomePage } from './pages/HomePage'
import { PreGamePage } from './pages/PreGamePage'
import { PlayPage } from './pages/PlayPage'
import { ResultsPage } from './pages/ResultsPage'
import { ProfilePage } from './pages/ProfilePage'

function FeedbackSettingsSync() {
  const { settings } = useSettings()
  useEffect(() => {
    if (!settings) return
    configureSound({ enabled: settings.sfxEnabled, volume: settings.masterVolume })
    configureHaptics({ enabled: settings.hapticsEnabled })
    document.documentElement.dataset.reduceMotion = String(settings.reduceMotion)
  }, [settings])
  return null
}

function MotionConfigured({ children }: { children: ReactNode }) {
  const { settings } = useSettings()
  return <MotionConfig reducedMotion={settings?.reduceMotion ? 'always' : 'never'}>{children}</MotionConfig>
}

export default function App() {
  return (
    <PlayerProvider>
      <ThunderProvider>
        <SettingsProvider>
          <FeedbackSettingsSync />
          <MotionConfigured>
            <SplashGate>
              <ToastProvider>
                <BrowserRouter>
                  <AppShell>
                    <Routes>
                      <Route path="/" element={<HomePage />} />
                      <Route path="/pre-game" element={<PreGamePage />} />
                      <Route path="/play" element={<PlayPage />} />
                      <Route path="/results" element={<ResultsPage />} />
                      <Route path="/profile" element={<ProfilePage />} />
                    </Routes>
                  </AppShell>
                </BrowserRouter>
              </ToastProvider>
            </SplashGate>
          </MotionConfigured>
        </SettingsProvider>
      </ThunderProvider>
    </PlayerProvider>
  )
}
