import { NextResponse } from 'next/server';

const BACKEND_URL = process.env.BACKEND_URL || 'http://web:8000';

export async function GET() {
  try {
    const response = await fetch(`${BACKEND_URL}/api/auth/csrf/`, {
      method: 'GET',
    });

    const data = await response.json();
    const cookies = response.headers.get('set-cookie');
    
    const nextResponse = NextResponse.json(data, { status: 200 });
    
    if (cookies) {
      nextResponse.headers.set('set-cookie', cookies);
    }
    
    return nextResponse;
  } catch (error) {
    console.error('Error fetching CSRF token:', error);
    return NextResponse.json(
      { error: 'Error al obtener token CSRF' },
      { status: 500 }
    );
  }
}
