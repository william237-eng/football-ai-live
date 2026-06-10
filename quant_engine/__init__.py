# quant_engine package — Legacy modules
try:
    from .api_layer import FootballAPI
    from .data_pipeline import DataPipeline
    from .features import FeatureEngineer
    from .modeling import ModelingEngine
    from .simulation import SimulationEngine
    from .risk import RiskEngine
    from .prediction import PredictionEngine
    from .validation import ValidationEngine
    from .confidence import ConfidenceEngine
except ImportError:
    pass

# Trading Orchestrator — 10 Piliers
try:
    from .trading_orchestrator import TradingOrchestrator
    from .data_tier_1 import DataTier1Ingestion, apply_ema_to_pressure_index
    from .environmental_factors import EnvironmentalFactorsCalculator
    from .market_veto import MarketVetoEngine
    from .prematch_engine import PreMatchEngine, EloRatingSystem, DixonColesModel
    from .live_engine import LiveEngine, BayesianLambdaUpdater, CopulaMonteCarloSimulator
    from .pricing_engine import PricingEngine, SkellamDistribution
    from .anomalies_money_management_execution import (
        AnomalyDetector,
        KellyCalculator,
        ExecutionEngine,
    )
except ImportError as e:
    print(f"Warning: Could not import trading modules: {e}")

__all__ = [
    # Legacy
    "FootballAPI",
    "DataPipeline",
    "FeatureEngineer",
    "ModelingEngine",
    "SimulationEngine",
    "RiskEngine",
    "PredictionEngine",
    "ValidationEngine",
    "ConfidenceEngine",
    # Trading Orchestrator (10 Piliers)
    "TradingOrchestrator",
    "DataTier1Ingestion",
    "apply_ema_to_pressure_index",
    "EnvironmentalFactorsCalculator",
    "MarketVetoEngine",
    "PreMatchEngine",
    "EloRatingSystem",
    "DixonColesModel",
    "LiveEngine",
    "BayesianLambdaUpdater",
    "CopulaMonteCarloSimulator",
    "PricingEngine",
    "SkellamDistribution",
    "AnomalyDetector",
    "KellyCalculator",
    "ExecutionEngine",
]

