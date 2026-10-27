'use client';

import { createContext, useContext, useState, useEffect, ReactNode } from 'react';

const API_BASE = 'https://riegoesp32.victorfg.work';

export interface User {
  id: number;
  username: string;
  email: string;
  first_name: string;
  last_name: string;
  is_staff: boolean;
  role: 'admin' | 'visitor';
}

interface UserContextType {
  user: User | null;
  isLoading: boolean;
  isAdmin: boolean;
  refreshUser: () => Promise<void>;
  logout: () => Promise<void>;
}

const UserContext = createContext<UserContextType | undefined>(undefined);

export function UserProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const refreshUser = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/auth/check`, {
        credentials: 'include',
        cache: 'no-store',
        headers: {
          'Cache-Control': 'no-cache',
          'Pragma': 'no-cache'
        }
      });

      if (res.ok) {
        const data = await res.json();
        if (data.authenticated && data.user) {
          setUser(data.user);
        } else {
          setUser(null);
        }
      } else {
        setUser(null);
      }
    } catch (error) {
      console.error('Error checking auth:', error);
      setUser(null);
    } finally {
      setIsLoading(false);
    }
  };

  const logout = async () => {
    try {
      // Hacer logout en el servidor
      await fetch(`${API_BASE}/api/auth/logout`, {
        method: 'POST',
        credentials: 'include',
        headers: {
          'Cache-Control': 'no-cache',
        }
      });
    } catch (error) {
      console.error('Error logging out:', error);
    } finally {
      // Siempre limpiar el estado local
      setUser(null);
      
      // Limpiar cualquier caché del navegador
      if (typeof window !== 'undefined') {
        // Limpiar cookies del lado del cliente si es posible
        document.cookie = 'sessionid=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;';
        document.cookie = 'csrftoken=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;';
        
        // Forzar recarga completa para limpiar cualquier estado en memoria
        window.location.replace('/app/login');
      }
    }
  };

  useEffect(() => {
    refreshUser();
  }, []);

  const isAdmin = user?.role === 'admin' || user?.is_staff === true;

  return (
    <UserContext.Provider value={{ user, isLoading, isAdmin, refreshUser, logout }}>
      {children}
    </UserContext.Provider>
  );
}

export function useUser() {
  const context = useContext(UserContext);
  if (context === undefined) {
    throw new Error('useUser must be used within a UserProvider');
  }
  return context;
}
