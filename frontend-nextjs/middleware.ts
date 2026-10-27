// middleware.ts
import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

export async function middleware(request: NextRequest) {
  // No hacer nada - dejar que Django maneje toda la autenticación
  return NextResponse.next();
}

// No aplicar middleware a ninguna ruta
export const config = {
  matcher: [],
};
