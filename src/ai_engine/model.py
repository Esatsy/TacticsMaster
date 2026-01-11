"""
MetaAwarePredictor - PyTorch Model for Match Prediction.

Features:
- Device-agnostic (MPS/CUDA/ROCm/CPU auto-detection)
- Champion embedding layer
- Multi-layer perceptron with dropout
- Optional item embedding for post-game analysis
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Optional, Tuple, List, Dict
import logging

from .config import config, ModelConfig

logger = logging.getLogger(__name__)


def get_device() -> torch.device:
    """
    Automatically select the best available device.
    
    Priority:
    1. Apple MPS (Metal Performance Shaders) - MacBook M-series
    2. CUDA (NVIDIA) / ROCm (AMD) - detected via torch.cuda
    3. CPU fallback
    
    Returns: torch.device
    """
    if torch.backends.mps.is_available() and torch.backends.mps.is_built():
        device = torch.device("mps")
        logger.info("Using Apple MPS (Metal) device")
        return device
        
    if torch.cuda.is_available():
        # This covers both CUDA (NVIDIA) and ROCm (AMD via HIP)
        device_name = torch.cuda.get_device_name(0)
        device = torch.device("cuda")
        logger.info(f"Using CUDA device: {device_name}")
        return device
        
    logger.info("Using CPU device")
    return torch.device("cpu")


def get_device_info() -> Dict[str, any]:
    """Get detailed device information."""
    info = {
        "device": str(get_device()),
        "mps_available": torch.backends.mps.is_available(),
        "mps_built": torch.backends.mps.is_built() if hasattr(torch.backends.mps, 'is_built') else False,
        "cuda_available": torch.cuda.is_available(),
        "cuda_device_count": torch.cuda.device_count() if torch.cuda.is_available() else 0,
    }
    
    if torch.cuda.is_available():
        info["cuda_device_name"] = torch.cuda.get_device_name(0)
        info["cuda_memory_total"] = torch.cuda.get_device_properties(0).total_memory
        
    return info


class ChampionEmbedding(nn.Module):
    """
    Learned embedding layer for champion representations.
    
    Maps champion IDs to dense vectors capturing champion characteristics.
    """
    
    def __init__(
        self, 
        num_champions: int = 170,
        embedding_dim: int = 64,
        padding_idx: int = 0
    ):
        super().__init__()
        self.embedding = nn.Embedding(
            num_embeddings=num_champions + 1,  # +1 for padding
            embedding_dim=embedding_dim,
            padding_idx=padding_idx
        )
        
    def forward(self, champion_ids: torch.Tensor) -> torch.Tensor:
        """
        Args:
            champion_ids: (batch_size, num_champions_per_team)
            
        Returns:
            embeddings: (batch_size, num_champions_per_team, embedding_dim)
        """
        return self.embedding(champion_ids)


class TeamEncoder(nn.Module):
    """
    Encodes a team composition into a fixed-size vector.
    
    Uses attention mechanism to weight champion importance.
    """
    
    def __init__(self, embedding_dim: int = 64, hidden_dim: int = 128):
        super().__init__()
        
        # Attention mechanism
        self.attention = nn.Sequential(
            nn.Linear(embedding_dim, hidden_dim),
            nn.Tanh(),
            nn.Linear(hidden_dim, 1)
        )
        
        # Team representation
        self.team_mlp = nn.Sequential(
            nn.Linear(embedding_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim)
        )
        
    def forward(self, champion_embeddings: torch.Tensor) -> torch.Tensor:
        """
        Args:
            champion_embeddings: (batch_size, 5, embedding_dim) - 5 champions per team
            
        Returns:
            team_vector: (batch_size, hidden_dim)
        """
        # Compute attention weights
        attn_scores = self.attention(champion_embeddings)  # (batch, 5, 1)
        attn_weights = F.softmax(attn_scores, dim=1)  # (batch, 5, 1)
        
        # Weighted sum of embeddings
        weighted = champion_embeddings * attn_weights  # (batch, 5, embed)
        team_repr = weighted.sum(dim=1)  # (batch, embed)
        
        # Transform
        team_vector = self.team_mlp(team_repr)
        
        return team_vector


class MetaAwarePredictor(nn.Module):
    """
    Main prediction model for match outcomes.
    
    Architecture:
    1. Champion Embeddings: Learn representations for each champion
    2. Team Encoders: Encode blue/red team compositions
    3. Interaction Layer: Model team matchup dynamics
    4. Prediction Head: Output win probability
    
    The model learns meta-specific patterns when trained only on
    current-patch data, making it "meta-aware".
    """
    
    def __init__(self, model_config: Optional[ModelConfig] = None):
        super().__init__()
        self.config = model_config or config.model
        
        # Champion embedding (shared between teams)
        self.champion_embedding = ChampionEmbedding(
            num_champions=self.config.num_champions,
            embedding_dim=self.config.embedding_dim
        )
        
        # Team encoders
        self.blue_encoder = TeamEncoder(
            embedding_dim=self.config.embedding_dim,
            hidden_dim=self.config.hidden_dims[0] // 2
        )
        self.red_encoder = TeamEncoder(
            embedding_dim=self.config.embedding_dim,
            hidden_dim=self.config.hidden_dims[0] // 2
        )
        
        # Interaction features
        hidden = self.config.hidden_dims[0] // 2
        interaction_input = hidden * 2 + hidden  # blue + red + interaction
        
        # MLP classifier
        layers = []
        prev_dim = interaction_input
        
        for hidden_dim in self.config.hidden_dims:
            layers.extend([
                nn.Linear(prev_dim, hidden_dim),
                nn.BatchNorm1d(hidden_dim),
                nn.ReLU(),
                nn.Dropout(self.config.dropout_rate)
            ])
            prev_dim = hidden_dim
            
        # Output layer
        layers.append(nn.Linear(prev_dim, 1))
        
        self.classifier = nn.Sequential(*layers)
        
        # Initialize weights
        self._init_weights()
        
    def _init_weights(self):
        """Initialize model weights."""
        for module in self.modules():
            if isinstance(module, nn.Linear):
                nn.init.kaiming_normal_(module.weight, mode='fan_out', nonlinearity='relu')
                if module.bias is not None:
                    nn.init.zeros_(module.bias)
            elif isinstance(module, nn.BatchNorm1d):
                nn.init.ones_(module.weight)
                nn.init.zeros_(module.bias)
            elif isinstance(module, nn.Embedding):
                nn.init.normal_(module.weight, mean=0, std=0.1)
                
    def forward(
        self, 
        blue_team: torch.Tensor, 
        red_team: torch.Tensor
    ) -> torch.Tensor:
        """
        Predict blue team win probability.
        
        Args:
            blue_team: (batch_size, 5) - Champion IDs for blue team
            red_team: (batch_size, 5) - Champion IDs for red team
            
        Returns:
            win_prob: (batch_size, 1) - Probability that blue team wins
        """
        # Get champion embeddings
        blue_embeds = self.champion_embedding(blue_team)  # (batch, 5, embed)
        red_embeds = self.champion_embedding(red_team)    # (batch, 5, embed)
        
        # Encode teams
        blue_vector = self.blue_encoder(blue_embeds)  # (batch, hidden/2)
        red_vector = self.red_encoder(red_embeds)     # (batch, hidden/2)
        
        # Compute interaction features
        interaction = blue_vector * red_vector  # Element-wise
        
        # Concatenate all features
        combined = torch.cat([blue_vector, red_vector, interaction], dim=1)
        
        # Predict
        logits = self.classifier(combined)
        
        return torch.sigmoid(logits)
    
    def predict(
        self, 
        blue_team: List[int], 
        red_team: List[int],
        device: Optional[torch.device] = None
    ) -> float:
        """
        Convenience method for single prediction.
        
        Args:
            blue_team: List of 5 champion IDs
            red_team: List of 5 champion IDs
            device: Target device (auto-detected if None)
            
        Returns:
            Blue team win probability (0-1)
        """
        if device is None:
            device = next(self.parameters()).device
            
        self.eval()
        with torch.no_grad():
            blue = torch.tensor([blue_team], dtype=torch.long, device=device)
            red = torch.tensor([red_team], dtype=torch.long, device=device)
            prob = self(blue, red)
            return prob.item()


class MetaAwarePredictorWithItems(MetaAwarePredictor):
    """
    Extended model that also considers item builds.
    
    Useful for post-game analysis or in-game predictions
    when item data is available.
    """
    
    def __init__(
        self, 
        model_config: Optional[ModelConfig] = None,
        num_items: int = 300,
        item_embedding_dim: int = 32
    ):
        super().__init__(model_config)
        
        self.num_items = num_items
        self.item_embedding_dim = item_embedding_dim
        
        # Item embeddings
        self.item_embedding = nn.Embedding(
            num_embeddings=num_items + 1,
            embedding_dim=item_embedding_dim,
            padding_idx=0
        )
        
        # Item encoder (per player: 6 items)
        self.item_encoder = nn.Sequential(
            nn.Linear(item_embedding_dim * 6, item_embedding_dim * 2),
            nn.ReLU(),
            nn.Linear(item_embedding_dim * 2, item_embedding_dim)
        )
        
        # Rebuild classifier with item features
        hidden = self.config.hidden_dims[0] // 2
        # base + item features for each player (5 blue + 5 red)
        interaction_input = hidden * 2 + hidden + item_embedding_dim * 10
        
        layers = []
        prev_dim = interaction_input
        
        for hidden_dim in self.config.hidden_dims:
            layers.extend([
                nn.Linear(prev_dim, hidden_dim),
                nn.BatchNorm1d(hidden_dim),
                nn.ReLU(),
                nn.Dropout(self.config.dropout_rate)
            ])
            prev_dim = hidden_dim
            
        layers.append(nn.Linear(prev_dim, 1))
        self.classifier_with_items = nn.Sequential(*layers)
        
    def forward(
        self, 
        blue_team: torch.Tensor, 
        red_team: torch.Tensor,
        blue_items: Optional[torch.Tensor] = None,
        red_items: Optional[torch.Tensor] = None
    ) -> torch.Tensor:
        """
        Predict with optional item data.
        
        Args:
            blue_team: (batch, 5) champion IDs
            red_team: (batch, 5) champion IDs
            blue_items: (batch, 5, 6) item IDs per player
            red_items: (batch, 5, 6) item IDs per player
        """
        # Get champion features
        blue_embeds = self.champion_embedding(blue_team)
        red_embeds = self.champion_embedding(red_team)
        blue_vector = self.blue_encoder(blue_embeds)
        red_vector = self.red_encoder(red_embeds)
        interaction = blue_vector * red_vector
        
        if blue_items is not None and red_items is not None:
            # Encode items
            batch_size = blue_team.size(0)
            
            # (batch, 5, 6) -> (batch, 5, 6, item_embed)
            blue_item_embeds = self.item_embedding(blue_items)
            red_item_embeds = self.item_embedding(red_items)
            
            # Flatten items per player: (batch, 5, 6 * item_embed)
            blue_item_flat = blue_item_embeds.view(batch_size, 5, -1)
            red_item_flat = red_item_embeds.view(batch_size, 5, -1)
            
            # Encode each player's items: (batch, 5, item_embed)
            blue_item_encoded = self.item_encoder(blue_item_flat)
            red_item_encoded = self.item_encoder(red_item_flat)
            
            # Flatten to (batch, 5 * item_embed)
            blue_item_vector = blue_item_encoded.view(batch_size, -1)
            red_item_vector = red_item_encoded.view(batch_size, -1)
            
            # Combine all features
            combined = torch.cat([
                blue_vector, red_vector, interaction,
                blue_item_vector, red_item_vector
            ], dim=1)
            
            logits = self.classifier_with_items(combined)
        else:
            # Fall back to champion-only prediction
            combined = torch.cat([blue_vector, red_vector, interaction], dim=1)
            logits = self.classifier(combined)
            
        return torch.sigmoid(logits)


class EarlyStopping:
    """Early stopping callback to prevent overfitting."""
    
    def __init__(
        self, 
        patience: int = 5, 
        min_delta: float = 0.001,
        mode: str = 'min'
    ):
        self.patience = patience
        self.min_delta = min_delta
        self.mode = mode
        self.counter = 0
        self.best_value = None
        self.should_stop = False
        
    def __call__(self, value: float) -> bool:
        """
        Check if training should stop.
        
        Args:
            value: Current validation metric
            
        Returns:
            True if training should stop
        """
        if self.best_value is None:
            self.best_value = value
            return False
            
        if self.mode == 'min':
            improved = value < self.best_value - self.min_delta
        else:
            improved = value > self.best_value + self.min_delta
            
        if improved:
            self.best_value = value
            self.counter = 0
        else:
            self.counter += 1
            if self.counter >= self.patience:
                self.should_stop = True
                return True
                
        return False


def save_model(
    model: nn.Module, 
    path: str,
    optimizer: Optional[torch.optim.Optimizer] = None,
    epoch: int = 0,
    metrics: Optional[Dict] = None
) -> None:
    """Save model checkpoint."""
    checkpoint = {
        'model_state_dict': model.state_dict(),
        'model_config': model.config if hasattr(model, 'config') else None,
        'epoch': epoch,
        'metrics': metrics or {}
    }
    
    if optimizer:
        checkpoint['optimizer_state_dict'] = optimizer.state_dict()
        
    torch.save(checkpoint, path)
    logger.info(f"Model saved to {path}")


def load_model(
    path: str,
    model_class: type = MetaAwarePredictor,
    device: Optional[torch.device] = None
) -> Tuple[nn.Module, Dict]:
    """
    Load model from checkpoint.
    
    Returns:
        (model, checkpoint_dict)
    """
    if device is None:
        device = get_device()
        
    checkpoint = torch.load(path, map_location=device)
    
    model_config = checkpoint.get('model_config')
    model = model_class(model_config)
    model.load_state_dict(checkpoint['model_state_dict'])
    model.to(device)
    
    logger.info(f"Model loaded from {path} (epoch {checkpoint.get('epoch', 'unknown')})")
    
    return model, checkpoint


if __name__ == "__main__":
    # Test device detection and model
    logging.basicConfig(level=logging.INFO)
    
    print("Device Info:")
    for k, v in get_device_info().items():
        print(f"  {k}: {v}")
        
    device = get_device()
    
    # Test model
    model = MetaAwarePredictor().to(device)
    print(f"\nModel parameters: {sum(p.numel() for p in model.parameters()):,}")
    
    # Test forward pass
    blue = torch.randint(1, 170, (32, 5), device=device)
    red = torch.randint(1, 170, (32, 5), device=device)
    
    output = model(blue, red)
    print(f"Output shape: {output.shape}")
    print(f"Sample predictions: {output[:5].squeeze().tolist()}")
