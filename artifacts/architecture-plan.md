# FPL Team Picker - Complete Architecture Plan

## 1. Executive Summary

FPL Picker is a full-stack web application that combines machine learning prediction models, mathematical optimization (ILP/GA), and a modern web UI to recommend optimal Fantasy Premier League squads, captain picks, transfer strategies, and chip timing. The system ingests live and historical FPL data, generates per-player expected-point forecasts across multiple gameweeks, and solves constrained optimization problems to produce actionable team recommendations.

---

## 2. Project Directory Structure

```
fpl-picker/
├── README.md
├── docker-compose.yml
├── Makefile
├── .env.example
├── .gitignore
│
├── backend/
│   ├── pyproject.toml                    # Python project config (Poetry)
│   ├── poetry.lock
│   ├── alembic.ini                       # DB migration config
│   ├── Dockerfile
│   │
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                       # FastAPI app factory
│   │   ├── config.py                     # Pydantic settings
│   │   ├── dependencies.py               # FastAPI dependency injection
│   │   │
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── router.py                 # Top-level API router
│   │   │   ├── endpoints/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── data.py               # /api/data/* endpoints
│   │   │   │   ├── predict.py            # /api/predict/* endpoints
│   │   │   │   ├── optimize.py           # /api/optimize/* endpoints
│   │   │   │   ├── transfers.py          # /api/transfers/* endpoints
│   │   │   │   ├── chips.py              # /api/chips/* endpoints
│   │   │   │   └── health.py             # /api/health
│   │   │   └── schemas/
│   │   │       ├── __init__.py
│   │   │       ├── common.py             # Shared response models
│   │   │       ├── player.py             # Player data schemas
│   │   │       ├── prediction.py         # Prediction request/response
│   │   │       ├── optimization.py       # Optimization request/response
│   │   │       ├── transfer.py           # Transfer recommendation schemas
│   │   │       └── chip.py               # Chip strategy schemas
│   │   │
│   │   ├── data/
│   │   │   ├── __init__.py
│   │   │   ├── fpl_client.py             # Official FPL API client
│   │   │   ├── github_loader.py          # vaastav historical data loader
│   │   │   ├── preprocessing.py          # Feature engineering pipeline
│   │   │   ├── cache.py                  # Redis/in-memory caching layer
│   │   │   └── models.py                 # SQLAlchemy / data models
│   │   │
│   │   ├── prediction/
│   │   │   ├── __init__.py
│   │   │   ├── engine.py                 # PredictionEngine orchestrator
│   │   │   ├── base.py                   # Abstract base model class
│   │   │   ├── arima_model.py            # ARIMA(1,0,0) rolling window
│   │   │   ├── weighted_avg_model.py     # Weighted average with recency
│   │   │   ├── hybrid_model.py           # Ridge + XGBoost/SHAP blend
│   │   │   ├── exponential_model.py      # Holt-Winters smoothing
│   │   │   ├── monte_carlo_model.py      # Monte Carlo simulation
│   │   │   ├── ensemble.py              # Ensemble/model-selection logic
│   │   │   └── features.py              # Feature extraction (ICT, xG, xA, xGI)
│   │   │
│   │   ├── optimization/
│   │   │   ├── __init__.py
│   │   │   ├── engine.py                 # OptimizationEngine orchestrator
│   │   │   ├── ilp_solver.py             # PuLP ILP solver
│   │   │   ├── ga_solver.py              # Genetic Algorithm solver
│   │   │   ├── constraints.py            # Constraint definitions
│   │   │   ├── captain.py                # Captain & vice-captain selection
│   │   │   ├── bench.py                  # Bench ordering optimization
│   │   │   └── sensitivity.py            # Sensitivity analysis for decisions
│   │   │
│   │   ├── transfers/
│   │   │   ├── __init__.py
│   │   │   ├── engine.py                 # TransferEngine orchestrator
│   │   │   ├── rolling_horizon.py        # Multi-GW transfer planning
│   │   │   ├── cost_model.py             # Transfer cost / hit penalty model
│   │   │   └── chip_strategy.py          # Chip timing optimizer
│   │   │
│   │   └── utils/
│   │       ├── __init__.py
│   │       ├── logging.py                # Structured logging setup
│   │       ├── errors.py                 # Custom exception hierarchy
│   │       └── timing.py                 # Performance decorators
│   │
│   ├── migrations/
│   │   └── versions/                     # Alembic migration files
│   │
│   └── tests/
│       ├── __init__.py
│       ├── conftest.py                   # Pytest fixtures
│       ├── test_data/                    # Mock FPL API responses
│       ├── test_api/
│       │   ├── test_data_endpoints.py
│       │   ├── test_predict_endpoints.py
│       │   ├── test_optimize_endpoints.py
│       │   ├── test_transfer_endpoints.py
│       │   └── test_chip_endpoints.py
│       ├── test_prediction/
│       │   ├── test_arima.py
│       │   ├── test_weighted_avg.py
│       │   ├── test_hybrid.py
│       │   └── test_ensemble.py
│       ├── test_optimization/
│       │   ├── test_ilp_solver.py
│       │   ├── test_ga_solver.py
│       │   └── test_constraints.py
│       └── test_transfers/
│           ├── test_rolling_horizon.py
│           └── test_chip_strategy.py
│
├── frontend/
│   ├── package.json
│   ├── pnpm-lock.yaml
│   ├── next.config.ts
│   ├── tsconfig.json
│   ├── tailwind.config.ts
│   ├── postcss.config.js
│   ├── Dockerfile
│   ├── .env.local.example
│   │
│   ├── public/
│   │   ├── favicon.ico
│   │   └── images/
│   │       └── pitch.svg                 # Football pitch background
│   │
│   ├── src/
│   │   ├── app/
│   │   │   ├── layout.tsx                # Root layout
│   │   │   ├── page.tsx                  # Dashboard (home)
│   │   │   ├── globals.css
│   │   │   ├── team/
│   │   │   │   └── page.tsx              # My Team view
│   │   │   ├── optimize/
│   │   │   │   └── page.tsx              # Optimization controls & results
│   │   │   ├── transfers/
│   │   │   │   └── page.tsx              # Transfer planner
│   │   │   ├── predictions/
│   │   │   │   └── page.tsx              # Prediction explorer
│   │   │   ├── players/
│   │   │   │   ├── page.tsx              # Player list / comparison
│   │   │   │   └── [id]/
│   │   │   │       └── page.tsx          # Player detail view
│   │   │   └── chips/
│   │   │       └── page.tsx              # Chip strategy planner
│   │   │
│   │   ├── components/
│   │   │   ├── ui/                       # shadcn/ui primitives
│   │   │   │   ├── button.tsx
│   │   │   │   ├── card.tsx
│   │   │   │   ├── table.tsx
│   │   │   │   ├── slider.tsx
│   │   │   │   ├── tabs.tsx
│   │   │   │   ├── badge.tsx
│   │   │   │   ├── dialog.tsx
│   │   │   │   ├── tooltip.tsx
│   │   │   │   └── skeleton.tsx
│   │   │   ├── layout/
│   │   │   │   ├── Navbar.tsx
│   │   │   │   ├── Sidebar.tsx
│   │   │   │   └── Footer.tsx
│   │   │   ├── team/
│   │   │   │   ├── PitchView.tsx         # Visual pitch with players
│   │   │   │   ├── PlayerCard.tsx        # Player info card on pitch
│   │   │   │   ├── BenchRow.tsx          # Bench player row
│   │   │   │   ├── FormationSelector.tsx # Formation dropdown
│   │   │   │   └── TeamSummary.tsx       # Budget, value, stats
│   │   │   ├── optimization/
│   │   │   │   ├── OptimizePanel.tsx     # Controls: budget, constraints
│   │   │   │   ├── ResultsTable.tsx      # Recommended squad table
│   │   │   │   ├── ComparisonView.tsx    # Before/after comparison
│   │   │   │   └── SensitivityChart.tsx  # Sensitivity analysis
│   │   │   ├── prediction/
│   │   │   │   ├── PredictionChart.tsx   # Time-series chart
│   │   │   │   ├── ModelSelector.tsx     # Model toggle
│   │   │   │   ├── ConfidenceBar.tsx     # Prediction confidence
│   │   │   │   └── FeatureImportance.tsx # SHAP-style feature chart
│   │   │   ├── transfers/
│   │   │   │   ├── TransferPlanner.tsx   # Multi-GW transfer timeline
│   │   │   │   ├── TransferCard.tsx      # Individual transfer in/out
│   │   │   │   └── HitCalculator.tsx     # Points-hit vs. gain viz
│   │   │   ├── players/
│   │   │   │   ├── PlayerTable.tsx       # Sortable, filterable table
│   │   │   │   ├── PlayerCompare.tsx     # Side-by-side comparison
│   │   │   │   └── PlayerSearch.tsx      # Autocomplete search
│   │   │   └── charts/
│   │   │       ├── LineChart.tsx          # Recharts line wrapper
│   │   │       ├── BarChart.tsx           # Recharts bar wrapper
│   │   │       └── RadarChart.tsx         # Player stat radar
│   │   │
│   │   ├── hooks/
│   │   │   ├── useApi.ts                 # Generic fetch wrapper
│   │   │   ├── usePlayers.ts             # Player data hook
│   │   │   ├── usePredictions.ts         # Prediction data hook
│   │   │   ├── useOptimization.ts        # Optimization trigger hook
│   │   │   └── useTransfers.ts           # Transfer plan hook
│   │   │
│   │   ├── lib/
│   │   │   ├── api-client.ts             # Axios/fetch client config
│   │   │   ├── utils.ts                  # General utilities
│   │   │   └── constants.ts              # Positions, formations, etc.
│   │   │
│   │   ├── stores/
│   │   │   ├── team-store.ts             # Zustand: current team state
│   │   │   ├── optimization-store.ts     # Zustand: optimization params
│   │   │   └── ui-store.ts               # Zustand: UI preferences
│   │   │
│   │   └── types/
│   │       ├── player.ts                 # Player interface
│   │       ├── prediction.ts             # Prediction types
│   │       ├── optimization.ts           # Optimization types
│   │       ├── transfer.ts               # Transfer types
│   │       └── api.ts                    # API response wrappers
│   │
│   └── tests/
│       ├── setup.ts
│       ├── components/
│       └── hooks/
│
└── shared/
    └── types/
        ├── player.schema.json            # JSON Schema for cross-language types
        ├── prediction.schema.json
        └── optimization.schema.json
```

