/**
 * TacticsMaster - TFT State Store
 * 
 * Global state management for TFT application using Zustand
 */

import { create } from 'zustand'
import type { 
  TFTAppState, 
  TFTPlayer, 
  TFTRankedInfo, 
  TFTMatchHistory,
  TFTComposition,
  CompRecommendation,
  TFTMetaData,
  TFTTier
} from '../types/tft'

// Mock compositions for initial data
const MOCK_COMPOSITIONS: TFTComposition[] = [
  {
    id: 'comp-1',
    name: 'Arcana Mages',
    tier: 'S',
    difficulty: 'medium',
    playstyle: 'standard',
    coreUnits: [
      { unitId: 'TFT13_Ahri', starLevel: 2, isCarry: true, itemPriority: ['JeweledGauntlet', 'RabadonsDeathcap', 'GiantSlayer'] },
      { unitId: 'TFT13_Xerath', starLevel: 2, isCarry: false, itemPriority: ['BlueBuff', 'Morellonomicon'] },
    ],
    flexUnits: [],
    targetTraits: [
      { traitId: 'Arcana', targetCount: 4 },
      { traitId: 'Mage', targetCount: 4 }
    ],
    carryUnit: 'TFT13_Ahri',
    carryItems: ['JeweledGauntlet', 'RabadonsDeathcap', 'GiantSlayer'],
    supportItems: [],
    bestAugments: ['MageConference', 'JeweledLotus', 'BlueBattery'],
    avgPlacement: 3.2,
    playRate: 12.5,
    top4Rate: 68.5,
    winRate: 15.2,
    earlyGame: 'Collect mage units and AP items',
    midGame: 'Transition to Arcana at level 7',
    lateGame: 'Add legendary units for frontline',
    tips: ['Position Ahri in backline corner', 'Prioritize Blue Buff on Xerath']
  },
  {
    id: 'comp-2',
    name: 'Bastion Bruisers',
    tier: 'S',
    difficulty: 'easy',
    playstyle: 'slowroll',
    coreUnits: [
      { unitId: 'TFT13_Sett', starLevel: 3, isCarry: true, itemPriority: ['Bloodthirster', 'TitansResolve', 'SterakGage'] },
    ],
    flexUnits: [],
    targetTraits: [
      { traitId: 'Bastion', targetCount: 4 },
      { traitId: 'Bruiser', targetCount: 4 }
    ],
    carryUnit: 'TFT13_Sett',
    carryItems: ['Bloodthirster', 'TitansResolve', 'SterakGage'],
    supportItems: [],
    bestAugments: ['BruiserHeart', 'CyberneticImplants', 'Meditation'],
    avgPlacement: 3.5,
    playRate: 8.2,
    top4Rate: 62.1,
    winRate: 12.8,
    tips: ['Slowroll at level 5 for 3-star Sett']
  },
  {
    id: 'comp-3',
    name: 'Faerie Queens',
    tier: 'A',
    difficulty: 'hard',
    playstyle: 'fast8',
    coreUnits: [],
    flexUnits: [],
    targetTraits: [
      { traitId: 'Faerie', targetCount: 6 }
    ],
    carryUnit: 'TFT13_Kalista',
    carryItems: ['GuinsoosRageblade', 'RunaansHurricane', 'GiantSlayer'],
    supportItems: [],
    bestAugments: ['FaerieCrown', 'AttackSpeedUp', 'LucianBlessing'],
    avgPlacement: 3.8,
    playRate: 6.5,
    top4Rate: 58.2,
    winRate: 11.5,
    tips: ['Go fast 8 and roll for legendaries']
  }
]

interface TFTStoreState extends TFTAppState {
  // Actions
  setConnectionStatus: (status: 'disconnected' | 'connecting' | 'connected') => void
  setCurrentPlayer: (player: TFTPlayer | null) => void
  setRankedInfo: (info: TFTRankedInfo | null) => void
  setMatchHistory: (matches: TFTMatchHistory[]) => void
  setCompRecommendations: (comps: CompRecommendation[]) => void
  setSelectedComp: (compId: string | null) => void
  setActiveTab: (tab: 'comps' | 'items' | 'augments' | 'stats') => void
  setMeta: (meta: TFTMetaData | null) => void
  
