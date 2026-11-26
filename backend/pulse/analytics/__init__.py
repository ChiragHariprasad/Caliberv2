"""Scientific F1 telemetry, pace estimation, degradation, and strategy analytics."""

from pulse.analytics.pace_and_tyre import (
    BaselinePrediction,
    DegradationEstimate,
    FuelCompensatedDegradationModel,
    PitWindowStrategySimulator,
    RollingCleanAirPaceEstimator,
    estimate_fuel_burn_rate,
    normalize_compound,
)

__all__ = [
    "BaselinePrediction",
    "DegradationEstimate",
    "FuelCompensatedDegradationModel",
    "PitWindowStrategySimulator",
    "RollingCleanAirPaceEstimator",
    "estimate_fuel_burn_rate",
    "normalize_compound",
]