---

## 3. Backend API Endpoints

### 3.1 Health & Meta

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Liveness / readiness probe |
| GET | `/api/meta/gameweeks` | List all gameweeks with deadlines |
| GET | `/api/meta/teams` | All PL clubs |

### 3.2 Data Endpoints (`/api/data`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/data/players` | All players with current stats. Query params: `position`, `team`, `min_price`, `max_price`, `sort_by`, `order`, `page`, `limit` |
| GET | `/api/data/players/{player_id}` | Detailed player profile + historical GW data |
| GET | `/api/data/players/{player_id}/history` | Full season-by-season history |
| GET | `/api/data/fixtures` | Upcoming fixtures with FDR (Fixture Difficulty Rating) |
| GET | `/api/data/fixtures/{gameweek}` | Fixtures for specific gameweek |
| GET | `/api/data/live/{gameweek}` | Live GW scores (during matches) |
| GET | `/api/data/effective-ownership` | Effective ownership percentages (top 10k) |
| POST | `/api/data/refresh` | Force-refresh cached FPL data |

### 3.3 Prediction Endpoints (`/api/predict`)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/predict/points` | Predict expected points for players. Body: `{ player_ids?: number[], gameweeks: number[], model?: "arima" \| "weighted_avg" \| "hybrid" \| "exponential" \| "monte_carlo" \| "ensemble" }` |
| GET | `/api/predict/players/{player_id}` | Get cached predictions for a single player across next 5 GWs |
| POST | `/api/predict/batch` | Bulk prediction for all players for specified GWs. Body: `{ gameweeks: number[], model?: string }` |
| GET | `/api/predict/models` | List available models with metadata and backtesting scores |
| POST | `/api/predict/backtest` | Run backtest of a model over historical GWs. Body: `{ model: string, gw_start: number, gw_end: number }` |