  // Demo mode
  isDemoMode: boolean
  enableDemoMode: () => void
  disableDemoMode: () => void
  
  // Computed
  getCompById: (id: string) => TFTComposition | undefined
  getTopComps: (count?: number) => TFTComposition[]
}

export const useTFTStore = create<TFTStoreState>((set, get) => ({
  // Initial state
  connectionStatus: 'disconnected',
  currentPlayer: null,
  rankedInfo: null,
  matchHistory: [],
  isInGame: false,
  gameState: null,
  compRecommendations: [],
  itemRecommendations: null,
  augmentRecommendations: null,
  meta: null,
  currentPatch: '14.24',
  selectedComp: null,
  activeTab: 'comps',
  isDemoMode: false,

  // Actions
  setConnectionStatus: (status) => set({ connectionStatus: status }),
  
  setCurrentPlayer: (player) => set({ currentPlayer: player }),
  
  setRankedInfo: (info) => set({ rankedInfo: info }),
  
  setMatchHistory: (matches) => set({ matchHistory: matches }),
  
  setCompRecommendations: (comps) => set({ compRecommendations: comps }),
  
  setSelectedComp: (compId) => set({ selectedComp: compId }),
  
  setActiveTab: (tab) => set({ activeTab: tab }),
  
  setMeta: (meta) => set({ meta }),
  
  // Demo mode
  enableDemoMode: () => {
    const demoRecommendations: CompRecommendation[] = MOCK_COMPOSITIONS.map((comp, index) => ({
      composition: comp,
      score: 95 - index * 5,
      reasoning: [
        'Strong in current meta',
        'Good augment synergies',
        'Flexible item options'
      ],
      contestedUnits: [],
      pivotOptions: []
    }))
    
    set({
      isDemoMode: true,
      connectionStatus: 'connected',
      compRecommendations: demoRecommendations,
      currentPlayer: {
        puuid: 'demo-puuid',
        summonerName: 'TacticsMaster',
        tagLine: 'TR1',
        region: 'TR',
        profileIconId: 4834
      },
      rankedInfo: {
        tier: 'DIAMOND',
        division: 'II',
        leaguePoints: 75,
        wins: 142,
        losses: 98,
        winRate: 59
      },
      matchHistory: [
        {
          matchId: 'demo-1',
          gameVersion: '14.24',
          placement: 1,
          level: 9,
          playersEliminated: 3,
          totalDamageToPlayers: 85,
          traits: [
            { name: 'Arcana', numUnits: 4, tierCurrent: 2 },
            { name: 'Mage', numUnits: 4, tierCurrent: 2 }
          ],
          units: [],
          augments: ['MageConference', 'JeweledLotus', 'BlueBattery'],
          gameLength: 1850,
          timestamp: Date.now() - 3600000
        },
        {
          matchId: 'demo-2',
          gameVersion: '14.24',
          placement: 3,
          level: 8,
          playersEliminated: 1,
          totalDamageToPlayers: 42,
          traits: [
            { name: 'Bastion', numUnits: 4, tierCurrent: 2 },
            { name: 'Bruiser', numUnits: 4, tierCurrent: 2 }
          ],
          units: [],
          augments: ['BruiserHeart', 'CyberneticImplants', 'Meditation'],
          gameLength: 1650,
          timestamp: Date.now() - 7200000
        }
      ]
    })
  },
  
  disableDemoMode: () => {
    set({
      isDemoMode: false,
      connectionStatus: 'disconnected',
      compRecommendations: [],
      currentPlayer: null,
      rankedInfo: null,
      matchHistory: []
    })
  },
  
  // Computed
  getCompById: (id) => {
    const recs = get().compRecommendations
    return recs.find(r => r.composition.id === id)?.composition
  },
  
  getTopComps: (count = 3) => {
    return get().compRecommendations
      .slice(0, count)
      .map(r => r.composition)
  }
}))

export default useTFTStore
