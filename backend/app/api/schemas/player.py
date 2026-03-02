"""Pydantic models for player-related API schemas."""

from pydantic import BaseModel


class PlayerSummary(BaseModel):
    """Lightweight player summary for list views."""

    id: int
    web_name: str
    first_name: str = ""
    second_name: str = ""
    team: int = 0
    position: str = ""  # GKP, DEF, MID, FWD
    now_cost: int = 0  # price * 10
    total_points: int = 0
    form: float = 0.0
    points_per_game: float = 0.0
    selected_by_percent: float = 0.0
    ict_index: float = 0.0
    minutes: int = 0
    goals_scored: int = 0
    assists: int = 0
    clean_sheets: int = 0
    bonus: int = 0
    bps: int = 0
    expected_goals: float = 0.0
    expected_assists: float = 0.0
    expected_goal_involvements: float = 0.0
    expected_goals_conceded: float = 0.0
    transfers_in_event: int = 0
    transfers_out_event: int = 0
    chance_of_playing_next_round: int | None = None
    value_season: float = 0.0
    status: str = ""
    news: str = ""

    # Derived features
    points_per_million: float = 0.0
    xgi_per_90: float = 0.0


class PlayerListResponse(BaseModel):
    """Paginated player list response."""

    players: list[PlayerSummary]
    total: int
    page: int
    limit: int


class PlayerDetailResponse(PlayerSummary):
    """Detailed player profile with history and fixture data."""

    history: list[dict] = []
    fixtures: list[dict] = []
