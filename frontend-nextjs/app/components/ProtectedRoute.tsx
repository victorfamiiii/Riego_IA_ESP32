'use client';

import { usePathname } from 'next/navigation';
import { useUser } from '../../lib/UserContext';

export default function ProtectedRoute({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const { user, isLoading } = useUser();

  // Si estamos en login, no forzar validación de sesión
  if (pathname === '/login' || pathname === '/app/login') {
    return <>{children}</>;
  }

  // Estado: cargando
  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gradient-to-br from-green-50 to-blue-50">
        <div className="text-center">
          <div className="animate-spin rounded-full h-16 w-16 border-t-4 border-b-4 border-green-500 mx-auto mb-4"></div>
          <p className="text-gray-600">Verificando sesión...</p>
        </div>
      </div>
    );
  }

  // Estado: no autenticado - redirigir
  if (!user) {
    // Ejecutar redirección
    if (typeof window !== 'undefined') {
      console.warn('🔐 Ejecutando redirección a login...');
      window.location.replace('/app/login');
    }
    
    return (
      <div className="flex items-center justify-center min-h-screen bg-gradient-to-br from-green-50 to-blue-50">
        <div className="text-center">
          <div className="animate-spin rounded-full h-16 w-16 border-t-4 border-b-4 border-green-500 mx-auto mb-4"></div>
          <p className="text-gray-600">Redirigiendo al login...</p>
        </div>
      </div>
    );
  }

  // Estado: autenticado - mostrar contenido
  return <>{children}</>;
}
