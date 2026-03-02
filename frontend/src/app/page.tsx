"use client";

import Link from "next/link";
import {
  Calendar,
  TrendingUp,
  DollarSign,
  Zap,
  Cpu,
  ArrowLeftRight,
  BarChart3,
  Users,
  RefreshCw,
} from "lucide-react";
import StatsCard from "@/components/StatsCard";
import PlayerCard from "@/components/PlayerCard";
import { usePlayers, useGameweeks, useRefreshData } from "@/hooks/useApi";
import type { Player, Gameweek } from "@/types";

export default function DashboardPage() {
  const {
    data: players,
    isLoading: playersLoading,
    error: playersError,
  } = usePlayers();
  const {
    data: gameweeks,
    isLoading: gwLoading,
  } = useGameweeks();
  const refreshData = useRefreshData();

  // Derive current gameweek
  const currentGw: Gameweek | undefined = gameweeks?.find((gw) => gw.is_current);
  const nextGw: Gameweek | undefined = gameweeks?.find((gw) => gw.is_next);

  // Derive top players (sorted by form / predicted points)
  const topPlayers: Player[] = players
    ? [...players]
        .sort((a, b) => (b.predicted_points ?? b.form) - (a.predicted_points ?? a.form))
        .slice(0, 6)
    : [];

  // Average points from current GW
  const avgScore = currentGw?.average_entry_score ?? "--";
  const highScore = currentGw?.highest_score ?? "--";

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Hero / Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-3xl font-bold fpl-gradient-text">Dashboard</h1>
          <p className="mt-1 text-[var(--muted-foreground)]">
            Your FPL command center - predictions, optimization, and strategy
            at a glance
          </p>
        </div>
        <button
          onClick={() => refreshData.mutate()}
          disabled={refreshData.isPending}
          className="fpl-button-outline gap-2 self-start"
        >
          <RefreshCw
            className={`h-4 w-4 ${refreshData.isPending ? "animate-spin" : ""}`}
          />
          {refreshData.isPending ? "Refreshing..." : "Refresh Data"}
        </button>
      </div>

      {/* Quick stats row */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatsCard
          icon={Calendar}
          label="Current Gameweek"
          value={currentGw ? `GW ${currentGw.id}` : "--"}
          subtext={
            nextGw
              ? `Next: ${new Date(nextGw.deadline_time).toLocaleDateString("en-GB", { weekday: "short", month: "short", day: "numeric" })}`
              : "Loading..."
          }
          accentColor="primary"
          loading={gwLoading}
        />
        <StatsCard
          icon={TrendingUp}
          label="Average Score"
          value={avgScore}
          subtext="This gameweek"
          accentColor="accent"
          loading={gwLoading}
        />
        <StatsCard
          icon={Zap}
          label="Highest Score"
          value={highScore}
          subtext="This gameweek"
          accentColor="pink"
          loading={gwLoading}
        />
        <StatsCard
          icon={DollarSign}
          label="Players Loaded"
          value={players ? players.length.toLocaleString() : "--"}
          subtext={playersError ? "Backend offline" : "In database"}
          accentColor="default"
          loading={playersLoading}
        />
      </div>

      {/* Main content grid */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Top picks */}
        <div className="fpl-card lg:col-span-2">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-semibold">Top Predicted Picks</h2>
              <p className="mt-1 text-sm text-[var(--muted-foreground)]">
                Highest predicted point scorers for the next gameweek
              </p>
            </div>
            <Link
              href="/players"
              className="text-sm text-[var(--primary)] hover:underline"
            >
              View all
            </Link>
          </div>

          {playersLoading ? (
            <div className="mt-4 space-y-3">
              {[...Array(4)].map((_, i) => (
                <div key={i} className="skeleton h-12 w-full" />
              ))}
            </div>
          ) : playersError ? (
            <div className="mt-4 rounded-md bg-red-500/10 border border-red-500/20 p-4 text-sm text-red-400">
              Could not load players. Make sure the backend is running.
            </div>
          ) : (
            <div className="mt-4 grid grid-cols-1 gap-2 sm:grid-cols-2">
              {topPlayers.map((player) => (
                <PlayerCard
                  key={player.id}
                  name={player.web_name}
                  team={player.team_short_name ?? `Team ${player.team_id}`}
                  position={player.position}
                  price={player.now_cost}
                  predictedPoints={player.predicted_points ?? player.form}
                  compact
                />
              ))}
            </div>
          )}
        </div>

        {/* Quick actions */}
        <div className="fpl-card">
          <h2 className="text-lg font-semibold">Quick Actions</h2>
          <p className="mt-1 text-sm text-[var(--muted-foreground)]">
            Jump to key features
          </p>
          <div className="mt-4 space-y-3">
            <Link
              href="/optimizer"
              className="fpl-button-primary w-full justify-start gap-3"
            >
              <Cpu className="h-4 w-4" />
              Optimize Squad
            </Link>
            <Link
              href="/predictions"
              className="fpl-button-secondary w-full justify-start gap-3"
            >
              <BarChart3 className="h-4 w-4" />
              View Predictions
            </Link>
            <Link
              href="/transfers"
              className="fpl-button-secondary w-full justify-start gap-3"
            >
              <ArrowLeftRight className="h-4 w-4" />
              Plan Transfers
            </Link>
            <Link
              href="/players"
              className="fpl-button-secondary w-full justify-start gap-3"
            >
              <Users className="h-4 w-4" />
              Explore Players
            </Link>
          </div>
        </div>
      </div>

      {/* Upcoming fixtures teaser */}
      <div className="fpl-card">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold">Upcoming Fixtures</h2>
            <p className="mt-1 text-sm text-[var(--muted-foreground)]">
              Fixture difficulty ratings for the next 5 gameweeks
            </p>
          </div>
        </div>
        <div className="mt-4 text-sm text-[var(--muted-foreground)]">
          {playersError
            ? "Connect to the backend to see fixture data."
            : "Select a player or team from the Players page to view their fixture schedule."}
        </div>
      </div>
    </div>
  );
}
