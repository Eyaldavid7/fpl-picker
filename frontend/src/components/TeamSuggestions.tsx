"use client";

import { useState } from "react";
import {
  ArrowRight,
  Repeat2,
  TrendingUp,
  Lightbulb,
  Loader2,
  CheckCircle2,
  ArrowDownUp,
} from "lucide-react";
import type {
  SubstituteResponse,
  SubstituteSuggestion,
  TransferResponse,
  TransferSuggestion,
  Position,
} from "@/types";

// ---------- Props ----------

interface TeamSuggestionsProps {
  substituteSuggestions: SubstituteResponse | undefined;
  transferSuggestions: TransferResponse | undefined;
  subsLoading: boolean;
  transfersLoading: boolean;
  onFetchTransfers: (budgetRemaining: number, freeTransfers: number) => void;
}

// ---------- Helpers ----------

type Tab = "substitutions" | "transfers";

const positionBadgeClass: Record<Position, string> = {
  GKP: "fpl-badge fpl-badge-gkp",
  DEF: "fpl-badge fpl-badge-def",
  MID: "fpl-badge fpl-badge-mid",
  FWD: "fpl-badge fpl-badge-fwd",
};

function formatPoints(pts: number): string {
  return pts.toFixed(1);
}

function formatPrice(price: number): string {
  return `${(price / 10).toFixed(1)}m`;
}

// ---------- Skeleton Loaders ----------

function SkeletonSubCard() {
  return (
    <div className="fpl-card animate-fade-in">
      <div className="flex items-center gap-4">
        {/* Left player */}
        <div className="flex-1 space-y-2">
          <div className="skeleton h-4 w-10 rounded-full" />
          <div className="skeleton h-5 w-28" />
          <div className="skeleton h-3 w-16" />
        </div>
        {/* Center arrow */}
        <div className="flex flex-col items-center gap-1 shrink-0">
          <div className="skeleton h-6 w-6 rounded-full" />
          <div className="skeleton h-4 w-14 rounded-full" />
        </div>
        {/* Right player */}
        <div className="flex-1 space-y-2 text-right">
          <div className="skeleton h-4 w-10 rounded-full ml-auto" />
          <div className="skeleton h-5 w-28 ml-auto" />
          <div className="skeleton h-3 w-16 ml-auto" />
        </div>
      </div>
      <div className="skeleton h-3 w-full mt-3" />
    </div>
  );
}

function SkeletonTransferCard() {
  return (
    <div className="fpl-card animate-fade-in">
      <div className="flex items-center gap-3">
        {/* OUT side */}
        <div className="flex-1 rounded-lg border border-red-500/20 bg-red-500/5 p-3 space-y-2">
          <div className="skeleton h-3 w-8" />
          <div className="skeleton h-4 w-10 rounded-full" />
          <div className="skeleton h-5 w-24" />
          <div className="flex gap-3">
            <div className="skeleton h-3 w-12" />
            <div className="skeleton h-3 w-14" />
          </div>
        </div>
        {/* Center */}
        <div className="shrink-0 flex flex-col items-center gap-1">
          <div className="skeleton h-6 w-6 rounded-full" />
          <div className="skeleton h-4 w-14 rounded-full" />
          <div className="skeleton h-3 w-12" />
        </div>
        {/* IN side */}
        <div className="flex-1 rounded-lg border border-green-500/20 bg-green-500/5 p-3 space-y-2">
          <div className="skeleton h-3 w-8" />
          <div className="skeleton h-4 w-10 rounded-full" />
          <div className="skeleton h-5 w-24" />
          <div className="flex gap-3">
            <div className="skeleton h-3 w-12" />
            <div className="skeleton h-3 w-14" />
          </div>
        </div>
      </div>
      <div className="skeleton h-3 w-full mt-3" />
    </div>
  );
}

// ---------- Substitution Card ----------

