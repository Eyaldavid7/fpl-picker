"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import {
  Cpu,
  DollarSign,
  Timer,
  Trophy,
  Users,
  Loader2,
  AlertCircle,
  Upload,
  Camera,
  CheckCircle2,
  Save,
  Hash,
} from "lucide-react";
import PitchView from "@/components/PitchView";
import PlayerCard from "@/components/PlayerCard";
import StatsCard from "@/components/StatsCard";
import FDRBadge from "@/components/FDRBadge";
import UpcomingFixtures from "@/components/UpcomingFixtures";
import TeamSuggestions from "@/components/TeamSuggestions";
import SavedTeams from "@/components/SavedTeams";
import {
  useOptimize,
  useScreenshotImport,
  useTeamIdImport,
  useSquadFixtures,
  useSubstituteSuggestions,
  useTransferSuggestions,
  useCaptainPicker,
  useBenchOptimizer,
} from "@/hooks/useApi";
import { useSaveTeam, useUpsertTeam } from "@/hooks/useFirestore";
import { friendlyErrorMessage, getApiBaseUrl } from "@/lib/api-client";
import type {
  OptimizationMethod,
  OptimizationResult,
  MatchedPlayer,
  TeamIdImportResult,
  SquadPlayer,
  SquadFixturesResponse,
} from "@/types";

const formations = [
  "3-4-3",
  "3-5-2",
  "4-3-3",
  "4-4-2",
  "4-5-1",
  "5-3-2",
  "5-4-1",
];

function confidenceColor(confidence: number): string {
  if (confidence >= 0.7) return "text-green-400";
  if (confidence >= 0.4) return "text-amber-400";
  return "text-red-400";
}

function confidenceBg(confidence: number): string {
  if (confidence >= 0.7) return "bg-green-500/10 border-green-500/30";
  if (confidence >= 0.4) return "bg-amber-500/10 border-amber-500/30";
  return "bg-red-500/10 border-red-500/30";
}

/** Enrich squad players with next-opponent and FDR data from the squad fixtures response. */
function enrichWithFixtures(
  players: SquadPlayer[],
  fixturesData: SquadFixturesResponse | undefined
): SquadPlayer[] {
  if (!fixturesData?.fixtures) return players;
  return players.map((p) => {
    const pFixtures = fixturesData.fixtures[String(p.player_id)];
    const next = pFixtures?.[0];
    if (!next) return { ...p, next_opponent: null, fdr: null };
    const venue = next.is_home ? "(H)" : "(A)";
    return {
      ...p,
      next_opponent: `${next.opponent_name} ${venue}`,
      fdr: next.difficulty,
    };
  });
}

