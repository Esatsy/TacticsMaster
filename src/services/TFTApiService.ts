/**
 * TacticsMaster - TFT API Service
 * 
 * Handles all Riot TFT API and Data Dragon interactions
 */

import type { 
  TFTSummonerResponse, 
  TFTLeagueEntryResponse, 
  TFTMatchResponse,
  TFTUnit,
  TFTTrait,
  TFTItem,
  TFTAugment,
  TFTMatchHistory,
  TFTRankedInfo
} from '../types/tft'

// Data Dragon CDN
const DDRAGON_BASE = 'https://ddragon.leagueoflegends.com'
let DDRAGON_VERSION = '14.24.1'
let TFT_SET_NUMBER = 13  // Current set number

// Riot API Regions
const RIOT_API_BASE: Record<string, string> = {
  TR: 'https://tr1.api.riotgames.com',
  EUW: 'https://euw1.api.riotgames.com',
  EUNE: 'https://eun1.api.riotgames.com',
  NA: 'https://na1.api.riotgames.com',
  KR: 'https://kr.api.riotgames.com',
  JP: 'https://jp1.api.riotgames.com',
  BR: 'https://br1.api.riotgames.com',
  OCE: 'https://oc1.api.riotgames.com',
}

// Routing regions for TFT Match API
const ROUTING_REGIONS: Record<string, string> = {
  TR: 'europe',
  EUW: 'europe',
  EUNE: 'europe',
  RU: 'europe',
  NA: 'americas',
  BR: 'americas',
  LAN: 'americas',
  LAS: 'americas',
  KR: 'asia',
  JP: 'asia',
  OCE: 'sea',
  PH: 'sea',
  SG: 'sea',
  TH: 'sea',
  TW: 'sea',
  VN: 'sea',
}

export type Region = keyof typeof RIOT_API_BASE

// Default API key (development - replace with production key)
let API_KEY = ''

class TFTApiService {
  private cache: Map<string, { data: any; timestamp: number }> = new Map()
  private CACHE_DURATION = 5 * 60 * 1000 // 5 minutes
  private region: Region = 'TR'
  private versionInitialized = false
  
  // Static data caches
  private units: Map<string, TFTUnit> = new Map()
  private traits: Map<string, TFTTrait> = new Map()
  private items: Map<string, TFTItem> = new Map()
  private augments: Map<string, TFTAugment> = new Map()

  // ==================== INITIALIZATION ====================

  async initialize(): Promise<void> {
    if (this.versionInitialized) return
    
    try {
      // Get latest version
      const versions = await this.fetchJson<string[]>(`${DDRAGON_BASE}/api/versions.json`)
      if (versions && versions.length > 0) {
        DDRAGON_VERSION = versions[0]
        console.log(`[TFT API] Using Data Dragon version: ${DDRAGON_VERSION}`)
      }
      
      // Load static data
      await Promise.all([
        this.loadUnits(),
        this.loadTraits(),
        this.loadItems(),
        this.loadAugments()
      ])
      
      this.versionInitialized = true
      console.log('[TFT API] Initialized successfully')
    } catch (error) {
      console.warn('[TFT API] Initialization error:', error)
    }
  }

  configure(config: { apiKey?: string; region?: Region }) {
    if (config.apiKey) API_KEY = config.apiKey
    if (config.region) this.region = config.region
  }

  getCurrentVersion(): string {
    return DDRAGON_VERSION
  }

  getCurrentSet(): number {
    return TFT_SET_NUMBER
  }

  // ==================== STATIC DATA LOADING ====================

  private async loadUnits(): Promise<void> {
    try {
      const url = `${DDRAGON_BASE}/cdn/${DDRAGON_VERSION}/data/en_US/tft-champion.json`
      const data = await this.fetchJson<{ data: Record<string, any> }>(url)
      
      if (data?.data) {
        for (const [id, unit] of Object.entries(data.data)) {
          this.units.set(id, this.parseUnit(unit))
        }
        console.log(`[TFT API] Loaded ${this.units.size} units`)
      }
    } catch (error) {
      console.warn('[TFT API] Failed to load units:', error)
    }
  }

