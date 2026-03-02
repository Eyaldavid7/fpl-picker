/**
 * UpcomingFixtures - Fixture Difficulty Ticker table.
 *
 * Shows each squad player's next 5 gameweek opponents in a compact
 * colour-coded grid, grouped by position (GKP, DEF, MID, FWD).
 */

import FDRBadge, { FDR_COLORS } from "@/components/FDRBadge";
import type {
  SquadFixturesResponse,
  SquadPlayer,
  PlayerFixture,
  Position,
} from "@/types";

interface UpcomingFixturesProps {
  /** Response from the squad-fixtures endpoint */
  fixturesData: SquadFixturesResponse | undefined;
  /** Current squad players */
  squad: SquadPlayer[];
  /** Whether the data is currently loading */
  loading: boolean;
}

const POSITION_ORDER: Position[] = ["GKP", "DEF", "MID", "FWD"];

const POSITION_LABEL: Record<Position, string> = {
  GKP: "Goalkeepers",
  DEF: "Defenders",
  MID: "Midfielders",
  FWD: "Forwards",
};

const FDR_LABELS: Record<number, string> = {
  1: "Very Easy",
  2: "Easy",
  3: "Medium",
  4: "Hard",
  5: "Very Hard",
};

/**
 * Derive the next N unique gameweek numbers from the fixture data so we can
 * use them as column headers. Falls back to currentGw+1..currentGw+5.
 */
function getGameweekColumns(
  fixturesData: SquadFixturesResponse | undefined,
  count: number = 5
): number[] {
  if (!fixturesData) return [];

  const gwSet = new Set<number>();
  for (const fixtures of Object.values(fixturesData.fixtures)) {
    for (const f of fixtures) {
      gwSet.add(f.gameweek);
    }
  }

  if (gwSet.size === 0) {
    const base = fixturesData.current_gameweek ?? 0;
    return Array.from({ length: count }, (_, i) => base + 1 + i);
  }

  return Array.from(gwSet)
    .sort((a, b) => a - b)
    .slice(0, count);
}

/**
 * Group the squad players by position in the standard order.
 */
function groupByPosition(squad: SquadPlayer[]): Record<Position, SquadPlayer[]> {
  const groups: Record<Position, SquadPlayer[]> = {
    GKP: [],
    DEF: [],
    MID: [],
    FWD: [],
  };
  for (const p of squad) {
    groups[p.position]?.push(p);
  }
  // Sort within each group by predicted points descending
  for (const pos of POSITION_ORDER) {
    groups[pos].sort((a, b) => b.predicted_points - a.predicted_points);
  }
  return groups;
}

export default function UpcomingFixtures({
  fixturesData,
  squad,
  loading,
}: UpcomingFixturesProps) {
  const gwColumns = getGameweekColumns(fixturesData);
  const groups = groupByPosition(squad);

  // --- Loading skeleton ---
  if (loading) {
    return (
      <div className="fpl-card animate-fade-in">
        <h2 className="text-lg font-semibold mb-4">Upcoming Fixtures</h2>
        <div className="overflow-x-auto">
          <table className="fpl-table">
            <thead>
              <tr>
                <th className="w-36">Player</th>
                {Array.from({ length: 5 }).map((_, i) => (
                  <th key={i} className="text-center w-20">
                    <div className="skeleton h-3 w-10 mx-auto" />
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {Array.from({ length: 10 }).map((_, rowIdx) => (
                <tr key={rowIdx}>
                  <td>
                    <div className="skeleton h-4 w-24" />
                  </td>
                  {Array.from({ length: 5 }).map((_, colIdx) => (
                    <td key={colIdx} className="text-center">
                      <div className="skeleton h-5 w-14 mx-auto rounded-md" />
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    );
  }

  // --- No data ---
  if (!fixturesData || gwColumns.length === 0) {
    return null;
  }

  return (
    <div className="fpl-card animate-fade-in">
      <h2 className="text-lg font-semibold mb-4">Upcoming Fixtures</h2>

      <div className="overflow-x-auto">
        <table className="fpl-table">
          <thead>
            <tr>
              <th className="w-36">Player</th>
              {gwColumns.map((gw) => (
                <th key={gw} className="text-center w-20">
                  GW{gw}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {POSITION_ORDER.map((pos) => {
              const players = groups[pos];
              if (players.length === 0) return null;

              return (
                <PositionGroup
                  key={pos}
                  position={pos}
                  players={players}
                  gwColumns={gwColumns}
                  fixturesData={fixturesData}
                />
              );
            })}
          </tbody>
        </table>
      </div>

      {/* FDR Legend */}
      <div className="mt-4 flex flex-wrap items-center gap-3 text-xs text-[var(--muted-foreground)]">
        <span className="font-medium">FDR:</span>
        {([1, 2, 3, 4, 5] as const).map((level) => (
          <span key={level} className="flex items-center gap-1.5">
            <span
              className={`${FDR_COLORS[level]} inline-block h-3 w-3 rounded-sm`}
            />
            {level} - {FDR_LABELS[level]}
          </span>
        ))}
      </div>
    </div>
  );
}

// --- Sub-component: Position group rows ---

interface PositionGroupProps {
  position: Position;
  players: SquadPlayer[];
  gwColumns: number[];
  fixturesData: SquadFixturesResponse;
}

function PositionGroup({
  position,
  players,
  gwColumns,
  fixturesData,
}: PositionGroupProps) {
  return (
    <>
      {/* Position header row */}
      <tr className="bg-[var(--muted)]/30">
        <td colSpan={gwColumns.length + 1} className="py-1.5 px-4">
          <span className={`fpl-badge fpl-badge-${position.toLowerCase()} text-xs`}>
            {position}
          </span>
          <span className="ml-2 text-xs text-[var(--muted-foreground)]">
            {POSITION_LABEL[position]}
          </span>
        </td>
      </tr>

      {/* Player rows */}
      {players.map((player) => {
        const playerFixtures: PlayerFixture[] =
          fixturesData.fixtures[String(player.player_id)] ?? [];

        // Index fixtures by gameweek for O(1) lookup
        const fixtureByGw: Record<number, PlayerFixture> = {};
        for (const f of playerFixtures) {
          fixtureByGw[f.gameweek] = f;
        }

        return (
          <tr key={player.player_id}>
            <td className="font-medium text-sm whitespace-nowrap">
              {player.web_name}
            </td>
            {gwColumns.map((gw) => {
              const fixture = fixtureByGw[gw];
              return (
                <td key={gw} className="text-center px-1">
                  {fixture ? (
                    <FDRBadge
                      difficulty={fixture.difficulty}
                      opponentShortName={fixture.opponent_short_name}
                      isHome={fixture.is_home}
                      compact
                    />
                  ) : (
                    <span className="text-[var(--muted-foreground)] text-xs">
                      --
                    </span>
                  )}
                </td>
              );
            })}
          </tr>
        );
      })}
    </>
  );
}
