importScripts('https://www.gstatic.com/firebasejs/10.12.0/firebase-app-compat.js');
importScripts('https://www.gstatic.com/firebasejs/10.12.0/firebase-messaging-compat.js');

firebase.initializeApp({
  apiKey:            "",
  authDomain:        "",
  projectId:         "",
  storageBucket:     "",
  messagingSenderId: "",
  appId:             "",
});

const messaging = firebase.messaging();

messaging.onBackgroundMessage((payload) => {
  // Solo mostrar si no hay clientes activos (app en background/cerrada)
  self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then(clients => {
    const appVisible = clients.some(c => c.visibilityState === 'visible');
    if (appVisible) return; // El onMessage del cliente ya lo maneja
    const { title = 'Riego ESP32', body = '' } = payload.notification ?? {};
    self.registration.showNotification(title, {
      body,
      icon: '/app/icon-192x192.png',
      badge: '/app/icon-192x192.png',
      tag: 'riego-notification',
      data: payload.data ?? {},
      vibrate: [200, 100, 200],
    });
  });
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const url = event.notification.data?.url || '/app/';
  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then((list) => {
      for (const client of list) {
        if (client.url === url && 'focus' in client) return client.focus();
      }
      if (clients.openWindow) return clients.openWindow(url);
    })
  );
});


console.log('[SW] Firebase Messaging SW ready');
