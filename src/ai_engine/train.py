"""
Training Pipeline for MetaAwarePredictor.

Features:
- CurrentPatchDataset: Streams data from SQLite
- Device-agnostic training loop
- Mixed precision training support
- Learning rate scheduling
- Comprehensive metrics tracking
"""

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader, random_split
from torch.cuda.amp import GradScaler, autocast
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Tuple, Iterator
from dataclasses import dataclass, field
import time

from .config import config, ModelConfig
from .database import get_database, MatchRecord
from .model import (
    MetaAwarePredictor, 
    MetaAwarePredictorWithItems,
    get_device, 
    EarlyStopping, 
    save_model
)

logger = logging.getLogger(__name__)


@dataclass
class TrainingMetrics:
    """Track training metrics."""
    train_loss: List[float] = field(default_factory=list)
    val_loss: List[float] = field(default_factory=list)
    train_acc: List[float] = field(default_factory=list)
    val_acc: List[float] = field(default_factory=list)
    learning_rates: List[float] = field(default_factory=list)
    epoch_times: List[float] = field(default_factory=list)
    
    best_val_loss: float = float('inf')
    best_val_acc: float = 0.0
    best_epoch: int = 0
    
    def update(
        self, 
        train_loss: float, 
        val_loss: float,
        train_acc: float,
        val_acc: float,
        lr: float,
        epoch_time: float
    ):
        self.train_loss.append(train_loss)
        self.val_loss.append(val_loss)
        self.train_acc.append(train_acc)
        self.val_acc.append(val_acc)
        self.learning_rates.append(lr)
        self.epoch_times.append(epoch_time)
        
        if val_loss < self.best_val_loss:
            self.best_val_loss = val_loss
            self.best_epoch = len(self.train_loss)
            
        if val_acc > self.best_val_acc:
            self.best_val_acc = val_acc
            
    def to_dict(self) -> Dict:
        return {
            'train_loss': self.train_loss,
            'val_loss': self.val_loss,
            'train_acc': self.train_acc,
            'val_acc': self.val_acc,
            'learning_rates': self.learning_rates,
            'epoch_times': self.epoch_times,
            'best_val_loss': self.best_val_loss,
            'best_val_acc': self.best_val_acc,
            'best_epoch': self.best_epoch
        }


