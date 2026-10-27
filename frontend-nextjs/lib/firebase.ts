import { initializeApp, getApps, FirebaseApp } from "firebase/app";
import { getMessaging, Messaging } from "firebase/messaging";

const firebaseConfig = {
  apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY || "",
  authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN || "riego-esp32-fcm.firebaseapp.com",
  projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID || "riego-esp32-fcm",
  storageBucket: process.env.NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET || "riego-esp32-fcm.appspot.com",
  messagingSenderId: process.env.NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID || "629937244404",
  appId: process.env.NEXT_PUBLIC_FIREBASE_APP_ID || "",
};

let app: FirebaseApp | null = null;
let messagingInstance: Messaging | null = null;
let initPromise: Promise<void> | null = null;

export async function initializeFirebase(): Promise<void> {
  if (typeof window === "undefined") return;

  // Si ya está inicializando, esperar
  if (initPromise) {
    return initPromise;
  }

  // Si ya está inicializado, no reintentar
  if (app && messagingInstance) {
    console.warn("[FCM] Firebase already initialized");
    return;
  }

  // Validar que la API key esté configurada
  if (!firebaseConfig.apiKey || firebaseConfig.apiKey === "") {
    console.error("[FCM] Firebase API key not configured. Please set NEXT_PUBLIC_FIREBASE_API_KEY environment variable.");
    throw new Error("Firebase API key is not configured");
  }

  // Crear la promesa de inicialización una sola vez
  initPromise = (async () => {
    try {
      console.warn("[FCM] Starting Firebase initialization...");
      
      app = getApps().length === 0 ? initializeApp(firebaseConfig) : getApps()[0];
      console.warn("[FCM] Firebase app initialized");
      
      // Esperar a que messaging esté disponible
      messagingInstance = getMessaging(app);
      console.warn("[FCM] Firebase messaging ready");
    } catch (error) {
      console.error("[FCM] Firebase initialization failed:", error);
      messagingInstance = null;
      throw error;
    }
  })();

  return initPromise;
}

export async function getFirebaseMessaging(): Promise<Messaging | null> {
  // Asegurar que Firebase esté inicializado
  if (!messagingInstance) {
    await initializeFirebase();
  }
  return messagingInstance;
}
