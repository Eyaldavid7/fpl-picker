import axios from "axios";

/**
 * Axios instance configured for the FPL Picker backend API.
 *
 * In development, Next.js rewrites /api/* to the FastAPI backend.
 * In production, this base URL would point to the deployed backend.
 */
const apiClient = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || "/api",
  timeout: 30000,
  headers: {
    "Content-Type": "application/json",
  },
});

// Response interceptor for error handling
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response) {
      // Server responded with error status
      console.error(
        `API Error ${error.response.status}:`,
        error.response.data
      );
    } else if (error.request) {
      // Request made but no response received
      console.error("API Error: No response received", error.message);
    } else {
      console.error("API Error:", error.message);
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

  // Predictions
  predictPoints: (data: { player_ids?: number[]; gameweeks: number[]; model?: string }) =>
    apiClient.post("/predict/points", data),
  getPlayerPredictions: (id: number) => apiClient.get(`/predict/players/${id}`),
  batchPredict: (data: { gameweeks: number[]; model?: string }) =>
    apiClient.post("/predict/batch", data),
  getModels: () => apiClient.get("/predict/models"),

  // Optimization
  optimizeSquad: (data: Record<string, unknown>) =>
    apiClient.post("/optimize/squad", data),
  selectCaptain: (data: { player_ids: number[]; gameweek: number; differential?: boolean }) =>
    apiClient.post("/optimize/captain", data),
  optimizeBench: (data: { xi_ids: number[]; bench_ids: number[]; gameweek: number }) =>
    apiClient.post("/optimize/bench", data),

  // Transfers
  recommendTransfers: (data: Record<string, unknown>) =>
    apiClient.post("/transfers/recommend", data),
  planTransfers: (data: Record<string, unknown>) =>
    apiClient.post("/transfers/plan", data),
  evaluateTransfers: (data: Record<string, unknown>) =>
    apiClient.post("/transfers/evaluate", data),

  // Chips
  chipStrategy: (data: Record<string, unknown>) =>
    apiClient.post("/chips/strategy", data),
  simulateChip: (data: Record<string, unknown>) =>
    apiClient.post("/chips/simulate", data),
};
