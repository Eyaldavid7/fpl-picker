import type { LucideIcon } from "lucide-react";

interface StatsCardProps {
  icon: LucideIcon;
  label: string;
  value: string | number;
  subtext?: string;
  trend?: "up" | "down" | "neutral";
  accentColor?: "primary" | "accent" | "pink" | "default";
  loading?: boolean;
}

const accentClasses: Record<string, string> = {
  primary: "text-[var(--primary)]",
  accent: "text-[var(--accent)]",
  pink: "text-[var(--fpl-pink,#e90052)]",
  default: "text-[var(--foreground)]",
};

const iconBgClasses: Record<string, string> = {
  primary: "bg-[var(--primary)]/10 text-[var(--primary)]",
  accent: "bg-[var(--accent)]/10 text-[var(--accent)]",
  pink: "bg-pink-500/10 text-pink-400",
  default: "bg-[var(--muted)] text-[var(--muted-foreground)]",
};

export default function StatsCard({
  icon: Icon,
  label,
  value,
  subtext,
  trend,
  accentColor = "default",
  loading = false,
}: StatsCardProps) {
  return (
    <div className="fpl-card flex items-start gap-4">
      <div
        className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-lg ${iconBgClasses[accentColor]}`}
      >
        <Icon className="h-5 w-5" />
      </div>
      <div className="min-w-0 flex-1">
        <p className="text-xs font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
          {label}
        </p>
        {loading ? (
          <div className="skeleton mt-1 h-7 w-20" />
        ) : (
          <p className={`mt-0.5 text-2xl font-bold ${accentClasses[accentColor]}`}>
            {value}
          </p>
        )}
        {subtext && (
          <p className="mt-0.5 text-xs text-[var(--muted-foreground)] flex items-center gap-1">
            {trend === "up" && <span className="text-emerald-400">+</span>}
            {trend === "down" && <span className="text-red-400">-</span>}
            {subtext}
          </p>
        )}
      </div>
    </div>
  );
}