### 3.4 Optimization Endpoints (`/api/optimize`)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/optimize/squad` | Select optimal 15-player squad. Body: `{ budget: number, formation?: string, method?: "ilp" \| "ga", locked_players?: number[], excluded_players?: number[], gameweek: number, horizon?: number, objective?: "maximize_points" \| "maximize_value" }` |
| POST | `/api/optimize/captain` | Select captain/vice-captain from given XI. Body: `{ player_ids: number[], gameweek: number, differential?: boolean }` |
| POST | `/api/optimize/bench` | Optimize bench order given XI and subs. Body: `{ xi_ids: number[], bench_ids: number[], gameweek: number }` |
| POST | `/api/optimize/formation` | Find optimal formation for a given squad. Body: `{ player_ids: number[], gameweek: number }` |
| POST | `/api/optimize/sensitivity` | Sensitivity analysis: how much would each swap affect total xPts. Body: `{ squad_ids: number[], gameweek: number }` |

### 3.5 Transfer Endpoints (`/api/transfers`)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/transfers/recommend` | Recommend best transfers. Body: `{ current_squad: number[], bank: number, free_transfers: number, horizon: number, max_hits?: number }` |
| POST | `/api/transfers/plan` | Multi-GW transfer plan with rolling horizon. Body: `{ current_squad: number[], bank: number, free_transfers: number, horizon: number, max_hits_per_gw?: number }` |
| POST | `/api/transfers/evaluate` | Evaluate a proposed set of transfers. Body: `{ transfers_in: number[], transfers_out: number[], current_squad: number[], bank: number }` |

### 3.6 Chip Strategy Endpoints (`/api/chips`)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/chips/strategy` | Recommend chip usage over remaining GWs. Body: `{ current_squad: number[], available_chips: string[], current_gw: number, bank: number, free_transfers: number }` |
| POST | `/api/chips/simulate` | Simulate using a specific chip in a specific GW. Body: `{ chip: "wildcard" \| "triple_captain" \| "bench_boost" \| "free_hit", gameweek: number, current_squad: number[] }` |

---

## 4. Data Layer Design

### 4.1 FPL API Client (`app/data/fpl_client.py`)

```python
class FPLClient:
    """Async HTTP client for the official FPL API."""

    BASE_URL = "https://fantasy.premierleague.com/api"

    ENDPOINTS = {
        "bootstrap": "/bootstrap-static/",          # All players, teams, GWs
        "element_summary": "/element-summary/{id}/", # Player detailed history
        "fixtures": "/fixtures/",                     # All fixtures
        "live": "/event/{gw}/live/",                  # Live GW data
        "entry": "/entry/{id}/",                      # Manager info
        "entry_history": "/entry/{id}/history/",      # Manager season history
        "entry_picks": "/entry/{id}/event/{gw}/picks/", # Manager GW picks
        "dream_team": "/dream-team/{gw}/",            # GW dream team
    }

    async def get_bootstrap(self) -> BootstrapData: ...
    async def get_player_summary(self, player_id: int) -> PlayerSummary: ...
    async def get_fixtures(self, gameweek: int | None = None) -> list[Fixture]: ...
    async def get_live_gameweek(self, gameweek: int) -> LiveGameweekData: ...
    async def get_entry(self, entry_id: int) -> EntryData: ...
```

**Rate Limiting:** Polite 1 req/sec rate limiter via `asyncio.Semaphore` + `aiohttp`.

### 4.2 Historical Data Loader (`app/data/github_loader.py`)

```python
class GitHubDataLoader:
    """Loads historical FPL data from vaastav/Fantasy-Premier-League repo."""

    REPO = "vaastav/Fantasy-Premier-League"
    BASE_URL = "https://raw.githubusercontent.com/{repo}/master/data/{season}"

    async def load_season(self, season: str) -> SeasonData: ...
    async def load_player_gameweeks(self, season: str, player_name: str) -> pd.DataFrame: ...
    async def load_all_gw_data(self, season: str) -> pd.DataFrame: ...
    async def load_fixtures(self, season: str) -> pd.DataFrame: ...
```

### 4.3 Data Preprocessing Pipeline (`app/data/preprocessing.py`)

```python
class DataPipeline:
    """Feature engineering and data transformation pipeline."""

    def build_player_features(self, raw_data: pd.DataFrame) -> pd.DataFrame:
        """
        Input: raw per-GW player data.
        Output: feature matrix with columns:
          - Base: minutes, goals, assists, clean_sheets, bonus, bps
          - Advanced: ict_index, influence, creativity, threat
          - Expected: xG, xA, xGI (expected goal involvement)
          - Form: rolling_3gw_avg, rolling_5gw_avg, form_trend
          - Fixture: fdr_next_1, fdr_next_3, fdr_next_5
          - Ownership: selected_by_percent, transfers_in_delta, eo_top10k
          - Value: now_cost, value_form, value_season
        """
        ...

    def handle_missing_data(self, df: pd.DataFrame) -> pd.DataFrame: ...
    def normalize_features(self, df: pd.DataFrame) -> pd.DataFrame: ...
    def create_target(self, df: pd.DataFrame, horizon: int = 1) -> pd.Series: ...
```

### 4.4 Caching Strategy (`app/data/cache.py`)

```python
class CacheLayer:
    """Two-tier caching: in-memory (LRU) + Redis."""

    # TTL Configuration:
    # - bootstrap-static:  6 hours  (refreshed ~2x daily by FPL)
    # - element-summary:   4 hours
    # - fixtures:          24 hours (changes rarely)
    # - live GW data:      60 seconds (during matches)
    # - predictions:       1 hour (recomputed on demand)
    # - optimization:      0 (never cached; depends on user inputs)

    async def get(self, key: str) -> Any | None: ...
    async def set(self, key: str, value: Any, ttl: int) -> None: ...
    async def invalidate(self, pattern: str) -> None: ...
```

**Storage:** Redis 7 for shared cache (multi-worker), Python `functools.lru_cache` for hot per-process data.

### 4.5 Database Models (`app/data/models.py`)

For persistence of user sessions and precomputed predictions:

