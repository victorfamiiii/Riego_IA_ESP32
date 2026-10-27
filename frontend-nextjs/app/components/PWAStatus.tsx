'use client';

import { useState, useEffect } from 'react';
interface BeforeInstallPromptEvent extends Event {
  readonly platforms: string[];
  readonly userChoice: Promise<{
    outcome: 'accepted' | 'dismissed';
    platform: string;
  }>;
  prompt(): Promise<void>;
}

declare global {
  interface WindowEventMap {
    beforeinstallprompt: BeforeInstallPromptEvent;
  }
}

export default function PWAStatus() {
  const [isOnline, setIsOnline] = useState(true);
  const [isPWAInstalled, setIsPWAInstalled] = useState(false);
  const [deferredPrompt, setDeferredPrompt] = useState<BeforeInstallPromptEvent | null>(null);
  const [swStatus, setSWStatus] = useState<'active' | 'installing' | 'waiting' | 'none'>('none');

  useEffect(() => {
    // Detectar estado de conexión
    setIsOnline(navigator.onLine);
    
    const handleOnline = () => {
      console.warn('🌐 PWA: Connection restored');
      setIsOnline(true);
    };
    
    const handleOffline = () => {
      console.warn('📴 PWA: Connection lost');
      setIsOnline(false);
    };

    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    // Detectar si PWA está instalada
    if (window.matchMedia('(display-mode: standalone)').matches) {
      console.warn('✅ PWA: Running in standalone mode');
      setIsPWAInstalled(true);
    }

    // Capturar evento de instalación
    const handleBeforeInstallPrompt = (e: BeforeInstallPromptEvent) => {
      console.warn('📥 PWA: Install prompt available');
      e.preventDefault();
      setDeferredPrompt(e);
    };

    window.addEventListener('beforeinstallprompt', handleBeforeInstallPrompt);

    // Detectar cuando se instala
    window.addEventListener('appinstalled', () => {
      console.warn('✅ PWA: App installed successfully');
      setIsPWAInstalled(true);
      setDeferredPrompt(null);
    });

    // Verificar Service Worker
    if ('serviceWorker' in navigator) {
      navigator.serviceWorker.ready.then((registration) => {
        console.warn('✅ PWA: Service Worker ready');
        if (registration.active) {
          setSWStatus('active');
        } else if (registration.installing) {
          setSWStatus('installing');
        } else if (registration.waiting) {
          setSWStatus('waiting');
        }
      });

      // Escuchar cambios en el Service Worker
      navigator.serviceWorker.addEventListener('controllerchange', () => {
        console.warn('🔄 PWA: Service Worker controller changed');
        setSWStatus('active');
      });
    }

    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
      window.removeEventListener('beforeinstallprompt', handleBeforeInstallPrompt);
    };
  }, []);

  const handleInstallClick = async () => {
    if (!deferredPrompt) {
      console.warn('❌ PWA: No install prompt available');
      return;
    }

    console.warn('📥 PWA: Showing install prompt');
    deferredPrompt.prompt();
    
    const { outcome } = await deferredPrompt.userChoice;
    console.warn(`👤 PWA: User choice: ${outcome}`);
    
    if (outcome === 'accepted') {
      setIsPWAInstalled(true);
    }
    
    setDeferredPrompt(null);
  };

  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2">
      {/* Estado de conexión */}
      <div 
        className={`flex items-center gap-2 px-4 py-2 rounded-xl shadow-lg backdrop-blur-lg border ${
          isOnline 
            ? 'bg-green-500/90 border-green-400 text-white' 
            : 'bg-red-500/90 border-red-400 text-white'
        }`}
      >
        {isOnline ? (
          <>
            <span className="material-icons h-5 w-5">wifi</span>
            <span className="text-sm font-semibold">En línea</span>
          </>
        ) : (
          <>
            <span className="material-icons h-5 w-5">wifi_off</span>
            <span className="text-sm font-semibold">Sin conexión</span>
          </>
        )}
      </div>

      {/* Estado del Service Worker */}
      {swStatus !== 'none' && (
        <div className="flex items-center gap-2 px-4 py-2 rounded-xl shadow-lg backdrop-blur-lg border bg-blue-500/90 border-blue-400 text-white">
          {swStatus === 'active' ? (
            <>
              <span className="material-icons h-5 w-5">check_circle</span>
              <span className="text-sm font-semibold">SW Activo</span>
            </>
          ) : swStatus === 'installing' ? (
            <>
              <div className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent" />
              <span className="text-sm font-semibold">SW Instalando...</span>
            </>
          ) : (
            <>
              <span className="material-icons h-5 w-5">cancel</span>
              <span className="text-sm font-semibold">SW Esperando</span>
            </>
          )}
        </div>
      )}

      {/* Botón de instalación */}
      {!isPWAInstalled && deferredPrompt && (
        <button
          onClick={handleInstallClick}
          className="flex items-center gap-2 px-4 py-2 rounded-xl shadow-lg backdrop-blur-lg border bg-purple-500/90 border-purple-400 text-white hover:bg-purple-600/90 transition-all duration-300 hover:scale-105"
        >
          <span className="material-icons h-5 w-5">cloud_download</span>
          <span className="text-sm font-semibold">Instalar App</span>
        </button>
      )}

      {/* PWA instalada */}
      {isPWAInstalled && (
        <div className="flex items-center gap-2 px-4 py-2 rounded-xl shadow-lg backdrop-blur-lg border bg-purple-500/90 border-purple-400 text-white">
          <span className="material-icons h-5 w-5">check_circle</span>
          <span className="text-sm font-semibold">PWA Instalada</span>
        </div>
      )}
    </div>
  );
}
