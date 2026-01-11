/**
 * TacticsMaster - TFT Type Definitions
 * 
 * Core types for Teamfight Tactics data structures
 */

// ==================== BASIC TYPES ====================

export type TFTTier = 'S+' | 'S' | 'A' | 'B' | 'C' | 'D'
export type TFTPlacement = 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8
export type TFTStage = '1-1' | '2-1' | '2-5' | '3-2' | '3-5' | '4-2' | '4-5' | '5-1' | '5-5' | '6-1'
export type AugmentStage = '2-1' | '3-2' | '4-2'
export type ItemSlot = 0 | 1 | 2

// ==================== UNITS ====================

export interface TFTUnit {
  id: string
  name: string
  cost: 1 | 2 | 3 | 4 | 5
  traits: string[]
  ability: {
    name: string
    description: string
  }
  stats: {
    health: number[]  // [1*, 2*, 3*]
    attackDamage: number[]
    armor: number
    magicResist: number
    attackSpeed: number
    range: number
  }
  recommendedItems: string[]
  tier: TFTTier
  imageUrl?: string
}

// ==================== TRAITS ====================

export interface TFTTrait {
  id: string
  name: string
  description: string
  type: 'origin' | 'class'
  breakpoints: TraitBreakpoint[]
  units: string[]  // Unit IDs
  imageUrl?: string
}

export interface TraitBreakpoint {
  count: number
  effect: string
  tier: 'bronze' | 'silver' | 'gold' | 'chromatic'
}

// ==================== ITEMS ====================

export interface TFTItem {
  id: string
  name: string
  description: string
  isComponent: boolean
  recipe?: [string, string]  // Component IDs if combined item
  stats: Record<string, number>
  unique?: boolean
  imageUrl?: string
}

export interface ItemRecommendation {
  itemId: string
  priority: number
  reason: string
}

// ==================== AUGMENTS ====================

export interface TFTAugment {
  id: string
  name: string
  description: string
  tier: 'silver' | 'gold' | 'prismatic'
  avgPlacement: number
  pickRate: number
  winRate: number  // Top 4 rate
  bestComps: string[]  // Comp IDs
  imageUrl?: string
}

export interface AugmentRecommendation {
  augmentId: string
  score: number
  reasoning: string
  synergies: string[]  // With current comp
}

// ==================== COMPOSITIONS ====================

export interface TFTComposition {
  id: string
  name: string
  tier: TFTTier
  difficulty: 'easy' | 'medium' | 'hard'
  playstyle: 'fast8' | 'slowroll' | 'reroll' | 'standard'
  
  // Core setup
  coreUnits: CompUnit[]
  flexUnits: CompUnit[]
  
  // Traits to aim for
  targetTraits: {
    traitId: string
    targetCount: number
  }[]
  
  // Items
  carryUnit: string
  carryItems: string[]
  supportItems: { unitId: string; items: string[] }[]
  
  // Augments
  bestAugments: string[]
  
  // Positioning
  positioning?: BoardPosition[]
  
  // Stats
  avgPlacement: number
  playRate: number
  top4Rate: number
  winRate: number
  
  // Guide
  earlyGame?: string
  midGame?: string
  lateGame?: string
  tips?: string[]
}

export interface CompUnit {
  unitId: string
  starLevel: 1 | 2 | 3
  isCarry: boolean
  itemPriority: string[]
}

export interface BoardPosition {
  unitId: string
  row: number  // 0-3 (front to back)
  col: number  // 0-6
}

// ==================== GAME STATE ====================

export interface TFTGameState {
  stage: string
  round: number
  level: number
  gold: number
  health: number
  streak: number
  
  // Board
  board: BoardUnit[]
  bench: BoardUnit[]
  
  // Augments
  augments: string[]
  
  // Items
  itemComponents: string[]
  completedItems: string[]
}

export interface BoardUnit {
  unitId: string
  starLevel: 1 | 2 | 3
  items: string[]
  position?: { row: number; col: number }
}

// ==================== PLAYER DATA ====================

export interface TFTPlayer {
  puuid: string
  summonerName: string
  tagLine: string
  region: string
  profileIconId: number
}