```python
# SQLite for development, PostgreSQL for production (via SQLAlchemy 2.0)

class Player(Base):
    __tablename__ = "players"
    id: int                    # FPL element ID
    web_name: str
    team_id: int
    position: str              # GKP, DEF, MID, FWD
    now_cost: int              # price * 10
    # Denormalized stats (refreshed from API)
    total_points: int
    ict_index: float
    form: float
    selected_by_percent: float

class Prediction(Base):
    __tablename__ = "predictions"
    id: int
    player_id: int             # FK -> players.id
    gameweek: int
    model: str                 # arima, weighted_avg, hybrid, etc.
    predicted_points: float
    confidence_lower: float    # 90% CI lower
    confidence_upper: float    # 90% CI upper
    created_at: datetime

class OptimizationRun(Base):
    __tablename__ = "optimization_runs"
    id: int
    params_json: str           # Serialized request params
    result_json: str           # Serialized squad result
    method: str                # ilp, ga
    solve_time_ms: int
    created_at: datetime
```

---

## 5. Prediction Engine Design

### 5.1 Abstract Base Model

```python
class BasePredictor(ABC):
    """All prediction models implement this interface."""

    @abstractmethod
    def fit(self, data: pd.DataFrame) -> None:
        """Train on historical data."""
        ...

    @abstractmethod
    def predict(self, player_id: int, gameweeks: list[int]) -> list[PointPrediction]:
        """Return predicted points with confidence intervals."""
        ...

    @abstractmethod
    def backtest(self, data: pd.DataFrame, gw_range: range) -> BacktestResult:
        """Evaluate on held-out gameweeks, return MAE / cumulative points."""
        ...
```

### 5.2 Model Implementations

#### ARIMA(1,0,0) with Rolling Window (Primary - Best performer at 704 cumulative pts)

```python
class ARIMAPredictor(BasePredictor):
    """
    ARIMA(1,0,0) fit on a rolling window of recent GWs.
    - Window size: 10 gameweeks (configurable)
    - Re-fit per player per prediction request
    - Uses statsmodels.tsa.arima.model.ARIMA
    - Predictions clipped to [0, 25] range
    """
    def __init__(self, window_size: int = 10, order: tuple = (1, 0, 0)): ...
```

#### Weighted Average with Recency Bias (Secondary - Consistent at 635 pts)

```python
class WeightedAvgPredictor(BasePredictor):
    """
    Exponentially decaying weights over recent GW points.
    - decay_factor: 0.85 (most recent GW has weight 1.0, previous 0.85, etc.)
    - Minimum 3 GWs of data required
    - Handles blank GWs (fixtures postponed)
    """
    def __init__(self, decay_factor: float = 0.85, min_gameweeks: int = 3): ...
```

#### Hybrid Ridge + XGBoost/SHAP (Tertiary - Best for feature analysis)

```python
class HybridPredictor(BasePredictor):
    """
    Blended model: lambda * Ridge + (1 - lambda) * XGBoost
    - lambda = 2/3 (Ridge-dominant blend)
    - Features: ICT index, xGI, xG, xA, form, FDR, minutes
    - SHAP values computed for explainability
    - XGBoost handles non-linear interactions
    - Ridge provides stable baseline
    """
    def __init__(self, blend_lambda: float = 2/3): ...
    def get_shap_values(self, player_id: int) -> dict[str, float]: ...
```

#### Exponential Smoothing (Holt-Winters)

```python
class ExponentialPredictor(BasePredictor):
    """
    Holt-Winters triple exponential smoothing.
    - Captures level, trend, and seasonal (GW-cycle) components
    - Uses statsmodels.tsa.holtwinters.ExponentialSmoothing
    """
    ...
```

#### Monte Carlo Simulation

```python
class MonteCarloPredictor(BasePredictor):
    """
    Simulate N=10,000 GW outcomes per player based on:
    - Probability distributions for goals/assists/CS derived from xG/xA/xGA
    - Minutes probability from recent starts
    - Bonus point distribution
    Returns: mean, median, P10, P90
    """
    def __init__(self, n_simulations: int = 10_000): ...
```

### 5.3 Ensemble & Model Selection

```python
class PredictionEngine:
    """
    Orchestrates all models and selects the best prediction strategy.

    Model selection logic:
    1. If backtest data is available for the current season, pick the model
       with the lowest MAE on the most recent 3-GW holdout.
    2. Otherwise, default to ARIMA (historically best).
    3. Ensemble mode: weighted average of all models, weights proportional
       to inverse MAE on holdout.

    Caching: Predictions are cached per (player_id, gameweek, model) tuple
    with 1-hour TTL.
    """

    models: dict[str, BasePredictor]    # Registry of all models
    default_model: str = "arima"

    def predict_all_players(self, gameweeks: list[int], model: str = "ensemble") -> pd.DataFrame: ...
    def select_best_model(self, holdout_gws: list[int]) -> str: ...
    def predict_ensemble(self, player_id: int, gameweeks: list[int]) -> list[PointPrediction]: ...
```

---

## 6. Optimization Engine Design

### 6.1 ILP Solver (Primary - PuLP)

```python
class ILPSolver:
    """
    Integer Linear Programming solver using PuLP.

    Decision Variables:
      x_j in {0, 1}  -- player j selected in squad (15 players)
      s_j in {0, 1}  -- player j in starting XI (11 players)
      c_j in {0, 1}  -- player j is captain (1 player)
      v_j in {0, 1}  -- player j is vice-captain (1 player)

    Objective:
      Maximize SUM(predicted_pts_j * s_j) + SUM(predicted_pts_j * c_j)
      (captain scores double, so the bonus term adds their points once more)

    Constraints:
      1. SUM(x_j) = 15                              (squad size)
      2. SUM(s_j) = 11                              (starting XI)
      3. s_j <= x_j for all j                       (starters must be in squad)
      4. c_j <= s_j for all j                       (captain must be starter)
      5. v_j <= s_j for all j                       (vice must be starter)
      6. SUM(c_j) = 1                               (exactly one captain)
      7. SUM(v_j) = 1                               (exactly one vice)
      8. c_j + v_j <= 1 for all j                   (captain != vice)
      9. SUM(x_j * price_j) <= budget               (budget constraint)
      10. SUM(x_j where team_j=t) <= 3 for each t   (max 3 per club)
      11. SUM(s_j where pos_j=GKP) = 1              (1 starting GK)
      12. SUM(x_j where pos_j=GKP) = 2              (2 GKs in squad)
      13. 3 <= SUM(s_j where pos_j=DEF) <= 5        (3-5 DEF)
      14. 3 <= SUM(s_j where pos_j=MID) <= 5        (3-5 MID)
      15. 1 <= SUM(s_j where pos_j=FWD) <= 3        (1-3 FWD)
      16. x_j = 1 for j in locked_players            (user locks)
      17. x_j = 0 for j in excluded_players           (user excludes)

    Solver: CBC (default in PuLP), GLPK as fallback.
    Typical solve time: <2 seconds for 15-player squad.
    """

    def solve(self, params: OptimizationRequest) -> OptimizationResult: ...
```