  private async loadTraits(): Promise<void> {
    try {
      const url = `${DDRAGON_BASE}/cdn/${DDRAGON_VERSION}/data/en_US/tft-trait.json`
      const data = await this.fetchJson<{ data: Record<string, any> }>(url)
      
      if (data?.data) {
        for (const [id, trait] of Object.entries(data.data)) {
          this.traits.set(id, this.parseTrait(trait))
        }
        console.log(`[TFT API] Loaded ${this.traits.size} traits`)
      }
    } catch (error) {
      console.warn('[TFT API] Failed to load traits:', error)
    }
  }

  private async loadItems(): Promise<void> {
    try {
      const url = `${DDRAGON_BASE}/cdn/${DDRAGON_VERSION}/data/en_US/tft-item.json`
      const data = await this.fetchJson<{ data: Record<string, any> }>(url)
      
      if (data?.data) {
        for (const [id, item] of Object.entries(data.data)) {
          this.items.set(id, this.parseItem(item))
        }
        console.log(`[TFT API] Loaded ${this.items.size} items`)
      }
    } catch (error) {
      console.warn('[TFT API] Failed to load items:', error)
    }
  }

  private async loadAugments(): Promise<void> {
    try {
      const url = `${DDRAGON_BASE}/cdn/${DDRAGON_VERSION}/data/en_US/tft-augments.json`
      const data = await this.fetchJson<{ data: Record<string, any> }>(url)
      
      if (data?.data) {
        for (const [id, augment] of Object.entries(data.data)) {
          this.augments.set(id, this.parseAugment(augment))
        }
        console.log(`[TFT API] Loaded ${this.augments.size} augments`)
      }
    } catch (error) {
      console.warn('[TFT API] Failed to load augments:', error)
    }
  }

  // ==================== DATA PARSERS ====================

  private parseUnit(raw: any): TFTUnit {
    return {
      id: raw.id || raw.apiName,
      name: raw.name,
      cost: raw.tier || 1,
      traits: raw.traits || [],
      ability: {
        name: raw.ability?.name || '',
        description: raw.ability?.desc || ''
      },
      stats: {
        health: raw.stats?.hp || [0, 0, 0],
        attackDamage: raw.stats?.damage || [0, 0, 0],
        armor: raw.stats?.armor || 0,
        magicResist: raw.stats?.magicResist || 0,
        attackSpeed: raw.stats?.attackSpeed || 0,
        range: raw.stats?.range || 1
      },
      recommendedItems: raw.recommendedItems || [],
      tier: 'B',
      imageUrl: this.getUnitImageUrl(raw.id || raw.apiName)
    }
  }

  private parseTrait(raw: any): TFTTrait {
    return {
      id: raw.id || raw.apiName,
      name: raw.name,
      description: raw.desc || '',
      type: raw.type === 'origin' ? 'origin' : 'class',
      breakpoints: (raw.effects || []).map((e: any, i: number) => ({
        count: e.minUnits || i + 1,
        effect: e.desc || '',
        tier: this.getBreakpointTier(i, raw.effects?.length || 1)
      })),
      units: [],
      imageUrl: this.getTraitImageUrl(raw.id || raw.apiName)
    }
  }

  private parseItem(raw: any): TFTItem {
    return {
      id: raw.id || raw.apiName,
      name: raw.name,
      description: raw.desc || '',
      isComponent: raw.composition?.length === 0 || !raw.composition,
      recipe: raw.composition?.length === 2 ? raw.composition : undefined,
      stats: raw.effects || {},
      unique: raw.unique || false,
      imageUrl: this.getItemImageUrl(raw.id || raw.apiName)
    }
  }

  private parseAugment(raw: any): TFTAugment {
    const tierMap: Record<number, 'silver' | 'gold' | 'prismatic'> = {
      1: 'silver',
      2: 'gold', 
      3: 'prismatic'
    }
    
    return {
      id: raw.id || raw.apiName,
      name: raw.name,
      description: raw.desc || '',
      tier: tierMap[raw.tier] || 'silver',
      avgPlacement: 4.5,
      pickRate: 0,
      winRate: 0,
      bestComps: [],
      imageUrl: this.getAugmentImageUrl(raw.id || raw.apiName)
    }
  }

