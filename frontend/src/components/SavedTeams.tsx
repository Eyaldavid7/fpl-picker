"use client";

import { useState } from "react";
import {
  Trash2,
  Loader2,
  FolderOpen,
  Check,
  X,
  Pencil,
  AlertCircle,
} from "lucide-react";
import {
  useSavedTeams,
  useDeleteTeam,
  useUpdateTeamName,
} from "@/hooks/useFirestore";
import type { SavedTeam } from "@/hooks/useFirestore";

interface SavedTeamsProps {
  onLoadTeam: (playerIds: number[], teamName?: string, fplTeamId?: number) => void;
}

function formatDate(date: Date): string {
  return new Date(date).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

function SkeletonTeamCard() {
  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--muted)]/20 p-4 animate-pulse">
      <div className="flex items-center justify-between mb-3">
        <div className="skeleton h-5 w-40" />
        <div className="skeleton h-4 w-16 rounded-full" />
      </div>
      <div className="flex items-center gap-2 mb-3">
        <div className="skeleton h-5 w-14 rounded-full" />
        <div className="skeleton h-5 w-16 rounded-full" />
      </div>
      <div className="flex items-center justify-between">
        <div className="skeleton h-3 w-24" />
        <div className="flex gap-2">
          <div className="skeleton h-8 w-16 rounded-lg" />
          <div className="skeleton h-8 w-8 rounded-lg" />
        </div>
      </div>
    </div>
  );
}

function TeamCard({
  team,
  onLoad,
  onDelete,
  onRename,
}: {
  team: SavedTeam;
  onLoad: () => void;
  onDelete: () => void;
  onRename: (name: string) => void;
}) {
  const [isEditing, setIsEditing] = useState(false);
  const [editName, setEditName] = useState(team.name);

  const handleSaveName = () => {
    const trimmed = editName.trim();
    if (trimmed && trimmed !== team.name) {
      onRename(trimmed);
    }
    setIsEditing(false);
  };

  const handleCancelEdit = () => {
    setEditName(team.name);
    setIsEditing(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") handleSaveName();
    if (e.key === "Escape") handleCancelEdit();
  };

  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--card)]/60 p-4 hover:border-[var(--primary)]/40 transition-colors">
      {/* Team name - editable */}
      <div className="flex items-center justify-between mb-3 min-h-[28px]">
        {isEditing ? (
          <div className="flex items-center gap-1.5 flex-1 mr-2">
            <input
              type="text"
              value={editName}
              onChange={(e) => setEditName(e.target.value)}
              onKeyDown={handleKeyDown}
              autoFocus
              className="flex-1 bg-[var(--muted)]/50 border border-[var(--border)] rounded px-2 py-1 text-sm font-semibold focus:outline-none focus:border-[var(--primary)] text-[var(--foreground)]"
            />
            <button
              onClick={handleSaveName}
              className="p-1 rounded hover:bg-emerald-500/20 text-emerald-400 transition-colors"
              title="Save name"
            >
              <Check className="h-3.5 w-3.5" />
            </button>
            <button
              onClick={handleCancelEdit}
              className="p-1 rounded hover:bg-red-500/20 text-red-400 transition-colors"
              title="Cancel"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        ) : (
          <button
            onClick={() => {
              setEditName(team.name);
              setIsEditing(true);
            }}
            className="flex items-center gap-1.5 text-sm font-semibold text-[var(--foreground)] hover:text-[var(--primary)] transition-colors truncate max-w-[70%] group"
            title="Click to rename"
          >
            <span className="truncate">{team.name}</span>
            <Pencil className="h-3 w-3 opacity-0 group-hover:opacity-60 transition-opacity shrink-0" />
          </button>
        )}
        <span className="text-xs text-[var(--muted-foreground)] shrink-0">
          {formatDate(team.createdAt)}
        </span>
      </div>

      {/* Badges row */}
      <div className="flex items-center gap-2 flex-wrap mb-3">
        {/* Formation badge */}
        <span className="fpl-badge bg-[var(--muted)]/50 text-[var(--foreground)] text-xs">
          {team.formation}
        </span>

        {/* Source badge */}
        {team.source === "import" ? (
          <span className="fpl-badge bg-blue-500/15 text-blue-400 border border-blue-500/30 text-xs">
            Imported
          </span>
        ) : (
          <span className="fpl-badge bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 text-xs">
            Optimized
          </span>
        )}

        {/* Predicted points */}
        {team.predictedPoints != null && (
          <span className="fpl-badge bg-[var(--primary)]/15 text-[var(--primary)] text-xs">
            {team.predictedPoints.toFixed(1)} pts
          </span>
        )}
      </div>

      {/* Actions row */}
      <div className="flex items-center justify-between">
        <span className="text-xs text-[var(--muted-foreground)]">
          {team.playerIds.length} players
        </span>
        <div className="flex items-center gap-2">
          <button
            onClick={onLoad}
            className="px-3 py-1.5 text-xs font-medium rounded-lg bg-[var(--primary)]/15 text-[var(--primary)] hover:bg-[var(--primary)]/25 transition-colors"
          >
            Load
          </button>
          <button
            onClick={onDelete}
            className="p-1.5 rounded-lg text-[var(--muted-foreground)] hover:text-red-400 hover:bg-red-500/10 transition-colors"
            title="Delete team"
          >
            <Trash2 className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>
    </div>
  );
}

export default function SavedTeams({ onLoadTeam }: SavedTeamsProps) {
  const { data: teams, isLoading, isError } = useSavedTeams();
  const deleteTeam = useDeleteTeam();
  const updateTeamName = useUpdateTeamName();

  const handleDelete = (team: SavedTeam) => {
    if (window.confirm(`Delete "${team.name}"? This cannot be undone.`)) {
      deleteTeam.mutate(team.id);
    }
  };

  const handleRename = (id: string, name: string) => {
    updateTeamName.mutate({ id, name });
  };

  return (
    <div className="fpl-card">
      <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
        <FolderOpen className="h-5 w-5 text-[var(--primary)]" />
        Saved Teams
      </h2>

      {/* Loading state */}
      {isLoading && (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <SkeletonTeamCard />
          <SkeletonTeamCard />
          <SkeletonTeamCard />
        </div>
      )}

      {/* Error state */}
      {isError && (
        <div className="text-sm text-red-400 flex items-center gap-2">
          <AlertCircle className="h-4 w-4" />
          Failed to load saved teams.
        </div>
      )}

      {/* Empty state */}
      {!isLoading && !isError && teams && teams.length === 0 && (
        <p className="text-sm text-[var(--muted-foreground)] py-4 text-center">
          No saved teams yet. Import or optimize a squad to save it.
        </p>
      )}

      {/* Team cards */}
      {!isLoading && !isError && teams && teams.length > 0 && (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {teams.map((team) => (
            <TeamCard
              key={team.id}
              team={team}
              onLoad={() => onLoadTeam(team.playerIds, team.name, team.fplTeamId)}
              onDelete={() => handleDelete(team)}
              onRename={(name) => handleRename(team.id, name)}
            />
          ))}
        </div>
      )}
    </div>
  );
}
