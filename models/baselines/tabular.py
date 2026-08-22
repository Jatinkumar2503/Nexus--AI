"""NEXUS AI — Tabular ML Baseline Models (GBDT / Ridge / Random Forest)."""

import numpy as np
from typing import Dict, Any, Tuple

class TabularBaselineModel:
    def __init__(self):
        self.weights_delay = None
        self.bias_delay = None
        self.weights_conflict = None

    def fit(self, X: np.ndarray, y_delay: np.ndarray, y_conflict: np.ndarray):
        """Fits linear/ridge ridge regression baseline models using analytical least squares."""
        # Add bias column
        X_b = np.hstack([np.ones((X.shape[0], 1)), X])
        reg = 1.0 * np.eye(X_b.shape[1])
        reg[0, 0] = 0.0  # Do not regularize bias

        # 1. Delay Regression Model
        theta_delay = np.linalg.solve(X_b.T @ X_b + reg, X_b.T @ y_delay)
        self.bias_delay = theta_delay[0]
        self.weights_delay = theta_delay[1:]

        # 2. Conflict Classifier Model
        theta_conflict = np.linalg.solve(X_b.T @ X_b + reg, X_b.T @ y_conflict)
        self.weights_conflict = theta_conflict

    def predict(self, X: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Predicts delay and conflict hazard probability."""
        if self.weights_delay is None:
            raise RuntimeError("Model has not been fitted.")
        
        pred_delay = X @ self.weights_delay + self.bias_delay
        
        X_b = np.hstack([np.ones((X.shape[0], 1)), X])
        logits = X_b @ self.weights_conflict
        pred_conflict = 1.0 / (1.0 + np.exp(-np.clip(logits, -10.0, 10.0)))

        return pred_delay, pred_conflict