### 6.2 Genetic Algorithm (Secondary - Diverse Exploration)

```python
class GASolver:
    """
    Genetic Algorithm for exploring diverse squad compositions.

    Encoding: Binary chromosome of length N_players.
    Population: 200 individuals.
    Selection: Tournament selection (k=5).
    Crossover: Uniform crossover with constraint repair.
    Mutation: Swap mutation (replace one player with feasible alternative).
    Fitness: Same objective as ILP.
    Termination: 500 generations or 30s wall-clock.

    Use case: When user wants to see multiple good-but-different squads
    (e.g., "Show me 5 alternative squads").
    """

    def solve(self, params: OptimizationRequest, n_solutions: int = 5) -> list[OptimizationResult]: ...
```

### 6.3 Constraint System

```python
class ConstraintManager:
    """
    Reusable constraint builder for both ILP and GA.

    Built-in constraints:
    - SquadSizeConstraint(15)
    - StartingXIConstraint(11)
    - BudgetConstraint(budget=1000)  # in 0.1m units
    - ClubLimitConstraint(max_per_club=3)
    - PositionConstraint(gkp=2, def_range=(3,5), mid_range=(3,5), fwd_range=(1,3))
    - FormationConstraint(formation="3-5-2")  # optional specific formation
    - LockedPlayersConstraint(player_ids=[...])
    - ExcludedPlayersConstraint(player_ids=[...])

    Custom constraints (advanced users):
    - MinMinutesConstraint(min_minutes=60)    # only players averaging 60+ mins
    - MaxPriceConstraint(max_price=130)       # max individual price
    - DifferentialConstraint(max_ownership=5) # max 5% ownership players only
    """
    ...
```

### 6.4 Captain Selection

```python
class CaptainSelector:
    """
    Captain selection with differential option.

    Standard: Pick highest predicted-points player from XI.
    Differential: Pick highest (predicted_points * (1 - effective_ownership/100))
                  to maximize rank gain vs field.

    Also computes expected captain points for each XI player for UI display.
    """
    def select(self, xi: list[Player], gameweek: int, differential: bool = False) -> CaptainPick: ...
```

### 6.5 Bench Optimization

```python
class BenchOptimizer:
    """
    Optimal bench ordering for auto-substitution.

    Bench order is: 1st sub, 2nd sub, 3rd sub (plus GK sub).
    Ordered by: P(starter doesn't play) * predicted_points_of_sub.
    Uses minutes probability to estimate non-appearance risk.
    """
    def optimize(self, xi: list[Player], bench: list[Player], gameweek: int) -> list[Player]: ...
```

### 6.6 Sensitivity Analysis

```python
class SensitivityAnalyzer:
    """
    For each player in the squad, compute:
    - Marginal value: How much total xPts drops if this player is removed
      and replaced with the best available alternative.
    - Break-even: The minimum points this player must score for the squad
      to be optimal vs. the next-best alternative.
    - Transfer urgency: Combines marginal value + fixture swing + injury risk.
    """
    def analyze(self, squad: list[Player], gameweek: int) -> list[SensitivityResult]: ...
```

---

## 7. Transfer Strategy Module Design

### 7.1 Rolling Horizon Optimizer

```python
class RollingHorizonOptimizer:
    """
    Multi-gameweek transfer planning.

    Algorithm:
    1. For a planning horizon of H gameweeks (default H=5):
    2. At each GW t, decide which transfers to make (0, 1, or 2+):
       - Free transfers available: min(ft_t, 5) where ft_t accumulates
       - Each extra transfer costs -4 points (hit)
    3. Solve a multi-period ILP:
       - Variables: x_j_t (player j in squad at GW t), transfer_in_j_t, transfer_out_j_t
       - Objective: SUM over t of [expected_points_t - 4 * extra_transfers_t]
       - Constraints: squad validity at each GW, budget feasibility, transfer chain consistency
    4. Return the full plan but only execute GW t decisions (re-solve next GW).

    Computational budget: Target <10s solve time. If infeasible, reduce horizon to H=3.
    """

    def plan(self, params: TransferPlanRequest) -> TransferPlan: ...
```

### 7.2 Transfer Cost Model

```python
class TransferCostModel:
    """
    Evaluates the true cost of a transfer beyond the -4 hit.

    Factors:
    - Points hit: -4 per extra transfer
    - Price change risk: players rising/falling in price
    - Opportunity cost: holding a FT vs using it
    - Value of a FT is approximately 2-4 points (empirically)

    Decision rule for a single transfer:
    transfer_if: predicted_gain_over_horizon > hit_cost + ft_opportunity_cost
    """
    def evaluate(self, transfer_in: Player, transfer_out: Player, horizon: int) -> TransferEvaluation: ...
```

### 7.3 Chip Strategy

```python
class ChipStrategyOptimizer:
    """
    Determines optimal GW to play each chip.

    Chips:
    - Wildcard (2x per season: 1 before GW20, 1 after): unlimited free transfers
    - Free Hit (1x): temporary full squad rebuild for 1 GW
    - Triple Captain (1x): captain scores 3x instead of 2x
    - Bench Boost (1x): bench players score points

    Strategy:
    1. For each remaining chip, score each future GW by chip-specific value:
       - WC: SUM(predicted_gain_from_optimal_rebuild) -- best when squad needs 5+ changes
       - FH: MAX(single_gw_squad_pts - current_squad_pts) -- best for DGWs/BGWs
       - TC: MAX(captain_xPts) -- best for DGW captains
       - BB: SUM(bench_xPts) -- best when bench is strong (DGW)
    2. Greedily assign chips to their highest-value GW, no two chips on same GW.
    3. Return ranked chip schedule with expected value of each placement.
    """
    def recommend(self, params: ChipStrategyRequest) -> ChipSchedule: ...
    def simulate_chip(self, chip: str, gameweek: int, squad: list[Player]) -> ChipSimResult: ...
```

