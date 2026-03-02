"use client";

import { useState, useRef, useEffect } from "react";
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
} from "lucide-react";
import PitchView from "@/components/PitchView";
import PlayerCard from "@/components/PlayerCard";
import StatsCard from "@/components/StatsCard";
import FDRBadge from "@/components/FDRBadge";
import UpcomingFixtures from "@/components/UpcomingFixtures";
import TeamSuggestions from "@/components/TeamSuggestions";
import {
  useOptimize,
  useScreenshotImport,
  useSquadFixtures,
  useSubstituteSuggestions,
  useTransferSuggestions,
} from "@/hooks/useApi";
import type {
  OptimizationMethod,
  OptimizationResult,
  MatchedPlayer,
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

  const fileInputRef = useRef<HTMLInputElement>(null);
  const optimize = useOptimize();
  const screenshotImport = useScreenshotImport();
  const squadFixtures = useSquadFixtures();
  const substituteSuggestions = useSubstituteSuggestions();
  const transferSuggestions = useTransferSuggestions();

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

      {/* Import squad from screenshot */}
      <div className="fpl-card">
        <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <Camera className="h-5 w-5 text-[var(--primary)]" />
          Import Your Squad
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
            <span>
              {screenshotImport.error?.message || "Failed to import screenshot. Please try again."}
            </span>
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

            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
              {screenshotImport.data.players.map((player: MatchedPlayer, idx: number) => (
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

            <button
              onClick={handleUseImportedSquad}
              disabled={screenshotImport.data.matched_count === 0}
              className="fpl-button-primary gap-2 w-full sm:w-auto"
            >
              <Cpu className="h-4 w-4" />
              Optimize with This Squad
            </button>
          </div>
        )}
      </div>

      {/* Error state */}
      {optimize.isError && (
        <div className="fpl-card border-red-500/30 bg-red-500/5">
          <div className="flex items-center gap-3 text-red-400">
            <AlertCircle className="h-5 w-5 shrink-0" />
            <div>
              <p className="font-semibold">Optimization Failed</p>
              <p className="text-sm mt-1 text-red-400/80">
                {optimize.error?.message ||
                  "Could not reach the backend. Make sure it is running."}
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
                    <th>Role</th>
                    <th>Next</th>
                  </tr>
                </thead>
                <tbody>
                  {result.squad
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
                          {player.is_captain ? (
                            <span className="fpl-badge bg-[var(--primary)]/20 text-[var(--primary)]">
                              Captain
                            </span>
                          ) : player.is_vice_captain ? (
                            <span className="fpl-badge bg-[var(--accent)]/20 text-[var(--accent)]">
                              Vice
                            </span>
                          ) : player.is_starter ? (
                            <span className="text-sm text-[var(--foreground)]">
                              XI
                            </span>
                          ) : (
                            <span className="text-sm text-[var(--muted-foreground)]">
                              Bench
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
