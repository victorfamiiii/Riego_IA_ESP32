// lib/api.ts
const getApiUrl = () => {
  // En el servidor (SSR), usa la URL interna de Docker
  if (typeof window === 'undefined') {
    return process.env.INTERNAL_API_URL || 'http://web:8000';
  }
  // En el cliente, usa URLs relativas (nginx hace proxy)
  return '';
};

export const apiUrl = getApiUrl();

// Función helper para hacer fetch con manejo de errores
export const fetchApi = async (endpoint: string, options?: RequestInit) => {
  const url = `${apiUrl}${endpoint}`;
  console.warn('🔍 Fetching from:', url);
  
  const response = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  });
  
  if (!response.ok) {
    throw new Error(`API error: ${response.status} ${response.statusText}`);
  }
  
  return response.json();
};