class CurrentPatchDataset(Dataset):
    """
    PyTorch Dataset that streams match data from SQLite.
    
    Only loads data from the current patch, ensuring the model
    learns meta-specific patterns.
    """
    
    def __init__(
        self,
        version: str,
        queue_id: int = 420,
        include_items: bool = False,
        max_samples: Optional[int] = None
    ):
        """
        Args:
            version: Patch version to filter (e.g., "14.24")
            queue_id: Queue type (420=Ranked Solo, 440=Ranked Flex)
            include_items: Whether to include item data
            max_samples: Limit number of samples (for testing)
        """
        self.db = get_database()
        self.version = version
        self.queue_id = queue_id
        self.include_items = include_items
        
        # Load match IDs for indexing
        self._load_match_ids(max_samples)
        
        logger.info(f"Dataset initialized: {len(self.match_ids)} matches (v{version})")
        
    def _load_match_ids(self, max_samples: Optional[int] = None) -> None:
        """Load all match IDs for the current patch."""
        self.match_ids: List[str] = []
        
        with self.db.get_connection() as conn:
            query = """
                SELECT match_id FROM matches 
                WHERE game_version LIKE ? AND queue_id = ?
                ORDER BY game_timestamp DESC
            """
            params = [f"{self.version}%", self.queue_id]
            
            if max_samples:
                query += " LIMIT ?"
                params.append(max_samples)
                
            cursor = conn.execute(query, params)
            self.match_ids = [row[0] for row in cursor]
            
    def __len__(self) -> int:
        return len(self.match_ids)
    
    def __getitem__(self, idx: int) -> Dict[str, torch.Tensor]:
        """
        Get a single training sample.
        
        Returns dict with:
            - blue_team: (5,) champion IDs
            - red_team: (5,) champion IDs
            - label: (1,) blue team win (1) or loss (0)
            - blue_items: (5, 6) optional item IDs
            - red_items: (5, 6) optional item IDs
        """
        match_id = self.match_ids[idx]
        
        with self.db.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM matches WHERE match_id = ?", (match_id,)
            ).fetchone()
            
        if row is None:
            # Return dummy data (shouldn't happen)
            return self._get_dummy_sample()
            
        blue_champs = json.loads(row['blue_team_champions'])
        red_champs = json.loads(row['red_team_champions'])
        blue_win = row['blue_team_win']
        
        sample = {
            'blue_team': torch.tensor(blue_champs, dtype=torch.long),
            'red_team': torch.tensor(red_champs, dtype=torch.long),
            'label': torch.tensor([blue_win], dtype=torch.float)
        }
        
        if self.include_items:
            blue_items = json.loads(row['blue_team_items']) if row['blue_team_items'] else [[0]*6]*5
            red_items = json.loads(row['red_team_items']) if row['red_team_items'] else [[0]*6]*5
            
            sample['blue_items'] = torch.tensor(blue_items, dtype=torch.long)
            sample['red_items'] = torch.tensor(red_items, dtype=torch.long)
            
        return sample
    
    def _get_dummy_sample(self) -> Dict[str, torch.Tensor]:
        """Return dummy sample for error cases."""
        return {
            'blue_team': torch.zeros(5, dtype=torch.long),
            'red_team': torch.zeros(5, dtype=torch.long),
            'label': torch.tensor([0.5], dtype=torch.float)
        }
    
    def get_class_weights(self) -> torch.Tensor:
        """
        Calculate class weights for imbalanced data.
        Returns tensor for BCEWithLogitsLoss pos_weight.
        """
        with self.db.get_connection() as conn:
            result = conn.execute("""
                SELECT 
                    SUM(CASE WHEN blue_team_win = 1 THEN 1 ELSE 0 END) as blue_wins,
                    SUM(CASE WHEN blue_team_win = 0 THEN 1 ELSE 0 END) as red_wins
                FROM matches 
                WHERE game_version LIKE ? AND queue_id = ?
            """, (f"{self.version}%", self.queue_id)).fetchone()
            
        blue_wins = result[0] or 1
        red_wins = result[1] or 1
        
        # pos_weight = negative_samples / positive_samples
        pos_weight = red_wins / blue_wins
        
        return torch.tensor([pos_weight])