  private getBreakpointTier(index: number, total: number): 'bronze' | 'silver' | 'gold' | 'chromatic' {
    if (total <= 2) return index === 0 ? 'bronze' : 'gold'
    if (total === 3) return ['bronze', 'silver', 'gold'][index] as any
    return ['bronze', 'silver', 'gold', 'chromatic'][index] as any
  }

  // ==================== IMAGE URLS ====================

  getUnitImageUrl(unitId: string): string {
    // TFT unit portraits
    const cleanId = unitId.replace('TFT' + TFT_SET_NUMBER + '_', '')
    return `${DDRAGON_BASE}/cdn/${DDRAGON_VERSION}/img/tft-champion/${cleanId}.png`
  }

  getTraitImageUrl(traitId: string): string {
    return `${DDRAGON_BASE}/cdn/${DDRAGON_VERSION}/img/tft-trait/${traitId}.png`
  }

  getItemImageUrl(itemId: string): string {
    return `${DDRAGON_BASE}/cdn/${DDRAGON_VERSION}/img/tft-item/${itemId}.png`
  }

  getAugmentImageUrl(augmentId: string): string {
    return `${DDRAGON_BASE}/cdn/${DDRAGON_VERSION}/img/tft-augment/${augmentId}.png`
  }

  // ==================== GETTERS FOR STATIC DATA ====================

  getUnit(id: string): TFTUnit | undefined {
    return this.units.get(id)
  }

  getAllUnits(): TFTUnit[] {
    return Array.from(this.units.values())
  }

  getUnitsByCost(cost: number): TFTUnit[] {
    return this.getAllUnits().filter(u => u.cost === cost)
  }

  getUnitsByTrait(traitId: string): TFTUnit[] {
    return this.getAllUnits().filter(u => u.traits.includes(traitId))
  }

  getTrait(id: string): TFTTrait | undefined {
    return this.traits.get(id)
  }

  getAllTraits(): TFTTrait[] {
    return Array.from(this.traits.values())
  }

  getItem(id: string): TFTItem | undefined {
    return this.items.get(id)
  }

  getAllItems(): TFTItem[] {
    return Array.from(this.items.values())
  }

  getComponentItems(): TFTItem[] {
    return this.getAllItems().filter(i => i.isComponent)
  }

  getCombinedItems(): TFTItem[] {
    return this.getAllItems().filter(i => !i.isComponent)
  }

  getAugment(id: string): TFTAugment | undefined {
    return this.augments.get(id)
  }

  getAllAugments(): TFTAugment[] {
    return Array.from(this.augments.values())
  }

  getAugmentsByTier(tier: 'silver' | 'gold' | 'prismatic'): TFTAugment[] {
    return this.getAllAugments().filter(a => a.tier === tier)
  }

  // ==================== RIOT API CALLS ====================

  async getSummoner(puuid: string): Promise<TFTSummonerResponse | null> {
    const url = `${RIOT_API_BASE[this.region]}/tft/summoner/v1/summoners/by-puuid/${puuid}`
    return this.apiRequest<TFTSummonerResponse>(url)
  }

  async getSummonerByName(gameName: string, tagLine: string): Promise<TFTSummonerResponse | null> {
    // First get PUUID from Riot Account API
    const routing = ROUTING_REGIONS[this.region]
    const accountUrl = `https://${routing}.api.riotgames.com/riot/account/v1/accounts/by-riot-id/${encodeURIComponent(gameName)}/${encodeURIComponent(tagLine)}`
    
    const account = await this.apiRequest<{ puuid: string; gameName: string; tagLine: string }>(accountUrl)
    if (!account) return null
    
    return this.getSummoner(account.puuid)
  }

