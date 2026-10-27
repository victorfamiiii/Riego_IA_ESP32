import { NextRequest, NextResponse } from 'next/server';

const BACKEND_URL = process.env.BACKEND_URL || 'http://web:8000';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    
    // Primero obtener el CSRF token
    const csrfResponse = await fetch(`${BACKEND_URL}/api/auth/csrf/`, {
      method: 'GET',
      credentials: 'include',
    });
    
    const csrfCookies = csrfResponse.headers.getSetCookie();
    let csrfToken = '';
    
    // Extraer el token CSRF de las cookies
    csrfCookies.forEach(cookie => {
      const match = cookie.match(/csrftoken=([^;]+)/);
      if (match) {
        csrfToken = match[1];
      }
    });

    // Hacer login con el CSRF token
    const response = await fetch(`${BACKEND_URL}/api/auth/login/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrfToken,
        'Cookie': csrfCookies.join('; '),
      },
      body: JSON.stringify(body),
      credentials: 'include',
    });

    const data = await response.json();

    if (response.ok) {
      // Obtener todas las cookies de la respuesta de Django
      const setCookieHeaders = response.headers.getSetCookie();
      
      const nextResponse = NextResponse.json(data, { status: 200 });
      
      // Pasar todas las cookies de Django a la respuesta de Next.js
      if (setCookieHeaders.length > 0) {
        setCookieHeaders.forEach(cookie => {
          nextResponse.headers.append('set-cookie', cookie);
        });
      }
      
      return nextResponse;
    } else {
      return NextResponse.json(data, { status: response.status });
    }
  } catch (error) {
    console.error('Error in login API:', error);
    return NextResponse.json(
      { error: 'Error al conectar con el backend' },
      { status: 500 }
    );
  }
}
