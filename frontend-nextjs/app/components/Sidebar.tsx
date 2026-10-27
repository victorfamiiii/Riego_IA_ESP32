'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useUser } from '../../lib/UserContext';

interface SidebarProps {
  isOpen: boolean;
  setIsOpen: (isOpen: boolean) => void;
}

export default function Sidebar({ isOpen, setIsOpen }: SidebarProps) {
  const pathname = usePathname();
  const { isAdmin } = useUser();

  const menuItems = [
    { name: 'Dashboard',             href: '/',              icon: 'home',           description: 'Vista general del sistema',             adminOnly: false },
    { name: 'Datos',                 href: '/datos',         icon: 'bar_chart',      description: 'Visualización de mediciones',            adminOnly: false },
    { name: 'Control de Riego',      href: '/riego',         icon: 'water_drop',     description: 'Gestión del sistema de riego',           adminOnly: false },
    { name: 'Ajustes',               href: '/ajustes',       icon: 'settings',       description: 'Configuración del sistema',              adminOnly: false },
    { name: 'IA',                    href: '/ia',            icon: 'auto_awesome',   description: 'Historial de comunicaciones IA',         adminOnly: false },
    { name: 'Notificaciones',        href: '/notificaciones',icon: 'notifications',  description: 'Historial y envío de notificaciones',    adminOnly: true  },
    { name: 'Administración',        href: '/admin',         icon: 'build',          description: 'Gestión de tablas y datos',              adminOnly: true  },
    { name: 'Calibración Sensores',  href: '/calibracion',   icon: 'tune',           description: 'Tanque, válvulas y humedad',             adminOnly: true  },
  ];

  const visibleMenuItems = menuItems.filter(item => !item.adminOnly || isAdmin);

  return (
    <>
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/50 backdrop-blur-sm z-40"
          onClick={() => setIsOpen(false)}
        />
      )}

      <aside
        className={`
          fixed top-0 left-0 h-full bg-gradient-to-b from-green-600 to-green-700
          text-white shadow-2xl z-50 transition-transform duration-300 ease-in-out w-72
          ${isOpen ? 'translate-x-0' : '-translate-x-full'}
        `}
      >
        <div className="flex flex-col h-full">

          {/* Header */}
          <div className="p-6 border-b border-green-500/30">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-3">
                {/* CORREGIDO: flex items-center justify-center en el wrapper del icono */}
                <div className="bg-white/20 p-2 rounded-xl backdrop-blur-sm flex items-center justify-center">
                  <span className="material-icons text-white leading-none">science</span>
                </div>
                <div>
                  <h2 className="text-xl font-bold">Sistema Riego</h2>
                  <p className="text-xs text-green-100">ESP32 IoT</p>
                </div>
              </div>
              <button
                onClick={() => setIsOpen(false)}
                className="p-2 hover:bg-white/10 rounded-lg transition-colors flex items-center justify-center"
              >
                <span className="material-icons text-white leading-none">close</span>
              </button>
            </div>
          </div>

          {/* Navegación */}
          <nav className="flex-1 p-4 overflow-y-auto">
            <ul className="space-y-2">
              {visibleMenuItems.map((item) => {
                const isActive = pathname === item.href;
                return (
                  <li key={item.href}>
                    <Link
                      href={item.href}
                      onClick={() => setIsOpen(false)}
                      className={`
                        flex items-center gap-3 p-3 rounded-xl transition-all duration-200
                        ${isActive ? 'bg-white text-green-700 shadow-lg scale-105' : 'hover:bg-white/10 hover:scale-105'}
                      `}
                    >
                      {/* CORREGIDO: flex items-center justify-center + leading-none en el span */}
                      <div className={`
                        p-2 rounded-lg flex items-center justify-center w-9 h-9 shrink-0
                        ${isActive ? 'bg-green-100' : 'bg-white/10'}
                      `}>
                        <span className={`material-icons text-xl leading-none ${isActive ? 'text-green-700' : 'text-white'}`}>
                          {item.icon}
                        </span>
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="font-semibold">{item.name}</p>
                        <p className={`text-xs ${isActive ? 'text-green-600' : 'text-green-100'}`}>
                          {item.description}
                        </p>
                      </div>
                    </Link>
                  </li>
                );
              })}
            </ul>
          </nav>

        </div>
      </aside>
    </>
  );
}