---

## 8. Frontend Design

### 8.1 Pages & Routing

| Route | Page | Description |
|-------|------|-------------|
| `/` | Dashboard | Overview: current GW, top picks, quick actions |
| `/team` | My Team | Visual pitch view of current/optimized squad |
| `/optimize` | Optimizer | Full optimization controls, results, comparison |
| `/transfers` | Transfer Planner | Multi-GW transfer timeline and recommendations |
| `/predictions` | Predictions | Player prediction explorer, model comparison |
| `/players` | Player Database | Sortable/filterable table, search, compare |
| `/players/[id]` | Player Detail | Full stats, prediction charts, fixture ticker |
| `/chips` | Chip Planner | Chip timing strategy and simulations |

### 8.2 Dashboard Layout

```
+----------------------------------------------------------+
|  Navbar: [Logo] [Dashboard] [Team] [Optimize] [Transfers]|
|          [Predictions] [Players] [Chips]        [GW: 25] |
+----------------------------------------------------------+
|                                                          |
|  +-------------------+  +-----------------------------+  |
|  | Current GW Info   |  | Quick Actions               |  |
|  | GW 25 Deadline:   |  | [Optimize Squad]            |  |
|  | Sat 15 Mar 11:00  |  | [Suggest Transfers]         |  |
|  | Most captained:   |  | [View Predictions]          |  |
|  | Haaland (34.2%)   |  |                             |  |
|  +-------------------+  +-----------------------------+  |
|                                                          |
|  +---------------------------------------------------+  |
|  | Top Predicted Players This GW                      |  |
|  | # | Player     | Team | Pos | xPts | Price | EO   |  |
|  | 1 | Haaland    | MCI  | FWD | 8.2  | 14.3  | 142% |  |
|  | 2 | Salah      | LIV  | MID | 7.8  | 13.1  | 138% |  |
|  | 3 | Palmer     | CHE  | MID | 6.9  | 10.8  | 89%  |  |
|  +---------------------------------------------------+  |
|                                                          |
|  +------------------------+  +------------------------+  |
|  | Points Prediction      |  | Transfer Suggestions   |  |
|  | [Line chart: xPts      |  | OUT: Player A (2.1)    |  |
|  |  over next 5 GWs]      |  | IN:  Player B (6.3)    |  |
|  |                        |  | Gain: +4.2 pts/GW      |  |
|  +------------------------+  +------------------------+  |
+----------------------------------------------------------+
```

### 8.3 Team View (Pitch View)

```
+----------------------------------------------------------+
|  [Formation: 3-5-2 v]  [Budget: 98.5/100.0]  [ITB: 1.5] |
+----------------------------------------------------------+
|                                                          |
|                     GK                                   |
|                  [Raya 5.2]                              |
|                                                          |
|            DEF    DEF    DEF                             |
|         [Saliba] [VVD] [Gabriel]                         |
|          5.8     6.5    5.3                              |
|                                                          |
|       MID   MID   MID   MID   MID                       |
|     [Salah][Palmer][Saka][Eze][Mbeumo]                   |
|      13.1  10.8   9.2   6.1  7.0                        |
|                                                          |
|              FWD         FWD                              |
|           [Haaland]   [Watkins]                          |
|             14.3        7.8                               |
|                                                          |
+----------------------------------------------------------+
| BENCH: [Henderson 4.5] [Lewis 4.0] [Wissa 6.2] [Ait-N] |
+----------------------------------------------------------+
| Captain: Haaland (C)  |  Vice: Salah (V)                |
| Total xPts: 62.4      |  Effective Ownership delta: +3.1 |
+----------------------------------------------------------+
```

### 8.4 State Management (Zustand)

```typescript
// stores/team-store.ts
interface TeamState {
  squad: Player[];          // 15 players
  xi: Player[];             // 11 starters
  bench: Player[];          // 4 bench
  captain: Player | null;
  viceCaptain: Player | null;
  formation: string;        // "3-5-2"
  budget: number;
  bank: number;
  freeTransfers: number;

  // Actions
  setSquad: (squad: Player[]) => void;
  swapPlayer: (out: Player, into: Player) => void;
  setCaptain: (player: Player) => void;
  setFormation: (formation: string) => void;
}

// stores/optimization-store.ts
interface OptimizationState {
  isOptimizing: boolean;
  method: 'ilp' | 'ga';
  result: OptimizationResult | null;
  constraints: ConstraintConfig;
  lockedPlayers: number[];
  excludedPlayers: number[];

  // Actions
  optimize: () => Promise<void>;
  lockPlayer: (id: number) => void;
  excludePlayer: (id: number) => void;
  setMethod: (method: 'ilp' | 'ga') => void;
}
```

### 8.5 Key UI Components

**PitchView** (`components/team/PitchView.tsx`):
- SVG-based football pitch with positioned player cards
- Drag-and-drop for manual lineup changes
- Color-coded by fixture difficulty
- Click player card to see prediction details

**OptimizePanel** (`components/optimization/OptimizePanel.tsx`):
- Budget slider
- Formation selector (or "Auto" to let optimizer decide)
- Lock/exclude player toggles
- Horizon selector (1-5 GWs)
- Method toggle (ILP vs GA)
- "Optimize" button with loading spinner
- Displays solve time and objective value

**TransferPlanner** (`components/transfers/TransferPlanner.tsx`):
- Horizontal timeline showing GWs
- Each GW shows: planned transfers, free transfers available, cumulative hits
- Drag-and-drop transfers between GWs
- Net points gain/loss visualization per GW

**PredictionChart** (`components/prediction/PredictionChart.tsx`):
- Line chart (Recharts) showing predicted points over next 5 GWs
- Shaded confidence interval bands
- Toggle between models
- Overlay actual points as they come in

---

## 9. Tech Stack

### 9.1 Backend

