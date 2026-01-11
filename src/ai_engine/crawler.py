"""
High-Performance Asynchronous Match Crawler.

Features:
- Dynamic version detection from DDragon API
- Strict current-patch filtering (discards old patch data)
- Recursive PUUID discovery from match participants
- Intelligent rate limit handling with Retry-After parsing
- Concurrent request management with semaphores
"""

import asyncio
import aiohttp
import logging
import time
import re
from datetime import datetime
from typing import List, Dict, Set, Optional, Any, Tuple
from dataclasses import dataclass, field
from collections import deque
from enum import Enum

from .config import config, CrawlerConfig
from .database import get_database, MatchRecord, PlayerRecord

logger = logging.getLogger(__name__)


class CrawlState(Enum):
    """Crawler state."""
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"


class RateLimiter:
    """
    Simple fixed-delay rate limiter for Riot API.
    Ensures minimum delay between requests to stay under limits.
    
    Development key: 100 requests / 2 minutes = 1 request per 1.2 seconds
    We use 1.5 seconds to be safe.
    """
    
    def __init__(self, min_delay: float = 1.5):
        self.min_delay = min_delay
        self._last_request: float = 0
        self._lock: Optional[asyncio.Lock] = None
        
    def _get_lock(self) -> asyncio.Lock:
        """Lazily create lock in the correct event loop."""
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock
    
    async def acquire(self) -> None:
        """Wait for minimum delay since last request."""
        async with self._get_lock():
            now = time.time()
            elapsed = now - self._last_request
            
            if elapsed < self.min_delay:
                wait_time = self.min_delay - elapsed
                await asyncio.sleep(wait_time)
            
            self._last_request = time.time()
    
    async def handle_retry_after(self, retry_after: int) -> None:
        """Handle a 429 response by waiting for Retry-After."""
        logger.warning(f"Rate limited! Waiting {retry_after}s...")
        await asyncio.sleep(retry_after + 1)  # Add 1 second buffer
        self._last_request = time.time()


@dataclass
class CrawlStats:
    """Crawl statistics tracker."""
    started_at: datetime = field(default_factory=datetime.now)
    matches_fetched: int = 0
    matches_stored: int = 0
    matches_filtered: int = 0  # Discarded due to wrong version
    players_discovered: int = 0
    players_crawled: int = 0
    requests_made: int = 0
    errors: int = 0
    rate_limits_hit: int = 0
    
    def log_summary(self) -> None:
        """Log crawl statistics."""
        elapsed = (datetime.now() - self.started_at).total_seconds()
        rate = self.matches_stored / elapsed if elapsed > 0 else 0
        
        logger.info(f"""
=== Crawl Statistics ===
Duration: {elapsed:.1f}s
Matches Fetched: {self.matches_fetched}
Matches Stored: {self.matches_stored}
Matches Filtered (old patch): {self.matches_filtered}
Players Discovered: {self.players_discovered}
Players Crawled: {self.players_crawled}
Requests Made: {self.requests_made}
Errors: {self.errors}
Rate Limits Hit: {self.rate_limits_hit}
Storage Rate: {rate:.2f} matches/sec
========================
        """)


