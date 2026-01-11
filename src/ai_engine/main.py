#!/usr/bin/env python3
"""
DraftBetter AI Engine - Command Line Interface

Usage:
    python main.py --mode crawl --region tr1 [--max-matches 10000]
    python main.py --mode train --version 14.24 [--epochs 50]
    python main.py --mode predict --blue "1,2,3,4,5" --red "6,7,8,9,10"
    python main.py --mode stats
    python main.py --mode clean --keep-version 14.24
"""

import argparse
import asyncio
import logging
import sys
import json
from pathlib import Path
from typing import List, Optional

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.ai_engine.config import config, initialize_config
from src.ai_engine.database import get_database, MatchDatabase
from src.ai_engine.crawler import MatchCrawler, main_crawl
from src.ai_engine.train import train_model
from src.ai_engine.model import (
    MetaAwarePredictor, 
    get_device, 
    get_device_info,
    load_model
)

logger = logging.getLogger(__name__)


def setup_logging(verbose: bool = False) -> None:
    """Configure logging."""
    level = logging.DEBUG if verbose else logging.INFO
    
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler("ai_engine.log")
        ]
    )


async def cmd_crawl(args: argparse.Namespace) -> int:
    """Run the crawler."""
    logger.info(f"Starting crawler for region: {args.region}")
    
    if not config.crawler.api_key:
        if args.api_key:
            config.crawler.api_key = args.api_key
        else:
            logger.error("Riot API key required. Set RIOT_API_KEY env var or use --api-key")
            return 1
    
    try:
        stats = await main_crawl(
            region=args.region,
            max_matches=args.max_matches,
            max_players=args.max_players
        )
        
        logger.info(f"Crawl complete: {stats.matches_stored} matches stored")
        return 0
        
    except Exception as e:
        logger.error(f"Crawl failed: {e}")
        return 1