class StreamingDataset(Dataset):
    """
    Memory-efficient dataset that streams from database.
    Uses SQLite cursor for large datasets.
    """
    
    def __init__(
        self,
        version: str,
        queue_id: int = 420,
        batch_size: int = 1000
    ):
        self.db = get_database()
        self.version = version
        self.queue_id = queue_id
        self.batch_size = batch_size
        
        # Get total count
        self.total = self.db.get_match_count(version, queue_id)
        
        # Cache for current batch
        self._cache: List[Dict] = []
        self._cache_start: int = -1
        
    def __len__(self) -> int:
        return self.total
    
    def _load_batch(self, start_idx: int) -> None:
        """Load a batch of matches into cache."""
        with self.db.get_connection() as conn:
            rows = conn.execute("""
                SELECT blue_team_champions, red_team_champions, blue_team_win
                FROM matches 
                WHERE game_version LIKE ? AND queue_id = ?
                ORDER BY match_id
                LIMIT ? OFFSET ?
            """, (f"{self.version}%", self.queue_id, self.batch_size, start_idx)).fetchall()
            
        self._cache = []
        for row in rows:
            self._cache.append({
                'blue_team': torch.tensor(json.loads(row[0]), dtype=torch.long),
                'red_team': torch.tensor(json.loads(row[1]), dtype=torch.long),
                'label': torch.tensor([row[2]], dtype=torch.float)
            })
        self._cache_start = start_idx
        
    def __getitem__(self, idx: int) -> Dict[str, torch.Tensor]:
        # Check if idx is in cache
        if self._cache_start < 0 or idx < self._cache_start or idx >= self._cache_start + len(self._cache):
            batch_start = (idx // self.batch_size) * self.batch_size
            self._load_batch(batch_start)
            
        cache_idx = idx - self._cache_start
        if cache_idx < len(self._cache):
            return self._cache[cache_idx]
        return self._get_dummy_sample()
    
    def _get_dummy_sample(self) -> Dict[str, torch.Tensor]:
        return {
            'blue_team': torch.zeros(5, dtype=torch.long),
            'red_team': torch.zeros(5, dtype=torch.long),
            'label': torch.tensor([0.5], dtype=torch.float)
        }


class Trainer:
    """
    Training orchestrator for MetaAwarePredictor.
    
    Handles:
    - Data loading and splitting
    - Training loop with validation
    - Learning rate scheduling
    - Checkpointing
    - Mixed precision training
    """
    
    def __init__(
        self,
        model: nn.Module,
        model_config: Optional[ModelConfig] = None,
        device: Optional[torch.device] = None
    ):
        self.model = model
        self.config = model_config or config.model
        self.device = device or get_device()
        
        self.model.to(self.device)
        
        # Training components (initialized in setup)
        self.optimizer: Optional[optim.Optimizer] = None
        self.scheduler: Optional[optim.lr_scheduler._LRScheduler] = None
        self.criterion: Optional[nn.Module] = None
        self.scaler: Optional[GradScaler] = None
        
        # Data loaders
        self.train_loader: Optional[DataLoader] = None
        self.val_loader: Optional[DataLoader] = None
        self.test_loader: Optional[DataLoader] = None
        
        # Metrics
        self.metrics = TrainingMetrics()
        
        # Early stopping
        self.early_stopping: Optional[EarlyStopping] = None
        
        logger.info(f"Trainer initialized on device: {self.device}")
        
    def setup_data(
        self,
        version: str,
        queue_id: int = 420,
        include_items: bool = False,
        max_samples: Optional[int] = None
    ) -> None:
        """
        Setup data loaders with train/val/test split.
        """
        # Create full dataset
        full_dataset = CurrentPatchDataset(
            version=version,
            queue_id=queue_id,
            include_items=include_items,
            max_samples=max_samples
        )
        
        total = len(full_dataset)
        train_size = int(total * self.config.train_ratio)
        val_size = int(total * self.config.val_ratio)
        test_size = total - train_size - val_size
        
        # Split
        train_dataset, val_dataset, test_dataset = random_split(
            full_dataset,
            [train_size, val_size, test_size],
            generator=torch.Generator().manual_seed(42)
        )
        
        # Create loaders
        self.train_loader = DataLoader(
            train_dataset,
            batch_size=self.config.batch_size,
            shuffle=True,
            num_workers=0,  # SQLite doesn't support multi-process well
            pin_memory=self.device.type == 'cuda',
            drop_last=True
        )
        
        self.val_loader = DataLoader(
            val_dataset,
            batch_size=self.config.batch_size,
            shuffle=False,
            num_workers=0,
            pin_memory=self.device.type == 'cuda'
        )
        
        self.test_loader = DataLoader(
            test_dataset,
            batch_size=self.config.batch_size,
            shuffle=False,
            num_workers=0,
            pin_memory=self.device.type == 'cuda'
        )
        
        # Get class weights for imbalanced data
        class_weights = full_dataset.get_class_weights().to(self.device)
        
        # Setup criterion with class weights
        self.criterion = nn.BCEWithLogitsLoss(pos_weight=class_weights)
        
        logger.info(f"Data split: Train={train_size}, Val={val_size}, Test={test_size}")
        
    def setup_training(self, use_amp: bool = True) -> None:
        """Setup optimizer, scheduler, and other training components."""
        
        # Optimizer
        self.optimizer = optim.AdamW(
            self.model.parameters(),
            lr=self.config.learning_rate,
            weight_decay=self.config.weight_decay
        )
        
        # Learning rate scheduler
        self.scheduler = optim.lr_scheduler.CosineAnnealingWarmRestarts(
            self.optimizer,
            T_0=10,
            T_mult=2,
            eta_min=1e-6
        )
        
        # Mixed precision (only for CUDA)
        if use_amp and self.device.type == 'cuda':
            self.scaler = GradScaler()
            logger.info("Mixed precision training enabled")
        else:
            self.scaler = None
            
        # Early stopping
        self.early_stopping = EarlyStopping(
            patience=self.config.early_stopping_patience,
            mode='min'
        )
        
    def train_epoch(self) -> Tuple[float, float]:
        """
        Train for one epoch.
        
        Returns: (avg_loss, accuracy)
        """
        self.model.train()
        total_loss = 0.0
        correct = 0
        total = 0
        
        for batch in self.train_loader:
            blue = batch['blue_team'].to(self.device)
            red = batch['red_team'].to(self.device)
            labels = batch['label'].to(self.device)
            
            self.optimizer.zero_grad()
            
            # Forward pass with optional AMP
            if self.scaler:
                with autocast():
                    outputs = self.model(blue, red)
                    # Remove sigmoid since BCEWithLogitsLoss applies it
                    logits = torch.logit(outputs.clamp(1e-7, 1-1e-7))
                    loss = self.criterion(logits, labels)
                    
                self.scaler.scale(loss).backward()
                self.scaler.step(self.optimizer)
                self.scaler.update()
            else:
                outputs = self.model(blue, red)
                logits = torch.logit(outputs.clamp(1e-7, 1-1e-7))
                loss = self.criterion(logits, labels)
                
                loss.backward()
                self.optimizer.step()
            
            total_loss += loss.item() * blue.size(0)
            
            # Accuracy
            preds = (outputs > 0.5).float()
            correct += (preds == labels).sum().item()
            total += labels.numel()
            
        avg_loss = total_loss / total
        accuracy = correct / total
        
        return avg_loss, accuracy
    
    @torch.no_grad()
    def validate(self, loader: Optional[DataLoader] = None) -> Tuple[float, float]:
        """
        Validate on validation set.
        
        Returns: (avg_loss, accuracy)
        """
        self.model.eval()
        loader = loader or self.val_loader
        
        total_loss = 0.0
        correct = 0
        total = 0
        
        for batch in loader:
            blue = batch['blue_team'].to(self.device)
            red = batch['red_team'].to(self.device)
            labels = batch['label'].to(self.device)
            
            outputs = self.model(blue, red)
            logits = torch.logit(outputs.clamp(1e-7, 1-1e-7))
            loss = self.criterion(logits, labels)
            
            total_loss += loss.item() * blue.size(0)
            
            preds = (outputs > 0.5).float()
            correct += (preds == labels).sum().item()
            total += labels.numel()
            
        avg_loss = total_loss / total if total > 0 else 0
        accuracy = correct / total if total > 0 else 0
        
        return avg_loss, accuracy
    
    def train(
        self,
        epochs: Optional[int] = None,
        save_best: bool = True
    ) -> TrainingMetrics:
        """
        Full training loop.
        
        Args:
            epochs: Number of epochs (uses config default if None)
            save_best: Save best model checkpoint
            
        Returns: Training metrics
        """
        epochs = epochs or self.config.epochs
        
        logger.info(f"Starting training for {epochs} epochs")
        
        best_val_loss = float('inf')
        
        for epoch in range(1, epochs + 1):
            start_time = time.time()
            
            # Train
            train_loss, train_acc = self.train_epoch()
            
            # Validate
            val_loss, val_acc = self.validate()
            
            # Update scheduler
            if self.scheduler:
                self.scheduler.step()
                
            epoch_time = time.time() - start_time
            current_lr = self.optimizer.param_groups[0]['lr']
            
            # Update metrics
            self.metrics.update(
                train_loss=train_loss,
                val_loss=val_loss,
                train_acc=train_acc,
                val_acc=val_acc,
                lr=current_lr,
                epoch_time=epoch_time
            )
            
            # Log progress
            logger.info(
                f"Epoch {epoch}/{epochs} | "
                f"Train Loss: {train_loss:.4f} | Val Loss: {val_loss:.4f} | "
                f"Train Acc: {train_acc:.4f} | Val Acc: {val_acc:.4f} | "
                f"LR: {current_lr:.2e} | Time: {epoch_time:.1f}s"
            )
            
            # Save best model
            if save_best and val_loss < best_val_loss:
                best_val_loss = val_loss
                save_model(
                    self.model,
                    str(self.config.best_model_path),
                    self.optimizer,
                    epoch,
                    {'val_loss': val_loss, 'val_acc': val_acc}
                )
                logger.info(f"New best model saved (val_loss: {val_loss:.4f})")
                
            # Early stopping check
            if self.early_stopping and self.early_stopping(val_loss):
                logger.info(f"Early stopping triggered at epoch {epoch}")
                break
                
        # Final evaluation on test set
        if self.test_loader:
            test_loss, test_acc = self.validate(self.test_loader)
            logger.info(f"Final Test Loss: {test_loss:.4f} | Test Acc: {test_acc:.4f}")
            
        return self.metrics


def train_model(
    version: str,
    queue_id: int = 420,
    epochs: int = 50,
    batch_size: int = 256,
    learning_rate: float = 1e-3,
    use_items: bool = False,
    max_samples: Optional[int] = None
) -> Tuple[nn.Module, TrainingMetrics]:
    """
    Convenience function to train a model.
    
    Args:
        version: Patch version to train on (e.g., "14.24")
        queue_id: Queue type
        epochs: Number of training epochs
        batch_size: Batch size
        learning_rate: Initial learning rate
        use_items: Include item data in model
        max_samples: Limit dataset size (for testing)
        
    Returns:
        (trained_model, training_metrics)
    """
    # Update config
    config.model.batch_size = batch_size
    config.model.learning_rate = learning_rate
    config.model.epochs = epochs
    
    # Ensure directories exist
    config.model.checkpoint_dir.mkdir(parents=True, exist_ok=True)
    config.model.best_model_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Create model
    if use_items:
        model = MetaAwarePredictorWithItems()
    else:
        model = MetaAwarePredictor()
        
    # Create trainer
    trainer = Trainer(model)
    
    # Setup data and training
    trainer.setup_data(
        version=version,
        queue_id=queue_id,
        include_items=use_items,
        max_samples=max_samples
    )
    trainer.setup_training()
    
    # Train
    metrics = trainer.train(epochs=epochs)
    
    return model, metrics


if __name__ == "__main__":
    import argparse
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )
    
    parser = argparse.ArgumentParser(description="Train MetaAwarePredictor")
    parser.add_argument("--version", type=str, default="14.24", help="Patch version")
    parser.add_argument("--epochs", type=int, default=50, help="Number of epochs")
    parser.add_argument("--batch-size", type=int, default=256, help="Batch size")
    parser.add_argument("--lr", type=float, default=1e-3, help="Learning rate")
    parser.add_argument("--max-samples", type=int, default=None, help="Max samples")
    
    args = parser.parse_args()
    
    model, metrics = train_model(
        version=args.version,
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.lr,
        max_samples=args.max_samples
    )
    
    print(f"\nTraining complete!")
    print(f"Best val loss: {metrics.best_val_loss:.4f}")
    print(f"Best val accuracy: {metrics.best_val_acc:.4f}")
