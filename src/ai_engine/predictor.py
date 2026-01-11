"""
Predictor Service - Integration with DraftBetter Frontend.

Provides a high-level API for making predictions that can be
called from the Electron main process via IPC.
"""

import torch
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass

from .config import config
from .model import MetaAwarePredictor, get_device, load_model

logger = logging.getLogger(__name__)


@dataclass
class PredictionResult:
    """Result of a match prediction."""
    blue_win_probability: float
    red_win_probability: float
    confidence: str  # "high", "medium", "low"
    blue_team: List[int]
    red_team: List[int]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "blueWinProbability": self.blue_win_probability,
            "redWinProbability": self.red_win_probability,
            "confidence": self.confidence,
            "blueTeam": self.blue_team,
            "redTeam": self.red_team
        }


@dataclass
class DraftAnalysis:
    """Comprehensive draft analysis."""
    prediction: PredictionResult
    team_strengths: Dict[str, Any]
    recommendations: List[Dict[str, Any]]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "prediction": self.prediction.to_dict(),
            "teamStrengths": self.team_strengths,
            "recommendations": self.recommendations
        }


class MatchPredictor:
    """
    High-level predictor service for DraftBetter.
    
    Integrates with the main application to provide:
    - Real-time draft predictions
    - Champion recommendations based on win probability
    - Team composition analysis
    """
    
    def __init__(self, model_path: Optional[Path] = None):
        self.model_path = model_path or config.model.best_model_path
        self.model: Optional[MetaAwarePredictor] = None
        self.device = get_device()
        self._loaded = False
        
    def is_ready(self) -> bool:
        """Check if model is loaded and ready."""
        return self._loaded and self.model is not None
        
    def load(self) -> bool:
        """
        Load the trained model.
        
        Returns: True if successful, False otherwise
        """
        if not self.model_path.exists():
            logger.warning(f"Model not found at {self.model_path}")
            return False
            
        try:
            self.model, checkpoint = load_model(self.model_path, device=self.device)
            self.model.eval()
            self._loaded = True
            
            logger.info(f"Model loaded successfully from {self.model_path}")
            logger.info(f"  Epoch: {checkpoint.get('epoch', 'unknown')}")
            logger.info(f"  Val Accuracy: {checkpoint.get('metrics', {}).get('val_acc', 'unknown')}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            return False
            
    def unload(self) -> None:
        """Unload model to free memory."""
        if self.model:
            del self.model
            self.model = None
            self._loaded = False
            
            # Clear CUDA cache if applicable
            if self.device.type == 'cuda':
                torch.cuda.empty_cache()
                
            logger.info("Model unloaded")
    
    def predict(
        self, 
        blue_team: List[int], 
        red_team: List[int]
    ) -> Optional[PredictionResult]:
        """
        Predict match outcome.
        
        Args:
            blue_team: List of 5 champion IDs for blue team
            red_team: List of 5 champion IDs for red team
            
        Returns:
            PredictionResult or None if model not ready
        """
        if not self.is_ready():
            if not self.load():
                return None
                
        # Validate input
        if len(blue_team) != 5 or len(red_team) != 5:
            logger.error("Each team must have exactly 5 champions")
            return None
            
        # Filter out zeros (unpicked champions)
        if 0 in blue_team or 0 in red_team:
            logger.warning("Incomplete team composition - prediction may be inaccurate")
            
        try:
            win_prob = self.model.predict(blue_team, red_team, self.device)
            
            # Determine confidence based on probability distance from 0.5
            diff = abs(win_prob - 0.5)
            if diff > 0.15:
                confidence = "high"
            elif diff > 0.08:
                confidence = "medium"
            else:
                confidence = "low"
                
            return PredictionResult(
                blue_win_probability=round(win_prob, 4),
                red_win_probability=round(1 - win_prob, 4),
                confidence=confidence,
                blue_team=blue_team,
                red_team=red_team
            )
            
        except Exception as e:
            logger.error(f"Prediction failed: {e}")
            return None
    
    def predict_with_pick(
        self,
        blue_team: List[int],
        red_team: List[int],
        pick_slot: str,  # "blue" or "red"
        candidate_champions: List[int]
    ) -> List[Tuple[int, float]]:
        """
        Evaluate multiple champion picks and rank by win probability.
        
        Useful for recommending which champion to pick next.
        
        Args:
            blue_team: Current blue team (may have zeros for unpicked)
            red_team: Current red team (may have zeros for unpicked)
            pick_slot: Which team is picking ("blue" or "red")
            candidate_champions: List of champion IDs to evaluate
            
        Returns:
            List of (champion_id, win_probability) sorted by probability
        """
        if not self.is_ready():
            if not self.load():
                return []
                
        results: List[Tuple[int, float]] = []
        
        for champ_id in candidate_champions:
            # Create hypothetical team with this pick
            if pick_slot == "blue":
                # Find first zero slot
                test_blue = blue_team.copy()
                for i, c in enumerate(test_blue):
                    if c == 0:
                        test_blue[i] = champ_id
                        break
                test_red = red_team
            else:
                test_blue = blue_team
                test_red = red_team.copy()
                for i, c in enumerate(test_red):
                    if c == 0:
                        test_red[i] = champ_id
                        break
            
            # Predict
            result = self.predict(test_blue, test_red)
            if result:
                # For red team picks, we want lower blue win probability
                prob = result.blue_win_probability if pick_slot == "blue" else result.red_win_probability
                results.append((champ_id, prob))
                
        # Sort by probability (highest first)
        results.sort(key=lambda x: x[1], reverse=True)
        
        return results
    
    def analyze_draft(
        self,
        blue_team: List[int],
        red_team: List[int],
        available_champions: Optional[List[int]] = None
    ) -> Optional[DraftAnalysis]:
        """
        Comprehensive draft analysis.
        
        Returns prediction along with recommendations for improving
        team composition.
        """
        prediction = self.predict(blue_team, red_team)
        if not prediction:
            return None
            
        # Analyze team strengths (simplified - could be expanded)
        team_strengths = {
            "blue": {
                "winProbability": prediction.blue_win_probability,
                "championCount": sum(1 for c in blue_team if c > 0)
            },
            "red": {
                "winProbability": prediction.red_win_probability,
                "championCount": sum(1 for c in red_team if c > 0)
            }
        }
        
        # Generate recommendations
        recommendations = []
        
        # If either team has unpicked slots and we have candidates
        if available_champions:
            # Check for unpicked slots
            blue_empty = sum(1 for c in blue_team if c == 0)
            red_empty = sum(1 for c in red_team if c == 0)
            
            if blue_empty > 0:
                blue_picks = self.predict_with_pick(
                    blue_team, red_team, "blue", 
                    available_champions[:20]  # Top 20 candidates
                )
                if blue_picks:
                    recommendations.append({
                        "team": "blue",
                        "type": "pick",
                        "champions": [
                            {"championId": c, "winProbability": p}
                            for c, p in blue_picks[:5]
                        ]
                    })
                    
            if red_empty > 0:
                red_picks = self.predict_with_pick(
                    blue_team, red_team, "red",
                    available_champions[:20]
                )
                if red_picks:
                    recommendations.append({
                        "team": "red",
                        "type": "pick",
                        "champions": [
                            {"championId": c, "winProbability": p}
                            for c, p in red_picks[:5]
                        ]
                    })
                    
        return DraftAnalysis(
            prediction=prediction,
            team_strengths=team_strengths,
            recommendations=recommendations
        )


# Singleton instance for app-wide use
_predictor: Optional[MatchPredictor] = None


def get_predictor() -> MatchPredictor:
    """Get the singleton predictor instance."""
    global _predictor
    if _predictor is None:
        _predictor = MatchPredictor()
    return _predictor


# ==================== API Functions for IPC ====================

def api_predict(blue_team: List[int], red_team: List[int]) -> Optional[Dict]:
    """
    API function for IPC calls from Electron.
    
    Returns JSON-serializable dict.
    """
    predictor = get_predictor()
    result = predictor.predict(blue_team, red_team)
    return result.to_dict() if result else None


def api_analyze_draft(
    blue_team: List[int], 
    red_team: List[int],
    available_champions: Optional[List[int]] = None
) -> Optional[Dict]:
    """
    API function for comprehensive draft analysis.
    
    Returns JSON-serializable dict.
    """
    predictor = get_predictor()
    analysis = predictor.analyze_draft(blue_team, red_team, available_champions)
    return analysis.to_dict() if analysis else None


def api_recommend_picks(
    blue_team: List[int],
    red_team: List[int],
    pick_slot: str,
    candidates: List[int]
) -> List[Dict]:
    """
    API function for pick recommendations.
    
    Returns list of {championId, winProbability} dicts.
    """
    predictor = get_predictor()
    results = predictor.predict_with_pick(blue_team, red_team, pick_slot, candidates)
    return [
        {"championId": c, "winProbability": p}
        for c, p in results
    ]


def api_is_ready() -> bool:
    """Check if AI predictor is ready."""
    predictor = get_predictor()
    return predictor.is_ready()


def api_load_model() -> bool:
    """Load the AI model."""
    predictor = get_predictor()
    return predictor.load()


if __name__ == "__main__":
    # Test the predictor
    logging.basicConfig(level=logging.INFO)
    
    predictor = get_predictor()
    
    if predictor.load():
        # Test prediction
        result = predictor.predict(
            blue_team=[1, 2, 3, 4, 5],
            red_team=[6, 7, 8, 9, 10]
        )
        
        if result:
            print(f"Blue Win: {result.blue_win_probability*100:.1f}%")
            print(f"Red Win: {result.red_win_probability*100:.1f}%")
            print(f"Confidence: {result.confidence}")
    else:
        print("Model not available - train first!")
