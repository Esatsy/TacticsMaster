"""
DraftBetter AI Engine - Current-Patch Match Predictor

A machine learning module that harvests current-patch League of Legends match data
and trains predictive models for draft analysis.

Modules:
    - database: SQLite storage with WAL mode for high-performance writes
    - crawler: Async data harvester with strict version filtering
    - model: PyTorch-based MetaAwarePredictor
    - train: Training pipeline with device-agnostic execution
"""

__version__ = "1.0.0"
__author__ = "DraftBetter Team"
