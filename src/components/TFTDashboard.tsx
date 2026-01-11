/**
 * TacticsMaster - Main TFT Dashboard
 * 
 * Central hub for TFT recommendations and statistics
 */

import { useState, useEffect } from 'react'
import { useTFTStore } from '../stores/tftStore'
import { tftApi } from '../services/TFTApiService'
import { cn } from '../lib/utils'
import type { TFTComposition, TFTTier, CompRecommendation } from '../types/tft'

// ==================== ICONS ====================

const CrownIcon = () => (
  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" />
  </svg>
)

const SwordIcon = () => (
  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.828 14.828a4 4 0 01-5.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
  </svg>
)

const SparklesIcon = () => (
  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z" />
  </svg>
)

const ChartIcon = () => (
  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
  </svg>
)

const ItemIcon = () => (
  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
  </svg>
)

// ==================== TIER BADGE ====================

const TIER_COLORS: Record<TFTTier, string> = {
  'S+': 'bg-amber-500/20 text-amber-400 border-amber-500/30',
  'S': 'bg-victory/20 text-victory border-victory/30',
  'A': 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  'B': 'bg-zinc-500/20 text-zinc-400 border-zinc-500/30',
  'C': 'bg-orange-500/20 text-orange-400 border-orange-500/30',
  'D': 'bg-red-500/20 text-red-400 border-red-500/30'
}

function TierBadge({ tier }: { tier: TFTTier }) {
  return (
    <span className={cn(
      "px-2 py-0.5 rounded text-[10px] font-bold border",
      TIER_COLORS[tier]
    )}>
      {tier}
    </span>
  )
}

// ==================== COMP CARD ====================

interface CompCardProps {
  recommendation: CompRecommendation
  rank: number
  isMain?: boolean
  onClick?: () => void
}

function CompCard({ recommendation, rank, isMain = false, onClick }: CompCardProps) {
  const { composition } = recommendation
  
  return (
    <div 
      onClick={onClick}
      className={cn(
        "relative rounded-2xl overflow-hidden border bg-surface cursor-pointer transition-all duration-300 hover:-translate-y-2",
        isMain 
          ? "border-primary/30 shadow-2xl shadow-primary/10" 
          : "border-white/10 hover:border-primary/20"
      )}
    >
      {/* Rank Badge */}
      <div className={cn(
        "absolute top-3 left-3 w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold",
        rank === 1 ? "bg-amber-500 text-black" :
        rank === 2 ? "bg-zinc-400 text-black" :
        "bg-amber-700 text-white"
      )}>
        {rank}
      </div>
      
      {/* Tier Badge */}
      <div className="absolute top-3 right-3">
        <TierBadge tier={composition.tier} />
      </div>
      
      {/* Content */}
      <div className="p-6 pt-14">
        {/* Comp Name */}
        <h3 className="text-lg font-semibold text-white mb-2">{composition.name}</h3>
        
        {/* Playstyle */}
        <div className="flex items-center gap-2 mb-4">
          <span className={cn(
            "px-2 py-0.5 rounded text-[10px] font-medium",
            composition.playstyle === 'reroll' ? "bg-purple-500/20 text-purple-400" :
            composition.playstyle === 'slowroll' ? "bg-blue-500/20 text-blue-400" :
            composition.playstyle === 'fast8' ? "bg-orange-500/20 text-orange-400" :
            "bg-zinc-500/20 text-zinc-400"
          )}>
            {composition.playstyle.toUpperCase()}
          </span>
          <span className={cn(
            "px-2 py-0.5 rounded text-[10px] font-medium",
            composition.difficulty === 'easy' ? "bg-green-500/20 text-green-400" :
            composition.difficulty === 'medium' ? "bg-yellow-500/20 text-yellow-400" :
            "bg-red-500/20 text-red-400"
          )}>
            {composition.difficulty.toUpperCase()}
          </span>
        </div>
        
        {/* Target Traits */}
        <div className="flex flex-wrap gap-1 mb-4">
          {composition.targetTraits.slice(0, 4).map(t => (
            <span 
              key={t.traitId} 
              className="px-2 py-0.5 rounded bg-white/5 text-[10px] text-zinc-400 border border-white/5"
            >
              {t.targetCount} {t.traitId.replace('TFT13_', '')}
            </span>
          ))}
        </div>
        
        {/* Stats */}
        <div className="grid grid-cols-3 gap-2 pt-4 border-t border-white/5">
          <div className="text-center">
            <div className="text-lg font-bold text-white">{composition.avgPlacement.toFixed(1)}</div>
            <div className="text-[10px] text-zinc-500">AVG</div>
          </div>
          <div className="text-center">
            <div className="text-lg font-bold text-victory">{composition.top4Rate}%</div>
            <div className="text-[10px] text-zinc-500">TOP 4</div>
          </div>
          <div className="text-center">
            <div className="text-lg font-bold text-primary">{composition.winRate}%</div>
            <div className="text-[10px] text-zinc-500">WIN</div>
          </div>
        </div>
      </div>
      
      {/* Glow Effect for Main Card */}
      {isMain && (
        <div className="absolute inset-0 bg-gradient-to-t from-primary/5 to-transparent pointer-events-none" />
      )}
    </div>
  )
}

