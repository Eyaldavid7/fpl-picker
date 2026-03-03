"use client";

import { useQuery, useMutation, type UseQueryOptions } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import type {
  Player,
  PlayerDetail,
  Team,
  Gameweek,
  Fixture,
  OptimizationRequest,
  OptimizationResult,
  ScreenshotImportResult,
  TeamIdImportResult,
  SquadFixturesRequest,
  SquadFixturesResponse,
  SubstituteRequest,
  SubstituteResponse,
  TransferRequest,
  TransferResponse,
} from "@/types";

// ---------- Query Keys ----------

export const queryKeys = {
  players: ["players"] as const,
  player: (id: number) => ["players", id] as const,
  teams: ["teams"] as const,
  gameweeks: ["gameweeks"] as const,
  fixtures: (gw?: number) => ["fixtures", gw] as const,
};

// ---------- Data Hooks ----------

/** Fetch all players. Optionally pass query params for server-side filtering. */
export function usePlayers(params?: Record<string, unknown>) {
  return useQuery<Player[]>({
    queryKey: [...queryKeys.players, params],
    queryFn: async () => {
      const res = await api.getPlayers(params);
      // Backend returns { players: [...], total, page, limit }
      return Array.isArray(res.data) ? res.data : res.data?.players ?? [];
    },
  });
}

/** Fetch a single player by ID with history and fixtures. */
export function usePlayer(id: number, options?: Partial<UseQueryOptions<PlayerDetail>>) {
  return useQuery<PlayerDetail>({
    queryKey: queryKeys.player(id),
    queryFn: async () => {
      const res = await api.getPlayer(id);
      return res.data;
    },
    enabled: id > 0,
    ...options,
  });
}

/** Fetch all teams. */
export function useTeams() {
  return useQuery<Team[]>({
    queryKey: queryKeys.teams,
    queryFn: async () => {
      const res = await api.getTeams();
      // Backend returns { teams: [...] }
      return Array.isArray(res.data) ? res.data : res.data?.teams ?? [];
    },
  });
}

/** Fetch all gameweeks. */
export function useGameweeks() {
  return useQuery<Gameweek[]>({
    queryKey: queryKeys.gameweeks,
    queryFn: async () => {
      const res = await api.getGameweeks();
      // Backend returns { gameweeks: [...] }
      return Array.isArray(res.data) ? res.data : res.data?.gameweeks ?? [];
    },
  });
}

/** Fetch fixtures, optionally for a specific gameweek. */
export function useFixtures(gameweek?: number) {
  return useQuery<Fixture[]>({
    queryKey: queryKeys.fixtures(gameweek),
    queryFn: async () => {
      const res = await api.getFixtures(gameweek);
      // Backend returns { fixtures: [...] }
      return Array.isArray(res.data) ? res.data : res.data?.fixtures ?? [];
    },
  });
}

// ---------- Mutation Hooks ----------

/** Optimize squad. Returns mutation that can be triggered imperatively. */
export function useOptimize() {
  return useMutation<OptimizationResult, Error, OptimizationRequest>({
    mutationFn: async (params) => {
      const res = await api.optimizeSquad(params as unknown as Record<string, unknown>);
      const raw = res.data;

      // The backend returns squad (SquadPlayer[]) with is_starter/is_captain/
      // is_vice_captain flags plus bench/starting_xi as ID arrays and
      // captain_id/vice_captain_id as plain ints.  Transform into the shape
      // the frontend expects.
      const squad = raw.squad ?? [];
      return {
        squad,
        xi: squad.filter((p: { is_starter: boolean }) => p.is_starter),
        bench: squad.filter((p: { is_starter: boolean }) => !p.is_starter),
        captain: squad.find((p: { is_captain: boolean }) => p.is_captain) ?? null,
        vice_captain: squad.find((p: { is_vice_captain: boolean }) => p.is_vice_captain) ?? null,
        formation: raw.formation ?? "",
        total_cost: raw.total_cost ?? 0,
        total_predicted_points: raw.total_predicted_points ?? 0,
        method: raw.method ?? "ilp",
        solve_time_ms: raw.solve_time_ms,
      } as OptimizationResult;
    },
  });
}

/** Import squad by FPL team ID. */
export function useTeamIdImport() {
  return useMutation<TeamIdImportResult, Error, number>({
    mutationFn: (teamId: number) => api.importTeamById(teamId),
  });
}

/** Import squad from a screenshot. */
export function useScreenshotImport() {
  return useMutation<ScreenshotImportResult, Error, File>({
    mutationFn: async (file) => {
      const res = await api.importScreenshot(file);
      return res.data;
    },
  });
}

/** Fetch upcoming fixtures for a list of squad player IDs. */
export function useSquadFixtures() {
  return useMutation<SquadFixturesResponse, Error, SquadFixturesRequest>({
    mutationFn: async (params) => {
      const res = await api.getSquadFixtures(params);
      return res.data;
    },
  });
}

/** Get substitute suggestions for a squad. */
export function useSubstituteSuggestions() {
  return useMutation<SubstituteResponse, Error, SubstituteRequest>({
    mutationFn: async (params) => {
      const res = await api.getSubstituteSuggestions(params);
      return res.data;
    },
  });
}

/** Get transfer suggestions for a squad. */
export function useTransferSuggestions() {
  return useMutation<TransferResponse, Error, TransferRequest>({
    mutationFn: async (params) => {
      const res = await api.getTransferSuggestions(params);
      return res.data;
    },
  });
}

/** Refresh backend data cache. */
export function useRefreshData() {
  return useMutation<void, Error>({
    mutationFn: async () => {
      await api.refreshData();
    },
  });
}
