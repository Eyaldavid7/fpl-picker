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
  Star,
  ShieldCheck,
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
} from "@/hooks/useApi";
import { useSaveTeam } from "@/hooks/useFirestore";
import { friendlyErrorMessage, getApiBaseUrl } from "@/lib/api-client";
import type {
  OptimizationMethod,
  OptimizationResult,
  MatchedPlayer,
  TeamIdImportResult,
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
  const [autoLoading, setAutoLoading] = useState(false);
  const [loadedTeamLabel, setLoadedTeamLabel] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);
  // Guard: when user manually loads a different team, ignore pending auto-load results
  const manuallyLoadedRef = useRef(false);
  const optimize = useOptimize();
  const teamIdImport = useTeamIdImport();
  const screenshotImport = useScreenshotImport();
  const squadFixtures = useSquadFixtures();
  const substituteSuggestions = useSubstituteSuggestions();
  const transferSuggestions = useTransferSuggestions();
  const saveTeam = useSaveTeam();

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
    screenshotImport.mutate(file);
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

  // Auto-fetch substitute suggestions when optimization result arrives
  useEffect(() => {
    if (optimize.data?.squad?.length) {
      const playerIds = optimize.data.squad.map((p) => p.player_id);
      substituteSuggestions.mutate({
        squad_player_ids: playerIds,
        formation: optimize.data.formation,
      });
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
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [importedPlayerIds]);

  // Auto-load saved team ID on mount
  useEffect(() => {
    const savedId = localStorage.getItem("fpl-team-id");
    if (savedId) {
      const parsed = parseInt(savedId, 10);
      if (!isNaN(parsed) && parsed > 0) {
        setTeamId(savedId);
        setAutoLoading(true);
        teamIdImport.mutate(parsed, {
          onSuccess: (data) => {
            // If user already loaded a different team, don't overwrite
            if (manuallyLoadedRef.current) return;
            const ids = data.players
              .filter((p: MatchedPlayer) => p.player_id !== null)
              .map((p: MatchedPlayer) => p.player_id as number);
            setImportedPlayerIds(ids);
          },
          onSettled: () => setAutoLoading(false),
        });
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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
      // Prevent any in-flight auto-load from overwriting this
      manuallyLoadedRef.current = true;
      setImportedPlayerIds(playerIds);
      setLoadedTeamLabel(teamName || `Saved team (${playerIds.length} players)`);

      if (savedFplTeamId) {
        setTeamId(savedFplTeamId.toString());
        teamIdImport.mutate(savedFplTeamId, {
          onSuccess: (data) => {
            const ids = data.players
              .filter((p: MatchedPlayer) => p.player_id !== null)
              .map((p: MatchedPlayer) => p.player_id as number);
            setImportedPlayerIds(ids);
          },
        });
      } else {
        // Reset team ID import state so the old team card disappears
        teamIdImport.reset();
        setTeamId("");
      }
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

      {/* Import squad by Team ID */}
      <div className="fpl-card">
        <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <Hash className="h-5 w-5 text-[var(--primary)]" />
          Import Your Squad by Team ID
        </h2>
        <p className="text-sm text-[var(--muted-foreground)] mb-4">
          Enter your FPL Team ID to import your current squad directly from the
          FPL API. You can find your Team ID in the URL when viewing your team
          on the official FPL site.
        </p>

        {autoLoading && (
          <div className="mb-4 flex items-center gap-2 text-sm text-[var(--primary)]">
            <Loader2 className="h-4 w-4 animate-spin" />
            Auto-loading your saved team...
          </div>
        )}

        <div className="flex flex-col sm:flex-row gap-3">
          <input
            type="text"
            inputMode="numeric"
            pattern="[0-9]*"
            placeholder="e.g. 123456"
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
                Import
              </>
            )}
          </button>
          {typeof window !== "undefined" && localStorage.getItem("fpl-team-id") && (
            <button
              onClick={handleForgetTeam}
              className="text-xs text-[var(--muted-foreground)] hover:text-red-400 transition-colors underline underline-offset-2 w-full sm:w-auto text-center"
            >
              Forget saved team
            </button>
          )}
        </div>

        {/* Team ID import error */}
        {teamIdImport.isError && (
          <div className="mt-4 p-3 rounded-lg bg-red-500/5 border border-red-500/30 text-red-400 text-sm flex items-start gap-2">
            <AlertCircle className="h-4 w-4 mt-0.5 shrink-0" />
            <div>
              <p className="whitespace-pre-line">
                {friendlyErrorMessage(teamIdImport.error)}
              </p>
              <p className="text-xs mt-1 text-red-400/60">
                API URL: {getApiBaseUrl()}
              </p>
            </div>
          </div>
        )}

        {/* Team ID import results */}
        {teamIdImport.data && !teamIdImport.isPending && (
          <div className="mt-4 space-y-4">
            {/* Team info card */}
            <div className="rounded-lg border border-[var(--primary)]/30 bg-[var(--primary)]/5 p-4">
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
                <div>
                  <p className="text-xs font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
                    Team Name
                  </p>
                  <p className="text-sm font-bold mt-0.5">
                    {teamIdImport.data.team_name}
                  </p>
                </div>
                <div>
                  <p className="text-xs font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
                    Manager
                  </p>
                  <p className="text-sm font-bold mt-0.5">
                    {teamIdImport.data.manager_name}
                  </p>
                </div>
                <div>
                  <p className="text-xs font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
                    Gameweek
                  </p>
                  <p className="text-sm font-bold mt-0.5">
                    GW{teamIdImport.data.gameweek}
                  </p>
                </div>
                <div>
                  <p className="text-xs font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
                    Overall Rank
                  </p>
                  <p className="text-sm font-bold mt-0.5">
                    {teamIdImport.data.overall_rank.toLocaleString()}
                  </p>
                </div>
                <div>
                  <p className="text-xs font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
                    Bank
                  </p>
                  <p className="text-sm font-bold mt-0.5">
                    {teamIdImport.data.bank.toFixed(1)}m
                  </p>
                </div>
                <div>
                  <p className="text-xs font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
                    Team Value
                  </p>
                  <p className="text-sm font-bold mt-0.5">
                    {teamIdImport.data.team_value.toFixed(1)}m
                  </p>
                </div>
              </div>
              <div className="mt-3 text-xs text-[var(--muted-foreground)]">
                Overall Points: {teamIdImport.data.overall_points.toLocaleString()}
              </div>
            </div>

            {/* Player count summary */}
            <div className="flex items-center justify-between">
              <p className="text-sm text-[var(--muted-foreground)]">
                {teamIdImport.data.players.filter((p: MatchedPlayer) => p.player_id !== null).length}{" "}
                players matched
              </p>
              {importedPlayerIds.length > 0 && (
                <span className="text-xs text-green-400 flex items-center gap-1">
                  <CheckCircle2 className="h-3 w-3" />
                  Squad loaded
                </span>
              )}
            </div>

            {/* Starting XI */}
            <div>
              <div className="flex items-center gap-2 mb-2">
                <div className="h-1 w-4 rounded bg-[var(--primary)]" />
                <span className="text-xs font-semibold uppercase tracking-wider text-[var(--primary)]">
                  Starting XI
                </span>
                <span className="text-xs text-[var(--muted-foreground)]">
                  ({teamIdImport.data.starting_xi.length} players)
                </span>
              </div>
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
                {teamIdImport.data.players
                  .filter((p: MatchedPlayer) =>
                    teamIdImport.data!.starting_xi.includes(p.player_id as number)
                  )
                  .map((player: MatchedPlayer, idx: number) => (
                    <div
                      key={idx}
                      className={`rounded-lg border p-3 ${confidenceBg(player.confidence)}`}
                    >
                      <div className="flex items-center justify-between">
                        <div>
                          <p className="font-medium text-sm flex items-center gap-1.5">
                            {player.web_name || player.extracted_name}
                            {player.player_id === teamIdImport.data!.captain_id && (
                              <span className="inline-flex items-center gap-0.5 fpl-badge bg-[var(--primary)]/20 text-[var(--primary)] text-[10px]">
                                <Star className="h-3 w-3" />
                                C
                              </span>
                            )}
                            {player.player_id === teamIdImport.data!.vice_captain_id && (
                              <span className="inline-flex items-center gap-0.5 fpl-badge bg-[var(--accent)]/20 text-[var(--accent)] text-[10px]">
                                <ShieldCheck className="h-3 w-3" />
                                VC
                              </span>
                            )}
                          </p>
                          <div className="flex items-center gap-2 mt-1">
                            {player.position && (
                              <span
                                className={`fpl-badge fpl-badge-${player.position.toLowerCase()} text-xs`}
                              >
                                {player.position}
                              </span>
                            )}
                            {player.team_name && (
                              <span className="text-xs text-[var(--muted-foreground)]">
                                {player.team_name}
                              </span>
                            )}
                          </div>
                        </div>
                        <span className={`text-sm font-bold ${confidenceColor(player.confidence)}`}>
                          {Math.round(player.confidence * 100)}%
                        </span>
                      </div>
                    </div>
                  ))}
              </div>
            </div>

            {/* Bench */}
            {teamIdImport.data.bench.length > 0 && (
              <div>
                <div className="flex items-center gap-2 mb-2">
                  <div className="h-1 w-4 rounded bg-[var(--muted-foreground)]" />
                  <span className="text-xs font-semibold uppercase tracking-wider text-[var(--muted-foreground)]">
                    Substitutes
                  </span>
                  <span className="text-xs text-[var(--muted-foreground)]">
                    ({teamIdImport.data.bench.length} players)
                  </span>
                </div>
                <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-4">
                  {teamIdImport.data.players
                    .filter((p: MatchedPlayer) =>
                      teamIdImport.data!.bench.includes(p.player_id as number)
                    )
                    .map((player: MatchedPlayer, idx: number) => (
                      <div
                        key={idx}
                        className={`rounded-lg border p-3 opacity-70 ${confidenceBg(player.confidence)}`}
                      >
                        <div className="flex items-center justify-between">
                          <div>
                            <p className="font-medium text-sm">
                              {player.web_name || player.extracted_name}
                            </p>
                            <div className="flex items-center gap-2 mt-1">
                              {player.position && (
                                <span
                                  className={`fpl-badge fpl-badge-${player.position.toLowerCase()} text-xs`}
                                >
                                  {player.position}
                                </span>
                              )}
                              {player.team_name && (
                                <span className="text-xs text-[var(--muted-foreground)]">
                                  {player.team_name}
                                </span>
                              )}
                            </div>
                          </div>
                          <div className="flex flex-col items-end gap-1">
                            <span className="text-[10px] font-medium uppercase tracking-wider text-[var(--muted-foreground)] bg-[var(--muted)]/40 px-1.5 py-0.5 rounded">
                              Bench
                            </span>
                            <span className={`text-sm font-bold ${confidenceColor(player.confidence)}`}>
                              {Math.round(player.confidence * 100)}%
                            </span>
                          </div>
                        </div>
                      </div>
                    ))}
                </div>
              </div>
            )}

            <div className="flex flex-wrap gap-3">
              <button
                onClick={handleUseTeamIdSquad}
                disabled={
                  teamIdImport.data.players.filter(
                    (p: MatchedPlayer) => p.player_id !== null
                  ).length === 0
                }
                className="fpl-button-primary gap-2 w-full sm:w-auto"
              >
                <Cpu className="h-4 w-4" />
                Optimize with This Squad
              </button>

              <button
                onClick={handleSaveTeamIdTeam}
                disabled={
                  teamIdImport.data.players.filter(
                    (p: MatchedPlayer) => p.player_id !== null
                  ).length === 0 || saveTeam.isPending
                }
                className="flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-semibold bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 hover:bg-emerald-500/25 transition-colors disabled:opacity-50 disabled:cursor-not-allowed w-full sm:w-auto justify-center"
              >
                {saveTeam.isPending ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Save className="h-4 w-4" />
                )}
                Save Team
              </button>
            </div>

            {/* Inline save feedback */}
            {saveMessage && (
              <p
                className={`text-sm mt-2 ${saveMessage.type === "success"
                    ? "text-emerald-400"
                    : "text-red-400"
                  }`}
              >
                {saveMessage.text}
              </p>
            )}
          </div>
        )}

        {/* Loaded from saved teams indicator */}
        {!teamIdImport.data && loadedTeamLabel && importedPlayerIds.length > 0 && (
          <div className="mt-4 rounded-lg border border-[var(--primary)]/30 bg-[var(--primary)]/5 p-4 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="h-5 w-5 text-[var(--primary)]" />
              <div>
                <p className="text-sm font-semibold text-[var(--foreground)]">
                  {loadedTeamLabel}
                </p>
                <p className="text-xs text-[var(--muted-foreground)]">
                  {importedPlayerIds.length} players loaded — suggestions updating below
                </p>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Import squad from screenshot */}
      <div className="fpl-card">
        <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <Camera className="h-5 w-5 text-[var(--primary)]" />
          Or Upload Screenshot
        </h2>
        <p className="text-sm text-[var(--muted-foreground)] mb-4">
          Upload a screenshot of your FPL team and we&apos;ll detect your players automatically.
        </p>

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
          className="fpl-button-primary gap-2"
        >
          {screenshotImport.isPending ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Analyzing Screenshot...
            </>
          ) : (
            <>
              <Upload className="h-4 w-4" />
              Upload Screenshot
            </>
          )}
        </button>

        {/* Import error */}
        {screenshotImport.isError && (
          <div className="mt-4 p-3 rounded-lg bg-red-500/5 border border-red-500/30 text-red-400 text-sm flex items-start gap-2">
            <AlertCircle className="h-4 w-4 mt-0.5 shrink-0" />
            <div>
              <p className="whitespace-pre-line">
                {friendlyErrorMessage(screenshotImport.error)}
              </p>
              <p className="text-xs mt-1 text-red-400/60">
                API URL: {getApiBaseUrl()}
              </p>
            </div>
          </div>
        )}

        {/* Matched players grid */}
        {screenshotImport.data && !screenshotImport.isPending && (
          <div className="mt-4 space-y-4">
            <div className="flex items-center justify-between">
              <p className="text-sm text-[var(--muted-foreground)]">
                Matched {screenshotImport.data.matched_count} of{" "}
                {screenshotImport.data.extracted_count} detected players
              </p>
              {importedPlayerIds.length > 0 && (
                <span className="text-xs text-green-400 flex items-center gap-1">
                  <CheckCircle2 className="h-3 w-3" />
                  Squad loaded
                </span>
              )}
            </div>

            {/* Starting XI */}
            <div>
              <div className="flex items-center gap-2 mb-2">
                <div className="h-1 w-4 rounded bg-[var(--primary)]" />
                <span className="text-xs font-semibold uppercase tracking-wider text-[var(--primary)]">
                  Starting XI
                </span>
                <span className="text-xs text-[var(--muted-foreground)]">
                  ({Math.min(11, screenshotImport.data.players.length)} players)
                </span>
              </div>
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
                {screenshotImport.data.players.slice(0, 11).map((player: MatchedPlayer, idx: number) => (
                  <div
                    key={idx}
                    className={`rounded-lg border p-3 ${confidenceBg(player.confidence)}`}
                  >
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="font-medium text-sm">
                          {player.web_name || player.extracted_name}
                        </p>
                        {player.web_name && player.web_name !== player.extracted_name && (
                          <p className="text-xs text-[var(--muted-foreground)]">
                            from &quot;{player.extracted_name}&quot;
                          </p>
                        )}
                        <div className="flex items-center gap-2 mt-1">
                          {player.position && (
                            <span
                              className={`fpl-badge fpl-badge-${player.position.toLowerCase()} text-xs`}
                            >
                              {player.position}
                            </span>
                          )}
                          {player.team_name && (
                            <span className="text-xs text-[var(--muted-foreground)]">
                              {player.team_name}
                            </span>
                          )}
                        </div>
                      </div>
                      <span className={`text-sm font-bold ${confidenceColor(player.confidence)}`}>
                        {Math.round(player.confidence * 100)}%
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Substitutes */}
            {screenshotImport.data.players.length > 11 && (
              <div>
                <div className="flex items-center gap-2 mb-2">
                  <div className="h-1 w-4 rounded bg-[var(--muted-foreground)]" />
                  <span className="text-xs font-semibold uppercase tracking-wider text-[var(--muted-foreground)]">
                    Substitutes
                  </span>
                  <span className="text-xs text-[var(--muted-foreground)]">
                    ({screenshotImport.data.players.length - 11} players)
                  </span>
                </div>
                <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-4">
                  {screenshotImport.data.players.slice(11).map((player: MatchedPlayer, idx: number) => (
                    <div
                      key={idx + 11}
                      className={`rounded-lg border p-3 opacity-70 ${confidenceBg(player.confidence)}`}
                    >
                      <div className="flex items-center justify-between">
                        <div>
                          <p className="font-medium text-sm">
                            {player.web_name || player.extracted_name}
                          </p>
                          {player.web_name && player.web_name !== player.extracted_name && (
                            <p className="text-xs text-[var(--muted-foreground)]">
                              from &quot;{player.extracted_name}&quot;
                            </p>
                          )}
                          <div className="flex items-center gap-2 mt-1">
                            {player.position && (
                              <span
                                className={`fpl-badge fpl-badge-${player.position.toLowerCase()} text-xs`}
                              >
                                {player.position}
                              </span>
                            )}
                            {player.team_name && (
                              <span className="text-xs text-[var(--muted-foreground)]">
                                {player.team_name}
                              </span>
                            )}
                          </div>
                        </div>
                        <div className="flex flex-col items-end gap-1">
                          <span className="text-[10px] font-medium uppercase tracking-wider text-[var(--muted-foreground)] bg-[var(--muted)]/40 px-1.5 py-0.5 rounded">
                            Bench
                          </span>
                          <span className={`text-sm font-bold ${confidenceColor(player.confidence)}`}>
                            {Math.round(player.confidence * 100)}%
                          </span>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div className="flex flex-wrap gap-3">
              <button
                onClick={handleUseImportedSquad}
                disabled={screenshotImport.data.matched_count === 0}
                className="fpl-button-primary gap-2 w-full sm:w-auto"
              >
                <Cpu className="h-4 w-4" />
                Optimize with This Squad
              </button>

              <button
                onClick={handleSaveImportedTeam}
                disabled={
                  screenshotImport.data.matched_count === 0 ||
                  saveTeam.isPending
                }
                className="flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-semibold bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 hover:bg-emerald-500/25 transition-colors disabled:opacity-50 disabled:cursor-not-allowed w-full sm:w-auto justify-center"
              >
                {saveTeam.isPending ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Save className="h-4 w-4" />
                )}
                Save Imported Team
              </button>
            </div>

            {/* Inline save feedback */}
            {saveMessage && (
              <p
                className={`text-sm mt-2 ${saveMessage.type === "success"
                    ? "text-emerald-400"
                    : "text-red-400"
                  }`}
              >
                {saveMessage.text}
              </p>
            )}
          </div>
        )}
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
              players={result.squad}
              formation={result.formation}
              captainId={result.captain?.player_id ?? null}
              viceCaptainId={result.vice_captain?.player_id ?? null}
            />
          </div>

          {/* Bench */}
          <div className="fpl-card">
            <h2 className="text-lg font-semibold mb-4">Bench</h2>
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-4">
              {result.bench.map((player) => (
                <PlayerCard
                  key={player.player_id}
                  name={player.web_name}
                  team={`Team ${player.team_id}`}
                  position={player.position}
                  price={player.cost}
                  predictedPoints={player.predicted_points}
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
        />
      )}

      {/* Empty state */}
      {!result && !optimize.isPending && !optimize.isError && (
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
    </div>
  );
}
