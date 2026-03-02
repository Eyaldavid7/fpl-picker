"use client";

import { useEffect, useRef } from "react";
import { X, Shirt } from "lucide-react";
import {
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
  Legend,
  ResponsiveContainer,
} from "recharts";
import type { Player } from "@/types";

interface CompareModalProps {
  playerA: Player;
  playerB: Player;
  onClose: () => void;
}

/** Normalise value to 0-100 range based on max */
function norm(value: number, max: number): number {
  if (max === 0) return 0;
  return Math.min(100, Math.round((value / max) * 100));
}

/**
 * Side-by-side player comparison modal with a radar chart and stat breakdown.
 */
export default function CompareModal({ playerA, playerB, onClose }: CompareModalProps) {
  const overlayRef = useRef<HTMLDivElement>(null);

  // Close on Escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  // Close on overlay click
  const handleOverlayClick = (e: React.MouseEvent) => {
    if (e.target === overlayRef.current) onClose();
  };

  // Build radar chart data
  const maxPoints = Math.max(playerA.total_points, playerB.total_points, 1);
  const maxForm = Math.max(playerA.form, playerB.form, 1);
  const maxGoals = Math.max(playerA.goals_scored, playerB.goals_scored, 1);
  const maxAssists = Math.max(playerA.assists, playerB.assists, 1);
  const maxIct = Math.max(playerA.ict_index, playerB.ict_index, 1);
  const maxXg = Math.max(playerA.expected_goals ?? 0, playerB.expected_goals ?? 0, 0.1);
  const maxXa = Math.max(playerA.expected_assists ?? 0, playerB.expected_assists ?? 0, 0.1);
  const maxBonus = Math.max(playerA.bonus, playerB.bonus, 1);

  const radarData = [
    {
      stat: "Points",
      A: norm(playerA.total_points, maxPoints),
      B: norm(playerB.total_points, maxPoints),
    },
    {
      stat: "Form",
      A: norm(playerA.form, maxForm),
      B: norm(playerB.form, maxForm),
    },
    {
      stat: "Goals",
      A: norm(playerA.goals_scored, maxGoals),
      B: norm(playerB.goals_scored, maxGoals),
    },
    {
      stat: "Assists",
      A: norm(playerA.assists, maxAssists),
      B: norm(playerB.assists, maxAssists),
    },
    {
      stat: "ICT",
      A: norm(playerA.ict_index, maxIct),
      B: norm(playerB.ict_index, maxIct),
    },
    {
      stat: "xG",
      A: norm(playerA.expected_goals ?? 0, maxXg),
      B: norm(playerB.expected_goals ?? 0, maxXg),
    },
    {
      stat: "xA",
      A: norm(playerA.expected_assists ?? 0, maxXa),
      B: norm(playerB.expected_assists ?? 0, maxXa),
    },
    {
      stat: "Bonus",
      A: norm(playerA.bonus, maxBonus),
      B: norm(playerB.bonus, maxBonus),
    },
  ];

  const statRows = [
    { label: "Total Points", a: playerA.total_points, b: playerB.total_points },
    { label: "Form", a: Number(playerA.form).toFixed(1), b: Number(playerB.form).toFixed(1) },
    { label: "Price", a: `${(playerA.now_cost / 10).toFixed(1)}m`, b: `${(playerB.now_cost / 10).toFixed(1)}m` },
    { label: "Goals", a: playerA.goals_scored, b: playerB.goals_scored },
    { label: "Assists", a: playerA.assists, b: playerB.assists },
    { label: "Clean Sheets", a: playerA.clean_sheets, b: playerB.clean_sheets },
    { label: "Bonus", a: playerA.bonus, b: playerB.bonus },
    { label: "ICT Index", a: Number(playerA.ict_index).toFixed(1), b: Number(playerB.ict_index).toFixed(1) },
    { label: "xG", a: playerA.expected_goals?.toFixed(2) ?? "-", b: playerB.expected_goals?.toFixed(2) ?? "-" },
    { label: "xA", a: playerA.expected_assists?.toFixed(2) ?? "-", b: playerB.expected_assists?.toFixed(2) ?? "-" },
    { label: "Ownership", a: `${Number(playerA.selected_by_percent).toFixed(1)}%`, b: `${Number(playerB.selected_by_percent).toFixed(1)}%` },
    { label: "Minutes", a: playerA.minutes.toLocaleString(), b: playerB.minutes.toLocaleString() },
  ];

  return (
    <div
      ref={overlayRef}
      onClick={handleOverlayClick}
      className="fixed inset-0 z-[80] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 animate-fade-in"
    >
      <div className="relative w-full max-w-3xl max-h-[90vh] overflow-y-auto rounded-xl border border-[var(--border)] bg-[var(--card)] shadow-2xl">
        {/* Header */}
        <div className="sticky top-0 z-10 flex items-center justify-between border-b border-[var(--border)] bg-[var(--card)] px-6 py-4">
          <h2 className="text-lg font-bold fpl-gradient-text">Player Comparison</h2>
          <button
            onClick={onClose}
            className="flex h-8 w-8 items-center justify-center rounded-md hover:bg-[var(--muted)] transition-colors"
          >
            <X className="h-5 w-5 text-[var(--muted-foreground)]" />
          </button>
        </div>

        <div className="p-6 space-y-6">
          {/* Player names header */}
          <div className="grid grid-cols-3 gap-4 text-center">
            <div>
              <div className="flex items-center justify-center gap-2">
                <Shirt className="h-5 w-5 text-[#00ff87]" />
                <span className="font-bold text-[var(--foreground)]">{playerA.web_name}</span>
              </div>
              <span className="text-xs text-[var(--muted-foreground)]">
                {playerA.position} - {playerA.team_short_name ?? `Team ${playerA.team_id}`}
              </span>
            </div>
            <div className="flex items-center justify-center text-sm font-semibold text-[var(--muted-foreground)]">
              VS
            </div>
            <div>
              <div className="flex items-center justify-center gap-2">
                <Shirt className="h-5 w-5 text-[#04f5ff]" />
                <span className="font-bold text-[var(--foreground)]">{playerB.web_name}</span>
              </div>
              <span className="text-xs text-[var(--muted-foreground)]">
                {playerB.position} - {playerB.team_short_name ?? `Team ${playerB.team_id}`}
              </span>
            </div>
          </div>

          {/* Radar chart */}
          <div className="h-[320px] w-full">
            <ResponsiveContainer width="100%" height="100%">
              <RadarChart data={radarData} outerRadius="75%">
                <PolarGrid stroke="rgba(255,255,255,0.1)" />
                <PolarAngleAxis
                  dataKey="stat"
                  tick={{ fill: "#a0a0a0", fontSize: 11 }}
                />
                <PolarRadiusAxis
                  angle={90}
                  domain={[0, 100]}
                  tick={false}
                  axisLine={false}
                />
                <Radar
                  name={playerA.web_name}
                  dataKey="A"
                  stroke="#00ff87"
                  fill="#00ff87"
                  fillOpacity={0.2}
                  strokeWidth={2}
                />
                <Radar
                  name={playerB.web_name}
                  dataKey="B"
                  stroke="#04f5ff"
                  fill="#04f5ff"
                  fillOpacity={0.2}
                  strokeWidth={2}
                />
                <Legend
                  wrapperStyle={{ fontSize: "12px", color: "#a0a0a0" }}
                />
              </RadarChart>
            </ResponsiveContainer>
          </div>

          {/* Stat comparison table */}
          <div className="overflow-x-auto rounded-lg border border-[var(--border)]">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[var(--border)]">
                  <th className="px-4 py-2 text-left text-xs uppercase tracking-wider text-[#00ff87] font-semibold w-1/3">
                    {playerA.web_name}
                  </th>
                  <th className="px-4 py-2 text-center text-xs uppercase tracking-wider text-[var(--muted-foreground)] font-semibold w-1/3">
                    Stat
                  </th>
                  <th className="px-4 py-2 text-right text-xs uppercase tracking-wider text-[#04f5ff] font-semibold w-1/3">
                    {playerB.web_name}
                  </th>
                </tr>
              </thead>
              <tbody>
                {statRows.map((row) => {
                  const aNum = typeof row.a === "number" ? row.a : parseFloat(String(row.a));
                  const bNum = typeof row.b === "number" ? row.b : parseFloat(String(row.b));
                  const aWins = !isNaN(aNum) && !isNaN(bNum) && aNum > bNum;
                  const bWins = !isNaN(aNum) && !isNaN(bNum) && bNum > aNum;

                  return (
                    <tr
                      key={row.label}
                      className="border-b border-[var(--border)]/50 transition-colors hover:bg-[var(--muted)]/20"
                    >
                      <td className={`px-4 py-2.5 ${aWins ? "text-[#00ff87] font-semibold" : "text-[var(--foreground)]"}`}>
                        {row.a}
                      </td>
                      <td className="px-4 py-2.5 text-center text-xs text-[var(--muted-foreground)]">
                        {row.label}
                      </td>
                      <td className={`px-4 py-2.5 text-right ${bWins ? "text-[#04f5ff] font-semibold" : "text-[var(--foreground)]"}`}>
                        {row.b}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
