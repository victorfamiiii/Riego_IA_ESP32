'use client';

import { useRouter } from 'next/navigation';
import { useState } from 'react';
import { useUser } from '../../lib/UserContext';

interface HeaderProps {
  onMenuClick: () => void;
}

export default function Header({ onMenuClick }: HeaderProps) {
  const router = useRouter();
  const { user, logout } = useUser();
  const [isRefreshing, setIsRefreshing] = useState(false);

  const handleLogout = async () => {
    await logout();
  };

  const handleRefresh = () => {
    if (isRefreshing) return;
    setIsRefreshing(true);
    setTimeout(() => {
      window.location.reload();
    }, 600);
  };

  return (
    <header className="fixed top-0 left-0 right-0 z-40 pt-[env(safe-area-inset-top)] bg-white/80 backdrop-blur-lg shadow-lg border-b border-green-100">
      <div className="px-4 py-3">
        <div className="flex items-center justify-between">
          {/* Izquierda: menú + logo + título */}
          <div className="flex items-center space-x-2 md:space-x-3">
            <button
              onClick={onMenuClick}
              className="flex items-center justify-center w-12 h-12 bg-gradient-to-br from-green-500 to-green-600 text-white rounded-2xl shadow-lg hover:from-green-600 hover:to-green-700 transition-all duration-300 hover:scale-105"
              aria-label="Abrir menú"
            >
              <span className="material-icons text-2xl leading-none" style={{ fontSize: '24px' }}>
                menu
              </span>
            </button>

            <button
              onClick={() => router.push('/')}
              className="flex items-center justify-center w-12 h-12 bg-gradient-to-br from-green-500 to-green-600 text-white rounded-2xl shadow-lg hover:from-green-600 hover:to-green-700 transition-all duration-300 hover:scale-105"
              aria-label="Ir al dashboard"
              title="Ir al dashboard"
              type="button"
            >
              <span className="material-icons text-2xl leading-none" style={{ fontSize: '24px' }}>
                cloud
              </span>
            </button>

            <div>
              <h1 className="text-lg md:text-2xl font-bold text-gray-900">Riego IoT</h1>
              <p className="hidden md:block text-xs text-gray-600">
                Monitoreo en tiempo real con ESP32
              </p>
            </div>
          </div>

          {/* Derecha: logout + refresh */}
          <div className="flex items-center gap-2 md:gap-3">
            {user && (
              <button
                onClick={handleLogout}
                className="flex items-center justify-center w-12 h-12 bg-gradient-to-br from-red-500 to-red-600 hover:from-red-600 hover:to-red-700 text-white rounded-2xl transition-all duration-300 shadow-lg hover:shadow-xl hover:scale-105"
                title="Cerrar sesión"
                aria-label="Cerrar sesión"
              >
                <span className="material-icons text-2xl leading-none">logout</span>
              </button>
            )}

            <button
              onClick={handleRefresh}
              disabled={isRefreshing}
              className="flex items-center justify-center w-12 h-12 bg-gradient-to-br from-green-500 to-green-600 hover:from-green-600 hover:to-green-700 text-white rounded-2xl transition-all duration-300 shadow-lg hover:shadow-xl hover:scale-105 disabled:opacity-80 disabled:cursor-not-allowed"
              title="Recargar"
              aria-label="Recargar página"
            >
              <span className={`material-icons text-2xl leading-none ${isRefreshing ? 'animate-spin' : ''}`}>
                refresh
              </span>
            </button>
          </div>
        </div>
      </div>
    </header>
  );
}