export default function OptimizerPage() {
  const [budget, setBudget] = useState(100);
  const [formation, setFormation] = useState("4-4-2");
  const [method, setMethod] = useState<OptimizationMethod>("ilp");
  const [importedPlayerIds, setImportedPlayerIds] = useState<number[]>([]);

  const [saveMessage, setSaveMessage] = useState<{
    type: "success" | "error";
    text: string;
  } | null>(null);

  const [teamId, setTeamId] = useState("");
  const [loadedTeamLabel, setLoadedTeamLabel] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const updateFileInputRef = useRef<HTMLInputElement>(null);
  const [updateMessage, setUpdateMessage] = useState<string | null>(null);
  const [teamDisplayOverride, setTeamDisplayOverride] = useState<{
    players: MatchedPlayer[];
    startingXi: number[];
    bench: number[];
  } | null>(null);
  // Guard: when user manually loads a different team, ignore pending auto-load results
  const manuallyLoadedRef = useRef(false);
  const optimize = useOptimize();
  const teamIdImport = useTeamIdImport();
  const screenshotImport = useScreenshotImport();
  const screenshotUpdate = useScreenshotImport(); // Second instance for update-with-screenshot flow
  const squadFixtures = useSquadFixtures();
  const substituteSuggestions = useSubstituteSuggestions();
  const transferSuggestions = useTransferSuggestions();
  const captainPicker = useCaptainPicker();
  const benchOptimizer = useBenchOptimizer();
  const saveTeam = useSaveTeam();
  const upsertTeam = useUpsertTeam();

  const handleOptimize = () => {
    optimize.mutate({
      budget: budget * 10, // Backend expects price * 10
      formation,
      method,
      ...(importedPlayerIds.length > 0 && { locked_players: importedPlayerIds }),
    });
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    screenshotImport.mutate(file, {
      onSuccess: (data) => {
        // Auto-load matched players
        const ids = data.players
          .filter((p: MatchedPlayer) => p.player_id !== null)
          .map((p: MatchedPlayer) => p.player_id as number);
        setImportedPlayerIds(ids);
      },
    });
    // Reset input so re-uploading the same file triggers onChange
    e.target.value = "";
  };

  const handleUseImportedSquad = () => {
    if (!screenshotImport.data) return;
    const ids = screenshotImport.data.players
      .filter((p: MatchedPlayer) => p.player_id !== null)
      .map((p: MatchedPlayer) => p.player_id as number);
    setImportedPlayerIds(ids);
  };

  const handleTeamIdImport = () => {
    const parsed = parseInt(teamId, 10);
    if (isNaN(parsed) || parsed <= 0) return;
    manuallyLoadedRef.current = true; // Prevent auto-load from overwriting
    setLoadedTeamLabel(null); // Clear saved-team label when importing by ID
    setTeamDisplayOverride(null); // Reset any screenshot merge override
    setUpdateMessage(null);
    teamIdImport.mutate(parsed, {
      onSuccess: (data) => {
        localStorage.setItem("fpl-team-id", parsed.toString());
        // Auto-load squad so suggestions trigger immediately
        const ids = data.players
          .filter((p: MatchedPlayer) => p.player_id !== null)
          .map((p: MatchedPlayer) => p.player_id as number);
        setImportedPlayerIds(ids);
      },
    });
  };

  const handleScreenshotUpdate = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !teamIdImport.data) return;
    setUpdateMessage(null);
    screenshotUpdate.mutate(file, {
      onSuccess: (data) => {
        const teamData = teamIdImport.data!;
        const matched = data.players.filter(
          (p: MatchedPlayer) => p.player_id !== null
        );

        if (matched.length === 0) {
          setUpdateMessage("Could not detect any players from the screenshot.");
          return;
        }

        // Screenshot shows the team as-is: first 11 = Starting XI, rest = bench
        const xiPlayers = matched.slice(0, 11);
        const benchPlayers = matched.slice(11);

        // Fully overwrite the displayed team with screenshot results
        setTeamDisplayOverride({
          players: matched,
          startingXi: xiPlayers.map((p: MatchedPlayer) => p.player_id as number),
          bench: benchPlayers.map((p: MatchedPlayer) => p.player_id as number),
        });

        // Update IDs used for optimization/suggestions
        const updatedIds = matched.map((p: MatchedPlayer) => p.player_id as number);
        setImportedPlayerIds(updatedIds);

        setUpdateMessage(
          `Squad overwritten from screenshot: ${matched.length} players detected.`
        );

        // Auto-save (upsert by FPL team ID — updates existing, doesn't create duplicate)
        const fplId = parseInt(teamId, 10);
        if (fplId > 0) {
          const name = teamData.team_name || `Team ${teamId}`;
          upsertTeam.mutate({
            fplTeamId: fplId,
            team: {
              name: `${name} - GW${teamData.gameweek}`,
              playerIds: updatedIds,
              players: matched.map((p: MatchedPlayer) => ({
                id: p.player_id as number,
                name: p.web_name || p.extracted_name,
                position: p.position || "MID",
                teamName: p.team_name || "",
              })),
              formation,
              source: "import",
              fplTeamId: fplId,
            },
          });
        }
      },
    });
    e.target.value = "";
  };

  const handleForgetTeam = () => {
    localStorage.removeItem("fpl-team-id");
    setTeamId("");
    teamIdImport.reset();
  };

  const handleUseTeamIdSquad = () => {
    if (!teamIdImport.data) return;
    const ids = teamIdImport.data.players
      .filter((p: MatchedPlayer) => p.player_id !== null)
      .map((p: MatchedPlayer) => p.player_id as number);
    setImportedPlayerIds(ids);
  };

  const handleSaveTeamIdTeam = () => {
    if (!teamIdImport.data) return;
    const matched = teamIdImport.data.players.filter(
      (p: MatchedPlayer) => p.player_id !== null
    );
    const name = teamIdImport.data.team_name || `Team ${teamId}`;
    saveTeam.mutate(
      {
        name: `${name} - GW${teamIdImport.data.gameweek}`,
        playerIds: matched.map((p: MatchedPlayer) => p.player_id as number),
        players: matched.map((p: MatchedPlayer) => ({
          id: p.player_id as number,
          name: p.web_name || p.extracted_name,
          position: p.position || "MID",
          teamName: p.team_name || "",
        })),
        formation,
        source: "import",
        fplTeamId: parseInt(teamId, 10) || undefined,
      },
      {
        onSuccess: () => showSaveMessage("success", "Team saved!"),
        onError: (err: Error) =>
          showSaveMessage("error", `Failed to save team: ${err.message}`),
      }
    );
  };

  const result: OptimizationResult | undefined = optimize.data;

  // Auto-fetch squad fixtures when optimization result arrives
  useEffect(() => {
    if (optimize.data?.squad?.length) {
      const playerIds = optimize.data.squad.map((p) => p.player_id);
      squadFixtures.mutate({ player_ids: playerIds });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [optimize.data]);

  // Auto-fetch squad fixtures when imported squad is loaded
  useEffect(() => {
    if (importedPlayerIds.length > 0) {
      squadFixtures.mutate({ player_ids: importedPlayerIds });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [importedPlayerIds]);

  // Auto-fetch substitute suggestions + captain picker when optimization result arrives
  useEffect(() => {
    if (optimize.data?.squad?.length) {
      const playerIds = optimize.data.squad.map((p) => p.player_id);
      substituteSuggestions.mutate({
        squad_player_ids: playerIds,
        formation: optimize.data.formation,
      });
      captainPicker.mutate({ player_ids: playerIds });
      // Auto-trigger bench optimizer
      const xiIds = optimize.data.squad.filter((p) => p.is_starter).map((p) => p.player_id);
      const benchIds = optimize.data.squad.filter((p) => !p.is_starter).map((p) => p.player_id);
      if (benchIds.length > 0) {
        benchOptimizer.mutate({ xi_ids: xiIds, bench_ids: benchIds });
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [optimize.data]);

  // Auto-fetch substitute suggestions when imported player IDs change
  useEffect(() => {
    if (importedPlayerIds.length > 0) {
      substituteSuggestions.mutate({
        squad_player_ids: importedPlayerIds,
        formation,
      });
      // Auto-trigger captain picker
      captainPicker.mutate({ player_ids: importedPlayerIds });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [importedPlayerIds]);

  // Auto-trigger bench optimizer when team ID import data arrives (has XI/bench split)
  useEffect(() => {
    let xiIds: number[] = [];
    let benchIds: number[] = [];
    if (teamDisplayOverride) {
      xiIds = teamDisplayOverride.startingXi;
      benchIds = teamDisplayOverride.bench;
    } else if (teamIdImport.data) {
      xiIds = teamIdImport.data.starting_xi;
      benchIds = teamIdImport.data.bench;
    }
    if (xiIds.length > 0 && benchIds.length > 0) {
      benchOptimizer.mutate({ xi_ids: xiIds, bench_ids: benchIds });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [teamIdImport.data, teamDisplayOverride]);

  // Restore last squad from localStorage on mount (no API call)
  useEffect(() => {
    const savedIds = localStorage.getItem("fpl-squad-ids");
    if (savedIds) {
      try {
        const ids = JSON.parse(savedIds) as number[];
        if (Array.isArray(ids) && ids.length > 0) {
          setImportedPlayerIds(ids);
        }
      } catch { /* ignore corrupt data */ }
    }
    // Pre-fill team ID input if saved
    const savedTeamId = localStorage.getItem("fpl-team-id");
    if (savedTeamId) setTeamId(savedTeamId);
  }, []);

  // Persist squad IDs to localStorage whenever they change
  useEffect(() => {
    if (importedPlayerIds.length > 0) {
      localStorage.setItem("fpl-squad-ids", JSON.stringify(importedPlayerIds));
    }
  }, [importedPlayerIds]);

  const handleFetchTransfers = (budgetRemaining: number, freeTransfers: number) => {
    const playerIds =
      optimize.data?.squad?.map((p) => p.player_id) ??
      (importedPlayerIds.length > 0 ? importedPlayerIds : []);
    if (playerIds.length === 0) return;
    transferSuggestions.mutate({
      squad_player_ids: playerIds,
      budget_remaining: budgetRemaining,
      free_transfers: freeTransfers,
    });
  };

  const handleLoadTeam = useCallback(
    (playerIds: number[], teamName?: string, savedFplTeamId?: number) => {
      manuallyLoadedRef.current = true;
      setImportedPlayerIds(playerIds);
      setLoadedTeamLabel(teamName || `Saved team (${playerIds.length} players)`);
      // Pre-fill team ID but don't auto-call API — user can import manually if needed
      if (savedFplTeamId) {
        setTeamId(savedFplTeamId.toString());
      } else {
        setTeamId("");
      }
      teamIdImport.reset();
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    []
  );

  const showSaveMessage = (type: "success" | "error", text: string) => {
    setSaveMessage({ type, text });
    setTimeout(() => setSaveMessage(null), 3000);
  };

  const handleSaveImportedTeam = () => {
    if (!screenshotImport.data) return;
    const matched = screenshotImport.data.players.filter(
      (p: MatchedPlayer) => p.player_id !== null
    );
    const dateStr = new Date().toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
    saveTeam.mutate(
      {
        name: `Imported Team - ${dateStr}`,
        playerIds: matched.map((p: MatchedPlayer) => p.player_id as number),
        players: matched.map((p: MatchedPlayer) => ({
          id: p.player_id as number,
          name: p.web_name || p.extracted_name,
          position: p.position || "MID",
          teamName: p.team_name || "",
        })),
        formation,
        source: "import",
      },
      {
        onSuccess: () => showSaveMessage("success", "Team saved!"),
        onError: (err: Error) =>
          showSaveMessage("error", `Failed to save team: ${err.message}`),
      }
    );
  };

  const handleSaveOptimizedTeam = () => {
    if (!result) return;
    const dateStr = new Date().toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
    saveTeam.mutate(
      {
        name: `Optimized ${result.formation} - ${dateStr}`,
        playerIds: result.squad.map((p) => p.player_id),
        players: result.squad.map((p) => ({
          id: p.player_id,
          name: p.web_name,
          position: p.position,
          teamName: `Team ${p.team_id}`,
        })),
        formation: result.formation,
        source: "optimize",
        predictedPoints: result.total_predicted_points,
        totalCost: result.total_cost,
        captainName: result.captain?.web_name,
        viceCaptainName: result.vice_captain?.web_name,
      },
      {
        onSuccess: () => showSaveMessage("success", "Team saved!"),
        onError: (err: Error) =>
          showSaveMessage("error", `Failed to save team: ${err.message}`),
      }
    );
  };

  // Effective display data (merged after screenshot update, or original import)
  const effectivePlayers = teamDisplayOverride?.players ?? teamIdImport.data?.players ?? [];
  const effectiveStartingXi = teamDisplayOverride?.startingXi ?? teamIdImport.data?.starting_xi ?? [];
  const effectiveBench = teamDisplayOverride?.bench ?? teamIdImport.data?.bench ?? [];

  const hasSquadData =
    (optimize.data?.squad?.length ?? 0) > 0 || importedPlayerIds.length > 0;

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Page header */}
      <div>
        <h1 className="text-3xl font-bold fpl-gradient-text">
          Team Optimizer
        </h1>
        <p className="mt-1 text-[var(--muted-foreground)]">
          Find the optimal squad using Integer Linear Programming or Genetic
          Algorithm solvers
        </p>
      </div>

      {/* Controls panel */}
      <div className="fpl-card">
        <h2 className="text-lg font-semibold mb-4">Optimization Parameters</h2>
        <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {/* Budget slider */}
          <div>
            <label className="block text-sm font-medium text-[var(--muted-foreground)] mb-2">
              Budget
            </label>
            <div className="flex items-center gap-3">
              <input
                type="range"
                min={80}
                max={100}
                step={0.5}
                value={budget}
                onChange={(e) => setBudget(Number(e.target.value))}
                className="flex-1 accent-[var(--primary)] h-2 rounded-full"
              />
              <span className="text-sm font-bold text-[var(--primary)] w-16 text-right">
                {budget.toFixed(1)}m
              </span>
            </div>
          </div>

          {/* Formation dropdown */}
          <div>
            <label className="block text-sm font-medium text-[var(--muted-foreground)] mb-2">
              Formation
            </label>
            <select
              value={formation}
              onChange={(e) => setFormation(e.target.value)}
              className="fpl-select"
            >
              {formations.map((f) => (
                <option key={f} value={f}>
                  {f}
                </option>
              ))}
            </select>
          </div>

          {/* Method selector */}
          <div>
            <label className="block text-sm font-medium text-[var(--muted-foreground)] mb-2">
              Method
            </label>
            <select
              value={method}
              onChange={(e) =>
                setMethod(e.target.value as OptimizationMethod)
              }
              className="fpl-select"
            >
              <option value="ilp">Integer Linear Programming</option>
              <option value="ga">Genetic Algorithm</option>
            </select>
          </div>

          {/* Optimize button */}
          <div className="flex items-end">
            <button
              onClick={handleOptimize}
              disabled={optimize.isPending}
              className="fpl-button-primary w-full gap-2"
            >
              {optimize.isPending ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Optimizing...
                </>
              ) : (
                <>
                  <Cpu className="h-4 w-4" />
                  Optimize
                </>
              )}
            </button>
          </div>
        </div>
      </div>

      {/* Saved teams */}
      {!optimize.isPending && (
        <SavedTeams onLoadTeam={handleLoadTeam} />
      )}

      {/* Error state */}
      {optimize.isError && (
        <div className="fpl-card border-red-500/30 bg-red-500/5">
          <div className="flex items-start gap-3 text-red-400">
            <AlertCircle className="h-5 w-5 shrink-0 mt-0.5" />
            <div>
              <p className="font-semibold">Optimization Failed</p>
              <p className="text-sm mt-1 text-red-400/80 whitespace-pre-line">
                {friendlyErrorMessage(optimize.error)}
              </p>
              <p className="text-xs mt-2 text-red-400/60">
                API URL: {getApiBaseUrl()}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Loading state */}
      {optimize.isPending && (
        <div className="fpl-card flex flex-col items-center justify-center py-16">
          <Loader2 className="h-10 w-10 animate-spin text-[var(--primary)]" />
          <p className="mt-4 text-[var(--muted-foreground)]">
            Running {method === "ilp" ? "ILP solver" : "Genetic Algorithm"}...
          </p>
          <p className="text-xs text-[var(--muted-foreground)] mt-1">
            This may take a few seconds
          </p>
        </div>
      )}

      {/* Results */}
      {result && !optimize.isPending && (
        <>
          {/* Stats summary */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatsCard
              icon={Trophy}
              label="Predicted Points"
              value={result.total_predicted_points.toFixed(1)}
              subtext="Starting XI total"
              accentColor="primary"
            />
            <StatsCard
              icon={DollarSign}
              label="Total Cost"
              value={`${(result.total_cost / 10).toFixed(1)}m`}
              subtext={`${((budget * 10 - result.total_cost) / 10).toFixed(1)}m remaining`}
              accentColor="accent"
            />
            <StatsCard
              icon={Users}
              label="Formation"
              value={result.formation}
              subtext={`${result.method.toUpperCase()} solver`}
              accentColor="default"
            />
            <StatsCard
              icon={Timer}
              label="Solve Time"
              value={
                result.solve_time_ms
                  ? `${result.solve_time_ms.toFixed(0)}ms`
                  : "--"
              }
              subtext="Computation time"
              accentColor="default"
            />
          </div>

          {/* Save optimized team */}
          <div className="flex flex-wrap items-center gap-3">
            <button
              onClick={handleSaveOptimizedTeam}
              disabled={saveTeam.isPending}
              className="flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-semibold bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 hover:bg-emerald-500/25 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {saveTeam.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Save className="h-4 w-4" />
              )}
              Save Optimized Team
            </button>

            {saveMessage && (
              <span
                className={`text-sm ${saveMessage.type === "success"
                    ? "text-emerald-400"
                    : "text-red-400"
                  }`}
              >
                {saveMessage.text}
              </span>
            )}
          </div>

          {/* Pitch view */}
          <div className="fpl-card overflow-hidden p-0">
            <div className="px-6 pt-6 pb-2">
              <h2 className="text-lg font-semibold">Starting XI</h2>
            </div>
            <PitchView
              players={enrichWithFixtures(result.squad, squadFixtures.data)}
              formation={result.formation}
              captainId={result.captain?.player_id ?? null}
              viceCaptainId={result.vice_captain?.player_id ?? null}
            />
          </div>

          {/* Bench */}
          <div className="fpl-card">
            <h2 className="text-lg font-semibold mb-4">Bench</h2>
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-4">
              {enrichWithFixtures(result.bench, squadFixtures.data).map((player) => (
                <PlayerCard
                  key={player.player_id}
                  name={player.web_name}
                  team={`Team ${player.team_id}`}
                  position={player.position}
                  price={player.cost}
                  predictedPoints={player.predicted_points}
                  nextOpponent={player.next_opponent}
                  fdr={player.fdr}
                  compact
                />
              ))}
              {result.bench.length === 0 && (
                <p className="text-sm text-[var(--muted-foreground)] col-span-full">
                  No bench players returned
                </p>
              )}
            </div>
          </div>

          {/* Full squad list */}
          <div className="fpl-card">
            <h2 className="text-lg font-semibold mb-4">Full Squad</h2>
            <div className="overflow-x-auto">
              <table className="fpl-table">
                <thead>
                  <tr>
                    <th>Player</th>
                    <th>Pos</th>
                    <th>Cost</th>
                    <th>Predicted</th>
                    <th>Avail</th>
                    <th>Role</th>
                    <th>Next</th>
                  </tr>
                </thead>
                <tbody>
                  {/* Starting XI header */}
                  <tr>
                    <td
                      colSpan={7}
                      className="!px-4 !py-2 bg-[var(--primary)]/10 border-l-2 border-l-[var(--primary)] text-xs font-semibold uppercase tracking-wider text-[var(--primary)]"
                    >
                      Starting XI
                    </td>
                  </tr>
                  {result.squad
                    .filter((p) => p.is_starter)
                    .sort((a, b) => {
                      const posOrder = { GKP: 0, DEF: 1, MID: 2, FWD: 3 };
                      return (
                        posOrder[a.position] - posOrder[b.position] ||
                        b.predicted_points - a.predicted_points
                      );
                    })
                    .map((player) => (
                      <tr key={player.player_id}>
                        <td className="font-medium">{player.web_name}</td>
                        <td>
                          <span
                            className={`fpl-badge fpl-badge-${player.position.toLowerCase()}`}
                          >
                            {player.position}
                          </span>
                        </td>
                        <td>
                          {(player.cost / 10).toFixed(1)}m
                        </td>
                        <td className="text-[var(--primary)] font-semibold">
                          {player.predicted_points.toFixed(1)}
                        </td>
                        <td>
                          {player.status !== "a" || (player.chance_of_playing != null && player.chance_of_playing < 100) ? (
                            <span
                              className={`fpl-badge ${player.status === "i" || player.status === "s" || player.status === "u"
                                  ? "bg-red-500/20 text-red-400"
                                  : "bg-yellow-500/20 text-yellow-400"
                                }`}
                              title={player.news || undefined}
                            >
                              {player.status === "i" ? "Injured" : player.status === "s" ? "Suspended" : player.status === "u" ? "Unavailable" : player.chance_of_playing != null ? `${player.chance_of_playing}%` : "Doubt"}
                            </span>
                          ) : (
                            <span className="fpl-badge bg-green-500/20 text-green-400">Fit</span>
                          )}
                        </td>
                        <td>
                          {player.is_captain ? (
                            <span className="fpl-badge bg-[var(--primary)]/20 text-[var(--primary)]">
                              Captain
                            </span>
                          ) : player.is_vice_captain ? (
                            <span className="fpl-badge bg-[var(--accent)]/20 text-[var(--accent)]">
                              Vice
                            </span>
                          ) : (
                            <span className="fpl-badge bg-[var(--primary)]/10 text-[var(--primary)]/70">
                              Starter
                            </span>
                          )}
                        </td>
                        <td>
                          {(() => {
                            const pFixtures =
                              squadFixtures.data?.fixtures[
                              String(player.player_id)
                              ];
                            const next = pFixtures?.[0];
                            if (!next) {
                              return (
                                <span className="text-sm text-[var(--muted-foreground)]">
                                  --
                                </span>
                              );
                            }
                            return (
                              <FDRBadge
                                difficulty={next.difficulty}
                                opponentShortName={next.opponent_short_name}
                                isHome={next.is_home}
                                compact
                              />
                            );
                          })()}
                        </td>
                      </tr>
                    ))}
                  {/* Substitutes header */}
                  <tr>
                    <td
                      colSpan={7}
                      className="!px-4 !py-2 bg-[var(--muted)]/30 border-l-2 border-l-[var(--muted-foreground)] text-xs font-semibold uppercase tracking-wider text-[var(--muted-foreground)]"
                    >
                      Substitutes
                    </td>
                  </tr>
                  {result.squad
                    .filter((p) => !p.is_starter)
                    .sort((a, b) => {
                      const posOrder = { GKP: 0, DEF: 1, MID: 2, FWD: 3 };
                      return (
                        posOrder[a.position] - posOrder[b.position] ||
                        b.predicted_points - a.predicted_points
                      );
                    })
                    .map((player) => (
                      <tr key={player.player_id} className="opacity-70">
                        <td className="font-medium">{player.web_name}</td>
                        <td>
                          <span
                            className={`fpl-badge fpl-badge-${player.position.toLowerCase()}`}
                          >
                            {player.position}
                          </span>
                        </td>
                        <td>
                          {(player.cost / 10).toFixed(1)}m
                        </td>
                        <td className="text-[var(--primary)] font-semibold">
                          {player.predicted_points.toFixed(1)}
                        </td>
                        <td>
                          {player.status !== "a" || (player.chance_of_playing != null && player.chance_of_playing < 100) ? (
                            <span
                              className={`fpl-badge ${player.status === "i" || player.status === "s" || player.status === "u"
                                  ? "bg-red-500/20 text-red-400"
                                  : "bg-yellow-500/20 text-yellow-400"
                                }`}
                              title={player.news || undefined}
                            >
                              {player.status === "i" ? "Injured" : player.status === "s" ? "Suspended" : player.status === "u" ? "Unavailable" : player.chance_of_playing != null ? `${player.chance_of_playing}%` : "Doubt"}
                            </span>
                          ) : (
                            <span className="fpl-badge bg-green-500/20 text-green-400">Fit</span>
                          )}
                        </td>
                        <td>
                          <span className="fpl-badge bg-[var(--muted)]/30 text-[var(--muted-foreground)]">
                            Bench
                          </span>
                        </td>
                        <td>
                          {(() => {
                            const pFixtures =
                              squadFixtures.data?.fixtures[
                              String(player.player_id)
                              ];
                            const next = pFixtures?.[0];
                            if (!next) {
                              return (
                                <span className="text-sm text-[var(--muted-foreground)]">
                                  --
                                </span>
                              );
                            }
                            return (
                              <FDRBadge
                                difficulty={next.difficulty}
                                opponentShortName={next.opponent_short_name}
                                isHome={next.is_home}
                                compact
                              />
                            );
                          })()}
                        </td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Upcoming Fixtures ticker */}
          <UpcomingFixtures
            fixturesData={squadFixtures.data}
            squad={result.squad}
            loading={squadFixtures.isPending}
          />
        </>
      )}

      {/* Team Suggestions - shown when squad data is available */}
      {hasSquadData && (
        <TeamSuggestions
          substituteSuggestions={substituteSuggestions.data}
          transferSuggestions={transferSuggestions.data}
          subsLoading={substituteSuggestions.isPending}
          transfersLoading={transferSuggestions.isPending}
          onFetchTransfers={handleFetchTransfers}
          teamBank={teamIdImport.data?.bank}
          captainData={captainPicker.data}
          captainLoading={captainPicker.isPending}
          benchData={benchOptimizer.data}
          benchLoading={benchOptimizer.isPending}
        />
      )}

      {/* Empty state */}
      {!result && !optimize.isPending && !optimize.isError && !hasSquadData && (
        <div className="fpl-card flex flex-col items-center justify-center py-16 text-center">
          <Cpu className="h-12 w-12 text-[var(--muted-foreground)]" />
          <h3 className="mt-4 text-lg font-semibold">
            Ready to Optimize
          </h3>
          <p className="mt-2 text-sm text-[var(--muted-foreground)] max-w-md">
            Configure your budget, preferred formation, and optimization method
            above, then click &quot;Optimize&quot; to find the best possible
            squad.
          </p>
        </div>
      )}

      {/* Import squad by Team ID */}
      <div className="fpl-card">
        <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <Hash className="h-5 w-5 text-[var(--primary)]" />
          Import / Update Squad
        </h2>
        <p className="text-sm text-[var(--muted-foreground)] mb-4">
          Import your squad by FPL Team ID, or upload a screenshot to update your current team.
        </p>

        <div className="flex flex-col sm:flex-row gap-3">
          <input
            type="text"
            inputMode="numeric"
            pattern="[0-9]*"
            placeholder="FPL Team ID e.g. 123456"
            value={teamId}
            onChange={(e) => setTeamId(e.target.value.replace(/\D/g, ""))}
            onKeyDown={(e) => {
              if (e.key === "Enter") handleTeamIdImport();
            }}
            className="fpl-select flex-1 sm:max-w-xs"
          />
          <button
            onClick={handleTeamIdImport}
            disabled={
              teamIdImport.isPending || !teamId || parseInt(teamId, 10) <= 0
            }
            className="fpl-button-primary gap-2 w-full sm:w-auto"
          >
            {teamIdImport.isPending ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Importing...
              </>
            ) : (
              <>
                <Upload className="h-4 w-4" />
                Import by ID
              </>
            )}
          </button>

          {/* Upload Screenshot */}
          <input
            ref={fileInputRef}
            type="file"
            accept="image/png,image/jpeg,image/webp"
            onChange={handleFileChange}
            className="hidden"
          />
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={screenshotImport.isPending}
            className="flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-semibold bg-blue-500/15 text-blue-400 border border-blue-500/30 hover:bg-blue-500/25 transition-colors disabled:opacity-50 disabled:cursor-not-allowed w-full sm:w-auto justify-center"
          >
            {screenshotImport.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Camera className="h-4 w-4" />
            )}
            {screenshotImport.isPending ? "Analyzing..." : "Upload Screenshot"}
          </button>

          {/* Update with Screenshot (only after team ID import) */}
          {teamIdImport.data && (
            <>
              <input
                ref={updateFileInputRef}
                type="file"
                accept="image/png,image/jpeg,image/webp"
                onChange={handleScreenshotUpdate}
                className="hidden"
              />
              <button
                onClick={() => updateFileInputRef.current?.click()}
                disabled={screenshotUpdate.isPending}
                className="flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-semibold bg-purple-500/15 text-purple-400 border border-purple-500/30 hover:bg-purple-500/25 transition-colors disabled:opacity-50 disabled:cursor-not-allowed w-full sm:w-auto justify-center"
              >
                {screenshotUpdate.isPending ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Camera className="h-4 w-4" />
                )}
                {screenshotUpdate.isPending ? "Updating..." : "Update with Screenshot"}
              </button>
            </>
          )}

          {typeof window !== "undefined" && localStorage.getItem("fpl-team-id") && (
            <button
              onClick={handleForgetTeam}
              className="text-xs text-[var(--muted-foreground)] hover:text-red-400 transition-colors underline underline-offset-2 w-full sm:w-auto text-center"
            >
              Forget saved ID
            </button>
          )}
        </div>

        {/* Import errors */}
        {teamIdImport.isError && (
          <div className="mt-4 p-3 rounded-lg bg-red-500/5 border border-red-500/30 text-red-400 text-sm flex items-start gap-2">
            <AlertCircle className="h-4 w-4 mt-0.5 shrink-0" />
            <p className="whitespace-pre-line">
              {friendlyErrorMessage(teamIdImport.error)}
            </p>
          </div>
        )}
        {screenshotImport.isError && (
          <div className="mt-4 p-3 rounded-lg bg-red-500/5 border border-red-500/30 text-red-400 text-sm flex items-start gap-2">
            <AlertCircle className="h-4 w-4 mt-0.5 shrink-0" />
            <p className="whitespace-pre-line">
              {friendlyErrorMessage(screenshotImport.error)}
            </p>
          </div>
        )}

        {/* Team ID import result summary */}
        {teamIdImport.data && !teamIdImport.isPending && (
          <div className="mt-4 rounded-lg border border-[var(--primary)]/30 bg-[var(--primary)]/5 p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-bold">
                  {teamIdImport.data.team_name} — {teamIdImport.data.manager_name}
                </p>
                <p className="text-xs text-[var(--muted-foreground)] mt-0.5">
                  GW{teamIdImport.data.gameweek} · Rank {teamIdImport.data.overall_rank.toLocaleString()} · Bank {teamIdImport.data.bank.toFixed(1)}m · Value {teamIdImport.data.team_value.toFixed(1)}m
                </p>
              </div>
              <span className="text-xs text-green-400 flex items-center gap-1">
                <CheckCircle2 className="h-3 w-3" />
                {effectivePlayers.filter((p: MatchedPlayer) => p.player_id !== null).length} players loaded
              </span>
            </div>
          </div>
        )}

        {/* Screenshot import result */}
        {screenshotImport.data && !screenshotImport.isPending && !teamIdImport.data && (
          <div className="mt-4 rounded-lg border border-blue-500/30 bg-blue-500/5 p-4">
            <div className="flex items-center justify-between">
              <p className="text-sm font-bold">
                Screenshot: {screenshotImport.data.matched_count} of {screenshotImport.data.extracted_count} players matched
              </p>
              <span className="text-xs text-green-400 flex items-center gap-1">
                <CheckCircle2 className="h-3 w-3" />
                Squad loaded
              </span>
            </div>
          </div>
        )}

        {/* Screenshot update feedback */}
        {updateMessage && (
          <p className="text-sm mt-3 text-blue-400">{updateMessage}</p>
        )}

        {/* Save feedback */}
        {saveMessage && (
          <p className={`text-sm mt-2 ${saveMessage.type === "success" ? "text-emerald-400" : "text-red-400"}`}>
            {saveMessage.text}
          </p>
        )}
      </div>
    </div>
  );
}
