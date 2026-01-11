"""
High-Performance SQLite Storage for Match Data.

Features:
- WAL mode for concurrent reads during writes
- Batch inserts for reduced disk I/O
- Proper indexing for fast queries
- Connection pooling for thread safety
"""

import sqlite3
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
import threading

from .config import config, DatabaseConfig

logger = logging.getLogger(__name__)


@dataclass
class MatchRecord:
    """Represents a stored match record."""
    match_id: str
    game_version: str
    region: str
    game_duration: int
    game_mode: str
    queue_id: int
    blue_team_win: bool
    blue_team_champions: List[int]
    red_team_champions: List[int]
    blue_team_items: List[List[int]]  # 5 players x items
    red_team_items: List[List[int]]
    timestamp: int
    json_data: Optional[str] = None  # Full JSON for detailed analysis


@dataclass
class PlayerRecord:
    """Represents a tracked player."""
    puuid: str
    region: str
    last_crawled: datetime
    matches_found: int = 0
    tier: Optional[str] = None
    rank: Optional[str] = None


class MatchDatabase:
    """
    SQLite database manager with optimizations for high-throughput match storage.
    
    Uses WAL mode and batch operations to maximize write performance while
    maintaining data integrity.
    """
    
    # Thread-local storage for connections
    _local = threading.local()
    
    def __init__(self, db_config: Optional[DatabaseConfig] = None):
        self.config = db_config or config.database
        self.db_path = Path(self.config.db_path)
        self._ensure_directory()
        self._init_schema()
        
    def _ensure_directory(self) -> None:
        """Ensure the database directory exists."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
    @contextmanager
    def get_connection(self):
        """
        Get a thread-safe database connection.
        Uses thread-local storage to ensure each thread has its own connection.
        """
        if not hasattr(self._local, 'connection') or self._local.connection is None:
            self._local.connection = self._create_connection()
            
        try:
            yield self._local.connection
        except Exception as e:
            self._local.connection.rollback()
            raise e
            
    def _create_connection(self) -> sqlite3.Connection:
        """Create an optimized SQLite connection."""
        conn = sqlite3.Connection(
            str(self.db_path),
            timeout=30.0,
            isolation_level=None  # Autocommit mode, we'll manage transactions
        )
        
        # Enable WAL mode for concurrent access
        if self.config.wal_mode:
            conn.execute("PRAGMA journal_mode=WAL;")
            
        # Performance optimizations
        conn.execute(f"PRAGMA cache_size=-{self.config.cache_size_kb};")  # Negative = KB
        conn.execute(f"PRAGMA mmap_size={self.config.mmap_size_bytes};")
        conn.execute("PRAGMA synchronous=NORMAL;")  # Good balance of safety/speed
        conn.execute("PRAGMA temp_store=MEMORY;")
        conn.execute("PRAGMA busy_timeout=30000;")  # 30 second timeout
        
        # Enable foreign keys
        conn.execute("PRAGMA foreign_keys=ON;")
        
        # Row factory for dict-like access
        conn.row_factory = sqlite3.Row
        
        return conn
    
    def _init_schema(self) -> None:
        """Initialize database schema with proper indexes."""
        with self.get_connection() as conn:
            conn.executescript("""
                -- Main matches table
                CREATE TABLE IF NOT EXISTS matches (
                    match_id TEXT PRIMARY KEY,
                    game_version TEXT NOT NULL,
                    region TEXT NOT NULL,
                    game_duration INTEGER NOT NULL,
                    game_mode TEXT NOT NULL,
                    queue_id INTEGER NOT NULL,
                    blue_team_win INTEGER NOT NULL,
                    blue_team_champions TEXT NOT NULL,  -- JSON array
                    red_team_champions TEXT NOT NULL,   -- JSON array
                    blue_team_items TEXT,               -- JSON 2D array
                    red_team_items TEXT,                -- JSON 2D array
                    game_timestamp INTEGER NOT NULL,
                    json_data TEXT,                     -- Full match JSON (optional)
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
                
                -- Players tracking table
                CREATE TABLE IF NOT EXISTS players (
                    puuid TEXT PRIMARY KEY,
                    region TEXT NOT NULL,
                    last_crawled TEXT NOT NULL,
                    matches_found INTEGER DEFAULT 0,
                    tier TEXT,
                    rank TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
                
                -- Crawl queue for async processing
                CREATE TABLE IF NOT EXISTS crawl_queue (
                    puuid TEXT PRIMARY KEY,
                    region TEXT NOT NULL,
                    priority INTEGER DEFAULT 0,
                    added_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
                
                -- Version tracking for data freshness
                CREATE TABLE IF NOT EXISTS patch_versions (
                    version TEXT PRIMARY KEY,
                    first_seen TEXT DEFAULT CURRENT_TIMESTAMP,
                    match_count INTEGER DEFAULT 0
                );
                
                -- Indexes for fast queries
                CREATE INDEX IF NOT EXISTS idx_matches_version ON matches(game_version);
                CREATE INDEX IF NOT EXISTS idx_matches_region ON matches(region);
                CREATE INDEX IF NOT EXISTS idx_matches_queue ON matches(queue_id);
                CREATE INDEX IF NOT EXISTS idx_matches_timestamp ON matches(game_timestamp);
                CREATE INDEX IF NOT EXISTS idx_matches_version_queue ON matches(game_version, queue_id);
                
                CREATE INDEX IF NOT EXISTS idx_players_region ON players(region);
                CREATE INDEX IF NOT EXISTS idx_players_crawled ON players(last_crawled);
                CREATE INDEX IF NOT EXISTS idx_players_tier ON players(tier);
                
                CREATE INDEX IF NOT EXISTS idx_queue_priority ON crawl_queue(priority DESC, added_at);
                CREATE INDEX IF NOT EXISTS idx_queue_region ON crawl_queue(region);
            """)
            logger.info(f"Database initialized at {self.db_path}")
    
    # ==================== MATCH OPERATIONS ====================
    
    def insert_match(self, match: MatchRecord) -> bool:
        """Insert a single match record."""
        try:
            with self.get_connection() as conn:
                conn.execute("""
                    INSERT OR IGNORE INTO matches 
                    (match_id, game_version, region, game_duration, game_mode, queue_id,
                     blue_team_win, blue_team_champions, red_team_champions,
                     blue_team_items, red_team_items, game_timestamp, json_data)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    match.match_id,
                    match.game_version,
                    match.region,
                    match.game_duration,
                    match.game_mode,
                    match.queue_id,
                    1 if match.blue_team_win else 0,
                    json.dumps(match.blue_team_champions),
                    json.dumps(match.red_team_champions),
                    json.dumps(match.blue_team_items) if match.blue_team_items else None,
                    json.dumps(match.red_team_items) if match.red_team_items else None,
                    match.timestamp,
                    match.json_data
                ))
                return True
        except sqlite3.Error as e:
            logger.error(f"Failed to insert match {match.match_id}: {e}")
            return False
    
    def insert_matches_batch(self, matches: List[MatchRecord]) -> int:
        """
        Insert multiple matches in a single transaction.
        Uses executemany for optimal performance.
        
        Returns: Number of matches successfully inserted.
        """
        if not matches:
            return 0
            
        data = [
            (
                m.match_id, m.game_version, m.region, m.game_duration,
                m.game_mode, m.queue_id, 1 if m.blue_team_win else 0,
                json.dumps(m.blue_team_champions), json.dumps(m.red_team_champions),
                json.dumps(m.blue_team_items) if m.blue_team_items else None,
                json.dumps(m.red_team_items) if m.red_team_items else None,
                m.timestamp, m.json_data
            )
            for m in matches
        ]
        
        try:
            with self.get_connection() as conn:
                conn.execute("BEGIN TRANSACTION;")
                conn.executemany("""
                    INSERT OR IGNORE INTO matches 
                    (match_id, game_version, region, game_duration, game_mode, queue_id,
                     blue_team_win, blue_team_champions, red_team_champions,
                     blue_team_items, red_team_items, game_timestamp, json_data)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, data)
                conn.execute("COMMIT;")
                
                # Update patch version counts
                self._update_patch_counts(conn, matches)
                
                logger.info(f"Batch inserted {len(matches)} matches")
                return len(matches)
                
        except sqlite3.Error as e:
            logger.error(f"Batch insert failed: {e}")
            with self.get_connection() as conn:
                conn.execute("ROLLBACK;")
            return 0
    
    def _update_patch_counts(self, conn: sqlite3.Connection, matches: List[MatchRecord]) -> None:
        """Update patch version match counts."""
        version_counts: Dict[str, int] = {}
        for m in matches:
            version_counts[m.game_version] = version_counts.get(m.game_version, 0) + 1
            
        for version, count in version_counts.items():
            conn.execute("""
                INSERT INTO patch_versions (version, match_count) 
                VALUES (?, ?)
                ON CONFLICT(version) DO UPDATE SET match_count = match_count + ?
            """, (version, count, count))
    
    def match_exists(self, match_id: str) -> bool:
        """Check if a match already exists."""
        with self.get_connection() as conn:
            result = conn.execute(
                "SELECT 1 FROM matches WHERE match_id = ?", (match_id,)
            ).fetchone()
            return result is not None
    
    def get_matches_by_version(
        self, 
        version: str, 
        queue_id: int = 420,  # Ranked Solo/Duo
        limit: Optional[int] = None
    ) -> Iterator[MatchRecord]:
        """
        Stream matches for a specific game version.
        Yields MatchRecord objects for memory efficiency.
        """
        query = """
            SELECT * FROM matches 
            WHERE game_version LIKE ? AND queue_id = ?
            ORDER BY game_timestamp DESC
        """
        params: List[Any] = [f"{version}%", queue_id]
        
        if limit:
            query += " LIMIT ?"
            params.append(limit)
            
        with self.get_connection() as conn:
            cursor = conn.execute(query, params)
            for row in cursor:
                yield MatchRecord(
                    match_id=row['match_id'],
                    game_version=row['game_version'],
                    region=row['region'],
                    game_duration=row['game_duration'],
                    game_mode=row['game_mode'],
                    queue_id=row['queue_id'],
                    blue_team_win=bool(row['blue_team_win']),
                    blue_team_champions=json.loads(row['blue_team_champions']),
                    red_team_champions=json.loads(row['red_team_champions']),
                    blue_team_items=json.loads(row['blue_team_items']) if row['blue_team_items'] else [],
                    red_team_items=json.loads(row['red_team_items']) if row['red_team_items'] else [],
                    timestamp=row['game_timestamp'],
                    json_data=row['json_data']
                )
    
    def get_match_count(self, version: Optional[str] = None, queue_id: int = 420) -> int:
        """Get total match count, optionally filtered by version."""
        with self.get_connection() as conn:
            if version:
                result = conn.execute(
                    "SELECT COUNT(*) FROM matches WHERE game_version LIKE ? AND queue_id = ?",
                    (f"{version}%", queue_id)
                ).fetchone()
            else:
                result = conn.execute(
                    "SELECT COUNT(*) FROM matches WHERE queue_id = ?",
                    (queue_id,)
                ).fetchone()
            return result[0] if result else 0
    
    def delete_old_patches(self, current_version: str) -> int:
        """
        Delete matches from older patches to keep database focused.
        Returns number of deleted matches.
        """
        major_minor = ".".join(current_version.split(".")[:2])
        
        with self.get_connection() as conn:
            # Count before delete
            old_count = conn.execute(
                "SELECT COUNT(*) FROM matches WHERE game_version NOT LIKE ?",
                (f"{major_minor}%",)
            ).fetchone()[0]
            
            if old_count > 0:
                conn.execute(
                    "DELETE FROM matches WHERE game_version NOT LIKE ?",
                    (f"{major_minor}%",)
                )
                conn.execute("VACUUM;")  # Reclaim space
                logger.info(f"Deleted {old_count} matches from old patches")
                
            return old_count
    
    # ==================== PLAYER OPERATIONS ====================
    
    def upsert_player(self, player: PlayerRecord) -> bool:
        """Insert or update a player record."""
        try:
            with self.get_connection() as conn:
                conn.execute("""
                    INSERT INTO players (puuid, region, last_crawled, matches_found, tier, rank)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(puuid) DO UPDATE SET
                        last_crawled = ?,
                        matches_found = matches_found + ?,
                        tier = COALESCE(?, tier),
                        rank = COALESCE(?, rank),
                        updated_at = CURRENT_TIMESTAMP
                """, (
                    player.puuid, player.region, player.last_crawled.isoformat(),
                    player.matches_found, player.tier, player.rank,
                    player.last_crawled.isoformat(), player.matches_found, player.tier, player.rank
                ))
                return True
        except sqlite3.Error as e:
            logger.error(f"Failed to upsert player {player.puuid}: {e}")
            return False
    
    def should_crawl_player(self, puuid: str, hours: int = 24) -> bool:
        """Check if a player should be crawled (not crawled recently)."""
        with self.get_connection() as conn:
            result = conn.execute(
                "SELECT last_crawled FROM players WHERE puuid = ?", (puuid,)
            ).fetchone()
            
            if not result:
                return True  # Never crawled
                
            last_crawled = datetime.fromisoformat(result['last_crawled'])
            return datetime.now() - last_crawled > timedelta(hours=hours)
    
    def get_players_to_crawl(self, region: str, limit: int = 100) -> List[str]:
        """Get PUUIDs that need crawling in a region."""
        cutoff = (datetime.now() - timedelta(hours=config.crawler.player_rescan_hours)).isoformat()
        
        with self.get_connection() as conn:
            results = conn.execute("""
                SELECT puuid FROM players 
                WHERE region = ? AND last_crawled < ?
                ORDER BY last_crawled ASC
                LIMIT ?
            """, (region, cutoff, limit)).fetchall()
            
            return [r['puuid'] for r in results]
    
    # ==================== QUEUE OPERATIONS ====================
    
    def add_to_queue(self, puuids: List[Tuple[str, str]], priority: int = 0) -> int:
        """
        Add PUUIDs to crawl queue.
        
        Args:
            puuids: List of (puuid, region) tuples
            priority: Higher = crawled sooner
            
        Returns: Number of PUUIDs added (excludes duplicates)
        """
        if not puuids:
            return 0
            
        data = [(p, r, priority) for p, r in puuids]
        
        with self.get_connection() as conn:
            conn.execute("BEGIN TRANSACTION;")
            conn.executemany("""
                INSERT OR IGNORE INTO crawl_queue (puuid, region, priority)
                VALUES (?, ?, ?)
            """, data)
            conn.execute("COMMIT;")
            
        return len(puuids)
    
    def pop_from_queue(self, region: str, count: int = 10) -> List[Tuple[str, str]]:
        """
        Pop PUUIDs from queue for crawling.
        Returns list of (puuid, region) tuples.
        """
        with self.get_connection() as conn:
            results = conn.execute("""
                SELECT puuid, region FROM crawl_queue
                WHERE region = ?
                ORDER BY priority DESC, added_at ASC
                LIMIT ?
            """, (region, count)).fetchall()
            
            if results:
                puuids = [r['puuid'] for r in results]
                placeholders = ",".join("?" * len(puuids))
                conn.execute(f"DELETE FROM crawl_queue WHERE puuid IN ({placeholders})", puuids)
                
            return [(r['puuid'], r['region']) for r in results]
    
    def get_queue_size(self, region: Optional[str] = None) -> int:
        """Get current queue size."""
        with self.get_connection() as conn:
            if region:
                result = conn.execute(
                    "SELECT COUNT(*) FROM crawl_queue WHERE region = ?", (region,)
                ).fetchone()
            else:
                result = conn.execute("SELECT COUNT(*) FROM crawl_queue").fetchone()
            return result[0] if result else 0
    
    # ==================== STATISTICS ====================
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get database statistics."""
        with self.get_connection() as conn:
            stats = {
                "total_matches": conn.execute("SELECT COUNT(*) FROM matches").fetchone()[0],
                "total_players": conn.execute("SELECT COUNT(*) FROM players").fetchone()[0],
                "queue_size": conn.execute("SELECT COUNT(*) FROM crawl_queue").fetchone()[0],
            }
            
            # Matches by version
            versions = conn.execute("""
                SELECT version, match_count FROM patch_versions
                ORDER BY first_seen DESC LIMIT 5
            """).fetchall()
            stats["patches"] = {r['version']: r['match_count'] for r in versions}
            
            # Matches by region
            regions = conn.execute("""
                SELECT region, COUNT(*) as count FROM matches
                GROUP BY region ORDER BY count DESC
            """).fetchall()
            stats["regions"] = {r['region']: r['count'] for r in regions}
            
            return stats
    
    def close(self) -> None:
        """Close database connection."""
        if hasattr(self._local, 'connection') and self._local.connection:
            self._local.connection.close()
            self._local.connection = None


# Singleton instance
_db_instance: Optional[MatchDatabase] = None


def get_database() -> MatchDatabase:
    """Get the singleton database instance."""
    global _db_instance
    if _db_instance is None:
        _db_instance = MatchDatabase()
    return _db_instance