def cmd_train(args: argparse.Namespace) -> int:
    """Run the training pipeline."""
    logger.info(f"Starting training for patch {args.version}")
    
    # Check data availability
    db = get_database()
    match_count = db.get_match_count(args.version)
    
    if match_count < 100:
        logger.error(f"Insufficient data: only {match_count} matches for patch {args.version}")
        logger.error("Run crawler first to collect more data.")
        return 1
        
    logger.info(f"Found {match_count} matches for training")
    
    try:
        model, metrics = train_model(
            version=args.version,
            epochs=args.epochs,
            batch_size=args.batch_size,
            learning_rate=args.learning_rate,
            use_items=args.use_items,
            max_samples=args.max_samples
        )
        
        logger.info(f"Training complete!")
        logger.info(f"Best validation loss: {metrics.best_val_loss:.4f}")
        logger.info(f"Best validation accuracy: {metrics.best_val_acc:.4f}")
        
        # Save metrics
        metrics_path = config.model.checkpoint_dir / "training_metrics.json"
        with open(metrics_path, "w") as f:
            json.dump(metrics.to_dict(), f, indent=2)
        logger.info(f"Metrics saved to {metrics_path}")
        
        return 0
        
    except Exception as e:
        logger.error(f"Training failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


def cmd_predict(args: argparse.Namespace) -> int:
    """Make a prediction with trained model."""
    model_path = config.model.best_model_path
    
    if not model_path.exists():
        logger.error(f"No trained model found at {model_path}")
        logger.error("Run training first with: python main.py --mode train")
        return 1
    
    # Parse team compositions
    try:
        blue_team = [int(x.strip()) for x in args.blue.split(",")]
        red_team = [int(x.strip()) for x in args.red.split(",")]
        
        if len(blue_team) != 5 or len(red_team) != 5:
            raise ValueError("Each team must have exactly 5 champion IDs")
            
    except ValueError as e:
        logger.error(f"Invalid team format: {e}")
        logger.error("Use comma-separated champion IDs, e.g., --blue '1,2,3,4,5'")
        return 1
    
    # Load model and predict
    try:
        model, checkpoint = load_model(model_path)
        
        win_prob = model.predict(blue_team, red_team)
        
        print(f"\n{'='*50}")
        print(f"Match Prediction")
        print(f"{'='*50}")
        print(f"Blue Team: {blue_team}")
        print(f"Red Team:  {red_team}")
        print(f"{'='*50}")
        print(f"Blue Team Win Probability: {win_prob*100:.1f}%")
        print(f"Red Team Win Probability:  {(1-win_prob)*100:.1f}%")
        print(f"{'='*50}")
        
        return 0
        
    except Exception as e:
        logger.error(f"Prediction failed: {e}")
        return 1


def cmd_stats(args: argparse.Namespace) -> int:
    """Show database statistics."""
    db = get_database()
    stats = db.get_statistics()
    
    print(f"\n{'='*50}")
    print(f"Database Statistics")
    print(f"{'='*50}")
    print(f"Total Matches: {stats['total_matches']:,}")
    print(f"Total Players: {stats['total_players']:,}")
    print(f"Queue Size:    {stats['queue_size']:,}")
    
    print(f"\nMatches by Patch:")
    for patch, count in stats.get('patches', {}).items():
        print(f"  {patch}: {count:,}")
        
    print(f"\nMatches by Region:")
    for region, count in stats.get('regions', {}).items():
        print(f"  {region}: {count:,}")
        
    print(f"\nDevice Info:")
    for key, value in get_device_info().items():
        print(f"  {key}: {value}")
        
    print(f"{'='*50}")
    
    return 0


def cmd_clean(args: argparse.Namespace) -> int:
    """Clean old patch data."""
    db = get_database()
    
    if args.keep_version:
        logger.info(f"Cleaning data, keeping only patch {args.keep_version}")
        deleted = db.delete_old_patches(args.keep_version)
        logger.info(f"Deleted {deleted} old matches")
    else:
        logger.info("Showing current data (use --keep-version to clean)")
        stats = db.get_statistics()
        for patch, count in stats.get('patches', {}).items():
            print(f"  {patch}: {count:,} matches")
            
    return 0


def cmd_info(args: argparse.Namespace) -> int:
    """Show system information."""
    print(f"\n{'='*50}")
    print(f"DraftBetter AI Engine - System Info")
    print(f"{'='*50}")
    
    # Device info
    print(f"\nCompute Device:")
    for key, value in get_device_info().items():
        print(f"  {key}: {value}")
    
    # Paths
    print(f"\nPaths:")
    print(f"  Database: {config.database.db_path}")
    print(f"  Checkpoints: {config.model.checkpoint_dir}")
    print(f"  Best Model: {config.model.best_model_path}")
    
    # Model info
    if config.model.best_model_path.exists():
        try:
            model, checkpoint = load_model(config.model.best_model_path)
            params = sum(p.numel() for p in model.parameters())
            print(f"\nTrained Model:")
            print(f"  Parameters: {params:,}")
            print(f"  Epoch: {checkpoint.get('epoch', 'unknown')}")
            print(f"  Val Loss: {checkpoint.get('metrics', {}).get('val_loss', 'unknown')}")
            print(f"  Val Acc: {checkpoint.get('metrics', {}).get('val_acc', 'unknown')}")
        except Exception as e:
            print(f"\nModel not loaded: {e}")
    else:
        print(f"\nNo trained model found.")
    
    print(f"{'='*50}")
    return 0


async def cmd_continuous_crawl(args: argparse.Namespace) -> int:
    """Run continuous multi-region crawler."""
    logger.info(f"Starting continuous crawler for regions: {args.regions}")
    
    if not config.crawler.api_key:
        if args.api_key:
            config.crawler.api_key = args.api_key
        else:
            logger.error("Riot API key required.")
            return 1
    
    regions = [r.strip() for r in args.regions.split(",")]
    
    crawler = MatchCrawler()
    await crawler.run_continuous(regions=regions, batch_size=args.batch_size)
    
    return 0


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="DraftBetter AI Engine - Match Prediction System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Crawl matches from Turkey region
  python main.py --mode crawl --region tr1 --max-matches 5000
  
  # Train model on patch 14.24
  python main.py --mode train --version 14.24 --epochs 30
  
  # Predict match outcome
  python main.py --mode predict --blue "1,2,3,4,5" --red "6,7,8,9,10"
  
  # Show database stats
  python main.py --mode stats
  
  # Clean old patch data
  python main.py --mode clean --keep-version 14.24
        """
    )
    
    parser.add_argument(
        "--mode", "-m",
        type=str,
        required=True,
        choices=["crawl", "train", "predict", "stats", "clean", "info", "continuous"],
        help="Operation mode"
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")
    parser.add_argument("--api-key", type=str, help="Riot API key")
    
    # Crawler args
    parser.add_argument("--region", type=str, default="tr1", help="Region code")
    parser.add_argument("--regions", type=str, default="tr1,euw1", help="Comma-separated regions for continuous mode")
    parser.add_argument("--max-matches", type=int, default=10000, help="Max matches to crawl")
    parser.add_argument("--max-players", type=int, default=500, help="Max players to crawl")
    
    # Training args
    parser.add_argument("--version", type=str, default="14.24", help="Patch version for training")
    parser.add_argument("--epochs", type=int, default=50, help="Training epochs")
    parser.add_argument("--batch-size", type=int, default=256, help="Batch size")
    parser.add_argument("--learning-rate", "--lr", type=float, default=1e-3, help="Learning rate")
    parser.add_argument("--use-items", action="store_true", help="Include item data")
    parser.add_argument("--max-samples", type=int, default=None, help="Max training samples")
    
    # Prediction args
    parser.add_argument("--blue", type=str, help="Blue team champion IDs (comma-separated)")
    parser.add_argument("--red", type=str, help="Red team champion IDs (comma-separated)")
    
    # Clean args
    parser.add_argument("--keep-version", type=str, help="Version to keep when cleaning")
    
    args = parser.parse_args()
    
    # Setup
    setup_logging(args.verbose)
    initialize_config()
    
    # Dispatch to command
    if args.mode == "crawl":
        return asyncio.run(cmd_crawl(args))
    elif args.mode == "continuous":
        return asyncio.run(cmd_continuous_crawl(args))
    elif args.mode == "train":
        return cmd_train(args)
    elif args.mode == "predict":
        return cmd_predict(args)
    elif args.mode == "stats":
        return cmd_stats(args)
    elif args.mode == "clean":
        return cmd_clean(args)
    elif args.mode == "info":
        return cmd_info(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
