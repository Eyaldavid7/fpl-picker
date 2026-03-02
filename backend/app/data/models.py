"""Core data models for FPL entities.

Uses Pydantic v2 syntax with model_config and field validators.
All models include factory classmethods to construct from raw FPL API dicts.
"""

from datetime import datetime
from enum import Enum
from typing import Self

from pydantic import BaseModel, field_validator, model_validator


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class Position(str, Enum):
    """Player position in FPL."""

    GKP = "GKP"
    DEF = "DEF"
    MID = "MID"
    FWD = "FWD"


POSITION_MAP: dict[int, Position] = {
    1: Position.GKP,
    2: Position.DEF,
    3: Position.MID,
    4: Position.FWD,
}

# Default stats by position used for imputing missing data
POSITION_DEFAULTS: dict[Position, dict] = {
    Position.GKP: {
        "expected_goals": 0.0,
        "expected_assists": 0.0,
        "expected_goal_involvements": 0.0,
        "expected_goals_conceded": 30.0,
        "clean_sheets": 5,
        "goals_scored": 0,
        "assists": 0,
    },
    Position.DEF: {
        "expected_goals": 1.0,
        "expected_assists": 1.5,
        "expected_goal_involvements": 2.5,
        "expected_goals_conceded": 25.0,
        "clean_sheets": 4,
        "goals_scored": 1,
        "assists": 1,
    },
    Position.MID: {
        "expected_goals": 3.0,
        "expected_assists": 3.0,
        "expected_goal_involvements": 6.0,
        "expected_goals_conceded": 0.0,
        "clean_sheets": 0,
        "goals_scored": 3,
        "assists": 3,
    },
    Position.FWD: {
        "expected_goals": 6.0,
        "expected_assists": 2.0,
        "expected_goal_involvements": 8.0,
        "expected_goals_conceded": 0.0,
        "clean_sheets": 0,
        "goals_scored": 5,
        "assists": 2,
    },
}


# ---------------------------------------------------------------------------
# Player
# ---------------------------------------------------------------------------

class Player(BaseModel):
    """Core player data model with all FPL stats."""

    model_config = {"frozen": False, "populate_by_name": True}

    id: int
    web_name: str
    first_name: str = ""
    second_name: str = ""
    team: int  # team ID
    element_type: int = 3  # raw position code (1-4)
    position: Position = Position.MID
    now_cost: int = 0  # price in 0.1m units
    total_points: int = 0
    form: float = 0.0
    points_per_game: float = 0.0
    minutes: int = 0
    goals_scored: int = 0
    assists: int = 0
    clean_sheets: int = 0
    bonus: int = 0
    bps: int = 0
    ict_index: float = 0.0
    influence: float = 0.0
    creativity: float = 0.0
    threat: float = 0.0
    expected_goals: float = 0.0
    expected_assists: float = 0.0
    expected_goal_involvements: float = 0.0
    expected_goals_conceded: float = 0.0
    selected_by_percent: float = 0.0
    news: str = ""
    chance_of_playing_next_round: int | None = None
    transfers_in_event: int = 0
    transfers_out_event: int = 0
    value_season: float = 0.0
    status: str = "a"  # a=available, d=doubtful, i=injured, s=suspended, u=unavailable

    # Derived features (populated by preprocessing)
    points_per_million: float = 0.0
    xgi_per_90: float = 0.0

    @field_validator(
        "form", "points_per_game", "ict_index", "influence", "creativity",
        "threat", "expected_goals", "expected_assists",
        "expected_goal_involvements", "expected_goals_conceded",
        "selected_by_percent", "value_season",
        mode="before",
    )
    @classmethod
    def coerce_float(cls, v: object) -> float:
        """Coerce string numbers from the API to float."""
        if v is None:
            return 0.0
        try:
            return float(v)
        except (TypeError, ValueError):
            return 0.0

    @model_validator(mode="after")
    def set_position_from_element_type(self) -> Self:
        """Derive the Position enum from the raw element_type integer."""
        self.position = POSITION_MAP.get(self.element_type, Position.MID)
        return self

    @property
    def price(self) -> float:
        """Return price in millions."""
        return self.now_cost / 10

    @classmethod
    def from_api_element(cls, element: dict) -> "Player":
        """Create a Player from an FPL API element dict."""
        return cls(
            id=element["id"],
            web_name=element.get("web_name", ""),
            first_name=element.get("first_name", ""),
            second_name=element.get("second_name", ""),
            team=element.get("team", 0),
            element_type=element.get("element_type", 3),
            now_cost=element.get("now_cost", 0),
            total_points=element.get("total_points", 0),
            form=element.get("form", 0),
            points_per_game=element.get("points_per_game", 0),
            minutes=element.get("minutes", 0),
            goals_scored=element.get("goals_scored", 0),
            assists=element.get("assists", 0),
            clean_sheets=element.get("clean_sheets", 0),
            bonus=element.get("bonus", 0),
            bps=element.get("bps", 0),
            ict_index=element.get("ict_index", 0),
            influence=element.get("influence", 0),
            creativity=element.get("creativity", 0),
            threat=element.get("threat", 0),
            expected_goals=element.get("expected_goals", 0),
            expected_assists=element.get("expected_assists", 0),
            expected_goal_involvements=element.get("expected_goal_involvements", 0),
            expected_goals_conceded=element.get("expected_goals_conceded", 0),
            selected_by_percent=element.get("selected_by_percent", 0),
            news=element.get("news", ""),
            chance_of_playing_next_round=element.get("chance_of_playing_next_round"),
            transfers_in_event=element.get("transfers_in_event", 0),
            transfers_out_event=element.get("transfers_out_event", 0),
            value_season=element.get("value_season", 0),
            status=element.get("status", "a"),
        )


