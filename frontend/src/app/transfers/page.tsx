"use client";

import { useState } from "react";
import {
  ArrowLeftRight,
  ArrowRight,
  Shield,
  Zap,
  Star,
  Users,
  Loader2,
  AlertCircle,
  ChevronRight,
  TrendingUp,
  TrendingDown,
  Minus,
} from "lucide-react";
import { useTransferPlan, useChipStrategy } from "@/hooks/useApi";
import PlayerCard from "@/components/PlayerCard";
import type {
  TransferPlan,
  ChipStrategy,
  ChipType,
  SensitivityLevel,
} from "@/types";

const chipInfo: Record<
  ChipType,
  { label: string; description: string; icon: typeof Star; color: string }
> = {
  wildcard: {
    label: "Wildcard",
    description: "Unlimited free transfers for one gameweek",
    icon: Zap,
    color: "text-yellow-400 bg-yellow-500/10 border-yellow-500/30",
  },
  free_hit: {
    label: "Free Hit",
    description: "Temporary squad for a single gameweek",
    icon: Shield,
    color: "text-blue-400 bg-blue-500/10 border-blue-500/30",
  },
  triple_captain: {
    label: "Triple Captain",
    description: "Captain scores triple points",
    icon: Star,
    color: "text-emerald-400 bg-emerald-500/10 border-emerald-500/30",
  },
  bench_boost: {
    label: "Bench Boost",
    description: "Bench players score points this gameweek",
    icon: Users,
    color: "text-purple-400 bg-purple-500/10 border-purple-500/30",
  },
};

function SensitivityBadge({ level }: { level: SensitivityLevel }) {
  const config: Record<
    SensitivityLevel,
    { label: string; className: string; icon: typeof TrendingUp }
  > = {
    strong: {
      label: "Strong",
      className: "badge-strong",
      icon: TrendingUp,
    },
    moderate: {
      label: "Moderate",
      className: "badge-moderate",
      icon: Minus,
    },
    volatile: {
      label: "Volatile",
      className: "badge-volatile",
      icon: TrendingDown,
    },
  };

  const c = config[level];
  const Icon = c.icon;

  return (
    <span
      className={`fpl-badge ${c.className} gap-1`}
    >
      <Icon className="h-3 w-3" />
      {c.label}
    </span>
  );
}

