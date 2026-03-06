import axios, { type AxiosError } from "axios";
import type { TeamIdImportResult } from "@/types";

/**
 * Axios instance configured for the FPL Picker backend API.
 *
 * Uses the NEXT_PUBLIC_API_URL env var if set (see .env.local / .env.production).
 * Falls back to the local FastAPI backend URL for development.
 */

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    "Content-Type": "application/json",
  },
});

// ---------------------------------------------------------------------------
// Error categorisation helpers
// ---------------------------------------------------------------------------

export type ApiErrorCategory = "network" | "server" | "client" | "unknown";

/**
 * Categorise an Axios error so the UI can show the right message.
 *
 * - **network**: Could not reach the server at all (connection refused, CORS,
 *   DNS failure, timeout, etc.)
 * - **server**: The server responded with a 5xx status code.
 * - **client**: The server responded with a 4xx status code (bad request, not
 *   found, validation error, etc.)
 * - **unknown**: Anything else.
 */
export function categoriseError(error: unknown): ApiErrorCategory {
  if (!axios.isAxiosError(error)) return "unknown";
  const axiosErr = error as AxiosError;
  if (!axiosErr.response) {
    // No response at all -- network-level issue
    return "network";
  }
  const status = axiosErr.response.status;
  if (status >= 500) return "server";
  if (status >= 400) return "client";
  return "unknown";
}

/**
 * Return a user-friendly error message for an Axios error.
 */
export function friendlyErrorMessage(error: unknown): string {
  const category = categoriseError(error);
  const baseUrl = getApiBaseUrl();

  switch (category) {
    case "network":
      return (
        `Unable to connect to the FPL backend at ${baseUrl}. ` +
        "If running locally, make sure the backend is started with:\n" +
        "  cd backend && uvicorn app.main:app --port 8000\n" +
        "If this is the deployed app, the backend may not be deployed yet."
      );
    case "server": {
      const status = axios.isAxiosError(error)
        ? (error as AxiosError).response?.status
        : undefined;
      return `The backend returned an internal error (HTTP ${status ?? "5xx"}). Please try again later.`;
    }
    case "client": {
      const axErr = error as AxiosError<{ detail?: string }>;
      const detail = axErr.response?.data?.detail;
      return detail
        ? `Request error: ${detail}`
        : `Request error (HTTP ${axErr.response?.status}).`;
    }
    default:
      return "An unexpected error occurred. Please try again.";
  }
}

// ---------------------------------------------------------------------------
// Debug helper
// ---------------------------------------------------------------------------

/** Return the API base URL the client is currently configured to use. */
export function getApiBaseUrl(): string {
  return API_BASE_URL;
}

// ---------------------------------------------------------------------------
// Response interceptor
// ---------------------------------------------------------------------------

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    const category = categoriseError(error);

    if (category === "network") {
      console.error(
        `[FPL API] Network error -- cannot reach ${API_BASE_URL}:`,
        error.message
      );
    } else if (category === "server") {
      console.error(
        `[FPL API] Server error ${error.response?.status}:`,
        error.response?.data
      );
    } else if (category === "client") {
      console.error(
        `[FPL API] Client error ${error.response?.status}:`,
        error.response?.data
      );
    } else {
      console.error("[FPL API] Unknown error:", error.message);
    }

    return Promise.reject(error);
  }
);

export default apiClient;

// Typed API helper functions
export const api = {
  // Health
  health: () => apiClient.get("/health"),

  // Data
  getPlayers: (params?: Record<string, unknown>) =>
    apiClient.get("/data/players", { params }),
  getPlayer: (id: number) => apiClient.get(`/data/players/${id}`),
  getFixtures: (gameweek?: number) =>
    apiClient.get("/data/fixtures", { params: gameweek ? { gameweek } : {} }),
  getTeams: () => apiClient.get("/data/teams"),
  getGameweeks: () => apiClient.get("/data/gameweeks"),
  refreshData: () => apiClient.post("/data/refresh"),

  // Optimization
  optimizeSquad: (data: Record<string, unknown>) =>
    apiClient.post("/optimize/squad", data),
  selectCaptain: (data: { player_ids: number[]; gameweek?: number; differential?: boolean }) =>
    apiClient.post("/optimize/captain", data),
  optimizeBench: (data: { xi_ids: number[]; bench_ids: number[]; gameweek?: number }) =>
    apiClient.post("/optimize/bench", data),

  // Fixtures Analysis
  getSquadFixtures: (data: { player_ids: number[]; num_gameweeks?: number }) =>
    apiClient.post("/fixtures/squad-fixtures", data),

  // Suggestions
  getSubstituteSuggestions: (data: { squad_player_ids: number[]; formation?: string }) =>
    apiClient.post("/suggestions/substitutes", data),
  getTransferSuggestions: (data: {
    squad_player_ids: number[];
    budget_remaining?: number;
    free_transfers?: number;
  }) => apiClient.post("/suggestions/transfers", data),

  // Squad Import
  importScreenshot: (file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    return apiClient.post("/squad-import/screenshot", formData, {
      headers: { "Content-Type": "multipart/form-data" },
      timeout: 60000,
    });
  },

  importTeamById: (teamId: number) =>
    apiClient
      .post<TeamIdImportResult>("/squad-import/team-id", { team_id: teamId })
      .then((r) => r.data),

};
