import {
  collection,
  addDoc,
  getDocs,
  getDoc,
  deleteDoc,
  updateDoc,
  doc,
  query,
  orderBy,
  serverTimestamp,
  Timestamp,
} from "firebase/firestore";
import { db } from "./firebase";

// ---------- Types ----------

export interface SavedTeam {
  id: string;
  name: string;
  playerIds: number[];
  players: Array<{
    id: number;
    name: string;
    position: string;
    teamName: string;
  }>;
  formation: string;
  source: "import" | "optimize";
  predictedPoints?: number;
  totalCost?: number;
  captainName?: string;
  viceCaptainName?: string;
  fplTeamId?: number;
  createdAt: Date;
  updatedAt: Date;
}

// ---------- Helpers ----------

const COLLECTION_NAME = "teams";

/** Convert Firestore Timestamp fields to JS Date objects. */
function docToSavedTeam(
  id: string,
  data: Record<string, unknown>
): SavedTeam {
  return {
    ...data,
    id,
    createdAt:
      data.createdAt instanceof Timestamp
        ? data.createdAt.toDate()
        : new Date(data.createdAt as string),
    updatedAt:
      data.updatedAt instanceof Timestamp
        ? data.updatedAt.toDate()
        : new Date(data.updatedAt as string),
  } as SavedTeam;
}

// ---------- CRUD Functions ----------

/** Save a new team to Firestore. Returns the new document ID. */
export async function saveTeam(
  team: Omit<SavedTeam, "id" | "createdAt" | "updatedAt">
): Promise<string> {
  const docRef = await addDoc(collection(db, COLLECTION_NAME), {
    ...team,
    createdAt: serverTimestamp(),
    updatedAt: serverTimestamp(),
  });
  return docRef.id;
}

/** Get all saved teams, ordered by createdAt descending. */
export async function getTeams(): Promise<SavedTeam[]> {
  const q = query(
    collection(db, COLLECTION_NAME),
    orderBy("createdAt", "desc")
  );
  const snapshot = await getDocs(q);
  return snapshot.docs.map((d) =>
    docToSavedTeam(d.id, d.data() as Record<string, unknown>)
  );
}

/** Get a single team by document ID. Returns null if not found. */
export async function getTeam(id: string): Promise<SavedTeam | null> {
  const docRef = doc(db, COLLECTION_NAME, id);
  const snapshot = await getDoc(docRef);
  if (!snapshot.exists()) return null;
  return docToSavedTeam(
    snapshot.id,
    snapshot.data() as Record<string, unknown>
  );
}

/** Delete a team by document ID. */
export async function deleteTeam(id: string): Promise<void> {
  const docRef = doc(db, COLLECTION_NAME, id);
  await deleteDoc(docRef);
}

/** Update the name of a saved team. */
export async function updateTeamName(
  id: string,
  name: string
): Promise<void> {
  const docRef = doc(db, COLLECTION_NAME, id);
  await updateDoc(docRef, {
    name,
    updatedAt: serverTimestamp(),
  });
}