export default function TransfersPage() {
  const transferPlan = useTransferPlan();
  const chipStrategy = useChipStrategy();

  const [squadIds] = useState<string>("");
  const [freeTransfers, setFreeTransfers] = useState(1);
  const [horizon, setHorizon] = useState(5);

  const handlePlanTransfers = () => {
    const currentSquad = squadIds
      .split(",")
      .map((s) => parseInt(s.trim(), 10))
      .filter((n) => !isNaN(n));

    transferPlan.mutate({
      current_squad: currentSquad.length > 0 ? currentSquad : undefined,
      free_transfers: freeTransfers,
      horizon_gameweeks: horizon,
    });
  };

  const handleChipStrategy = () => {
    const currentSquad = squadIds
      .split(",")
      .map((s) => parseInt(s.trim(), 10))
      .filter((n) => !isNaN(n));

    chipStrategy.mutate({
      current_squad: currentSquad.length > 0 ? currentSquad : undefined,
      chips_available: [
        "wildcard",
        "free_hit",
        "triple_captain",
        "bench_boost",
      ],
    });
  };

  const plan: TransferPlan | undefined = transferPlan.data;
  const chips: ChipStrategy | undefined = chipStrategy.data;

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Page header */}
      <div>
        <h1 className="text-3xl font-bold fpl-gradient-text">
          Transfer Planner
        </h1>
        <p className="mt-1 text-[var(--muted-foreground)]">
          AI-powered transfer recommendations and chip strategy planning
        </p>
      </div>

      {/* Controls */}
      <div className="fpl-card">
        <h2 className="text-lg font-semibold mb-4">Planning Parameters</h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {/* Free transfers */}
          <div>
            <label className="block text-sm font-medium text-[var(--muted-foreground)] mb-2">
              Free Transfers Available
            </label>
            <select
              value={freeTransfers}
              onChange={(e) => setFreeTransfers(Number(e.target.value))}
              className="fpl-select"
            >
              {[0, 1, 2, 3, 4, 5].map((n) => (
                <option key={n} value={n}>
                  {n} transfer{n !== 1 ? "s" : ""}
                </option>
              ))}
            </select>
          </div>

          {/* Horizon */}
          <div>
            <label className="block text-sm font-medium text-[var(--muted-foreground)] mb-2">
              Planning Horizon
            </label>
            <select
              value={horizon}
              onChange={(e) => setHorizon(Number(e.target.value))}
              className="fpl-select"
            >
              {[1, 3, 5, 8, 10].map((n) => (
                <option key={n} value={n}>
                  {n} gameweek{n !== 1 ? "s" : ""}
                </option>
              ))}
            </select>
          </div>

          {/* Plan transfers button */}
          <div className="flex items-end">
            <button
              onClick={handlePlanTransfers}
              disabled={transferPlan.isPending}
              className="fpl-button-primary w-full gap-2"
            >
              {transferPlan.isPending ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Planning...
                </>
              ) : (
                <>
                  <ArrowLeftRight className="h-4 w-4" />
                  Plan Transfers
                </>
              )}
            </button>
          </div>

          {/* Chip strategy button */}
          <div className="flex items-end">
            <button
              onClick={handleChipStrategy}
              disabled={chipStrategy.isPending}
              className="fpl-button-secondary w-full gap-2"
            >
              {chipStrategy.isPending ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Analyzing...
                </>
              ) : (
                <>
                  <Zap className="h-4 w-4" />
                  Chip Strategy
                </>
              )}
            </button>
          </div>
        </div>
      </div>

      {/* Error states */}
      {transferPlan.isError && (
        <div className="fpl-card border-red-500/30 bg-red-500/5">
          <div className="flex items-center gap-3 text-red-400">
            <AlertCircle className="h-5 w-5 shrink-0" />
            <div>
              <p className="font-semibold">Transfer Planning Failed</p>
              <p className="text-sm mt-1 text-red-400/80">
                {transferPlan.error?.message ||
                  "Could not generate transfer plan. Ensure the backend is running."}
              </p>
            </div>
          </div>
        </div>
      )}

      {chipStrategy.isError && (
        <div className="fpl-card border-red-500/30 bg-red-500/5">
          <div className="flex items-center gap-3 text-red-400">
            <AlertCircle className="h-5 w-5 shrink-0" />
            <div>
              <p className="font-semibold">Chip Strategy Failed</p>
              <p className="text-sm mt-1 text-red-400/80">
                {chipStrategy.error?.message ||
                  "Could not generate chip strategy."}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Loading states */}
      {(transferPlan.isPending || chipStrategy.isPending) && (
        <div className="fpl-card flex flex-col items-center justify-center py-16">
          <Loader2 className="h-10 w-10 animate-spin text-[var(--primary)]" />
          <p className="mt-4 text-[var(--muted-foreground)]">
            {transferPlan.isPending
              ? "Analyzing transfer options..."
              : "Evaluating chip strategies..."}
          </p>
        </div>
      )}

      {/* Transfer recommendations */}
      {plan && !transferPlan.isPending && (
        <div className="space-y-4">
          {/* Summary stats */}
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <div className="fpl-card text-center">
              <p className="text-xs text-[var(--muted-foreground)] uppercase tracking-wider">
                Transfers
              </p>
              <p className="mt-1 text-2xl font-bold text-[var(--primary)]">
                {plan.transfers.length}
              </p>
            </div>
            <div className="fpl-card text-center">
              <p className="text-xs text-[var(--muted-foreground)] uppercase tracking-wider">
                Expected Gain
              </p>
              <p className="mt-1 text-2xl font-bold text-emerald-400">
                +{plan.total_expected_gain.toFixed(1)}
              </p>
            </div>
            <div className="fpl-card text-center">
              <p className="text-xs text-[var(--muted-foreground)] uppercase tracking-wider">
                Hits Taken
              </p>
              <p className="mt-1 text-2xl font-bold text-red-400">
                {plan.hits_taken > 0
                  ? `-${plan.hits_taken * 4}`
                  : "0"}
              </p>
            </div>
            <div className="fpl-card text-center">
              <p className="text-xs text-[var(--muted-foreground)] uppercase tracking-wider">
                Net Gain
              </p>
              <p
                className={`mt-1 text-2xl font-bold ${
                  plan.net_expected_gain >= 0
                    ? "text-emerald-400"
                    : "text-red-400"
                }`}
              >
                {plan.net_expected_gain >= 0 ? "+" : ""}
                {plan.net_expected_gain.toFixed(1)}
              </p>
            </div>
          </div>

          {/* Transfer cards */}
          <div className="fpl-card">
            <h2 className="text-lg font-semibold mb-4">
              Recommended Transfers
            </h2>
            {plan.transfers.length === 0 ? (
              <p className="text-sm text-[var(--muted-foreground)]">
                No transfers recommended. Your squad is already optimal for the
                given horizon.
              </p>
            ) : (
              <div className="space-y-3">
                {plan.transfers.map((transfer, idx) => (
                  <div
                    key={idx}
                    className="flex items-center gap-3 rounded-lg border border-[var(--border)] bg-[var(--background)] p-3 sm:p-4"
                  >
                    {/* Priority number */}
                    <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[var(--muted)] text-xs font-bold">
                      {idx + 1}
                    </span>

                    {/* Out player */}
                    <div className="flex-1 min-w-0">
                      <PlayerCard
                        name={transfer.player_out_name}
                        position={transfer.player_out_position ?? "MID"}
                        price={0}
                        team={transfer.player_out_team}
                        compact
                      />
                    </div>

                    {/* Arrow */}
                    <div className="flex flex-col items-center shrink-0 px-2">
                      <ArrowRight className="h-5 w-5 text-[var(--primary)]" />
                      <span
                        className={`mt-1 text-[10px] font-semibold ${
                          transfer.expected_point_gain >= 0
                            ? "text-emerald-400"
                            : "text-red-400"
                        }`}
                      >
                        {transfer.expected_point_gain >= 0 ? "+" : ""}
                        {transfer.expected_point_gain.toFixed(1)}
                      </span>
                    </div>

                    {/* In player */}
                    <div className="flex-1 min-w-0">
                      <PlayerCard
                        name={transfer.player_in_name}
                        position={transfer.player_in_position ?? "MID"}
                        price={0}
                        team={transfer.player_in_team}
                        compact
                      />
                    </div>

                    {/* Cost delta */}
                    <div className="hidden sm:block shrink-0 text-right">
                      <span
                        className={`text-xs font-semibold ${
                          transfer.cost_delta > 0
                            ? "text-red-400"
                            : transfer.cost_delta < 0
                            ? "text-emerald-400"
                            : "text-[var(--muted-foreground)]"
                        }`}
                      >
                        {transfer.cost_delta > 0 ? "+" : ""}
                        {(transfer.cost_delta / 10).toFixed(1)}m
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Sensitivity indicator */}
          <div className="fpl-card">
            <h2 className="text-lg font-semibold mb-3">
              Recommendation Confidence
            </h2>
            <div className="flex flex-wrap gap-3">
              {plan.net_expected_gain > 5 ? (
                <SensitivityBadge level="strong" />
              ) : plan.net_expected_gain > 1 ? (
                <SensitivityBadge level="moderate" />
              ) : (
                <SensitivityBadge level="volatile" />
              )}
              <span className="text-sm text-[var(--muted-foreground)]">
                {plan.net_expected_gain > 5
                  ? "High confidence - strong expected returns over the planning horizon."
                  : plan.net_expected_gain > 1
                  ? "Moderate confidence - transfers offer marginal improvement."
                  : "Low confidence - small margins; consider holding transfers."}
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Chip strategy results */}
      {chips && !chipStrategy.isPending && (
        <div className="space-y-4">
          <h2 className="text-xl font-bold">Chip Strategy</h2>

          {/* Chip cards */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            {chips.recommendations.map((rec) => {
              const info = chipInfo[rec.chip];
              const Icon = info.icon;
              return (
                <div
                  key={rec.chip}
                  className={`rounded-lg border p-5 ${info.color} transition-shadow hover:shadow-lg`}
                >
                  <div className="flex items-center gap-3 mb-3">
                    <Icon className="h-6 w-6" />
                    <div>
                      <h3 className="font-semibold text-lg">{info.label}</h3>
                      <p className="text-xs opacity-70">{info.description}</p>
                    </div>
                  </div>

                  <div className="space-y-2">
                    <div className="flex items-center justify-between text-sm">
                      <span className="opacity-70">Recommended GW</span>
                      <span className="font-bold">
                        GW {rec.recommended_gameweek}
                      </span>
                    </div>
                    <div className="flex items-center justify-between text-sm">
                      <span className="opacity-70">Expected Gain</span>
                      <span className="font-bold text-emerald-400">
                        +{rec.expected_gain.toFixed(1)} pts
                      </span>
                    </div>
                    <div className="flex items-center justify-between text-sm">
                      <span className="opacity-70">Confidence</span>
                      <span className="font-bold">
                        {(rec.confidence * 100).toFixed(0)}%
                      </span>
                    </div>
                  </div>

                  <p className="mt-3 text-xs opacity-70 leading-relaxed">
                    {rec.reasoning}
                  </p>

                  {/* Sensitivity badge */}
                  <div className="mt-3">
                    <SensitivityBadge
                      level={
                        rec.confidence > 0.7
                          ? "strong"
                          : rec.confidence > 0.4
                          ? "moderate"
                          : "volatile"
                      }
                    />
                  </div>
                </div>
              );
            })}
          </div>

          {/* Chips available / used */}
          {(chips.chips_available.length > 0 || chips.chips_used.length > 0) && (
            <div className="fpl-card">
              <h3 className="font-semibold mb-3">Chip Status</h3>
              <div className="flex flex-wrap gap-2">
                {chips.chips_available.map((c) => (
                  <span
                    key={c}
                    className="fpl-badge bg-emerald-500/10 text-emerald-400 border border-emerald-500/30"
                  >
                    {chipInfo[c]?.label ?? c} - Available
                  </span>
                ))}
                {chips.chips_used.map((c) => (
                  <span
                    key={c}
                    className="fpl-badge bg-[var(--muted)] text-[var(--muted-foreground)] border border-[var(--border)] line-through"
                  >
                    {chipInfo[c]?.label ?? c} - Used
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Empty state */}
      {!plan &&
        !chips &&
        !transferPlan.isPending &&
        !chipStrategy.isPending &&
        !transferPlan.isError &&
        !chipStrategy.isError && (
          <div className="fpl-card flex flex-col items-center justify-center py-16 text-center">
            <ArrowLeftRight className="h-12 w-12 text-[var(--muted-foreground)]" />
            <h3 className="mt-4 text-lg font-semibold">
              Plan Your Transfers
            </h3>
            <p className="mt-2 text-sm text-[var(--muted-foreground)] max-w-md">
              Set your planning parameters above and click &quot;Plan
              Transfers&quot; to get AI-powered transfer recommendations, or
              &quot;Chip Strategy&quot; to find the optimal time to use your
              chips.
            </p>
          </div>
        )}
    </div>
  );
}