# ---------------------------------------------------------------------------
# PlayerHistory  (one row per past-gameweek appearance)
# ---------------------------------------------------------------------------

class PlayerHistory(BaseModel):
    """A single gameweek record from a player's history."""

    model_config = {"frozen": False, "populate_by_name": True}

    round: int  # gameweek number
    total_points: int = 0
    minutes: int = 0
    goals_scored: int = 0
    assists: int = 0
    clean_sheets: int = 0
    bonus: int = 0
    bps: int = 0
    ict_index: float = 0.0
    influence: float = 0.0
    creativity: float = 0.0
    threat: float = 0.0
    expected_goals: float = 0.0
    expected_assists: float = 0.0
    expected_goal_involvements: float = 0.0
    expected_goals_conceded: float = 0.0
    value: int = 0  # cost at that point in time (0.1m units)
    opponent_team: int = 0
    was_home: bool = False
    fixture: int = 0  # fixture ID

    @field_validator(
        "ict_index", "influence", "creativity", "threat",
        "expected_goals", "expected_assists",
        "expected_goal_involvements", "expected_goals_conceded",
        mode="before",
    )
    @classmethod
    def coerce_float(cls, v: object) -> float:
        if v is None:
            return 0.0
        try:
            return float(v)
        except (TypeError, ValueError):
            return 0.0

    @classmethod
    def from_api_history(cls, h: dict) -> "PlayerHistory":
        """Create from one item in the element-summary 'history' list."""
        return cls(
            round=h.get("round", 0),
            total_points=h.get("total_points", 0),
            minutes=h.get("minutes", 0),
            goals_scored=h.get("goals_scored", 0),
            assists=h.get("assists", 0),
            clean_sheets=h.get("clean_sheets", 0),
            bonus=h.get("bonus", 0),
            bps=h.get("bps", 0),
            ict_index=h.get("ict_index", 0),
            influence=h.get("influence", 0),
            creativity=h.get("creativity", 0),
            threat=h.get("threat", 0),
            expected_goals=h.get("expected_goals", 0),
            expected_assists=h.get("expected_assists", 0),
            expected_goal_involvements=h.get("expected_goal_involvements", 0),
            expected_goals_conceded=h.get("expected_goals_conceded", 0),
            value=h.get("value", 0),
            opponent_team=h.get("opponent_team", 0),
            was_home=h.get("was_home", False),
            fixture=h.get("fixture", 0),
        )


