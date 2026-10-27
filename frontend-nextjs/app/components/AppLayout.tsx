'use client';

import { useState } from 'react';
import Sidebar from './Sidebar';
import Header from './Header';
import ProtectedRoute from './ProtectedRoute';
import { UserProvider } from '../../lib/UserContext';

export default function AppLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <UserProvider>
      <ProtectedRoute>
        <div className="flex min-h-screen bg-gradient-to-br from-green-50 via-blue-50 to-purple-50">
          <Sidebar isOpen={sidebarOpen} setIsOpen={setSidebarOpen} />
          <Header onMenuClick={() => setSidebarOpen(true)} />
          <main className="flex-1 w-full pt-[calc(6rem+env(safe-area-inset-top))] md:pt-[4.5rem] transition-all duration-300">
            {children}
          </main>
        </div>
      </ProtectedRoute>
    </UserProvider>
  );
}