| Dependency | Version | Purpose |
|-----------|---------|---------|
| Python | 3.12+ | Runtime |
| FastAPI | 0.115.x | Web framework |
| Uvicorn | 0.34.x | ASGI server |
| Pydantic | 2.10.x | Data validation & serialization |
| SQLAlchemy | 2.0.x | ORM / database toolkit |
| Alembic | 1.14.x | Database migrations |
| aiohttp | 3.11.x | Async HTTP client (FPL API) |
| Redis (redis-py) | 5.2.x | Caching layer |
| PuLP | 2.9.x | ILP solver |
| pandas | 2.2.x | Data manipulation |
| NumPy | 2.1.x | Numerical computing |
| scikit-learn | 1.6.x | Ridge regression, preprocessing |
| XGBoost | 2.1.x | Gradient boosted trees |
| statsmodels | 0.14.x | ARIMA, Holt-Winters |
| SHAP | 0.46.x | Model explainability |
| DEAP | 1.4.x | Genetic Algorithm framework |
| pytest | 8.3.x | Testing framework |
| pytest-asyncio | 0.25.x | Async test support |
| httpx | 0.28.x | Test client for FastAPI |
| ruff | 0.8.x | Linter + formatter |
| mypy | 1.13.x | Static type checking |

### 9.2 Frontend

| Dependency | Version | Purpose |
|-----------|---------|---------|
| Node.js | 22 LTS | Runtime |
| Next.js | 15.x | React framework (App Router) |
| React | 19.x | UI library |
| TypeScript | 5.7.x | Type safety |
| Tailwind CSS | 4.x | Utility-first styling |
| shadcn/ui | latest | Component primitives |
| Zustand | 5.x | State management |
| React Query (TanStack) | 5.x | Server state / data fetching |
| Recharts | 2.15.x | Charting library |
| Axios | 1.7.x | HTTP client |
| Zod | 3.24.x | Runtime schema validation |
| Vitest | 2.x | Unit testing |
| Playwright | 1.49.x | E2E testing |
| pnpm | 9.x | Package manager |

### 9.3 Infrastructure

| Tool | Version | Purpose |
|------|---------|---------|
| Docker | 27.x | Containerization |
| Docker Compose | 2.31.x | Local orchestration |
| PostgreSQL | 17 | Production database |
| SQLite | 3.x | Development database |
| Redis | 7.4.x | Caching / rate limiting |
| GitHub Actions | - | CI/CD pipeline |

---

## 10. Milestone-Based Implementation Plan

### Milestone 1: Foundation (Week 1-2)
**Deliverables:**
- Project scaffolding: monorepo structure, Docker Compose, Makefiles
- Backend: FastAPI app skeleton, config, health endpoint
- Frontend: Next.js app with routing, layout, Tailwind, shadcn/ui setup
- Data layer: FPL API client with caching, bootstrap data loading
- `/api/data/players` and `/api/data/fixtures` endpoints functional
- Basic player list page in frontend with sorting/filtering
- CI pipeline: lint, type-check, test (both backend and frontend)

### Milestone 2: Prediction Engine (Week 3-4)
**Deliverables:**
- Historical data loader (vaastav GitHub dataset)
- Feature engineering pipeline (ICT, xG, xA, form, fixtures)
- ARIMA(1,0,0) model implementation with rolling window
- Weighted average model implementation
- Hybrid Ridge+XGBoost model with SHAP
- Ensemble model selector with backtesting
- `/api/predict/*` endpoints
- Prediction explorer page with charts and model comparison
- Unit tests for all prediction models with mock data

### Milestone 3: Optimization Engine (Week 5-6)
**Deliverables:**
- ILP solver (PuLP) with full constraint system
- Captain and vice-captain selection
- Bench ordering optimization
- Formation auto-selection
- GA solver for diverse squad exploration
- Sensitivity analysis
- `/api/optimize/*` endpoints
- Team pitch view with formation display
- Optimization controls panel in frontend
- Before/after comparison view

### Milestone 4: Transfer Strategy (Week 7-8)
**Deliverables:**
- Single-transfer evaluation model
- Rolling horizon multi-GW transfer planner
- Transfer cost model (hits vs. gains)
- `/api/transfers/*` endpoints
- Transfer planner timeline UI
- Transfer recommendation cards with gain/loss visualization

### Milestone 5: Chip Strategy & Polish (Week 9-10)
**Deliverables:**
- Chip timing optimizer (WC, FH, TC, BB)
- Chip simulation for each remaining GW
- `/api/chips/*` endpoints
- Chip planner page with strategy visualization
- Effective ownership integration
- Differential captaincy analysis
- Dashboard page with all quick-action widgets
- Responsive design pass (mobile-friendly)

### Milestone 6: Production Readiness (Week 11-12)
**Deliverables:**
- PostgreSQL migration and production config
- Redis caching in production
- API rate limiting and error handling
- Performance optimization (prediction caching, query optimization)
- E2E tests with Playwright
- Docker production images
- Documentation: API docs (auto-generated via FastAPI /docs), user guide
- Deployment configuration (Docker Compose for self-hosting)
- Load testing and performance benchmarks

---

## 11. Data Flow Diagram

```
                         +------------------+
                         |   FPL Official   |
                         |      API         |
                         +--------+---------+
                                  |
                                  v
+------------------+    +------------------+    +------------------+
|  vaastav/FPL     +--->|   Data Layer     +--->|     Redis        |
|  GitHub Dataset  |    |  (FPL Client +   |    |     Cache        |
+------------------+    |   Preprocessing) |    +------------------+
                        +--------+---------+
                                 |
                    +------------+------------+
                    |            |            |
                    v            v            v
            +-------+--+  +----+-----+  +---+--------+
            | Prediction|  |Optimization| |  Transfer  |
            |  Engine   |  |  Engine   | |  Strategy  |
            |           |  |           | |  Module    |
            +-----------+  +-----------+ +------------+
                    |            |            |
                    v            v            v
               +----+------------+------------+----+
               |           FastAPI Backend         |
               |     (REST API + WebSocket)        |
               +-------------------+---------------+
                                   |
                                   | HTTP/JSON
                                   v
               +-------------------+---------------+
               |         Next.js Frontend          |
               |  React + Zustand + React Query    |
               |  Recharts + shadcn/ui + Tailwind  |
               +-----------------------------------+
```

---

## 12. Key Design Decisions

1. **Deterministic over Robust Optimization**: Research shows robust optimization underperforms deterministic for FPL. We use deterministic ILP as primary, with confidence intervals for user information only.

2. **ARIMA as Default Model**: ARIMA(1,0,0) scored 704 cumulative points in benchmarks, outperforming all other individual models. Ensemble is available but ARIMA is the safe default.