function SubstitutionCard({ suggestion }: { suggestion: SubstituteSuggestion }) {
  return (
    <div className="fpl-card hover-lift">
      <div className="flex items-center gap-4">
        {/* Bench player (IN) */}
        <div className="flex-1 min-w-0">
          <span className={positionBadgeClass[suggestion.bench_player_position]}>
            {suggestion.bench_player_position}
          </span>
          <p className="mt-1.5 font-semibold text-[var(--foreground)] truncate">
            {suggestion.bench_player_name}
          </p>
          <p className="text-xs text-[var(--muted-foreground)]">
            {formatPoints(suggestion.bench_predicted_points)} pts predicted
          </p>
        </div>

        {/* Arrow + gain badge */}
        <div className="flex flex-col items-center gap-1 shrink-0">
          <ArrowRight className="h-5 w-5 text-[var(--primary)]" />
          <span className="inline-flex items-center gap-0.5 rounded-full bg-green-500/15 border border-green-500/30 px-2 py-0.5 text-xs font-bold text-green-400">
            <TrendingUp className="h-3 w-3" />
            +{formatPoints(suggestion.point_gain)} pts
          </span>
        </div>

        {/* Starter (OUT) */}
        <div className="flex-1 min-w-0 text-right">
          <span className={positionBadgeClass[suggestion.starter_player_position]}>
            {suggestion.starter_player_position}
          </span>
          <p className="mt-1.5 font-semibold text-[var(--foreground)] truncate">
            {suggestion.starter_player_name}
          </p>
          <p className="text-xs text-[var(--muted-foreground)]">
            {formatPoints(suggestion.starter_predicted_points)} pts predicted
          </p>
        </div>
      </div>

      {/* Reason */}
      <p className="mt-3 text-xs text-[var(--muted-foreground)] border-t border-[var(--border)] pt-3">
        {suggestion.reason}
      </p>
    </div>
  );
}

// ---------- Transfer Card ----------

