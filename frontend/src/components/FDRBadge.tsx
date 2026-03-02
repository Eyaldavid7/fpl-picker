/**
 * FDRBadge - Fixture Difficulty Rating badge component.
 *
 * Renders a colored badge indicating a player's upcoming opponent and
 * fixture difficulty (1-5). Used in the Full Squad table and the
 * UpcomingFixtures ticker.
 */

interface FDRBadgeProps {
  /** FDR difficulty rating from 1 (easiest) to 5 (hardest) */
  difficulty: number;
  /** Short name of the opponent, e.g. "ARS" */
  opponentShortName: string;
  /** Whether the fixture is at home */
  isHome: boolean;
  /** Compact mode: smaller text & padding (for ticker cells) */
  compact?: boolean;
}

const FDR_COLORS: Record<number, string> = {
  1: "bg-[#1e8449]", // dark green - very easy
  2: "bg-[#27ae60]", // green - easy
  3: "bg-[#95a5a6]", // grey - medium
  4: "bg-[#e67e22]", // orange - hard
  5: "bg-[#c0392b]", // red - very hard
};

export default function FDRBadge({
  difficulty,
  opponentShortName,
  isHome,
  compact = false,
}: FDRBadgeProps) {
  const bgColor = FDR_COLORS[difficulty] ?? FDR_COLORS[3];
  const venue = isHome ? "H" : "A";

  return (
    <span
      className={[
        bgColor,
        "text-white font-semibold rounded-md inline-flex items-center justify-center whitespace-nowrap",
        compact ? "text-[10px] px-1.5 py-0.5" : "text-xs px-2 py-1",
      ].join(" ")}
      title={`FDR ${difficulty} — ${opponentShortName} (${venue})`}
    >
      {opponentShortName} ({venue})
    </span>
  );
}

/** Exported color map so the legend can reuse the exact same values. */
export { FDR_COLORS };
