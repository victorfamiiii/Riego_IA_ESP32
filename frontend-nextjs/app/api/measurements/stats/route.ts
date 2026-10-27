import { NextResponse } from 'next/server';

export async function GET() {
  try {
    // En producción usa el nombre del servicio Docker, en desarrollo usa localhost
    const backendUrl = process.env.NODE_ENV === 'production' 
      ? 'http://esp32-web:8000'
      : 'http://localhost:8000';
    
    const response = await fetch(`${backendUrl}/api/measurements/stats/`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
      cache: 'no-store', // No cachear para obtener datos en tiempo real
    });

    if (!response.ok) {
      throw new Error(`Backend responded with status: ${response.status}`);
    }

    const data = await response.json();
    
    return NextResponse.json(data, {
      headers: {
        'Cache-Control': 'no-store, no-cache, must-revalidate',
      },
    });
  } catch (error) {
    console.error('Error fetching stats:', error);
    return NextResponse.json(
      { error: 'Failed to fetch stats from backend' },
      { status: 500 }
    );
  }
}
