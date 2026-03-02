"""Transfer strategy and chip timing module.

Sub-modules:
- models: Data models (TransferAction, TransferPlan, ChipRecommendation, etc.)
- transfer_planner: Multi-GW rolling-horizon transfer planner
- chip_strategy: Chip timing optimiser (WC, FH, TC, BB)
- sensitivity: Transfer sensitivity / robustness analysis
- effective_ownership: Effective ownership (EO) calculator
- engine: Facade that composes all sub-modules
"""