// ==================== EMPTY STATE ====================

function EmptyCard({ isMain = false }: { isMain?: boolean }) {
  return (
    <div className={cn(
      "rounded-2xl border border-dashed border-white/10 flex items-center justify-center",
      isMain ? "h-80" : "h-64"
    )}>
      <div className="text-center">
        <div className="w-12 h-12 rounded-full bg-white/5 flex items-center justify-center mx-auto mb-3">
          <SparklesIcon />
        </div>
        <p className="text-sm text-zinc-500">Waiting for recommendations...</p>
      </div>
    </div>
  )
}

// ==================== WAITING STATE ====================

function WaitingState({ connectionStatus }: { connectionStatus: string }) {
  return (
    <div className="flex flex-col items-center justify-center h-full">
      <div className="glass-panel p-12 rounded-2xl text-center max-w-md">
        <div className={cn(
          "w-16 h-16 rounded-full flex items-center justify-center mx-auto mb-6",
          connectionStatus === 'connecting' ? "bg-primary/10 animate-pulse" : "bg-zinc-800"
        )}>
          <CrownIcon />
        </div>
        
        <h2 className="text-2xl font-semibold text-white mb-3">
          {connectionStatus === 'connecting' ? 'Connecting...' : 'Welcome to TacticsMaster'}
        </h2>
        
        <p className="text-zinc-400 mb-6">
          {connectionStatus === 'connecting' 
            ? 'Looking for TFT client...'
            : 'Start TFT to see personalized recommendations'}
        </p>
        
        <div className="flex items-center justify-center gap-2 text-xs text-zinc-500">
          <div className={cn(
            "w-2 h-2 rounded-full",
            connectionStatus === 'connecting' ? "bg-primary animate-pulse" : "bg-zinc-600"
          )} />
          {connectionStatus === 'connecting' ? 'Searching...' : 'TFT Not Detected'}
        </div>
      </div>
    </div>
  )
}

// ==================== MAIN DASHBOARD ====================

