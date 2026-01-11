"""
Configuration settings for the AI Engine.
"""

import os
from dataclasses import dataclass, field
from typing import List, Optional
from pathlib import Path


@dataclass
class CrawlerConfig:
    """Crawler configuration settings."""
    
    # Riot API Settings
    api_key: str = field(default_factory=lambda: os.getenv("RIOT_API_KEY", ""))
    
    # Rate Limiting (Development key limits - conservative)
    requests_per_second: int = 15  # Stay under 20/s limit
    requests_per_two_minutes: int = 80  # Stay under 100/2min limit
    
    # Crawling Parameters
    max_concurrent_requests: int = 3  # Low concurrency to avoid rate limits
    batch_size: int = 100  # Matches to commit per batch
    max_matches_per_player: int = 10  # Recent matches to fetch per player
    player_rescan_hours: int = 24  # Don't rescan a player within this window
    
    # Queue Management
    max_queue_size: int = 10000  # Max PUUIDs to hold in memory
    
    # Regions
    regions: List[str] = field(default_factory=lambda: [
        "tr1", "euw1", "eun1", "na1", "kr", "jp1", "br1", "la1", "la2", "oc1", "ru", "ph2", "sg2", "th2", "tw2", "vn2"
    ])
    
    # Routing regions for match-v5
    routing_regions: dict = field(default_factory=lambda: {
        "na1": "americas", "br1": "americas", "la1": "americas", "la2": "americas",
        "euw1": "europe", "eun1": "europe", "tr1": "europe", "ru": "europe",
        "kr": "asia", "jp1": "asia",
        "oc1": "sea", "ph2": "sea", "sg2": "sea", "th2": "sea", "tw2": "sea", "vn2": "sea"
    })


@dataclass
class DatabaseConfig:
    """Database configuration settings."""
    
    db_path: Path = field(default_factory=lambda: Path("data/matches.db"))
    wal_mode: bool = True
    cache_size_kb: int = 64000  # 64MB cache
    mmap_size_bytes: int = 268435456  # 256MB mmap
    

@dataclass
class ModelConfig:
    """Model configuration settings."""
    
    # Architecture
    embedding_dim: int = 64
    hidden_dims: List[int] = field(default_factory=lambda: [512, 256, 128])
    dropout_rate: float = 0.3
    num_champions: int = 170  # Current champion count + buffer
    
    # Training
    batch_size: int = 256
    learning_rate: float = 1e-3
    weight_decay: float = 1e-4
    epochs: int = 50
    early_stopping_patience: int = 5
    
    # Data Split
    train_ratio: float = 0.8
    val_ratio: float = 0.1
    test_ratio: float = 0.1
    
    # Checkpoints
    checkpoint_dir: Path = field(default_factory=lambda: Path("models/checkpoints"))
    best_model_path: Path = field(default_factory=lambda: Path("models/best_model.pt"))


@dataclass
class Config:
    """Master configuration."""
    
    crawler: CrawlerConfig = field(default_factory=CrawlerConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    model: ModelConfig = field(default_factory=ModelConfig)
    
    # Seed players (High ELO accounts to start crawling from)
    seed_puuids: dict = field(default_factory=lambda: {
        "tr1": [],  # Will be populated dynamically or from file
        "euw1": [],
        "kr": [],
        "na1": []
    })


# Global config instance
config = Config()


def load_api_key_from_file(filepath: str = ".riot_api_key") -> Optional[str]:
    """Load API key from a local file (not committed to git)."""
    try:
        with open(filepath, "r") as f:
            return f.read().strip()
    except FileNotFoundError:
        return None


def initialize_config() -> Config:
    """Initialize configuration with environment/file overrides."""
    global config
    
    # Try to load API key from file if not in env
    if not config.crawler.api_key:
        file_key = load_api_key_from_file()
        if file_key:
            config.crawler.api_key = file_key
    
    # Ensure directories exist
    config.database.db_path.parent.mkdir(parents=True, exist_ok=True)
    config.model.checkpoint_dir.mkdir(parents=True, exist_ok=True)
    
    return config
