'use client';

import { useEffect } from 'react';

export default function ServiceWorkerRegistration() {
  useEffect(() => {
    if (
      typeof window !== 'undefined' &&
      'serviceWorker' in navigator &&
      process.env.NODE_ENV === 'production'
    ) {
      // Registrar el Service Worker personalizado
      navigator.serviceWorker
        .register('/app/sw-custom.js', { scope: '/app/' })
        .then((registration) => {
          console.warn('✅ Service Worker registered:', registration.scope);

          // Detectar actualizaciones
          registration.addEventListener('updatefound', () => {
            const newWorker = registration.installing;
            console.warn('🔄 Service Worker update found');

            if (newWorker) {
              newWorker.addEventListener('statechange', () => {
                if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
                  console.warn('⚡ New Service Worker available, reloading...');
                  // Notificar al nuevo SW que tome control inmediatamente
                  newWorker.postMessage({ type: 'SKIP_WAITING' });
                }
              });
            }
          });

          // Verificar actualizaciones cada 60 segundos
          setInterval(() => {
            registration.update();
          }, 60000);
        })
        .catch((error) => {
          console.error('❌ Service Worker registration failed:', error);
        });

      // Detectar cuando un nuevo SW toma control (sin recargar automaticamente).
      navigator.serviceWorker.addEventListener('controllerchange', () => {
        console.warn('🔄 Service Worker controller changed');
      });
    }
  }, []);

  return null;
}