# ---------------------------------------------------------------------------
# Team
# ---------------------------------------------------------------------------

class Team(BaseModel):
    """Premier League team model."""

    model_config = {"frozen": False, "populate_by_name": True}

    id: int
    name: str
    short_name: str
    strength: int = 0
    strength_overall_home: int = 0
    strength_overall_away: int = 0
    strength_attack_home: int = 0
    strength_attack_away: int = 0
    strength_defence_home: int = 0
    strength_defence_away: int = 0

    @classmethod
    def from_api_team(cls, team: dict) -> "Team":
        """Create a Team from an FPL API team dict."""
        return cls(
            id=team["id"],
            name=team.get("name", ""),
            short_name=team.get("short_name", ""),
            strength=team.get("strength", 0),
            strength_overall_home=team.get("strength_overall_home", 0),
            strength_overall_away=team.get("strength_overall_away", 0),
            strength_attack_home=team.get("strength_attack_home", 0),
            strength_attack_away=team.get("strength_attack_away", 0),
            strength_defence_home=team.get("strength_defence_home", 0),
            strength_defence_away=team.get("strength_defence_away", 0),
        )


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

class Fixture(BaseModel):
    """Match fixture model."""

    model_config = {"frozen": False, "populate_by_name": True}

    id: int
    event: int | None = None  # gameweek number
    team_h: int  # home team ID
    team_a: int  # away team ID
    team_h_difficulty: int = 3  # FDR 1-5
    team_a_difficulty: int = 3
    kickoff_time: str | None = None
    finished: bool = False
    team_h_score: int | None = None
    team_a_score: int | None = None

    @classmethod
    def from_api_fixture(cls, fixture: dict) -> "Fixture":
        """Create a Fixture from an FPL API fixture dict."""
        return cls(
            id=fixture["id"],
            event=fixture.get("event"),
            team_h=fixture.get("team_h", 0),
            team_a=fixture.get("team_a", 0),
            team_h_difficulty=fixture.get("team_h_difficulty", 3),
            team_a_difficulty=fixture.get("team_a_difficulty", 3),
            kickoff_time=fixture.get("kickoff_time"),
            finished=fixture.get("finished", False),
            team_h_score=fixture.get("team_h_score"),
            team_a_score=fixture.get("team_a_score"),
        )


# ---------------------------------------------------------------------------
# Gameweek
# ---------------------------------------------------------------------------

class Gameweek(BaseModel):
    """Gameweek (event) model."""

    model_config = {"frozen": False, "populate_by_name": True}

    id: int
    name: str = ""
    deadline_time: str = ""
    finished: bool = False
    is_current: bool = False
    is_next: bool = False
    is_previous: bool = False
    average_score: int = 0  # aliased from average_entry_score
    highest_score: int | None = None
    most_captained: int | None = None
    most_vice_captained: int | None = None

    @classmethod
    def from_api_event(cls, event: dict) -> "Gameweek":
        """Create a Gameweek from an FPL API event dict."""
        return cls(
            id=event["id"],
            name=event.get("name", f"Gameweek {event['id']}"),
            deadline_time=event.get("deadline_time", ""),
            finished=event.get("finished", False),
            is_current=event.get("is_current", False),
            is_next=event.get("is_next", False),
            is_previous=event.get("is_previous", False),
            average_score=event.get("average_entry_score", 0),
            highest_score=event.get("highest_score"),
            most_captained=event.get("most_captained"),
            most_vice_captained=event.get("most_vice_captained"),
        )


# ---------------------------------------------------------------------------
# Prediction helper (kept for compatibility)
# ---------------------------------------------------------------------------

class PointPrediction(BaseModel):
    """Prediction result for a player in a gameweek."""

    model_config = {"frozen": False}

    player_id: int
    gameweek: int
    predicted_points: float
    confidence_lower: float = 0.0
    confidence_upper: float = 0.0
    model: str = "ensemble"
    created_at: datetime | None = None
