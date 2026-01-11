"""
Utility functions for the AI Engine.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Set
from datetime import datetime

logger = logging.getLogger(__name__)


# ==================== Champion Data ====================

# Path to champion data in DraftBetter
CHAMPION_DATA_PATH = Path(__file__).parent.parent / "data" / "champions_raw.json"


def load_champion_mapping() -> Dict[int, str]:
    """
    Load champion ID to name mapping from DraftBetter data.
    
    Returns: Dict mapping champion_id -> champion_name
    """
    try:
        if CHAMPION_DATA_PATH.exists():
            with open(CHAMPION_DATA_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                
            mapping = {}
            for champ_name, champ_data in data.get("data", {}).items():
                champ_id = int(champ_data.get("key", 0))
                if champ_id > 0:
                    mapping[champ_id] = champ_name
                    
            logger.info(f"Loaded {len(mapping)} champions from local data")
            return mapping
            
    except Exception as e:
        logger.warning(f"Failed to load champion data: {e}")
        
    return {}


def get_champion_name(champion_id: int, mapping: Optional[Dict[int, str]] = None) -> str:
    """Get champion name from ID."""
    if mapping is None:
        mapping = load_champion_mapping()
    return mapping.get(champion_id, f"Champion_{champion_id}")


def get_all_champion_ids(mapping: Optional[Dict[int, str]] = None) -> List[int]:
    """Get list of all champion IDs."""
    if mapping is None:
        mapping = load_champion_mapping()
    return list(mapping.keys())


# ==================== Version Utilities ====================

def parse_version(version_string: str) -> tuple:
    """
    Parse version string into comparable tuple.
    
    Examples:
        "14.24.1" -> (14, 24, 1)
        "14.24.636.9802" -> (14, 24, 636, 9802)
    """
    parts = version_string.split(".")
    return tuple(int(p) for p in parts if p.isdigit())


def version_matches(game_version: str, target_version: str) -> bool:
    """
    Check if game version matches target version (major.minor).
    
    Args:
        game_version: Full game version (e.g., "14.24.636.9802")
        target_version: Target version (e.g., "14.24" or "14.24.1")
        
    Returns: True if major.minor match
    """
    game_parts = game_version.split(".")[:2]
    target_parts = target_version.split(".")[:2]
    return game_parts == target_parts


def get_major_minor(version: str) -> str:
    """Extract major.minor from version string."""
    parts = version.split(".")[:2]
    return ".".join(parts)


# ==================== Data Validation ====================

def validate_team_composition(team: List[int]) -> tuple:
    """
    Validate a team composition.
    
    Returns: (is_valid, error_message)
    """
    if not isinstance(team, list):
        return False, "Team must be a list"
        
    if len(team) != 5:
        return False, f"Team must have 5 champions, got {len(team)}"
        
    # Check for invalid IDs
    for i, champ_id in enumerate(team):
        if not isinstance(champ_id, int):
            return False, f"Champion ID at position {i} must be integer"
        if champ_id < 0:
            return False, f"Champion ID at position {i} cannot be negative"
            
    # Check for duplicates (excluding zeros)
    non_zero = [c for c in team if c > 0]
    if len(non_zero) != len(set(non_zero)):
        return False, "Team contains duplicate champions"
        
    return True, ""


def validate_match_data(
    blue_team: List[int],
    red_team: List[int],
    blue_win: bool
) -> tuple:
    """
    Validate match data for training.
    
    Returns: (is_valid, error_message)
    """
    # Validate teams
    valid, msg = validate_team_composition(blue_team)
    if not valid:
        return False, f"Blue team invalid: {msg}"
        
    valid, msg = validate_team_composition(red_team)
    if not valid:
        return False, f"Red team invalid: {msg}"
        
    # Check no overlap
    blue_set = set(c for c in blue_team if c > 0)
    red_set = set(c for c in red_team if c > 0)
    
    overlap = blue_set & red_set
    if overlap:
        return False, f"Teams share champions: {overlap}"
        
    # All champions should be picked
    if 0 in blue_team or 0 in red_team:
        return False, "Match has unpicked champions"
        
    return True, ""


# ==================== File Utilities ====================

def ensure_directories() -> None:
    """Ensure all required directories exist."""
    from .config import config
    
    directories = [
        config.database.db_path.parent,
        config.model.checkpoint_dir,
        config.model.best_model_path.parent,
        Path("logs"),
        Path("data")
    ]
    
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)
        

def cleanup_old_checkpoints(checkpoint_dir: Path, keep_last: int = 5) -> int:
    """
    Clean up old checkpoint files, keeping only the most recent.
    
    Returns: Number of files deleted
    """
    checkpoints = sorted(
        checkpoint_dir.glob("*.pt"),
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )
    
    to_delete = checkpoints[keep_last:]
    
    for ckpt in to_delete:
        try:
            ckpt.unlink()
        except Exception as e:
            logger.warning(f"Failed to delete {ckpt}: {e}")
            
    return len(to_delete)


# ==================== Logging Utilities ====================

def setup_file_logging(log_dir: Path = Path("logs")) -> None:
    """Setup file logging in addition to console."""
    log_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"ai_engine_{timestamp}.log"
    
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    )
    
    logging.getLogger().addHandler(file_handler)
    logger.info(f"Logging to {log_file}")


# ==================== Statistics ====================

def calculate_accuracy(predictions: List[float], labels: List[int]) -> float:
    """Calculate binary classification accuracy."""
    if len(predictions) != len(labels):
        raise ValueError("Predictions and labels must have same length")
        
    correct = sum(
        1 for pred, label in zip(predictions, labels)
        if (pred >= 0.5 and label == 1) or (pred < 0.5 and label == 0)
    )
    
    return correct / len(predictions) if predictions else 0.0


def calculate_precision_recall(
    predictions: List[float],
    labels: List[int],
    threshold: float = 0.5
) -> Dict[str, float]:
    """Calculate precision and recall."""
    tp = fp = tn = fn = 0
    
    for pred, label in zip(predictions, labels):
        pred_class = 1 if pred >= threshold else 0
        
        if pred_class == 1 and label == 1:
            tp += 1
        elif pred_class == 1 and label == 0:
            fp += 1
        elif pred_class == 0 and label == 0:
            tn += 1
        else:
            fn += 1
            
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    
    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "true_positives": tp,
        "false_positives": fp,
        "true_negatives": tn,
        "false_negatives": fn
    }
