'use client';

/**
 * Componente para inicializar FCM y registrar tokens
 * Se carga automáticamente en el layout
 */

import { useFCM } from '../../lib/useFCM';

export default function FCMHandler() {
  // useFCM hook maneja la inicialización de Firebase y todo el setup
  useFCM();

  return null; // No renderiza nada, solo maneja FCM en background
}
