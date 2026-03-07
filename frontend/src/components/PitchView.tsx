"use client";

import type { SquadPlayer, Position } from "@/types";
import FDRBadge from "@/components/FDRBadge";

interface PitchViewProps {
  players: SquadPlayer[];
  formation: string; // e.g. "4-4-2"
  captainId?: number | null;
  viceCaptainId?: number | null;
}

interface PitchPlayerProps {
  player: SquadPlayer;
  isCaptain: boolean;
  isViceCaptain: boolean;
}

const positionColors: Record<Position, string> = {
  GKP: "#eab308", // yellow
  DEF: "#22c55e", // green
  MID: "#3b82f6", // blue
  FWD: "#ef4444", // red
};

function PitchPlayer({ player, isCaptain, isViceCaptain }: PitchPlayerProps) {
  const color = positionColors[player.position];
  const isUnavailable = player.status === "i" || player.status === "s" || player.status === "u";
  const isDoubtful = isUnavailable || player.status === "d" || (player.chance_of_playing != null && player.chance_of_playing < 100);

  return (
    <div className="flex flex-col items-center gap-1 w-16 sm:w-20" title={player.news || undefined}>
      {/* Jersey icon */}
      <div className="relative">
        <svg
          width="40"
          height="40"
          viewBox="0 0 40 40"
          fill="none"
          className="drop-shadow-md"
        >
          {/* Jersey shape */}
          <path
            d="M12 6 L6 12 L6 18 L10 18 L10 34 L30 34 L30 18 L34 18 L34 12 L28 6 L24 8 L20 6 L16 8 Z"
            fill={color}
            stroke="rgba(255,255,255,0.3)"
            strokeWidth="1"
          />
          {/* Collar */}
          <path
            d="M16 8 L20 6 L24 8"
            fill="none"
            stroke="rgba(255,255,255,0.5)"
            strokeWidth="1"
          />
        </svg>
        {/* Captain badge */}
        {isCaptain && (
          <span className="absolute -top-1 -right-1 flex h-5 w-5 items-center justify-center rounded-full bg-[var(--primary)] text-[9px] font-black text-[var(--primary-foreground)] shadow-md">
            C
          </span>
        )}
        {isViceCaptain && (
          <span className="absolute -top-1 -right-1 flex h-5 w-5 items-center justify-center rounded-full bg-[var(--accent)] text-[9px] font-black text-[var(--accent-foreground)] shadow-md">
            V
          </span>
        )}
        {/* Availability warning badge */}
        {isDoubtful && !isCaptain && !isViceCaptain && (
          <span className={`absolute -top-1 -right-1 flex h-5 w-5 items-center justify-center rounded-full ${isUnavailable ? "bg-red-500" : "bg-yellow-500"} text-[9px] font-black text-black shadow-md`}>
            {isUnavailable ? "X" : "!"}
          </span>
        )}
      </div>

      {/* Player name */}
      <span className="max-w-full truncate rounded bg-[var(--card)]/90 px-1.5 py-0.5 text-[10px] sm:text-xs font-semibold text-white text-center leading-tight">
        {player.web_name}
      </span>

      {/* Predicted points + chance of playing */}
      <span className="rounded bg-[var(--primary)]/20 px-1.5 py-0.5 text-[10px] font-bold text-[var(--primary)]">
        {player.predicted_points.toFixed(1)}
      </span>
      {isDoubtful && (
        <span className={`rounded px-1 py-0.5 text-[9px] font-semibold leading-none ${isUnavailable ? "bg-red-500/20 text-red-400" : "bg-yellow-500/20 text-yellow-400"}`}>
          {isUnavailable ? "Out" : player.chance_of_playing != null ? `${player.chance_of_playing}%` : "doubt"}
        </span>
      )}
      {player.next_opponent && player.fdr != null && (
        <FDRBadge
          difficulty={player.fdr}
          opponentShortName={player.next_opponent.replace(/\s*\([HA]\)\s*$/, "").trim().substring(0, 3)}
          isHome={player.next_opponent.includes("(H)")}
          compact
        />
      )}
    </div>
  );
}

