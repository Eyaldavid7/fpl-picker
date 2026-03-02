/**
 * Core TypeScript types for the FPL Team Picker frontend.
 */

// ---------- Enums & Unions ----------

/** Player position type */
export type Position = "GKP" | "DEF" | "MID" | "FWD";

/** Player availability status */
export type PlayerStatus = "a" | "d" | "i" | "s" | "u";

/** Chip types available in FPL */
export type ChipType = "wildcard" | "triple_captain" | "bench_boost" | "free_hit";

/** Optimization method */
export type OptimizationMethod = "ilp" | "ga";

/** Sensitivity level */
export type SensitivityLevel = "strong" | "moderate" | "volatile";

/** Sort direction */
export type SortDirection = "asc" | "desc";

// ---------- Player ----------

/** Player summary data from the API. */
export interface Player {
  id: number;
  web_name: string;
  first_name: string;
  second_name: string;
  team_id: number;
  team_name?: string;
  team_short_name?: string;
  position: Position;
  now_cost: number; // price * 10
  total_points: number;
  form: number;
  points_per_game: number;
  selected_by_percent: number;
  ict_index: number;
  minutes: number;
  goals_scored: number;
  assists: number;
  clean_sheets: number;
  bonus: number;
  status: PlayerStatus;
  news: string;
  expected_goals?: number;
  expected_assists?: number;
  expected_goal_involvements?: number;
  predicted_points?: number;
}

/** Detailed player with history. */
export interface PlayerDetail extends Player {
  history: GameweekHistory[];
  fixtures: UpcomingFixture[];
}

/** Past gameweek performance for a player. */
export interface GameweekHistory {
  round: number;
  total_points: number;
  minutes: number;
  goals_scored: number;
  assists: number;
  clean_sheets: number;
  bonus: number;
  bps: number;
  influence: number;
  creativity: number;
  threat: number;
  ict_index: number;
  selected: number;
  transfers_in: number;
  transfers_out: number;
  value: number;
}

/** Upcoming fixture for a player. */
export interface UpcomingFixture {
  event: number;
  team_h: number;
  team_a: number;
  difficulty: number;
  is_home: boolean;
}

// ---------- Team ----------

/** Premier League team. */
export interface Team {
  id: number;
  name: string;
  short_name: string;
  strength: number;
  strength_overall_home?: number;
  strength_overall_away?: number;
  strength_attack_home?: number;
  strength_attack_away?: number;
  strength_defence_home?: number;
  strength_defence_away?: number;
}

// ---------- Gameweek ----------

/** Gameweek / event. */
export interface Gameweek {
  id: number;
  name: string;
  deadline_time: string;
  finished: boolean;
  is_current: boolean;
  is_next: boolean;
  average_entry_score: number;
  highest_score?: number;
}

// ---------- Fixture ----------

/** A single fixture. */
export interface Fixture {
  id: number;
  event: number;
  team_h: number;
  team_a: number;
  team_h_score: number | null;
  team_a_score: number | null;
  team_h_difficulty: number;
  team_a_difficulty: number;
  finished: boolean;
  kickoff_time: string;
}

// ---------- Squad ----------

/** Squad state for optimization and display. */
export interface Squad {
  players: SquadPlayer[];
  formation: string;
  total_cost: number;
  bank: number;
  captain_id: number | null;
  vice_captain_id: number | null;
}

/** Player within a squad context. */
export interface SquadPlayer {
  player_id: number;
  web_name: string;
  position: Position;
  team_id: number;
  cost: number;
  predicted_points: number;
  is_starter: boolean;
  is_captain: boolean;
  is_vice_captain: boolean;
}

// ---------- Optimization ----------

/** Parameters for squad optimization request. */
export interface OptimizationRequest {
  budget: number;
  formation: string;
  method: OptimizationMethod;
  gameweek?: number;
  excluded_players?: number[];
  included_players?: number[];
  existing_squad?: number[];
  max_players_per_team?: number;
  objective?: string;
}

/** Result from squad optimization. */
export interface OptimizationResult {
  squad: SquadPlayer[];
  xi: SquadPlayer[];
  bench: SquadPlayer[];
  captain: SquadPlayer | null;
  vice_captain: SquadPlayer | null;
  formation: string;
  total_cost: number;
  total_predicted_points: number;
  method: OptimizationMethod;
  solve_time_ms?: number;
}

// ---------- Predictions ----------

/** Point prediction for a player in a gameweek. */
export interface Prediction {
  player_id: number;
  player_name?: string;
  gameweek: number;
  predicted_points: number;
  confidence_lower: number;
  confidence_upper: number;
  model: string;
}

/** Result from batch prediction. */
export interface PredictionResult {
  predictions: Prediction[];
  gameweek: number;
  model: string;
  timestamp?: string;
}

/** Comparison of models. */
export interface ModelComparison {
  model: string;
  mae: number;
  rmse: number;
  r2: number;
  accuracy_within_1: number;
  accuracy_within_2: number;
}

/** Available prediction model info. */
export interface ModelInfo {
  name: string;
  display_name: string;
  description: string;
  type: string;
}

// ---------- Transfers ----------

/** Transfer recommendation. */
export interface TransferMove {
  player_in_id: number;
  player_out_id: number;
  player_in_name: string;
  player_out_name: string;
  player_in_position?: Position;
  player_out_position?: Position;
  player_in_team?: string;
  player_out_team?: string;
  cost_delta: number;
  expected_point_gain: number;
  priority?: number;
}

/** Complete transfer plan. */
export interface TransferPlan {
  transfers: TransferMove[];
  total_cost: number;
  total_expected_gain: number;
  free_transfers_used: number;
  hits_taken: number;
  net_expected_gain: number;
  horizon_gameweeks: number;
}

// ---------- Chips ----------

/** Chip recommendation. */
export interface ChipRecommendation {
  chip: ChipType;
  recommended_gameweek: number;
  expected_gain: number;
  reasoning: string;
  confidence: number;
}

/** Chip strategy response. */
export interface ChipStrategy {
  recommendations: ChipRecommendation[];
  chips_available: ChipType[];
  chips_used: ChipType[];
  current_gameweek: number;
}

// ---------- Sensitivity ----------

/** Sensitivity analysis for a recommendation. */
export interface SensitivityAnalysis {
  level: SensitivityLevel;
  variance: number;
  factors: string[];
  description: string;
}

// ---------- API Responses ----------

/** API paginated response wrapper. */
export interface PaginatedResponse<T> {
  data: T[];
  total: number;
  page: number;
  limit: number;
}

/** Generic API error response. */
export interface ApiError {
  detail: string;
  status_code: number;
}

// ---------- UI State ----------

/** Column sort state. */
export interface SortState {
  column: string;
  direction: SortDirection;
}

/** Filter state for player explorer. */
export interface PlayerFilters {
  search: string;
  position: Position | "ALL";
  team: number | null;
  minPrice: number;
  maxPrice: number;
}
