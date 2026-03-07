# FPL Picker

A full-stack Fantasy Premier League squad optimizer that uses fixture-aware scoring, temporal analysis, and mathematical optimization to help you pick the best team every gameweek.

**Live:** [fpl-picker-app.web.app](https://fpl-picker-app.web.app)

## What It Does

- **Squad Optimization** -- ILP (Integer Linear Programming) and Genetic Algorithm solvers find the mathematically optimal 15-man squad within your budget and formation constraints.
- **Captain Picker** -- Three modes: **Safe** (highest expected points), **Differential** (punishes high ownership), and **Aggressive** (variance-weighted ceiling scores).
- **Bench Optimizer** -- Recommends the optimal bench order and identifies bench players who should start over current starters.
- **Transfer Suggestions** -- Scans 600+ FPL players to find the best upgrades your budget allows, respecting the 3-per-team rule.
- **Fixture Analysis** -- 5-gameweek fixture ticker with FDR color coding, opponent strength analysis, and home/away context.
- **Backtesting** -- Validate scoring accuracy against historical gameweek data with MAE, R-squared, and captain accuracy metrics.

## Scoring Engine

The prediction engine goes beyond raw season averages:

| Feature | Description |
|---|---|
| **Poisson Clean Sheet Model** | `P(CS) = e^(-lambda)` where lambda derives from opponent attack strength |
| **Exponential Time Decay** | Recent form weighted 65/35 (in-form) or 55/45 (out-of-form) instead of flat averages |
| **Form Momentum** | Detects hot/cold streaks and applies 5% bonus/penalty |
| **Multi-Window Temporal** | Rolling 3, 5, 10 GW averages with trend detection (improving/declining/stable) |
| **Opponent Strength** | Per-fixture multipliers using team attack/defense ratings, home/away splits |
| **Position-Aware FDR** | Steeper difficulty curve for DEF/GKP (0.75-1.25) vs FWD/MID (0.85-1.15) |
| **Minutes Probability** | Blends availability percentage with nailedness (minutes history) |
| **ICT Index** | Influence, Creativity, Threat metrics as supplementary scoring signal |

## Tech Stack

### Backend
- **Python 3.11+** / **FastAPI** -- async API with automatic OpenAPI docs
- **PuLP** -- ILP solver for squad optimization
- **DEAP** -- genetic algorithm alternative solver
- **httpx** -- async FPL API client with caching
- **Cloud Run** -- serverless deployment with auto-scaling

### Frontend
- **Next.js 15** / **React 19** -- static export, no SSR needed
- **TypeScript** -- end-to-end type safety
- **Tailwind CSS** -- dark-mode-first responsive UI
- **TanStack Query** -- data fetching with cache invalidation
- **Firebase Hosting** -- CDN-backed static hosting
- **Firestore** -- saved teams persistence

## Project Structure

```
backend/
  app/
    api/
      endpoints/       # FastAPI route handlers
      schemas/          # Pydantic request/response models
    data/
      fpl_client.py    # Async FPL API client with caching
      models.py        # Player, Team, Fixture data models
    prediction/
      fixture_scorer.py  # Core scoring engine
      temporal.py        # Multi-window rolling averages
      backtester.py      # Historical validation framework
  tests/               # 256 tests, pytest

frontend/
  src/
    app/optimizer/     # Main optimizer page
    components/        # PitchView, PlayerCard, TeamSuggestions, etc.
    hooks/             # useApi, useFirestore custom hooks
    lib/               # API client, Firestore helpers
    types/             # Shared TypeScript interfaces
```

## Getting Started

### Prerequisites
- Python 3.11+
- Node.js 18+
- A Firebase project (for Firestore + Hosting)

### Backend

```bash
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --port 8000 --reload
```

API docs at [localhost:8000/api/docs](http://localhost:8000/api/docs)

### Frontend

```bash
cd frontend
npm install
npm run dev
```

App at [localhost:3000](http://localhost:3000)

### Environment Variables

**Frontend** (`frontend/.env.local`):
```
NEXT_PUBLIC_API_URL=http://localhost:8000/api
```

**Backend**: No env vars required for local dev. The FPL API is public.

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/health` | Health check |
| `POST` | `/api/optimize/squad` | Optimize full 15-man squad |
| `POST` | `/api/optimize/captain` | Captain/vice-captain picker |
| `POST` | `/api/optimize/bench` | Bench order optimizer |
| `POST` | `/api/suggestions/substitutes` | Bench-to-starter swap suggestions |
| `POST` | `/api/suggestions/transfers` | Transfer-in recommendations |
| `POST` | `/api/squad-import/team-id` | Import squad by FPL Team ID |
| `POST` | `/api/squad-import/screenshot` | Import squad from screenshot (OCR) |
| `POST` | `/api/fixtures/squad` | Squad fixture analysis (5 GWs) |
| `POST` | `/api/predict/backtest` | Backtest scoring model |
| `GET` | `/api/data/players` | All FPL player data |
| `GET` | `/api/data/fixtures` | Fixture list |

## Deployment

### Backend (Cloud Run)
```bash
cd backend
gcloud run deploy fpl-picker-backend \
  --source . \
  --region us-east1 \
  --allow-unauthenticated \
  --project <your-project>
```

### Frontend (Firebase Hosting)
```bash
cd frontend
npm run build
firebase deploy --only hosting --project <your-project>
```

## Testing

```bash
# Backend (256 tests)
cd backend && python3 -m pytest tests/ -v

# Frontend type check
cd frontend && npx tsc --noEmit
```

## License

MIT
