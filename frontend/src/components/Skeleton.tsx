/**
 * Reusable skeleton loading components for consistent loading states across pages.
 */

interface SkeletonProps {
  className?: string;
}

/** Basic skeleton block */
export function Skeleton({ className = "" }: SkeletonProps) {
  return <div className={`skeleton ${className}`} />;
}

/** Skeleton for stat cards (used on dashboard, optimizer) */
export function SkeletonCard() {
  return (
    <div className="fpl-card flex items-start gap-4 animate-fade-in">
      <div className="skeleton h-10 w-10 shrink-0 rounded-lg" />
      <div className="flex-1 space-y-2">
        <div className="skeleton h-3 w-20" />
        <div className="skeleton h-7 w-24" />
        <div className="skeleton h-3 w-32" />
      </div>
    </div>
  );
}

/** Skeleton for player rows in tables */
export function SkeletonTableRow({ columns = 8 }: { columns?: number }) {
  return (
    <tr>
      {Array.from({ length: columns }).map((_, i) => (
        <td key={i} className="px-4 py-3">
          <div className={`skeleton h-4 ${i === 0 ? "w-8" : i === 1 ? "w-28" : "w-16"}`} />
        </td>
      ))}
    </tr>
  );
}

/** Skeleton for a full table */
export function SkeletonTable({ rows = 8, columns = 8 }: { rows?: number; columns?: number }) {
  return (
    <div className="fpl-card overflow-hidden p-0 animate-fade-in">
      {/* Header */}
      <div className="flex items-center gap-4 px-6 pt-6 pb-4">
        <div className="skeleton h-5 w-32" />
        <div className="skeleton h-5 w-24 ml-auto" />
      </div>
      <div className="overflow-x-auto">
        <table className="fpl-table">
          <thead>
            <tr>
              {Array.from({ length: columns }).map((_, i) => (
                <th key={i}>
                  <div className="skeleton h-3 w-14" />
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {Array.from({ length: rows }).map((_, i) => (
              <SkeletonTableRow key={i} columns={columns} />
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/** Skeleton for the pitch view */
export function SkeletonPitch() {
  return (
    <div className="fpl-card overflow-hidden p-0 animate-fade-in">
      <div className="px-6 pt-6 pb-2">
        <div className="skeleton h-5 w-28" />
      </div>
      <div className="relative w-full rounded-xl overflow-hidden">
        {/* Pitch background placeholder */}
        <div className="bg-[#1a5f2a] min-h-[400px] sm:min-h-[500px] flex flex-col items-center gap-6 py-10">
          {/* GK row */}
          <div className="flex justify-center gap-4">
            <div className="skeleton h-16 w-16 rounded-lg bg-[#1d6930]" />
          </div>
          {/* DEF row */}
          <div className="flex justify-center gap-4">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="skeleton h-16 w-16 rounded-lg bg-[#1d6930]" />
            ))}
          </div>
          {/* MID row */}
          <div className="flex justify-center gap-4">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="skeleton h-16 w-16 rounded-lg bg-[#1d6930]" />
            ))}
          </div>
          {/* FWD row */}
          <div className="flex justify-center gap-4">
            {[1, 2].map((i) => (
              <div key={i} className="skeleton h-16 w-16 rounded-lg bg-[#1d6930]" />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

/** Skeleton for player cards (compact) */
export function SkeletonPlayerCard() {
  return (
    <div className="flex items-center gap-2 rounded-md border border-[var(--border)] bg-[var(--muted)]/30 px-3 py-2">
      <div className="skeleton h-4 w-8" />
      <div className="skeleton h-4 w-24 flex-1" />
      <div className="skeleton h-4 w-12" />
    </div>
  );
}

/** Skeleton for filter controls bar */
export function SkeletonFilters() {
  return (
    <div className="fpl-card animate-fade-in">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
        <div className="skeleton h-10 flex-1" />
        <div className="skeleton h-10 w-36" />
        <div className="skeleton h-10 w-36" />
      </div>
    </div>
  );
}
