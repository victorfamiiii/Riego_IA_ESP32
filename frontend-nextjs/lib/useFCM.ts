"use client";
import { useEffect, useState } from "react";
import { getFirebaseMessaging, initializeFirebase } from "./firebase";
import { getToken, onMessage } from "firebase/messaging";

function getCsrfToken(): string {
  return document.cookie
    .split("; ")
    .find((row) => row.startsWith("csrftoken="))
    ?.split("=")[1] ?? "";
}

const NOTIFICATIONS_STORAGE_KEY = "fcm_notifications_enabled";

export function getNotificationsEnabled(): boolean {
  if (typeof window === "undefined") return true;
  const stored = localStorage.getItem(NOTIFICATIONS_STORAGE_KEY);
  return stored ? JSON.parse(stored) : true;
}

export async function registerNotifications(): Promise<boolean> {
  try {
    console.warn("[FCM] User requesting notifications...");
    
    // Inicializar Firebase y obtener messaging
    await initializeFirebase();
    const messaging = await getFirebaseMessaging();
    if (!messaging) {
      console.error("[FCM] Firebase messaging not available");
      return false;
    }

    // Solicitar permiso (requiere user gesture)
    const permission = await Notification.requestPermission();
    if (permission !== "granted") {
      console.warn("[FCM] Notification permission denied by user");
      return false;
    }

    console.warn("[FCM] Using active service worker...");
    const registration = await navigator.serviceWorker.ready;

    const vapidKey = process.env.NEXT_PUBLIC_VAPID_PUBLIC_KEY || "BN5mgsKm9PhU52v4Lbly_t8b2VXydIuYmW5yYNFiWJHnR78dQfPCTaOk7H6CPgThlzZqJ96WTj9idMka8hA3oQY";
    const token = await getToken(messaging, {
      vapidKey,
      serviceWorkerRegistration: registration,
    });

    if (token) {
      console.warn("[FCM] Token obtained, registering with server...");
      const response = await fetch("https://riegoesp32.victorfg.work/api/fcm/register", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCsrfToken(),   // ← esto es lo que faltaba
        },
        credentials: "include",
        body: JSON.stringify({
          token,
          device_name: navigator.userAgent,
          user_agent: navigator.userAgent,
        }),
      });

      if (!response.ok) {
        console.error("[FCM] Register failed:", response.status);
        return false;
      }

      console.warn("[FCM] Token registered successfully");
      setNotificationsEnabled(true);
      return true;
    }

    return false;
  } catch (error) {
    console.error("[FCM] Registration error:", error);
    return false;
  }
}

export function setNotificationsEnabled(enabled: boolean): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(NOTIFICATIONS_STORAGE_KEY, JSON.stringify(enabled));
  // Dispatch event para que otros componentes se actualicen
  window.dispatchEvent(
    new CustomEvent("notificationsToggled", { detail: { enabled } })
  );
}

export function useFCM(): { notificationsEnabled: boolean } {
  const [notificationsEnabled, setNotificationsEnabled] = useState(true);

  useEffect(() => {
    // Inicializar estado desde localStorage
    setNotificationsEnabled(getNotificationsEnabled());

    // Escuchar cambios de otros tabs
    const handleToggle = (e: Event) => {
      const customEvent = e as CustomEvent;
      setNotificationsEnabled(customEvent.detail.enabled);
    };
    window.addEventListener("notificationsToggled", handleToggle);
    return () => window.removeEventListener("notificationsToggled", handleToggle);
  }, []);

  useEffect(() => {
    if (!notificationsEnabled) return;

    const setup = async () => {
      try {
        const messaging = await getFirebaseMessaging();
        if (!messaging) {
          console.warn("[FCM] Firebase messaging not initialized");
          return;
        }

        onMessage(messaging, (payload) => {
          if (!getNotificationsEnabled()) return;
          console.warn("[FCM] Foreground message:", payload);

          if (Notification.permission === 'granted') {
            // Chrome móvil requiere SW; escritorio acepta Notification directa
            navigator.serviceWorker.getRegistration('/app/sw-custom.js').then(reg => {
              if (reg) {
                reg.showNotification(
                  payload.notification?.title ?? 'Riego ESP32',
                  {
                    body: payload.notification?.body ?? '',
                    icon: '/app/icon-192x192.png',
                    badge: '/app/favicon-32x32.png',
                    tag: 'riego-notification',
                    data: payload.data ?? {},
                  }
                );
              } else {
                new Notification(
                  payload.notification?.title ?? 'Riego ESP32',
                  { body: payload.notification?.body ?? '', icon: '/app/icon-192x192.png' }
                );
              }
            });
          }
        });
      } catch (error) {
        console.error("[FCM] Setup error:", error);
      }
    };

    setup();
  }, [notificationsEnabled]);

  return { notificationsEnabled };
}