3. **Rolling Horizon over Myopic**: Single-GW optimization misses transfer chain value. Rolling horizon (5 GW lookahead) captures the value of banking transfers and planning ahead.

4. **3-5-2 as Default Formation**: Research indicates 3-5-2 produces the highest expected points. The optimizer can override this, but it serves as a sensible starting formation.

5. **Server-Side Prediction Caching**: Predictions are cached for 1 hour because the underlying data (player stats) changes at most twice daily. Optimization is never cached because it depends on user-specific constraints.

6. **Separate ILP and GA Solvers**: ILP gives the provably optimal squad but only one solution. GA gives multiple diverse solutions for exploration. Both have value and serve different user needs.

7. **Feature-Driven ML over Pure Time Series**: The hybrid model (Ridge + XGBoost) with ICT, xG, xA features provides the best explainability through SHAP values, which is critical for user trust and understanding.

8. **React Query for Server State**: All API data flows through React Query for automatic caching, refetching, and optimistic updates. Zustand handles only client-side UI state (selections, preferences).

---

## 13. API Request/Response Examples

### POST `/api/optimize/squad`

**Request:**
```json
{
  "budget": 1000,
  "formation": "auto",
  "method": "ilp",
  "locked_players": [233, 318],
  "excluded_players": [112],
  "gameweek": 25,
  "horizon": 3,
  "objective": "maximize_points"
}
```

**Response:**
```json
{
  "status": "optimal",
  "solve_time_ms": 1240,
  "objective_value": 68.4,
  "squad": {
    "formation": "3-5-2",
    "xi": [
      {"id": 233, "name": "Haaland", "team": "MCI", "position": "FWD", "predicted_pts": 8.2, "price": 143, "is_captain": true, "is_vice": false},
      {"id": 318, "name": "Salah", "team": "LIV", "position": "MID", "predicted_pts": 7.8, "price": 131, "is_captain": false, "is_vice": true}
    ],
    "bench": [
      {"id": 401, "name": "Henderson", "team": "CRY", "position": "GKP", "predicted_pts": 3.1, "price": 45, "bench_order": 0}
    ],
    "total_predicted_pts": 68.4,
    "total_cost": 985,
    "remaining_budget": 15
  }
}
```

### POST `/api/predict/points`

**Request:**
```json
{
  "player_ids": [233, 318, 427],
  "gameweeks": [25, 26, 27, 28, 29],
  "model": "ensemble"
}
```

**Response:**
```json
{
  "model_used": "ensemble",
  "predictions": [
    {
      "player_id": 233,
      "player_name": "Haaland",
      "gameweeks": [
        {"gw": 25, "predicted_pts": 8.2, "ci_lower": 4.1, "ci_upper": 14.3},
        {"gw": 26, "predicted_pts": 6.5, "ci_lower": 2.8, "ci_upper": 11.9}
      ]
    }
  ],
  "model_weights": {
    "arima": 0.40,
    "weighted_avg": 0.20,
    "hybrid": 0.25,
    "exponential": 0.10,
    "monte_carlo": 0.05
  }
}
```

### POST `/api/transfers/plan`

**Request:**
```json
{
  "current_squad": [233, 318, 427, 112, 89, 201, 55, 340, 178, 292, 405, 67, 388, 156, 444],
  "bank": 15,
  "free_transfers": 2,
  "horizon": 5,
  "max_hits_per_gw": 1
}
```

**Response:**
```json
{
  "plan": [
    {
      "gameweek": 25,
      "transfers": [
        {"out": {"id": 112, "name": "Son", "price": 98}, "in": {"id": 427, "name": "Palmer", "price": 108}}
      ],
      "free_transfers_used": 1,
      "hits": 0,
      "expected_gain": 4.2,
      "squad_predicted_pts": 64.1
    },
    {
      "gameweek": 26,
      "transfers": [],
      "free_transfers_used": 0,
      "hits": 0,
      "expected_gain": 0,
      "squad_predicted_pts": 58.7
    }
  ],
  "total_expected_gain": 12.8,
  "total_hits_cost": 0
}
```

---

## 14. Environment Configuration

### `.env.example`
```bash
# Backend
ENVIRONMENT=development
DEBUG=true
DATABASE_URL=sqlite:///./fpl_picker.db
REDIS_URL=redis://localhost:6379/0
FPL_API_BASE_URL=https://fantasy.premierleague.com/api
LOG_LEVEL=INFO
CORS_ORIGINS=http://localhost:3000

# Frontend
NEXT_PUBLIC_API_URL=http://localhost:8000/api
NEXT_PUBLIC_APP_NAME=FPL Picker
```

### `docker-compose.yml` (services)
```yaml
services:
  backend:
    build: ./backend
    ports: ["8000:8000"]
    depends_on: [redis, db]
    env_file: .env

  frontend:
    build: ./frontend
    ports: ["3000:3000"]
    depends_on: [backend]
    env_file: .env

  redis:
    image: redis:7.4-alpine
    ports: ["6379:6379"]

  db:
    image: postgres:17-alpine
    ports: ["5432:5432"]
    environment:
      POSTGRES_DB: fpl_picker
      POSTGRES_USER: fpl
      POSTGRES_PASSWORD: fpl_secret
    volumes:
      - pgdata:/var/lib/postgresql/data

volumes:
  pgdata:
```

---

## 15. Testing Strategy

| Layer | Tool | Coverage Target | Strategy |
|-------|------|----------------|----------|
| Backend unit | pytest | 90%+ | Mock FPL API responses, test each predictor/solver independently |
| Backend integration | pytest + httpx | 80%+ | Test full API request/response cycles with test database |
| Prediction accuracy | pytest | N/A | Backtest each model on historical GWs 1-38, assert MAE < threshold |
| Optimization correctness | pytest | 100% constraints | Verify every constraint is satisfied in solutions; compare ILP vs brute-force on small instances |
| Frontend unit | Vitest | 80%+ | Test hooks, stores, utility functions |
| Frontend component | Vitest + Testing Library | 70%+ | Test component rendering, user interactions |
| E2E | Playwright | Critical paths | Full flow: load dashboard -> optimize squad -> view results -> plan transfers |

---

This architecture plan provides a complete blueprint for building the FPL Picker application. Each module is designed to be independently testable, and the milestone plan provides a clear path from foundation to production.