export interface TFTRankedInfo {
  tier: string  // 'IRON' | 'BRONZE' | ... | 'CHALLENGER'
  division: string  // 'I' | 'II' | 'III' | 'IV'
  leaguePoints: number
  wins: number
  losses: number
  winRate: number
}

export interface TFTMatchHistory {
  matchId: string
  gameVersion: string
  placement: TFTPlacement
  level: number
  playersEliminated: number
  totalDamageToPlayers: number
  
  // Comp played
  traits: { name: string; numUnits: number; tierCurrent: number }[]
  units: {
    unitId: string
    tier: number
    items: string[]
  }[]
  
  // Augments
  augments: string[]
  
  // Timestamps
  gameLength: number
  timestamp: number
}

// ==================== RECOMMENDATIONS ====================

export interface CompRecommendation {
  composition: TFTComposition
  score: number
  reasoning: string[]
  contestedUnits: string[]
  pivotOptions: string[]  // Alternative comp IDs
}

export interface ItemRecommendationResult {
  items: ItemRecommendation[]
  carouselPriority: string[]
  slamRecommendations: {
    item: string
    holder: string
    reason: string
  }[]
}

export interface AugmentRecommendationResult {
  stage: AugmentStage
  recommendations: AugmentRecommendation[]
  avoid: { augmentId: string; reason: string }[]
}

// ==================== META DATA ====================

export interface TFTMetaData {
  patch: string
  lastUpdated: number
  
  // Tier lists
  unitTierList: Record<TFTTier, string[]>
  compTierList: Record<TFTTier, string[]>
  augmentTierList: Record<string, TFTTier>  // augmentId -> tier
  itemTierList: Record<string, TFTTier>
  
  // Stats
  unitStats: Record<string, {
    avgPlacement: number
    playRate: number
    winRate: number
  }>
  
  compStats: Record<string, {
    avgPlacement: number
    playRate: number
    winRate: number
    top4Rate: number
  }>
}

// ==================== API RESPONSES ====================

export interface TFTSummonerResponse {
  accountId: string
  profileIconId: number
  revisionDate: number
  summonerLevel: number
  id: string
  puuid: string
}

export interface TFTLeagueEntryResponse {
  leagueId: string
  queueType: string
  tier: string
  rank: string
  summonerId: string
  leaguePoints: number
  wins: number
  losses: number
  veteran: boolean
  inactive: boolean
  freshBlood: boolean
  hotStreak: boolean
}

export interface TFTMatchResponse {
  metadata: {
    data_version: string
    match_id: string
    participants: string[]
  }
  info: {
    game_datetime: number
    game_length: number
    game_version: string
    participants: TFTParticipantResponse[]
    queue_id: number
    tft_game_type: string
    tft_set_core_name: string
    tft_set_number: number
  }
}

export interface TFTParticipantResponse {
  augments: string[]
  companion: {
    content_ID: string
    item_ID: number
    skin_ID: number
    species: string
  }
  gold_left: number
  last_round: number
  level: number
  placement: number
  players_eliminated: number
  puuid: string
  time_eliminated: number
  total_damage_to_players: number
  traits: {
    name: string
    num_units: number
    style: number
    tier_current: number
    tier_total: number
  }[]
  units: {
    character_id: string
    itemNames: string[]
    name: string
    rarity: number
    tier: number
  }[]
}

// ==================== APP STATE ====================

export interface TFTAppState {
  // Connection
  connectionStatus: 'disconnected' | 'connecting' | 'connected'
  
  // User
  currentPlayer: TFTPlayer | null
  rankedInfo: TFTRankedInfo | null
  matchHistory: TFTMatchHistory[]
  
  // Current Game (if in game)
  isInGame: boolean
  gameState: TFTGameState | null
  
  // Recommendations
  compRecommendations: CompRecommendation[]
  itemRecommendations: ItemRecommendationResult | null
  augmentRecommendations: AugmentRecommendationResult | null
  
  // Meta
  meta: TFTMetaData | null
  currentPatch: string
  
  // UI
  selectedComp: string | null
  activeTab: 'comps' | 'items' | 'augments' | 'stats'
}