export default function PitchView({
  players,
  formation,
  captainId,
  viceCaptainId,
}: PitchViewProps) {
  // Parse formation string like "4-4-2" into rows
  const formationParts = formation.split("-").map(Number);

  // Group starters by position
  const starters = players.filter((p) => p.is_starter);
  const gks = starters.filter((p) => p.position === "GKP");
  const defs = starters.filter((p) => p.position === "DEF");
  const mids = starters.filter((p) => p.position === "MID");
  const fwds = starters.filter((p) => p.position === "FWD");

  // Build rows (GK is always 1)
  const rows: SquadPlayer[][] = [gks];
  if (formationParts.length === 3) {
    // Standard: DEF-MID-FWD
    rows.push(defs.slice(0, formationParts[0]));
    rows.push(mids.slice(0, formationParts[1]));
    rows.push(fwds.slice(0, formationParts[2]));
  } else {
    // Fallback: just push all by position
    if (defs.length) rows.push(defs);
    if (mids.length) rows.push(mids);
    if (fwds.length) rows.push(fwds);
  }

  return (
    <div className="relative w-full overflow-hidden rounded-xl">
      {/* Pitch background */}
      <svg
        viewBox="0 0 600 800"
        className="absolute inset-0 h-full w-full"
        preserveAspectRatio="xMidYMid slice"
      >
        {/* Grass */}
        <rect width="600" height="800" fill="#1a5f2a" />
        {/* Alternating grass stripes */}
        <rect x="0" y="0" width="600" height="200" fill="#1d6930" opacity="0.3" />
        <rect x="0" y="400" width="600" height="200" fill="#1d6930" opacity="0.3" />
        {/* Outer lines */}
        <rect
          x="30"
          y="30"
          width="540"
          height="740"
          fill="none"
          stroke="rgba(255,255,255,0.25)"
          strokeWidth="2"
        />
        {/* Center line */}
        <line
          x1="30"
          y1="400"
          x2="570"
          y2="400"
          stroke="rgba(255,255,255,0.25)"
          strokeWidth="2"
        />
        {/* Center circle */}
        <circle
          cx="300"
          cy="400"
          r="70"
          fill="none"
          stroke="rgba(255,255,255,0.25)"
          strokeWidth="2"
        />
        {/* Center dot */}
        <circle cx="300" cy="400" r="4" fill="rgba(255,255,255,0.25)" />
        {/* Top penalty box */}
        <rect
          x="150"
          y="30"
          width="300"
          height="120"
          fill="none"
          stroke="rgba(255,255,255,0.2)"
          strokeWidth="2"
        />
        {/* Top 6-yard box */}
        <rect
          x="220"
          y="30"
          width="160"
          height="50"
          fill="none"
          stroke="rgba(255,255,255,0.2)"
          strokeWidth="2"
        />
        {/* Top penalty arc */}
        <path
          d="M 220 150 A 60 60 0 0 0 380 150"
          fill="none"
          stroke="rgba(255,255,255,0.15)"
          strokeWidth="2"
        />
        {/* Bottom penalty box */}
        <rect
          x="150"
          y="650"
          width="300"
          height="120"
          fill="none"
          stroke="rgba(255,255,255,0.2)"
          strokeWidth="2"
        />
        {/* Bottom 6-yard box */}
        <rect
          x="220"
          y="720"
          width="160"
          height="50"
          fill="none"
          stroke="rgba(255,255,255,0.2)"
          strokeWidth="2"
        />
        {/* Bottom penalty arc */}
        <path
          d="M 220 650 A 60 60 0 0 1 380 650"
          fill="none"
          stroke="rgba(255,255,255,0.15)"
          strokeWidth="2"
        />
      </svg>

      {/* Player positions overlay */}
      <div className="relative z-10 flex flex-col items-center gap-4 sm:gap-6 py-6 sm:py-10 min-h-[400px] sm:min-h-[500px]">
        {rows.map((row, rowIdx) => (
          <div
            key={rowIdx}
            className="flex items-center justify-center gap-2 sm:gap-4 md:gap-6 w-full px-2"
          >
            {row.map((player) => (
              <PitchPlayer
                key={player.player_id}
                player={player}
                isCaptain={player.player_id === captainId}
                isViceCaptain={player.player_id === viceCaptainId}
              />
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}
