import type { Position } from "@/types";

interface PlayerCardProps {
  name: string;
  team?: string;
  position: Position;
  price: number;
  predictedPoints?: number;
  isCaptain?: boolean;
  isViceCaptain?: boolean;
  compact?: boolean;
  onClick?: () => void;
}

const positionColors: Record<Position, { bg: string; text: string; border: string }> = {
  GKP: { bg: "bg-yellow-500/20", text: "text-yellow-400", border: "border-yellow-500/30" },
  DEF: { bg: "bg-green-500/20", text: "text-green-400", border: "border-green-500/30" },
  MID: { bg: "bg-blue-500/20", text: "text-blue-400", border: "border-blue-500/30" },
  FWD: { bg: "bg-red-500/20", text: "text-red-400", border: "border-red-500/30" },
};

const positionLabels: Record<Position, string> = {
  GKP: "GK",
  DEF: "DEF",
  MID: "MID",
  FWD: "FWD",
};

export default function PlayerCard({
  name,
  team,
  position,
  price,
  predictedPoints,
  isCaptain = false,
  isViceCaptain = false,
  compact = false,
  onClick,
}: PlayerCardProps) {
  const colors = positionColors[position];

  if (compact) {
    return (
      <div
        onClick={onClick}
        className={`flex items-center gap-2 rounded-md border ${colors.border} ${colors.bg} px-3 py-2 text-sm transition-colors ${
          onClick ? "cursor-pointer hover:brightness-110" : ""
        }`}
      >
        <span className={`text-xs font-semibold ${colors.text}`}>
          {positionLabels[position]}
        </span>
        <span className="flex-1 truncate font-medium text-[var(--foreground)]">
          {name}
        </span>
        {isCaptain && (
          <span className="flex h-5 w-5 items-center justify-center rounded-full bg-[var(--primary)] text-[10px] font-bold text-[var(--primary-foreground)]">
            C
          </span>
        )}
        {isViceCaptain && (
          <span className="flex h-5 w-5 items-center justify-center rounded-full bg-[var(--accent)] text-[10px] font-bold text-[var(--accent-foreground)]">
            V
          </span>
        )}
        {predictedPoints !== undefined && (
          <span className="text-xs font-semibold text-[var(--primary)]">
            {predictedPoints.toFixed(1)}pts
          </span>
        )}
      </div>
    );
  }

  return (
    <div
      onClick={onClick}
      className={`relative rounded-lg border ${colors.border} ${colors.bg} p-4 transition-all ${
        onClick ? "cursor-pointer hover:brightness-110 hover:shadow-md" : ""
      }`}
    >
      {/* Captain / VC badge */}
      {(isCaptain || isViceCaptain) && (
        <span
          className={`absolute -top-2 -right-2 flex h-6 w-6 items-center justify-center rounded-full text-xs font-bold ${
            isCaptain
              ? "bg-[var(--primary)] text-[var(--primary-foreground)]"
              : "bg-[var(--accent)] text-[var(--accent-foreground)]"
          }`}
        >
          {isCaptain ? "C" : "V"}
        </span>
      )}

      <div className="flex items-center gap-3">
        {/* Position badge */}
        <span
          className={`inline-flex h-8 w-8 items-center justify-center rounded-md text-xs font-bold ${colors.bg} ${colors.text} border ${colors.border}`}
        >
          {positionLabels[position]}
        </span>

        <div className="min-w-0 flex-1">
          <p className="truncate font-semibold text-[var(--foreground)]">{name}</p>
          {team && (
            <p className="text-xs text-[var(--muted-foreground)]">{team}</p>
          )}
        </div>
      </div>

      <div className="mt-3 flex items-center justify-between text-sm">
        <span className="text-[var(--muted-foreground)]">
          {(price / 10).toFixed(1)}m
        </span>
        {predictedPoints !== undefined && (
          <span className="font-semibold text-[var(--primary)]">
            {predictedPoints.toFixed(1)} pts
          </span>
        )}
      </div>
    </div>
  );
}
