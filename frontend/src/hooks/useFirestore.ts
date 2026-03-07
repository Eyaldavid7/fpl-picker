"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getTeams,
  saveTeam,
  deleteTeam,
  updateTeamName,
  upsertTeamByFplId,
} from "@/lib/firestore";
import type { SavedTeam } from "@/lib/firestore";

// Re-export the type for convenience
export type { SavedTeam };

const SAVED_TEAMS_KEY = ["savedTeams"] as const;

/** Fetch all saved teams from Firestore. */
export function useSavedTeams() {
  return useQuery<SavedTeam[]>({
    queryKey: [...SAVED_TEAMS_KEY],
    queryFn: getTeams,
  });
}

/** Save a new team to Firestore. Invalidates the saved teams cache on success. */
export function useSaveTeam() {
  const queryClient = useQueryClient();

  return useMutation<
    string,
    Error,
    Omit<SavedTeam, "id" | "createdAt" | "updatedAt">
  >({
    mutationFn: saveTeam,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [...SAVED_TEAMS_KEY] });
    },
  });
}

/** Delete a saved team from Firestore. Invalidates the saved teams cache on success. */
export function useDeleteTeam() {
  const queryClient = useQueryClient();

  return useMutation<void, Error, string>({
    mutationFn: deleteTeam,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [...SAVED_TEAMS_KEY] });
    },
  });
}

/** Upsert a team by FPL team ID (update existing or create new). */
export function useUpsertTeam() {
  const queryClient = useQueryClient();

  return useMutation<
    string,
    Error,
    { fplTeamId: number; team: Omit<SavedTeam, "id" | "createdAt" | "updatedAt"> }
  >({
    mutationFn: ({ fplTeamId, team }) => upsertTeamByFplId(fplTeamId, team),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [...SAVED_TEAMS_KEY] });
    },
  });
}

/** Update a saved team's name. Invalidates the saved teams cache on success. */
export function useUpdateTeamName() {
  const queryClient = useQueryClient();

  return useMutation<void, Error, { id: string; name: string }>({
    mutationFn: ({ id, name }) => updateTeamName(id, name),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [...SAVED_TEAMS_KEY] });
    },
  });
}