class MatchCrawler:
    """
    High-performance asynchronous match crawler.
    
    Implements recursive PUUID discovery with strict version filtering
    to maintain a current-patch-only dataset.
    """
    
    # DDragon API
    DDRAGON_VERSIONS_URL = "https://ddragon.leagueoflegends.com/api/versions.json"
    
    # Riot API endpoints (templated)
    MATCH_BY_PUUID_URL = "https://{routing}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids"
    MATCH_DETAILS_URL = "https://{routing}.api.riotgames.com/lol/match/v5/matches/{match_id}"
    SUMMONER_BY_PUUID_URL = "https://{region}.api.riotgames.com/lol/summoner/v4/summoners/by-puuid/{puuid}"
    LEAGUE_ENTRIES_URL = "https://{region}.api.riotgames.com/lol/league/v4/entries/by-summoner/{summoner_id}"
    CHALLENGER_LEAGUE_URL = "https://{region}.api.riotgames.com/lol/league/v4/challengerleagues/by-queue/{queue}"
    GRANDMASTER_LEAGUE_URL = "https://{region}.api.riotgames.com/lol/league/v4/grandmasterleagues/by-queue/{queue}"
    MASTER_LEAGUE_URL = "https://{region}.api.riotgames.com/lol/league/v4/masterleagues/by-queue/{queue}"
    
    def __init__(self, crawler_config: Optional[CrawlerConfig] = None):
        self.config = crawler_config or config.crawler
        self.db = get_database()
        # 1.5 second delay = ~40 requests per minute, safe under 100/2min limit
        self.rate_limiter = RateLimiter(min_delay=1.5)
        
        # Current patch info
        self.current_version: Optional[str] = None
        self.current_major_minor: Optional[str] = None
        
        # Crawl state
        self.state = CrawlState.IDLE
        self.stats = CrawlStats()
        
        # In-memory queues
        self.puuid_queue: deque[Tuple[str, str]] = deque(maxlen=self.config.max_queue_size)
        self.seen_puuids: Set[str] = set()
        self.seen_matches: Set[str] = set()
        
        # Match buffer for batch insert
        self.match_buffer: List[MatchRecord] = []
        
        # Concurrency control
        self.semaphore: Optional[asyncio.Semaphore] = None
        
        # Session
        self._session: Optional[aiohttp.ClientSession] = None
        
    @property
    def headers(self) -> Dict[str, str]:
        """Get API request headers."""
        return {
            "X-Riot-Token": self.config.api_key,
            "Accept": "application/json",
            "Accept-Charset": "application/json;charset=UTF-8"
        }
    
    def get_routing(self, region: str) -> str:
        """Get routing region for match-v5 API."""
        return self.config.routing_regions.get(region, "europe")
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=30)
            connector = aiohttp.TCPConnector(limit=50, limit_per_host=20)
            self._session = aiohttp.ClientSession(
                headers=self.headers,
                timeout=timeout,
                connector=connector
            )
        return self._session
    
    async def close(self) -> None:
        """Close resources."""
        if self._session and not self._session.closed:
            await self._session.close()
        self.state = CrawlState.STOPPED
    
    # ==================== VERSION MANAGEMENT ====================
    
    async def fetch_current_version(self) -> str:
        """
        Fetch the latest LoL version from DDragon.
        Critical for filtering matches by current patch.
        """
        session = await self._get_session()
        
        try:
            async with session.get(self.DDRAGON_VERSIONS_URL) as resp:
                if resp.status == 200:
                    versions = await resp.json()
                    if versions and len(versions) > 0:
                        latest = versions[0]  # e.g., "14.24.1"
                        self.current_version = latest
                        # Extract major.minor for comparison
                        parts = latest.split(".")
                        self.current_major_minor = f"{parts[0]}.{parts[1]}"
                        logger.info(f"Current patch: {latest} (filtering for {self.current_major_minor})")
                        return latest
        except Exception as e:
            logger.error(f"Failed to fetch version: {e}")
            
        # Fallback
        self.current_version = "14.24.1"
        self.current_major_minor = "14.24"
        return self.current_version
    
    def is_current_patch(self, game_version: str) -> bool:
        """
        Check if a match's game version matches current patch.
        
        Game versions from match API look like "14.24.636.9802"
        We compare only major.minor parts.
        """
        if not self.current_major_minor:
            return True  # No filter if version not fetched
            
        # Extract major.minor from game version
        parts = game_version.split(".")
        if len(parts) >= 2:
            match_major_minor = f"{parts[0]}.{parts[1]}"
            return match_major_minor == self.current_major_minor
            
        return False
    
    # ==================== API REQUESTS ====================
    
    async def _make_request(
        self, 
        url: str, 
        params: Optional[Dict] = None
    ) -> Tuple[Optional[Any], int]:
        """
        Make a rate-limited API request.
        
        Returns: (json_data, status_code)
        """
        await self.rate_limiter.acquire()
        
        session = await self._get_session()
        self.stats.requests_made += 1
        
        try:
            async with self.semaphore:
                async with session.get(url, params=params) as resp:
                    status = resp.status
                    
                    if status == 200:
                        return await resp.json(), status
                        
                    elif status == 429:
                        # Rate limited
                        self.stats.rate_limits_hit += 1
                        retry_after = int(resp.headers.get("Retry-After", 60))
                        await self.rate_limiter.handle_retry_after(retry_after)
                        return None, status
                        
                    elif status == 404:
                        # Not found - not an error for our purposes
                        return None, status
                        
                    else:
                        logger.warning(f"Request failed: {url} -> {status}")
                        self.stats.errors += 1
                        return None, status
                        
        except asyncio.TimeoutError:
            logger.warning(f"Request timeout: {url}")
            self.stats.errors += 1
            return None, 0
            
        except Exception as e:
            logger.error(f"Request error: {url} -> {e}")
            self.stats.errors += 1
            return None, 0
    
    # ==================== DATA FETCHING ====================
    
    async def fetch_match_ids(
        self, 
        puuid: str, 
        region: str,
        count: int = 20,
        queue: int = 420  # Ranked Solo/Duo
    ) -> List[str]:
        """Fetch recent match IDs for a player."""
        routing = self.get_routing(region)
        url = self.MATCH_BY_PUUID_URL.format(routing=routing, puuid=puuid)
        
        params = {
            "queue": queue,
            "type": "ranked",
            "start": 0,
            "count": count
        }
        
        data, status = await self._make_request(url, params)
        
        if data and isinstance(data, list):
            # Filter out already seen matches
            new_matches = [m for m in data if m not in self.seen_matches]
            return new_matches
            
        return []
    
    async def fetch_match_details(self, match_id: str, region: str) -> Optional[MatchRecord]:
        """
        Fetch match details and convert to MatchRecord.
        
        Applies strict version filtering - returns None for old patches.
        """
        routing = self.get_routing(region)
        url = self.MATCH_DETAILS_URL.format(routing=routing, match_id=match_id)
        
        data, status = await self._make_request(url)
        
        if not data:
            return None
            
        self.stats.matches_fetched += 1
        
        # Parse and validate
        try:
            info = data.get("info", {})
            metadata = data.get("metadata", {})
            
            game_version = info.get("gameVersion", "")
            
            # ===== CRITICAL: VERSION FILTER =====
            if not self.is_current_patch(game_version):
                self.stats.matches_filtered += 1
                logger.debug(f"Filtered match {match_id} - version {game_version}")
                return None
            # ====================================
            
            # Only process Summoner's Rift ranked games
            queue_id = info.get("queueId", 0)
            if queue_id not in [420, 440]:  # Ranked Solo/Flex
                return None
                
            # Extract team compositions
            participants = info.get("participants", [])
            if len(participants) != 10:
                return None
                
            blue_team: List[int] = []
            red_team: List[int] = []
            blue_items: List[List[int]] = []
            red_items: List[List[int]] = []
            blue_win = False
            
            for p in participants:
                champ_id = p.get("championId", 0)
                team_id = p.get("teamId", 0)
                
                # Get items (slots 0-5)
                items = [p.get(f"item{i}", 0) for i in range(6)]
                
                if team_id == 100:  # Blue
                    blue_team.append(champ_id)
                    blue_items.append(items)
                    if p.get("win", False):
                        blue_win = True
                else:  # Red
                    red_team.append(champ_id)
                    red_items.append(items)
            
            # Discover new players
            new_puuids = [
                (p, region) for p in metadata.get("participants", [])
                if p not in self.seen_puuids
            ]
            if new_puuids:
                for puuid, reg in new_puuids:
                    if len(self.puuid_queue) < self.config.max_queue_size:
                        self.puuid_queue.append((puuid, reg))
                        self.seen_puuids.add(puuid)
                        self.stats.players_discovered += 1
            
            return MatchRecord(
                match_id=match_id,
                game_version=game_version,
                region=region,
                game_duration=info.get("gameDuration", 0),
                game_mode=info.get("gameMode", ""),
                queue_id=queue_id,
                blue_team_win=blue_win,
                blue_team_champions=blue_team,
                red_team_champions=red_team,
                blue_team_items=blue_items,
                red_team_items=red_items,
                timestamp=info.get("gameCreation", 0)
            )
            
        except Exception as e:
            logger.error(f"Failed to parse match {match_id}: {e}")
            self.stats.errors += 1
            return None
    
    async def fetch_high_elo_players(self, region: str) -> List[str]:
        """
        Fetch high ELO player PUUIDs to seed the crawler.
        Gets Challenger/GM/Master players.
        """
        puuids: List[str] = []
        
        league_urls = [
            (self.CHALLENGER_LEAGUE_URL, "RANKED_SOLO_5x5"),
            (self.GRANDMASTER_LEAGUE_URL, "RANKED_SOLO_5x5"),
            (self.MASTER_LEAGUE_URL, "RANKED_SOLO_5x5")
        ]
        
        for url_template, queue in league_urls:
            url = url_template.format(region=region, queue=queue)
            data, status = await self._make_request(url)
            
            if data and "entries" in data:
                entries = data["entries"]
                
                # Riot API now returns PUUID directly in league entries
                for entry in entries[:50]:  # Limit per tier
                    puuid = entry.get("puuid")
                    if puuid:
                        puuids.append(puuid)
                    else:
                        # Fallback: Old API format with summonerId
                        summoner_id = entry.get("summonerId")
                        if summoner_id:
                            summoner_url = f"https://{region}.api.riotgames.com/lol/summoner/v4/summoners/{summoner_id}"
                            summoner_data, _ = await self._make_request(summoner_url)
                            if summoner_data and "puuid" in summoner_data:
                                puuids.append(summoner_data["puuid"])
                            
                    # Rate limit friendly
                    if len(puuids) >= 100:
                        break
                        
        logger.info(f"Fetched {len(puuids)} high ELO players from {region}")
        return puuids
    
    # ==================== CRAWL LOGIC ====================
    
    async def crawl_player(self, puuid: str, region: str) -> int:
        """
        Crawl a single player's recent matches.
        
        Returns: Number of new matches stored
        """
        self.stats.players_crawled += 1
        
        # Get match IDs
        match_ids = await self.fetch_match_ids(
            puuid, region, 
            count=self.config.max_matches_per_player
        )
        
        if not match_ids:
            return 0
            
        # Fetch match details SEQUENTIALLY to avoid rate limits
        valid_matches: List[MatchRecord] = []
        for match_id in match_ids:
            if match_id in self.seen_matches:
                continue
            
            match = await self.fetch_match_details(match_id, region)
            if match is not None:
                valid_matches.append(match)
            
            # Small delay between requests
            await asyncio.sleep(0.1)
        
        for match in valid_matches:
            self.seen_matches.add(match.match_id)
            self.match_buffer.append(match)
            
        # Batch insert when buffer is full
        if len(self.match_buffer) >= self.config.batch_size:
            await self._flush_buffer()
            
        # Update player record
        player = PlayerRecord(
            puuid=puuid,
            region=region,
            last_crawled=datetime.now(),
            matches_found=len(valid_matches)
        )
        self.db.upsert_player(player)
        
        return len(valid_matches)
    
    async def _flush_buffer(self) -> None:
        """Flush match buffer to database."""
        if not self.match_buffer:
            return
            
        stored = self.db.insert_matches_batch(self.match_buffer)
        self.stats.matches_stored += stored
        self.match_buffer.clear()
        
        logger.info(f"Flushed {stored} matches to database (Total: {self.stats.matches_stored})")
    
    async def run(
        self, 
        region: str,
        seed_puuids: Optional[List[str]] = None,
        max_matches: Optional[int] = None,
        max_players: Optional[int] = None
    ) -> CrawlStats:
        """
        Run the crawler for a specific region.
        
        Args:
            region: Region code (e.g., "tr1", "euw1")
            seed_puuids: Optional starting PUUIDs (fetches high ELO if empty)
            max_matches: Stop after storing this many matches
            max_players: Stop after crawling this many players
            
        Returns: Crawl statistics
        """
        self.state = CrawlState.RUNNING
        self.stats = CrawlStats()
        self.semaphore = asyncio.Semaphore(self.config.max_concurrent_requests)
        
        logger.info(f"Starting crawler for region: {region}")
        
        try:
            # 1. Fetch current version
            await self.fetch_current_version()
            
            # 2. Seed the queue
            if seed_puuids:
                for puuid in seed_puuids:
                    if puuid not in self.seen_puuids:
                        self.puuid_queue.append((puuid, region))
                        self.seen_puuids.add(puuid)
            else:
                # Fetch high ELO players as seeds
                high_elo = await self.fetch_high_elo_players(region)
                for puuid in high_elo:
                    if puuid not in self.seen_puuids:
                        self.puuid_queue.append((puuid, region))
                        self.seen_puuids.add(puuid)
                        
            logger.info(f"Queue seeded with {len(self.puuid_queue)} players")
            
            # 3. Crawl loop
            while self.puuid_queue and self.state == CrawlState.RUNNING:
                # Check limits
                if max_matches and self.stats.matches_stored >= max_matches:
                    logger.info(f"Reached max matches limit: {max_matches}")
                    break
                    
                if max_players and self.stats.players_crawled >= max_players:
                    logger.info(f"Reached max players limit: {max_players}")
                    break
                
                # Get next player
                puuid, reg = self.puuid_queue.popleft()
                
                # Check if recently crawled
                if not self.db.should_crawl_player(puuid, self.config.player_rescan_hours):
                    continue
                    
                # Crawl
                try:
                    await self.crawl_player(puuid, reg)
                except Exception as e:
                    logger.error(f"Failed to crawl {puuid}: {e}")
                    self.stats.errors += 1
                    
                # Progress log
                if self.stats.players_crawled % 10 == 0:
                    logger.info(
                        f"Progress: {self.stats.players_crawled} players, "
                        f"{self.stats.matches_stored} matches, "
                        f"Queue: {len(self.puuid_queue)}"
                    )
            
            # 4. Final flush
            await self._flush_buffer()
            
        finally:
            await self.close()
            self.stats.log_summary()
            
        return self.stats
    
    async def run_continuous(
        self, 
        regions: List[str],
        batch_size: int = 100
    ) -> None:
        """
        Run continuous crawling across multiple regions.
        Rotates between regions to balance data collection.
        """
        self.state = CrawlState.RUNNING
        region_idx = 0
        
        logger.info(f"Starting continuous crawl for regions: {regions}")
        
        try:
            while self.state == CrawlState.RUNNING:
                region = regions[region_idx % len(regions)]
                
                # Run batch for this region
                await self.run(
                    region=region,
                    max_players=batch_size
                )
                
                # Rotate
                region_idx += 1
                
                # Cool down between regions
                await asyncio.sleep(5)
                
        except KeyboardInterrupt:
            logger.info("Crawler stopped by user")
            self.state = CrawlState.STOPPED
            
        finally:
            await self.close()


async def main_crawl(
    region: str = "tr1",
    api_key: Optional[str] = None,
    max_matches: int = 10000,
    max_players: int = 500
) -> CrawlStats:
    """
    Main entry point for crawling.
    
    Args:
        region: Target region
        api_key: Riot API key (or use env/file)
        max_matches: Maximum matches to collect
        max_players: Maximum players to crawl
        
    Returns: Crawl statistics
    """
    # Setup config
    if api_key:
        config.crawler.api_key = api_key
        
    if not config.crawler.api_key:
        raise ValueError(
            "Riot API key required. Set RIOT_API_KEY env var or pass api_key parameter."
        )
    
    crawler = MatchCrawler()
    return await crawler.run(
        region=region,
        max_matches=max_matches,
        max_players=max_players
    )


if __name__ == "__main__":
    import sys
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )
    
    region = sys.argv[1] if len(sys.argv) > 1 else "tr1"
    
    asyncio.run(main_crawl(region=region))