export function TFTDashboard() {
  const { 
    connectionStatus,
    compRecommendations,
    activeTab,
    setActiveTab,
    isDemoMode,
    selectedComp,
    setSelectedComp
  } = useTFTStore()
  
  // Initialize API
  useEffect(() => {
    tftApi.initialize()
  }, [])
  
  // Show waiting state when not connected
  if (connectionStatus !== 'connected' && !isDemoMode) {
    return <WaitingState connectionStatus={connectionStatus} />
  }
  
  const topComps = compRecommendations.slice(0, 3)
  
  return (
    <div className="flex flex-col h-full w-full animate-fade-in">
      {/* Header */}
      <div className="h-16 border-b border-border/50 px-8 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-4">
          {/* Tabs */}
          <div className="flex gap-1 p-1 bg-surface/50 rounded-lg border border-white/5">
            <button 
              onClick={() => setActiveTab('comps')}
              className={cn(
                "flex items-center gap-2 py-2 px-4 rounded-md text-sm font-medium transition-colors",
                activeTab === 'comps' 
                  ? "bg-surface text-white border-b-2 border-primary" 
                  : "text-zinc-400 hover:text-white"
              )}
            >
              <CrownIcon />
              Comps
            </button>
            <button 
              onClick={() => setActiveTab('items')}
              className={cn(
                "flex items-center gap-2 py-2 px-4 rounded-md text-sm font-medium transition-colors",
                activeTab === 'items' 
                  ? "bg-surface text-white border-b-2 border-primary" 
                  : "text-zinc-400 hover:text-white"
              )}
            >
              <ItemIcon />
              Items
            </button>
            <button 
              onClick={() => setActiveTab('augments')}
              className={cn(
                "flex items-center gap-2 py-2 px-4 rounded-md text-sm font-medium transition-colors",
                activeTab === 'augments' 
                  ? "bg-surface text-white border-b-2 border-primary" 
                  : "text-zinc-400 hover:text-white"
              )}
            >
              <SparklesIcon />
              Augments
            </button>
            <button 
              onClick={() => setActiveTab('stats')}
              className={cn(
                "flex items-center gap-2 py-2 px-4 rounded-md text-sm font-medium transition-colors",
                activeTab === 'stats' 
                  ? "bg-surface text-white border-b-2 border-primary" 
                  : "text-zinc-400 hover:text-white"
              )}
            >
              <ChartIcon />
              Stats
            </button>
          </div>
          
          {/* Patch Badge */}
          <span className="px-2 py-0.5 rounded text-[10px] font-medium bg-zinc-800 text-zinc-400 border border-zinc-700/50">
            Patch {tftApi.getCurrentVersion().substring(0, 5)}
          </span>
        </div>
        
        <div className="flex items-center gap-4">
          {/* Demo Mode Indicator */}
          {isDemoMode && (
            <span className="px-3 py-1 rounded-full text-xs font-medium bg-amber-500/10 text-amber-400 border border-amber-500/20">
              Demo Mode
            </span>
          )}
          
          {/* Connection Status */}
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-full border bg-victory/10 border-victory/20">
            <div className="w-2 h-2 rounded-full bg-victory animate-pulse" />
            <span className="text-xs font-medium text-victory">Connected</span>
          </div>
        </div>
      </div>
      
      {/* Content */}
      <div className="flex-1 overflow-y-auto p-8">
        {activeTab === 'comps' && (
          <div className="space-y-8">
            {/* Section Header */}
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-2xl font-bold text-white">Top Meta Compositions</h2>
                <p className="text-sm text-zinc-500 mt-1">Based on current patch data from high ELO matches</p>
              </div>
            </div>
            
            {/* Comp Cards */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {topComps.length > 0 ? (
                topComps.map((rec, index) => (
                  <CompCard 
                    key={rec.composition.id}
                    recommendation={rec}
                    rank={index + 1}
                    isMain={index === 0}
                    onClick={() => setSelectedComp(rec.composition.id)}
                  />
                ))
              ) : (
                <>
                  <EmptyCard />
                  <EmptyCard isMain />
                  <EmptyCard />
                </>
              )}
            </div>
            
            {/* More Comps */}
            {compRecommendations.length > 3 && (
              <div className="space-y-4">
                <h3 className="text-lg font-semibold text-white">More Compositions</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                  {compRecommendations.slice(3).map((rec, index) => (
                    <div 
                      key={rec.composition.id}
                      className="glass-panel p-4 rounded-xl cursor-pointer hover:border-primary/20 transition-colors"
                      onClick={() => setSelectedComp(rec.composition.id)}
                    >
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-sm font-medium text-white">{rec.composition.name}</span>
                        <TierBadge tier={rec.composition.tier} />
                      </div>
                      <div className="flex items-center gap-4 text-xs text-zinc-500">
                        <span>AVG {rec.composition.avgPlacement.toFixed(1)}</span>
                        <span className="text-victory">Top4 {rec.composition.top4Rate}%</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
        
        {activeTab === 'items' && (
          <div className="flex items-center justify-center h-full">
            <div className="text-center">
              <ItemIcon />
              <h3 className="text-xl font-semibold text-white mt-4">Item Recommendations</h3>
              <p className="text-zinc-500 mt-2">Coming soon...</p>
            </div>
          </div>
        )}
        
        {activeTab === 'augments' && (
          <div className="flex items-center justify-center h-full">
            <div className="text-center">
              <SparklesIcon />
              <h3 className="text-xl font-semibold text-white mt-4">Augment Tier List</h3>
              <p className="text-zinc-500 mt-2">Coming soon...</p>
            </div>
          </div>
        )}
        
        {activeTab === 'stats' && (
          <div className="flex items-center justify-center h-full">
            <div className="text-center">
              <ChartIcon />
              <h3 className="text-xl font-semibold text-white mt-4">Personal Statistics</h3>
              <p className="text-zinc-500 mt-2">Coming soon...</p>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default TFTDashboard