  async getRankedInfo(summonerId: string): Promise<TFTRankedInfo | null> {
    const url = `${RIOT_API_BASE[this.region]}/tft/league/v1/entries/by-summoner/${summonerId}`
    const entries = await this.apiRequest<TFTLeagueEntryResponse[]>(url)
    
    if (!entries || entries.length === 0) return null
    
    // Find ranked TFT entry
    const ranked = entries.find(e => e.queueType === 'RANKED_TFT')
    if (!ranked) return null
    
    const totalGames = ranked.wins + ranked.losses
    return {
      tier: ranked.tier,
      division: ranked.rank,
      leaguePoints: ranked.leaguePoints,
      wins: ranked.wins,
      losses: ranked.losses,
      winRate: totalGames > 0 ? Math.round((ranked.wins / totalGames) * 100) : 0
    }
  }

  async getMatchHistory(puuid: string, count: number = 20): Promise<TFTMatchHistory[]> {
    const routing = ROUTING_REGIONS[this.region]
    const idsUrl = `https://${routing}.api.riotgames.com/tft/match/v1/matches/by-puuid/${puuid}/ids?count=${count}`
    
    const matchIds = await this.apiRequest<string[]>(idsUrl)
    if (!matchIds || matchIds.length === 0) return []
    
    const matches: TFTMatchHistory[] = []
    
    // Fetch match details (limit concurrency)
    for (const matchId of matchIds.slice(0, 10)) {
      const match = await this.getMatchDetail(matchId, puuid)
      if (match) matches.push(match)
    }
    
    return matches
  }

  async getMatchDetail(matchId: string, puuid: string): Promise<TFTMatchHistory | null> {
    const routing = ROUTING_REGIONS[this.region]
    const url = `https://${routing}.api.riotgames.com/tft/match/v1/matches/${matchId}`
    
    const match = await this.apiRequest<TFTMatchResponse>(url)
    if (!match) return null
    
    const participant = match.info.participants.find(p => p.puuid === puuid)
    if (!participant) return null
    
    return {
      matchId,
      gameVersion: match.info.game_version,
      placement: participant.placement as any,
      level: participant.level,
      playersEliminated: participant.players_eliminated,
      totalDamageToPlayers: participant.total_damage_to_players,
      traits: participant.traits.map(t => ({
        name: t.name,
        numUnits: t.num_units,
        tierCurrent: t.tier_current
      })),
      units: participant.units.map(u => ({
        unitId: u.character_id,
        tier: u.tier,
        items: u.itemNames || []
      })),
      augments: participant.augments,
      gameLength: match.info.game_length,
      timestamp: match.info.game_datetime
    }
  }

  async getChallengerLeague(): Promise<any> {
    const url = `${RIOT_API_BASE[this.region]}/tft/league/v1/challenger`
    return this.apiRequest(url)
  }

  async getGrandmasterLeague(): Promise<any> {
    const url = `${RIOT_API_BASE[this.region]}/tft/league/v1/grandmaster`
    return this.apiRequest(url)
  }

  async getMasterLeague(): Promise<any> {
    const url = `${RIOT_API_BASE[this.region]}/tft/league/v1/master`
    return this.apiRequest(url)
  }

  // ==================== HTTP UTILITIES ====================

  private async fetchJson<T>(url: string): Promise<T | null> {
    try {
      const response = await fetch(url)
      if (!response.ok) return null
      return await response.json()
    } catch {
      return null
    }
  }

  private async apiRequest<T>(url: string): Promise<T | null> {
    if (!API_KEY) {
      console.warn('[TFT API] No API key configured')
      return null
    }
    
    // Check cache
    const cached = this.cache.get(url)
    if (cached && Date.now() - cached.timestamp < this.CACHE_DURATION) {
      return cached.data as T
    }
    
    try {
      const response = await fetch(url, {
        headers: { 'X-Riot-Token': API_KEY }
      })
      
      if (!response.ok) {
        console.warn(`[TFT API] Request failed: ${url} -> ${response.status}`)
        return null
      }
      
      const data = await response.json()
      
      // Cache response
      this.cache.set(url, { data, timestamp: Date.now() })
      
      return data as T
    } catch (error) {
      console.error('[TFT API] Request error:', error)
      return null
    }
  }
}

export const tftApi = new TFTApiService()
export default tftApi