function TransferCard({ suggestion }: { suggestion: TransferSuggestion }) {
  const costChange = suggestion.net_cost;
  const costPositive = costChange > 0;
  const costNeutral = costChange === 0;

  return (
    <div className="fpl-card hover-lift">
      <div className="flex items-center gap-3">
        {/* OUT section */}
        <div className="flex-1 min-w-0 rounded-lg border border-red-500/20 bg-red-500/5 p-3">
          <p className="text-[10px] font-bold uppercase tracking-wider text-red-400 mb-1.5">
            Out
          </p>
          <span className={positionBadgeClass[suggestion.player_out_position]}>
            {suggestion.player_out_position}
          </span>
          <p className="mt-1.5 font-semibold text-[var(--foreground)] truncate">
            {suggestion.player_out_name}
          </p>
          <div className="flex items-center gap-3 mt-1 text-xs text-[var(--muted-foreground)]">
            <span>{formatPrice(suggestion.player_out_price)}</span>
            <span>{formatPoints(suggestion.player_out_predicted)} pts</span>
          </div>
        </div>

        {/* Center arrow + badges */}
        <div className="flex flex-col items-center gap-1.5 shrink-0">
          <ArrowDownUp className="h-5 w-5 text-[var(--accent)]" />
          <span className="inline-flex items-center gap-0.5 rounded-full bg-green-500/15 border border-green-500/30 px-2 py-0.5 text-xs font-bold text-green-400">
            <TrendingUp className="h-3 w-3" />
            +{formatPoints(suggestion.point_gain)}
          </span>
          <span
            className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-semibold ${
              costNeutral
                ? "bg-[var(--muted)]/50 text-[var(--muted-foreground)] border border-[var(--border)]"
                : costPositive
                ? "bg-red-500/10 text-red-400 border border-red-500/30"
                : "bg-green-500/10 text-green-400 border border-green-500/30"
            }`}
          >
            {costNeutral
              ? "0.0m"
              : costPositive
              ? `+${formatPrice(costChange)}`
              : `-${formatPrice(Math.abs(costChange))}`}
          </span>
        </div>

        {/* IN section */}
        <div className="flex-1 min-w-0 rounded-lg border border-green-500/20 bg-green-500/5 p-3">
          <p className="text-[10px] font-bold uppercase tracking-wider text-green-400 mb-1.5">
            In
          </p>
          <span className={positionBadgeClass[suggestion.player_in_position]}>
            {suggestion.player_in_position}
          </span>
          <p className="mt-1.5 font-semibold text-[var(--foreground)] truncate">
            {suggestion.player_in_name}
          </p>
          <p className="text-[10px] text-[var(--muted-foreground)] mt-0.5">
            {suggestion.player_in_team}
          </p>
          <div className="flex items-center gap-3 mt-1 text-xs text-[var(--muted-foreground)]">
            <span>{formatPrice(suggestion.player_in_price)}</span>
            <span>{formatPoints(suggestion.player_in_predicted)} pts</span>
          </div>
        </div>
      </div>

      {/* Reason */}
      <p className="mt-3 text-xs text-[var(--muted-foreground)] border-t border-[var(--border)] pt-3">
        {suggestion.reason}
      </p>
    </div>
  );
}

// ---------- Main Component ----------

export default function TeamSuggestions({
  substituteSuggestions,
  transferSuggestions,
  subsLoading,
  transfersLoading,
  onFetchTransfers,
}: TeamSuggestionsProps) {
  const [activeTab, setActiveTab] = useState<Tab>("substitutions");
  const [budgetRemaining, setBudgetRemaining] = useState(0);
  const [freeTransfers, setFreeTransfers] = useState(1);

  const tabs: { key: Tab; label: string; icon: React.ReactNode }[] = [
    {
      key: "substitutions",
      label: "Substitutions",
      icon: <Repeat2 className="h-4 w-4" />,
    },
    {
      key: "transfers",
      label: "Transfers",
      icon: <ArrowDownUp className="h-4 w-4" />,
    },
  ];

  return (
    <div className="fpl-card animate-fade-in">
      {/* Header */}
      <div className="flex items-center gap-2 mb-5">
        <Lightbulb className="h-5 w-5 text-[var(--primary)]" />
        <h2 className="text-lg font-semibold">Team Suggestions</h2>
      </div>

      {/* Tab bar */}
      <div className="flex gap-1 p-1 rounded-lg bg-[var(--background)] border border-[var(--border)] mb-6">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`flex-1 flex items-center justify-center gap-2 rounded-md px-4 py-2.5 text-sm font-medium transition-all duration-200 ${
              activeTab === tab.key
                ? "bg-[var(--primary)] text-[var(--primary-foreground)] shadow-[0_0_12px_rgba(0,255,135,0.2)]"
                : "text-[var(--muted-foreground)] hover:text-[var(--foreground)] hover:bg-[var(--muted)]/40"
            }`}
          >
            {tab.icon}
            {tab.label}
          </button>
        ))}
      </div>

      {/* ===== SUBSTITUTIONS TAB ===== */}
      {activeTab === "substitutions" && (
        <div className="space-y-4 animate-fade-in">
          {/* Loading skeleton */}
          {subsLoading && (
            <div className="space-y-4">
              {[1, 2, 3].map((i) => (
                <SkeletonSubCard key={i} />
              ))}
            </div>
          )}

          {/* No suggestions */}
          {!subsLoading &&
            substituteSuggestions &&
            substituteSuggestions.suggestions.length === 0 && (
              <div className="flex flex-col items-center py-10 text-center">
                <CheckCircle2 className="h-10 w-10 text-green-400 mb-3" />
                <p className="text-sm font-medium text-[var(--foreground)]">
                  Your starting XI looks optimal
                </p>
                <p className="text-xs text-[var(--muted-foreground)] mt-1">
                  No changes recommended - your bench players are not predicted
                  to outscore any starters.
                </p>
              </div>
            )}

          {/* Suggestion cards */}
          {!subsLoading &&
            substituteSuggestions &&
            substituteSuggestions.suggestions.length > 0 && (
              <div className="space-y-3 stagger-children">
                <p className="text-xs text-[var(--muted-foreground)] mb-2">
                  {substituteSuggestions.suggestions.length} substitution
                  {substituteSuggestions.suggestions.length !== 1 && "s"}{" "}
                  recommended
                </p>
                {substituteSuggestions.suggestions.map((s, idx) => (
                  <SubstitutionCard key={idx} suggestion={s} />
                ))}
              </div>
            )}

          {/* Waiting state (no data, no loading) */}
          {!subsLoading && !substituteSuggestions && (
            <div className="flex flex-col items-center py-10 text-center">
              <Repeat2 className="h-10 w-10 text-[var(--muted-foreground)] mb-3" />
              <p className="text-sm text-[var(--muted-foreground)]">
                Substitution suggestions will appear once your squad is loaded.
              </p>
            </div>
          )}
        </div>
      )}

      {/* ===== TRANSFERS TAB ===== */}
      {activeTab === "transfers" && (
        <div className="space-y-5 animate-fade-in">
          {/* Controls row */}
          <div className="rounded-lg border border-[var(--border)] bg-[var(--background)] p-4">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-end">
              {/* Budget remaining */}
              <div className="flex-1">
                <label className="block text-xs font-medium text-[var(--muted-foreground)] mb-1.5">
                  Budget Remaining (millions)
                </label>
                <input
                  type="number"
                  min={0}
                  max={50}
                  step={0.1}
                  value={budgetRemaining}
                  onChange={(e) =>
                    setBudgetRemaining(
                      Math.max(0, parseFloat(e.target.value) || 0)
                    )
                  }
                  className="fpl-input"
                  placeholder="0.0"
                />
              </div>

              {/* Free transfers */}
              <div className="flex-1">
                <label className="block text-xs font-medium text-[var(--muted-foreground)] mb-1.5">
                  Free Transfers
                </label>
                <div className="flex gap-1">
                  {[1, 2, 3, 4, 5].map((n) => (
                    <button
                      key={n}
                      onClick={() => setFreeTransfers(n)}
                      className={`flex-1 rounded-md px-3 py-2 text-sm font-semibold transition-all duration-200 ${
                        freeTransfers === n
                          ? "bg-[var(--primary)] text-[var(--primary-foreground)] shadow-[0_0_10px_rgba(0,255,135,0.2)]"
                          : "border border-[var(--border)] text-[var(--muted-foreground)] hover:text-[var(--foreground)] hover:bg-[var(--muted)]/40"
                      }`}
                    >
                      {n}
                    </button>
                  ))}
                </div>
              </div>

              {/* Fetch button */}
              <div>
                <button
                  onClick={() =>
                    onFetchTransfers(budgetRemaining * 10, freeTransfers)
                  }
                  disabled={transfersLoading}
                  className="fpl-button-primary gap-2 w-full sm:w-auto"
                >
                  {transfersLoading ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Analyzing...
                    </>
                  ) : (
                    <>
                      <TrendingUp className="h-4 w-4" />
                      Get Suggestions
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>

          {/* Loading skeleton */}
          {transfersLoading && (
            <div className="space-y-4">
              {[1, 2, 3].map((i) => (
                <SkeletonTransferCard key={i} />
              ))}
            </div>
          )}

          {/* No suggestions */}
          {!transfersLoading &&
            transferSuggestions &&
            transferSuggestions.suggestions.length === 0 && (
              <div className="flex flex-col items-center py-10 text-center">
                <CheckCircle2 className="h-10 w-10 text-green-400 mb-3" />
                <p className="text-sm font-medium text-[var(--foreground)]">
                  No improvements found
                </p>
                <p className="text-xs text-[var(--muted-foreground)] mt-1">
                  Your squad is well positioned - no transfers would improve
                  predicted points.
                </p>
              </div>
            )}

          {/* Transfer suggestion cards */}
          {!transfersLoading &&
            transferSuggestions &&
            transferSuggestions.suggestions.length > 0 && (
              <div className="space-y-3 stagger-children">
                {transferSuggestions.suggestions.map((s, idx) => (
                  <TransferCard key={idx} suggestion={s} />
                ))}

                {/* Summary bar */}
                <div className="rounded-lg border border-[var(--primary)]/20 bg-[var(--primary)]/5 p-4 mt-4">
                  <div className="flex flex-wrap items-center justify-between gap-4">
                    <div className="flex items-center gap-2">
                      <TrendingUp className="h-4 w-4 text-[var(--primary)]" />
                      <span className="text-sm font-medium text-[var(--foreground)]">
                        Total Point Gain
                      </span>
                      <span className="text-sm font-bold text-green-400">
                        +{formatPoints(transferSuggestions.total_point_gain)} pts
                      </span>
                    </div>

                    <div className="flex items-center gap-4 text-sm">
                      <span className="text-[var(--muted-foreground)]">
                        Net Cost:{" "}
                        <span
                          className={`font-semibold ${
                            transferSuggestions.total_cost_change > 0
                              ? "text-red-400"
                              : transferSuggestions.total_cost_change < 0
                              ? "text-green-400"
                              : "text-[var(--foreground)]"
                          }`}
                        >
                          {transferSuggestions.total_cost_change === 0
                            ? "0.0m"
                            : transferSuggestions.total_cost_change > 0
                            ? `+${formatPrice(transferSuggestions.total_cost_change)}`
                            : `-${formatPrice(Math.abs(transferSuggestions.total_cost_change))}`}
                        </span>
                      </span>
                      <span className="text-[var(--muted-foreground)]">
                        Transfers:{" "}
                        <span className="font-semibold text-[var(--foreground)]">
                          {transferSuggestions.transfers_used}
                        </span>
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            )}

          {/* Waiting state (no data, no loading) */}
          {!transfersLoading && !transferSuggestions && (
            <div className="flex flex-col items-center py-10 text-center">
              <ArrowDownUp className="h-10 w-10 text-[var(--muted-foreground)] mb-3" />
              <p className="text-sm text-[var(--muted-foreground)]">
                Set your budget and free transfers, then click &quot;Get
                Suggestions&quot; to find transfer recommendations.
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
