"use client";

import { useState, useMemo } from "react";
import {
  Search,
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
  Users,
  Loader2,
  AlertCircle,
} from "lucide-react";
import { usePlayers, useTeams } from "@/hooks/useApi";
import type { Player, Position, SortDirection } from "@/types";

type SortColumn =
  | "web_name"
  | "position"
  | "now_cost"
  | "total_points"
  | "form"
  | "predicted_points"
  | "goals_scored"
  | "assists"
  | "selected_by_percent"
  | "expected_goals"
  | "expected_assists";

interface SortState {
  column: SortColumn;
  direction: SortDirection;
}

const columns: { key: SortColumn; label: string; shortLabel?: string }[] = [
  { key: "web_name", label: "Name" },
  { key: "position", label: "Pos" },
  { key: "now_cost", label: "Price" },
  { key: "total_points", label: "Points", shortLabel: "Pts" },
  { key: "form", label: "Form" },
  { key: "predicted_points", label: "Predicted", shortLabel: "Pred" },
  { key: "expected_goals", label: "xG" },
  { key: "expected_assists", label: "xA" },
  { key: "goals_scored", label: "Goals", shortLabel: "G" },
  { key: "assists", label: "Assists", shortLabel: "A" },
  { key: "selected_by_percent", label: "Ownership", shortLabel: "Own%" },
];

const positionFilters: { value: Position | "ALL"; label: string }[] = [
  { value: "ALL", label: "All Positions" },
  { value: "GKP", label: "Goalkeepers" },
  { value: "DEF", label: "Defenders" },
  { value: "MID", label: "Midfielders" },
  { value: "FWD", label: "Forwards" },
];

