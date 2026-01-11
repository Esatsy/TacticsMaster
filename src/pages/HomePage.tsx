/**
 * TacticsMaster - Home Page
 * 
 * Dashboard with user stats and quick access
 */

import { useTFTStore } from '../stores/tftStore'
import { cn } from '../lib/utils'

// Icons
const TrophyIcon = () => (
  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
  </svg>
)

const ChartIcon = () => (
  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
  </svg>
)

const GameIcon = () => (
  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
  </svg>
)

const CrownIcon = () => (
  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" />
  </svg>
)

// Stats Card Component
function StatsCard({ 
  icon, 
  label, 
  value, 
  subtext, 
  subtextColor = 'text-zinc-500' 
}: { 
  icon: React.ReactNode
  label: string
  value: string
  subtext?: string
  subtextColor?: string
}) {
  return (
    <div className="glass-panel p-6 rounded-xl">
      <div className="flex items-center gap-3 mb-4">
        <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center text-primary">
          {icon}
        </div>
        <span className="text-sm text-zinc-500">{label}</span>
      </div>
      <div className="text-2xl font-bold text-white">{value}</div>
      {subtext && (
        <div className={cn("text-sm mt-1", subtextColor)}>{subtext}</div>
      )}
    </div>
  )
}

// Match Item Component
function MatchItem({ 
  placement, 
  comp, 
  timeAgo 
}: { 
  placement: number
  comp: string
  timeAgo: string
}) {
  const isTop4 = placement <= 4
  
  return (
    <div className={cn(
      "flex items-center p-4 rounded-lg bg-white/5 hover:bg-white/10 transition-colors border-l-2",
      isTop4 ? "border-victory" : "border-defeat"
    )}>
      <div className={cn(
        "w-8 h-8 rounded-full flex items-center justify-center font-bold text-sm",
        placement === 1 ? "bg-amber-500 text-black" :
        placement <= 4 ? "bg-victory/20 text-victory" :
        "bg-defeat/20 text-defeat"
      )}>
        {placement}
      </div>
      <div className="ml-4 flex-1">
        <div className="text-sm font-medium text-white">{comp}</div>
        <div className="text-xs text-zinc-500">{timeAgo}</div>
      </div>
    </div>
  )
}

export function HomePage({ isConnected }: { isConnected: boolean }) {
  const { currentPlayer, rankedInfo, matchHistory, isDemoMode } = useTFTStore()

  // Not connected state
  if (!isConnected && !isDemoMode) {
    return (
      <div className="flex flex-col h-full w-full p-8 animate-fade-in">
        <div className="flex-1 flex items-center justify-center">
          <div className="glass-panel p-12 rounded-2xl text-center max-w-lg">
            <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-primary to-cyan-400 flex items-center justify-center mx-auto mb-6 shadow-lg shadow-primary/20">
              <span className="text-3xl font-bold text-white">TM</span>
            </div>
            
            <h1 className="text-3xl font-bold text-white mb-4">
              Welcome to TacticsMaster
            </h1>
            
            <p className="text-zinc-400 mb-8">
              Your AI-powered TFT companion. Get real-time composition recommendations, 
              augment tier lists, and item optimization to climb the ranked ladder.
            </p>
            
            <div className="grid grid-cols-3 gap-4 mb-8">
              <div className="p-4 rounded-lg bg-white/5">
                <CrownIcon />
                <p className="text-xs text-zinc-500 mt-2">Meta Comps</p>
              </div>
              <div className="p-4 rounded-lg bg-white/5">
                <ChartIcon />
                <p className="text-xs text-zinc-500 mt-2">AI Predictions</p>
              </div>
              <div className="p-4 rounded-lg bg-white/5">
                <TrophyIcon />
                <p className="text-xs text-zinc-500 mt-2">Climb Faster</p>
              </div>
            </div>
            
            <div className="flex items-center justify-center gap-2 text-sm text-zinc-500">
              <div className="w-2 h-2 rounded-full bg-zinc-600" />
              Start TFT to connect
            </div>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full w-full p-8 overflow-y-auto animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div className="flex items-center gap-4">
          {/* Profile Icon */}
          <div className="w-16 h-16 rounded-xl bg-gradient-to-br from-primary/20 to-cyan-500/20 border border-primary/20 flex items-center justify-center">
            <span className="text-2xl font-bold text-primary">
              {currentPlayer?.summonerName?.charAt(0) || 'T'}
            </span>
          </div>
          
          <div>
            <h1 className="text-2xl font-bold text-white">
              {currentPlayer?.summonerName || 'Summoner'}
              <span className="text-zinc-500 font-normal text-base ml-2">
                #{currentPlayer?.tagLine || 'TR1'}
              </span>
            </h1>
            <div className="flex items-center gap-2 mt-1">
              {rankedInfo && (
                <span className="px-2 py-0.5 rounded text-xs font-medium bg-primary/10 text-primary border border-primary/20">
                  {rankedInfo.tier} {rankedInfo.division}
                </span>
              )}
              {isDemoMode && (
                <span className="px-2 py-0.5 rounded text-xs font-medium bg-amber-500/10 text-amber-400 border border-amber-500/20">
                  Demo
                </span>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
        <StatsCard
          icon={<CrownIcon />}
          label="Ranked TFT"
          value={rankedInfo ? `${rankedInfo.tier} ${rankedInfo.division}` : "Unranked"}
          subtext={rankedInfo ? `${rankedInfo.leaguePoints} LP` : "Play ranked games"}
          subtextColor="text-primary"
        />
        <StatsCard
          icon={<TrophyIcon />}
          label="Win Rate"
          value={rankedInfo ? `${rankedInfo.winRate}%` : "N/A"}
          subtext={rankedInfo ? `${rankedInfo.wins}W ${rankedInfo.losses}L` : "No data"}
          subtextColor={rankedInfo && rankedInfo.winRate >= 50 ? "text-victory" : "text-defeat"}
        />
        <StatsCard
          icon={<ChartIcon />}
          label="Avg Placement"
          value={matchHistory.length > 0 
            ? (matchHistory.reduce((a, m) => a + m.placement, 0) / matchHistory.length).toFixed(1)
            : "N/A"
          }
          subtext={matchHistory.length > 0 ? `Last ${matchHistory.length} games` : "No recent games"}
        />
        <StatsCard
          icon={<GameIcon />}
          label="Games Played"
          value={rankedInfo ? `${rankedInfo.wins + rankedInfo.losses}` : "0"}
          subtext="This set"
        />
      </div>

      {/* Recent Matches */}
      <div className="glass-panel p-6 rounded-xl">
        <h2 className="text-lg font-semibold text-white mb-4">Recent Matches</h2>
        
        {matchHistory.length > 0 ? (
          <div className="space-y-2">
            {matchHistory.slice(0, 5).map((match, index) => {
              const timeDiff = Date.now() - match.timestamp
              const hours = Math.floor(timeDiff / 3600000)
              const timeAgo = hours < 1 ? 'Just now' : hours < 24 ? `${hours}h ago` : `${Math.floor(hours/24)}d ago`
              
              // Get main trait
              const mainTrait = match.traits[0]?.name || 'Unknown Comp'
              
              return (
                <MatchItem 
                  key={match.matchId || index}
                  placement={match.placement}
                  comp={mainTrait}
                  timeAgo={timeAgo}
                />
              )
            })}
          </div>
        ) : (
          <div className="text-center py-8 text-zinc-500">
            <GameIcon />
            <p className="mt-2">No recent matches</p>
          </div>
        )}
      </div>
    </div>
  )
}

export default HomePage
