'use client';

import { useState, useEffect } from 'react';
import TwemojiEmoji from '../../components/TwemojiEmoji';

const API_BASE = 'https://riegoesp32.victorfg.work';

type PlantId = 'lechuga' | 'fresa';

interface GeminiLog {
  id: number;
  tipo_planta: string;
  prompt: string;
  prompt_completo: string;
  respuesta_raw: string;
  respuesta_completa: string;
  decision_regar: boolean;
  decision_duracion_s: number;
  decision_razon: string;
  latencia_ms: number;
  exito: boolean;
  error_mensaje: string | null;
  created_at: string;
}

const STATUS_COLORS: Record<string, { bg: string; text: string; badge: string; iconName: string }> = {
  success: { bg: 'bg-green-50', text: 'text-green-700', badge: 'bg-green-100 text-green-800', iconName: 'check_circle' },
  error:   { bg: 'bg-red-50',   text: 'text-red-700',   badge: 'bg-red-100 text-red-800',     iconName: 'cancel' },
};

export default function IAPage() {
  const [geminiLogs, setGeminiLogs] = useState<GeminiLog[]>([]);
  const [loadingGeminiLogs, setLoadingGeminiLogs] = useState(false);
  const [selectedPlant, setSelectedPlant] = useState<PlantId>('lechuga');

  useEffect(() => {
    loadGeminiLogs('lechuga');
  }, []);

  const loadGeminiLogs = async (plantId: PlantId) => {
    try {
      setLoadingGeminiLogs(true);
      setSelectedPlant(plantId);

      const res = await fetch(`${API_BASE}/api/admin/gemini-logs?tipo_planta=${plantId}&limit=100`, {
        credentials: 'include',
        cache: 'no-store',
      });

      if (res.ok) {
        const data = await res.json();
        setGeminiLogs(data.logs || []);
      }
    } catch (error) {
      console.error('Error loading Gemini logs:', error);
    } finally {
      setLoadingGeminiLogs(false);
    }
  };

  const getStatusConfig = (log: GeminiLog) => {
    return log.exito ? STATUS_COLORS.success : STATUS_COLORS.error;
  };

  return (
    <div className="p-8">

      {/* Header */}
      <div className="mb-8">
        <h1 className="text-4xl font-bold mb-2 flex items-center gap-2 text-gray-900">
          <TwemojiEmoji emoji="🤖" size={32} />
          <span>Inteligencia Artificial</span>
        </h1>
        <p className="text-gray-600">Historial de comunicaciones y decisiones con Gemini AI</p>
      </div>

      {/* Historial */}
      <div className="bg-white/80 backdrop-blur-lg rounded-3xl shadow-xl border border-gray-100 overflow-hidden">

        {/* Filtros */}
        <div className="p-6 border-b border-gray-100">
          <p className="block text-sm font-medium text-gray-700 mb-3">
            Selecciona una planta:
          </p>
          <div className="flex gap-3">
            <button
              onClick={() => loadGeminiLogs('lechuga')}
              className={`px-6 py-2 rounded-lg font-semibold transition-all flex items-center gap-2 ${
                selectedPlant === 'lechuga'
                  ? 'bg-gradient-to-r from-emerald-500 to-emerald-600 text-white shadow-lg'
                  : 'bg-gray-50 text-gray-700 border border-gray-300 hover:bg-gray-100'
              }`}
            >
              <TwemojiEmoji emoji="🥬" size={18} /> Lechugas
            </button>
            <button
              onClick={() => loadGeminiLogs('fresa')}
              className={`px-6 py-2 rounded-lg font-semibold transition-all flex items-center gap-2 ${
                selectedPlant === 'fresa'
                  ? 'bg-gradient-to-r from-rose-500 to-rose-600 text-white shadow-lg'
                  : 'bg-gray-50 text-gray-700 border border-gray-300 hover:bg-gray-100'
              }`}
            >
              <TwemojiEmoji emoji="🍓" size={18} /> Fresas
            </button>
          </div>
        </div>

        {/* Tabla */}
        <div>
          {loadingGeminiLogs ? (
            <div className="flex items-center justify-center p-12">
              <div className="text-center">
                <div className="animate-spin rounded-full h-10 w-10 border-t-4 border-b-4 border-purple-500 mx-auto mb-3" />
                <p className="text-gray-600">Cargando historial...</p>
              </div>
            </div>
          ) : geminiLogs.length === 0 ? (
            <div className="text-center p-12">
              <span className="material-icons text-6xl text-gray-300 block mx-auto mb-4">auto_awesome</span>
              <p className="text-gray-500">No hay registros disponibles</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-semibold text-gray-600 uppercase">Fecha y Hora</th>
                    <th className="px-6 py-3 text-left text-xs font-semibold text-gray-600 uppercase">Decisión</th>
                    <th className="px-6 py-3 text-left text-xs font-semibold text-gray-600 uppercase">Razón</th>
                    <th className="px-6 py-3 text-left text-xs font-semibold text-gray-600 uppercase">Duración</th>
                    <th className="px-6 py-3 text-left text-xs font-semibold text-gray-600 uppercase">Latencia</th>
                    <th className="px-6 py-3 text-left text-xs font-semibold text-gray-600 uppercase">Estado</th>
                    <th className="px-6 py-3 text-left text-xs font-semibold text-gray-600 uppercase">Detalles</th>
                  </tr>
                </thead>
                <tbody>
                  {geminiLogs.map((log) => {
                    const statusConfig = getStatusConfig(log);

                    return (
                      <tr key={log.id} className={`border-t border-gray-100 hover:brightness-95 transition-all ${statusConfig.bg}`}>
                        <td className="px-6 py-4 text-sm text-gray-900 whitespace-nowrap">
                          {new Date(log.created_at).toLocaleString('es-ES', {
                            year: 'numeric',
                            month: '2-digit',
                            day: '2-digit',
                            hour: '2-digit',
                            minute: '2-digit',
                          })}
                        </td>

                        <td className="px-6 py-4 text-sm">
                          <span className={`px-3 py-1 rounded-full text-xs font-semibold inline-flex items-center gap-1 whitespace-nowrap ${
                            log.decision_regar ? 'bg-blue-100 text-blue-800' : 'bg-yellow-100 text-yellow-800'
                          }`}>
                            <TwemojiEmoji emoji={log.decision_regar ? '💧' : '⏸️'} size={12} />
                            {log.decision_regar ? 'REGAR' : 'NO REGAR'}
                          </span>
                        </td>

                        <td className="px-6 py-4 text-sm text-gray-600 max-w-xs truncate">
                          {log.decision_razon || '-'}
                        </td>

                        <td className="px-6 py-4 text-sm text-gray-600 whitespace-nowrap">
                          {log.decision_duracion_s ? `${log.decision_duracion_s}s` : '-'}
                        </td>

                        <td className="px-6 py-4 text-sm text-gray-600 whitespace-nowrap">
                          {log.latencia_ms}ms
                        </td>

                        <td className="px-6 py-4 text-sm">
                          <span className={`px-3 py-1 rounded-full text-xs font-semibold inline-flex items-center gap-1 w-fit ${statusConfig.badge}`}>
                            <span className="material-icons leading-none" style={{ fontSize: '14px' }}>
                              {statusConfig.iconName}
                            </span>
                            {log.exito ? 'Éxito' : 'Error'}
                          </span>
                        </td>

                        <td className="px-6 py-4 text-sm">
                          <details>
                            <summary className="cursor-pointer text-blue-600 hover:text-blue-800 text-sm font-medium list-none flex items-center gap-1">
                              <span className="material-icons leading-none" style={{ fontSize: '14px' }}>expand_more</span>
                              Ver más
                            </summary>

                            <div
                              className="mt-2 p-3 bg-white border border-gray-200 rounded-lg text-gray-700 w-80"
                              style={{ fontSize: '12px', lineHeight: '1.5' }}
                            >
                              <p className="font-semibold text-gray-800 mb-1">Decisión:</p>
                              <p className="mb-3">
                                <span className={`px-2 py-0.5 rounded-full text-xs font-semibold inline-flex items-center gap-1 whitespace-nowrap ${
                                  log.decision_regar ? 'bg-blue-100 text-blue-800' : 'bg-yellow-100 text-yellow-800'
                                }`}>
                                  <TwemojiEmoji emoji={log.decision_regar ? '💧' : '⏸️'} size={12} />
                                  {log.decision_regar ? 'REGAR' : 'NO REGAR'}
                                </span>
                                {log.decision_duracion_s > 0 && (
                                  <span className="ml-2 text-gray-600">{log.decision_duracion_s}s</span>
                                )}
                              </p>

                              {log.decision_razon && (
                                <>
                                  <p className="font-semibold text-gray-800 mb-1">Razón:</p>
                                  <p className="mb-3 break-words text-gray-600">{log.decision_razon}</p>
                                </>
                              )}

                              <p className="font-semibold text-gray-800 mb-1">Latencia:</p>
                              <p className="mb-3 text-gray-600">{log.latencia_ms}ms</p>

                              {log.prompt_completo && (
                                <>
                                  <p className="font-semibold text-gray-800 mb-1">Prompt enviado:</p>
                                  <div className="mb-3 break-words text-gray-600 font-mono bg-gray-50 p-2 rounded max-h-32 overflow-y-auto whitespace-pre-wrap">
                                    {log.prompt_completo}
                                  </div>
                                </>
                              )}

                              {log.respuesta_completa && (
                                <>
                                  <p className="font-semibold text-gray-800 mb-1">Respuesta recibida:</p>
                                  <div className="mb-3 break-words text-gray-600 font-mono bg-gray-50 p-2 rounded max-h-32 overflow-y-auto whitespace-pre-wrap">
                                    {log.respuesta_completa}
                                  </div>
                                </>
                              )}

                              {log.error_mensaje && (
                                <>
                                  <p className="font-semibold text-red-600 mb-1">Error:</p>
                                  <p className="text-red-600 break-words">{log.error_mensaje}</p>
                                </>
                              )}
                            </div>
                          </details>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}