export default function PlayersPage() {
  const { data: players, isLoading, error } = usePlayers();
  const { data: teams } = useTeams();

  const [search, setSearch] = useState("");
  const [positionFilter, setPositionFilter] = useState<Position | "ALL">("ALL");
  const [teamFilter, setTeamFilter] = useState<number | null>(null);
  const [sort, setSort] = useState<SortState>({
    column: "total_points",
    direction: "desc",
  });

  const teamMap = useMemo(() => {
    const map = new Map<number, string>();
    teams?.forEach((t) => map.set(t.id, t.short_name));
    return map;
  }, [teams]);

  const handleSort = (column: SortColumn) => {
    setSort((prev) =>
      prev.column === column
        ? { column, direction: prev.direction === "asc" ? "desc" : "asc" }
        : { column, direction: "desc" }
    );
  };

  // Filter and sort players
  const filteredPlayers = useMemo(() => {
    if (!players) return [];

    let list = [...players];

    // Search
    if (search) {
      const q = search.toLowerCase();
      list = list.filter(
        (p) =>
          p.web_name.toLowerCase().includes(q) ||
          p.first_name.toLowerCase().includes(q) ||
          p.second_name.toLowerCase().includes(q)
      );
    }

    // Position filter
    if (positionFilter !== "ALL") {
      list = list.filter((p) => p.position === positionFilter);
    }

    // Team filter
    if (teamFilter !== null) {
      list = list.filter((p) => p.team_id === teamFilter);
    }

    // Sort
    list.sort((a, b) => {
      const col = sort.column;
      let aVal: string | number = a[col] as string | number;
      let bVal: string | number = b[col] as string | number;

      // Handle undefined predicted/expected values
      if (aVal === undefined || aVal === null) aVal = 0;
      if (bVal === undefined || bVal === null) bVal = 0;

      if (typeof aVal === "string" && typeof bVal === "string") {
        return sort.direction === "asc"
          ? aVal.localeCompare(bVal)
          : bVal.localeCompare(aVal);
      }

      return sort.direction === "asc"
        ? (aVal as number) - (bVal as number)
        : (bVal as number) - (aVal as number);
    });

    return list;
  }, [players, search, positionFilter, teamFilter, sort]);

  const SortIcon = ({ column }: { column: SortColumn }) => {
    if (sort.column !== column)
      return <ArrowUpDown className="h-3 w-3 opacity-40" />;
    return sort.direction === "asc" ? (
      <ArrowUp className="h-3 w-3 text-[var(--primary)]" />
    ) : (
      <ArrowDown className="h-3 w-3 text-[var(--primary)]" />
    );
  };

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Page header */}
      <div>
        <h1 className="text-3xl font-bold fpl-gradient-text">
          Player Explorer
        </h1>
        <p className="mt-1 text-[var(--muted-foreground)]">
          Browse, search, and compare all Premier League players
        </p>
      </div>

      {/* Filters bar */}
      <div className="fpl-card">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
          {/* Search */}
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--muted-foreground)]" />
            <input
              type="text"
              placeholder="Search players..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="fpl-input pl-10"
            />
          </div>

          {/* Position filter */}
          <select
            value={positionFilter}
            onChange={(e) =>
              setPositionFilter(e.target.value as Position | "ALL")
            }
            className="fpl-select sm:w-44"
          >
            {positionFilters.map((pf) => (
              <option key={pf.value} value={pf.value}>
                {pf.label}
              </option>
            ))}
          </select>

          {/* Team filter */}
          <select
            value={teamFilter ?? ""}
            onChange={(e) =>
              setTeamFilter(e.target.value ? Number(e.target.value) : null)
            }
            className="fpl-select sm:w-44"
          >
            <option value="">All Teams</option>
            {teams?.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name}
              </option>
            ))}
          </select>
        </div>

        {/* Results count */}
        <div className="mt-3 text-xs text-[var(--muted-foreground)]">
          {isLoading
            ? "Loading..."
            : `${filteredPlayers.length} players found`}
        </div>
      </div>

      {/* Loading */}
      {isLoading && (
        <div className="fpl-card flex items-center justify-center py-16">
          <Loader2 className="h-8 w-8 animate-spin text-[var(--primary)]" />
          <span className="ml-3 text-[var(--muted-foreground)]">
            Loading players...
          </span>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="fpl-card border-red-500/30 bg-red-500/5">
          <div className="flex items-center gap-3 text-red-400">
            <AlertCircle className="h-5 w-5 shrink-0" />
            <div>
              <p className="font-semibold">Failed to load players</p>
              <p className="text-sm mt-1 text-red-400/80">
                Make sure the backend is running and accessible.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Table */}
      {!isLoading && !error && (
        <div className="fpl-card overflow-hidden p-0">
          <div className="overflow-x-auto">
            <table className="fpl-table">
              <thead>
                <tr>
                  <th className="sticky left-0 bg-[var(--card)] z-10 w-8 text-center">
                    #
                  </th>
                  {columns.map((col) => (
                    <th
                      key={col.key}
                      onClick={() => handleSort(col.key)}
                      className={
                        col.key === "web_name"
                          ? "sticky left-8 bg-[var(--card)] z-10"
                          : ""
                      }
                    >
                      <div className="flex items-center gap-1">
                        <span className="hidden sm:inline">{col.label}</span>
                        <span className="sm:hidden">
                          {col.shortLabel || col.label}
                        </span>
                        <SortIcon column={col.key} />
                      </div>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filteredPlayers.slice(0, 100).map((player, idx) => (
                  <tr key={player.id}>
                    <td className="sticky left-0 bg-[var(--card)] z-10 text-center text-xs text-[var(--muted-foreground)]">
                      {idx + 1}
                    </td>
                    <td className="sticky left-8 bg-[var(--card)] z-10 font-medium">
                      <div className="flex items-center gap-2">
                        <span>{player.web_name}</span>
                        {teamMap.get(player.team_id) && (
                          <span className="text-xs text-[var(--muted-foreground)]">
                            {teamMap.get(player.team_id)}
                          </span>
                        )}
                      </div>
                    </td>
                    <td>
                      <span
                        className={`fpl-badge fpl-badge-${player.position.toLowerCase()}`}
                      >
                        {player.position}
                      </span>
                    </td>
                    <td>
                      {(player.now_cost / 10).toFixed(1)}
                    </td>
                    <td className="font-semibold">{player.total_points}</td>
                    <td>{Number(player.form).toFixed(1)}</td>
                    <td className="text-[var(--primary)] font-semibold">
                      {player.predicted_points?.toFixed(1) ?? "-"}
                    </td>
                    <td>{player.expected_goals?.toFixed(2) ?? "-"}</td>
                    <td>{player.expected_assists?.toFixed(2) ?? "-"}</td>
                    <td>{player.goals_scored}</td>
                    <td>{player.assists}</td>
                    <td>
                      {Number(player.selected_by_percent).toFixed(1)}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {filteredPlayers.length > 100 && (
            <div className="border-t border-[var(--border)] px-4 py-3 text-center text-xs text-[var(--muted-foreground)]">
              Showing 100 of {filteredPlayers.length} players. Use search and
              filters to narrow results.
            </div>
          )}

          {filteredPlayers.length === 0 && !isLoading && (
            <div className="flex flex-col items-center justify-center py-12">
              <Users className="h-10 w-10 text-[var(--muted-foreground)]" />
              <p className="mt-3 text-sm text-[var(--muted-foreground)]">
                No players match your filters
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
