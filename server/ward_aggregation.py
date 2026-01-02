"""
Ward-level flood risk aggregation module.

Provides functions to aggregate grid-level predictions to ward level.
Supports multiple aggregation strategies.
"""

from typing import List, Dict, Optional, Tuple
import numpy as np
import pandas as pd


class WardAggregator:
    """Aggregates grid-level predictions to ward level."""
    
    # Risk level constants
    RISK_CLASSES = {
        0: "High",
        1: "Low",
        2: "Medium"
    }
    
    RISK_ORDER = {"Low": 0, "Medium": 1, "High": 2}  # For comparison
    
    @staticmethod
    def aggregate_predictions(
        grid_predictions: Dict[int, float],
        method: str = "mean"
    ) -> float:
        """
        Aggregate grid predictions to a single ward score.
        
        Args:
            grid_predictions: Dict of {grid_id: risk_score (0-1)} or {grid_id: class_id (0/1/2)}
            method: Aggregation method - "mean", "max", "median", "percentile_75", "percentile_90"
            
        Returns:
            Aggregated risk score (float between 0-1)
        """
        if not grid_predictions:
            return 0.5  # Default to medium risk
        
        scores = list(grid_predictions.values())
        
        if method == "mean":
            return float(np.mean(scores))
        elif method == "max":
            return float(np.max(scores))
        elif method == "median":
            return float(np.median(scores))
        elif method == "percentile_75":
            return float(np.percentile(scores, 75))
        elif method == "percentile_90":
            return float(np.percentile(scores, 90))
        elif method == "min":
            return float(np.min(scores))
        else:
            return float(np.mean(scores))
    
    @staticmethod
    def score_to_class(score: float) -> Tuple[int, str]:
        """
        Convert a risk score (0-1) to a risk class.
        
        Args:
            score: Risk score between 0-1
            
        Returns:
            Tuple of (class_id, class_name)
        """
        if score < 0.33:
            return (1, "Low")
        elif score < 0.66:
            return (2, "Medium")
        else:
            return (0, "High")
    
    @staticmethod
    def class_to_score(class_id: int) -> float:
        """
        Convert a risk class ID to a continuous score.
        
        Args:
            class_id: Risk class (0=High, 1=Low, 2=Medium)
            
        Returns:
            Normalized score between 0-1
        """
        if class_id == 0:  # High
            return 0.8
        elif class_id == 1:  # Low
            return 0.2
        elif class_id == 2:  # Medium
            return 0.5
        else:
            return 0.5
    
    @staticmethod
    def get_risk_distribution(
        grid_predictions: Dict[int, float]
    ) -> Dict[str, float]:
        """
        Get the distribution of risk levels across grids.
        
        Args:
            grid_predictions: Dict of {grid_id: risk_score or class_id}
            
        Returns:
            Dict with counts: {"High": 0.3, "Medium": 0.4, "Low": 0.3}
        """
        if not grid_predictions:
            return {"High": 0, "Low": 0, "Medium": 0}
        
        distribution = {"High": 0, "Low": 0, "Medium": 0}
        
        for score in grid_predictions.values():
            # Assume scores are 0-1 or 0-2 (handle both cases)
            if score <= 1.0:
                # Continuous score
                _, class_name = WardAggregator.score_to_class(score)
            else:
                # Discrete class (0/1/2)
                class_name = WardAggregator.RISK_CLASSES.get(int(score), "Medium")
            
            distribution[class_name] += 1
        
        # Convert to percentages
        total = sum(distribution.values())
        if total > 0:
            distribution = {k: v / total for k, v in distribution.items()}
        
        return distribution
    
    @staticmethod
    def weighted_aggregation(
        grid_predictions: Dict[int, float],
        grid_weights: Optional[Dict[int, float]] = None
    ) -> float:
        """
        Aggregate predictions with optional weights (e.g., population density).
        
        Args:
            grid_predictions: Dict of {grid_id: risk_score}
            grid_weights: Dict of {grid_id: weight} - uniform if None
            
        Returns:
            Weighted average risk score
        """
        if not grid_predictions:
            return 0.5
        
        if grid_weights is None:
            grid_weights = {gid: 1.0 for gid in grid_predictions.keys()}
        
        weighted_sum = 0.0
        weight_sum = 0.0
        
        for grid_id, score in grid_predictions.items():
            weight = grid_weights.get(grid_id, 1.0)
            weighted_sum += score * weight
            weight_sum += weight
        
        if weight_sum == 0:
            return 0.5
        
        return weighted_sum / weight_sum


def create_ward_prediction_summary(
    ward_id: int,
    ward_name: Optional[str],
    grid_predictions: Dict[int, float],
    aggregation_method: str = "mean"
) -> Dict:
    """
    Create a comprehensive ward-level flood risk summary.
    
    Args:
        ward_id: The Ward ID
        ward_name: Human-readable ward name
        grid_predictions: Dict of {grid_id: risk_score (0-1)}
        aggregation_method: How to aggregate grid predictions
        
    Returns:
        Dict with comprehensive ward risk information
    """
    aggregator = WardAggregator()
    
    # Calculate aggregated score
    aggregated_score = aggregator.aggregate_predictions(
        grid_predictions,
        method=aggregation_method
    )
    
    # Convert to risk class
    risk_class_id, risk_class_name = aggregator.score_to_class(aggregated_score)
    
    # Get risk distribution
    risk_distribution = aggregator.get_risk_distribution(grid_predictions)
    
    return {
        "Ward_ID": ward_id,
        "Ward_Name": ward_name or f"Ward_{ward_id}",
        "Flood_Risk_Score": round(aggregated_score, 4),
        "Flood_Risk_Class": risk_class_name,
        "Flood_Risk_Class_ID": risk_class_id,
        "Grid_Count": len(grid_predictions),
        "Risk_Distribution": {
            k: round(v, 4) for k, v in risk_distribution.items()
        },
        "Min_Grid_Risk": round(min(grid_predictions.values()), 4) if grid_predictions else 0,
        "Max_Grid_Risk": round(max(grid_predictions.values()), 4) if grid_predictions else 0,
        "Median_Grid_Risk": round(np.median(list(grid_predictions.values())), 4) if grid_predictions else 0,
    }
