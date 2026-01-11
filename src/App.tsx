/**
 * TacticsMaster - Main Application
 * 
 * TFT Companion App for Teamfight Tactics
 */

import { useEffect, useState } from 'react'
import { TFTDashboard } from './components/TFTDashboard'
import { TitleBar } from './components/TitleBar'
import { Navigation, Page } from './components/Navigation'
import { HomePage } from './pages/HomePage'
import { useTFTStore } from './stores/tftStore'

// Settings Page (inline for now)
function SettingsPage() {
  const { isDemoMode, enableDemoMode, disableDemoMode } = useTFTStore()
  const [apiKey, setApiKey] = useState('')

  return (
    <div className="flex flex-col h-full w-full p-8 animate-fade-in overflow-y-auto">
      <h1 className="text-3xl font-bold text-white mb-8">Settings</h1>
      
      <div className="space-y-6 max-w-2xl">
        {/* Demo Mode */}
        <div className="glass-panel p-6 rounded-xl">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-lg font-semibold text-white">Demo Mode</h3>
              <p className="text-sm text-zinc-500 mt-1">
                Preview the app with sample data without connecting to TFT
              </p>
            </div>
            <button
              onClick={() => isDemoMode ? disableDemoMode() : enableDemoMode()}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                isDemoMode 
                  ? 'bg-primary text-white' 
                  : 'bg-zinc-800 text-zinc-400 hover:text-white'
              }`}
            >
              {isDemoMode ? 'Enabled' : 'Enable'}
            </button>
          </div>
        </div>
        
        {/* API Key */}
        <div className="glass-panel p-6 rounded-xl">
          <h3 className="text-lg font-semibold text-white mb-4">Riot API Key</h3>
          <p className="text-sm text-zinc-500 mb-4">
            Enter your Riot API key for additional features (optional)
          </p>
          <div className="flex gap-3">
            <input
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder="RGAPI-..."
              className="flex-1 bg-surface border border-white/10 rounded-lg px-4 py-2.5 text-sm text-white placeholder-zinc-600 focus:outline-none focus:border-primary/50"
            />
            <button
              onClick={() => {
                localStorage.setItem('riotApiKey', apiKey)
                alert('Saved!')
              }}
              className="px-4 py-2 bg-primary text-white rounded-lg text-sm font-medium hover:bg-primary/80 transition-colors"
            >
              Save
            </button>
          </div>
        </div>
        
        {/* About */}
        <div className="glass-panel p-6 rounded-xl">
          <h3 className="text-lg font-semibold text-white mb-2">About TacticsMaster</h3>
          <p className="text-sm text-zinc-500">
            Your AI-powered TFT companion. Get composition recommendations, 
            augment tier lists, and item optimization to climb the ranked ladder.
          </p>
          <div className="mt-4 pt-4 border-t border-white/5">
            <p className="text-xs text-zinc-600">
              TacticsMaster isn't endorsed by Riot Games and doesn't reflect the views 
              or opinions of Riot Games or anyone officially involved in producing or 
              managing Riot Games properties.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}

function App() {
  const { connectionStatus, isDemoMode } = useTFTStore()
  const [currentPage, setCurrentPage] = useState<Page>('comps')

  // Initialize UnicornStudio background animation
  useEffect(() => {
    if (!(window as any).UnicornStudio) {
      (window as any).UnicornStudio = { isInitialized: false }
      const script = document.createElement('script')
      script.src = 'https://cdn.jsdelivr.net/gh/hiunicornstudio/unicornstudio.js@v1.4.29/dist/unicornStudio.umd.js'
      script.onload = () => {
        if (!(window as any).UnicornStudio.isInitialized) {
          (window as any).UnicornStudio.init()
          ;(window as any).UnicornStudio.isInitialized = true
        }
      }
      document.head.appendChild(script)
    }
  }, [])

  const isConnected = connectionStatus === 'connected' || isDemoMode

  const renderPage = () => {
    switch (currentPage) {
      case 'home': return <HomePage isConnected={isConnected} />
      case 'comps': return <TFTDashboard />
      case 'items': return <TFTDashboard />
      case 'augments': return <TFTDashboard />
      case 'stats': return <TFTDashboard />
      case 'settings': return <SettingsPage />
      default: return <TFTDashboard />
    }
  }

  return (
    <div className="h-screen flex flex-col overflow-hidden">
      {/* Animated Background */}
      <div 
        className="fixed -z-10 w-full h-screen top-0 saturate-50 hue-rotate-180"
        style={{
          maskImage: 'linear-gradient(to bottom, transparent, black 0%, black 72%, transparent)',
          WebkitMaskImage: 'linear-gradient(to bottom, transparent, black 0%, black 72%, transparent)'
        }}
      >
        <div className="absolute top-0 w-full h-full -z-10">
          <div 
            data-us-project="vTTCp5g4cVl9nwjlT56Z" 
            className="absolute w-full h-full left-0 top-0 -z-10"
          />
        </div>
      </div>

      {/* Title Bar */}
      <TitleBar title="TacticsMaster" />

      {/* Main Content */}
      <div className="flex-1 flex overflow-hidden">
        <Navigation currentPage={currentPage} onPageChange={setCurrentPage} />
        <main className="flex-1 overflow-hidden">
          {renderPage()}
        </main>
      </div>
    </div>
  )
}

export default App
