/**
 * Core TypeScript types for the FPL Team Picker frontend.
 */

// ---------- Enums & Unions ----------

/** Player position type */
export type Position = "GKP" | "DEF" | "MID" | "FWD";

/** Player availability status */
export type PlayerStatus = "a" | "d" | "i" | "s" | "u";

/** Optimization method */
export type OptimizationMethod = "ilp" | "ga";

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
  status: PlayerStatus;
  chance_of_playing: number | null;
  news: string;
  next_opponent: string | null;   // e.g. "Arsenal (A)"
  fdr: number | null;             // Fixture Difficulty Rating 1-5
}

// ---------- Optimization ----------

/** Parameters for squad optimization request. */
export interface OptimizationRequest {
  budget: number;
  formation: string;
  method: OptimizationMethod;
  gameweek?: number;
  excluded_players?: number[];
  locked_players?: number[];
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

// ---------- Screenshot Import ----------

/** A player matched from a screenshot import. */
export interface MatchedPlayer {
  extracted_name: string;
  player_id: number | null;
  web_name: string | null;
  position: Position | null;
  team_name: string | null;
  confidence: number;
}

/** Response from the screenshot import endpoint. */
export interface ScreenshotImportResult {
  players: MatchedPlayer[];
  extracted_count: number;
  matched_count: number;
}

/** Response from the team-ID import endpoint. */
export interface TeamIdImportResult {
  team_name: string;
  manager_name: string;
  gameweek: number;
  players: MatchedPlayer[];
  starting_xi: number[];
  bench: number[];
  captain_id: number | null;
  vice_captain_id: number | null;
  overall_points: number;
  overall_rank: number;
  bank: number;
  team_value: number;
}

// ---------- Squad Fixtures (Next-Opponent) ----------

/** A single upcoming fixture for a player in the squad. */
export interface PlayerFixture {
  gameweek: number;
  opponent_team_id: number;
  opponent_name: string;
  opponent_short_name: string;
  is_home: boolean;
  difficulty: number;
  kickoff_time: string | null;
}

/** Team info entry in the squad fixtures response. */
export interface FixtureTeamInfo {
  name: string;
  short_name: string;
}

/** Response from the squad-fixtures endpoint. */
export interface SquadFixturesResponse {
  fixtures: Record<string, PlayerFixture[]>;
  teams: Record<string, FixtureTeamInfo>;
  current_gameweek: number;
}

/** Request payload for the squad-fixtures endpoint. */
export interface SquadFixturesRequest {
  player_ids: number[];
  num_gameweeks?: number;
}

// ---------- Suggestions ----------

/** A single substitute swap recommendation. */
export interface SubstituteSuggestion {
  bench_player_id: number;
  bench_player_name: string;
  bench_player_position: Position;
  bench_predicted_points: number;
  bench_next_opponent: string | null;
  bench_fdr: number | null;
  starter_player_id: number;
  starter_player_name: string;
  starter_player_position: Position;
  starter_predicted_points: number;
  starter_next_opponent: string | null;
  starter_fdr: number | null;
  point_gain: number;
  reason: string;
}

/** Request payload for the substitutes endpoint. */
export interface SubstituteRequest {
  squad_player_ids: number[];
  formation?: string;
}

/** Next-fixture context for a squad player (returned with substitute suggestions). */
export interface SquadPlayerFixture {
  player_id: number;
  web_name: string;
  position: Position;
  is_starter: boolean;
  predicted_points: number;
  next_opponent: string | null;
  fdr: number | null;
}

/** Response from the substitutes endpoint. */
export interface SubstituteResponse {
  suggestions: SubstituteSuggestion[];
  squad_fixtures: SquadPlayerFixture[];
}

/** A single transfer-in / transfer-out recommendation. */
export interface TransferSuggestion {
  player_out_id: number;
  player_out_name: string;
  player_out_position: Position;
  player_out_price: number;
  player_out_predicted: number;
  player_in_id: number;
  player_in_name: string;
  player_in_position: Position;
  player_in_price: number;
  player_in_predicted: number;
  player_in_team: string;
  point_gain: number;
  net_cost: number;
  reason: string;
  is_hit: boolean;
  hit_cost: number;
  net_gain_after_hit: number;
}

/** Request payload for the transfers endpoint. */
export interface TransferRequest {
  squad_player_ids: number[];
  budget_remaining?: number;
  free_transfers?: number;
}

/** Response from the transfers endpoint. */
export interface TransferResponse {
  suggestions: TransferSuggestion[];
  total_point_gain: number;
  total_cost_change: number;
  transfers_used: number;
  hit_transfers_count: number;
  total_hit_cost: number;
  net_gain_after_hits: number;
}

// ---------- Captain Picker ----------

/** Request payload for the captain picker endpoint. */
export interface CaptainRequest {
  player_ids: number[];
  gameweek?: number;
  differential?: boolean;
  mode?: string; // "safe" | "differential" | "aggressive"
}

/** A single captain ranking entry. */
export interface CaptainRanking {
  player_id: number;
  web_name: string;
  position: Position;
  team_name: string;
  predicted_points: number;
  effective_ownership: number;
  opponent: string;
  fdr: number | null;
  reasoning: string;
  ceiling_score: number;
}

/** Response from the captain picker endpoint. */
export interface CaptainResponse {
  captain_id: number;
  vice_captain_id: number;
  captain_xpts: number;
  vice_captain_xpts: number;
  rankings: CaptainRanking[];
}

// ---------- Bench Optimizer ----------

/** Request payload for the bench optimizer endpoint. */
export interface BenchOrderRequest {
  xi_ids: number[];
  bench_ids: number[];
  gameweek?: number;
}

/** Bench player detail with scoring breakdown. */
export interface BenchPlayerDetail {
  player_id: number;
  web_name: string;
  position: Position;
  final_score: number;
  opponent: string;
  reasoning: string;
}

/** Response from the bench optimizer endpoint. */
export interface BenchOrderResponse {
  bench_order: number[];
  expected_auto_sub_points: number;
  bench_players: BenchPlayerDetail[];
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
