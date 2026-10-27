import { NextRequest, NextResponse } from 'next/server';

const BACKEND_URL = process.env.BACKEND_URL || 'http://web:8000';

export async function GET(request: NextRequest) {
  try {
    const cookies = request.headers.get('cookie');

    const response = await fetch(`${BACKEND_URL}/api/auth/check/`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        ...(cookies && { 'Cookie': cookies }),
      },
    });

    const data = await response.json();

    return NextResponse.json(data, { status: response.status });
  } catch (error) {
    console.error('Error in check auth API:', error);
    return NextResponse.json(
      { authenticated: false },
      { status: 401 }
    );
  }
}
