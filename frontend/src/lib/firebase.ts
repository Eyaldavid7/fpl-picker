import { initializeApp, getApps, getApp } from "firebase/app";
import { getFirestore } from "firebase/firestore";

// Primary Firebase app (hosting, auth, etc.)
const firebaseConfig = {
  apiKey: "AIzaSyC4ebD7WhzF8p6qUkrHW0bWhUnHnb2Xjaw",
  authDomain: "fpl-picker-app.firebaseapp.com",
  projectId: "fpl-picker-app",
  storageBucket: "fpl-picker-app.firebasestorage.app",
  messagingSenderId: "711868239490",
  appId: "1:711868239490:web:f6ca4aa5ae08f340b76e9b",
};

// Firestore lives on finance-categorizer-fbbb1 (fpl-picker-app has no billing
// so Firestore cannot be provisioned there).
const firestoreConfig = {
  apiKey: "AIzaSyD_KCBissWvOnuygVQIGXKRp5xEOvMugo0",
  authDomain: "finance-categorizer-fbbb1.firebaseapp.com",
  projectId: "finance-categorizer-fbbb1",
  storageBucket: "finance-categorizer-fbbb1.firebasestorage.app",
  messagingSenderId: "567427318686",
  appId: "1:567427318686:web:fba03da31b02b6313b0c8f",
};

// Avoid re-initializing Firebase when hot-reloading in development
const app = getApps().length > 0 ? getApp() : initializeApp(firebaseConfig);

const FIRESTORE_APP_NAME = "firestore-app";
const firestoreApp = getApps().find((a) => a.name === FIRESTORE_APP_NAME)
  ?? initializeApp(firestoreConfig, FIRESTORE_APP_NAME);

export { app };
export const db = getFirestore(firestoreApp);
