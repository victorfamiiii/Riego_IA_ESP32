'use client';

import { useState, useEffect, useCallback } from 'react';
import TwemojiEmoji from '../../components/TwemojiEmoji';

const API_BASE = 'https://riegoesp32.victorfg.work';

interface IrrigationStatus {
  active: boolean;
  last_activation?: string;
  total_activations: number;
  active_plant?: string;
  relay?: number | null;
  automatic_enabled?: boolean;
  plants_active?: Record<string, {
    active: boolean;
    event_id?: number | null;
    time_remaining?: number;
    reason?: string;
  }>;
  automatic_config?: {
    umbral_humedad?: number;
    tiempo_riego?: number;
    max_riegos_dia?: number;
    plants?: Record<string, {
      umbral_humedad_minimo?: number;
      tiempo_riego_segundos?: number;
      max_riegos_dia?: number;
      tiempo_minimo_entre_riegos?: number;
    }>;
  };
}

interface IrrigationEvent {
  id: number;
  fecha_inicio: string;
  fecha_fin: string | null;
  duracion_planificada_segundos: number;
  duracion_real_segundos: number | null;
  humedad_inicial: number;
  humedad_final: number | null;
  razon: string;
  automatico: boolean;
  litros?: number;
}

interface PlantType {
  id: string;
  name: string;
  emoji: string;
  description: string;
  waterNeeds: string;
  duration: number;
  color: string;
  colorLight: string;
}

const PLANT_TYPES: PlantType[] = [
  {
    id: 'lechuga',
    name: 'Lechugas',
    emoji: '🥬',
    description: 'Cultivo de lechugas - Necesita humedad constante y moderada',
    waterNeeds: 'Media-Alta',
    duration: 40,
    color: 'from-green-500 to-lime-500',
    colorLight: 'bg-green-50 border-green-200',
  },
  {
    id: 'fresa',
    name: 'Fresas',
    emoji: '🍓',
    description: 'Cultivo de fresas - Riego frecuente, suelo húmedo pero bien drenado',
    waterNeeds: 'Media-Alta',
    duration: 35,
    color: 'from-red-500 to-pink-500',
    colorLight: 'bg-red-50 border-pink-200',
  },
];

const DURATION_OPTIONS = [5, 10, 15, 20, 30, 40, 60];

export default function RiegoPage() {
  const [status, setStatus] = useState<IrrigationStatus>({
    active: false,
    total_activations: 0,
  });
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [selectedPlant, setSelectedPlant] = useState<PlantType>(PLANT_TYPES[0]);
  const [selectedDuration, setSelectedDuration] = useState<number>(5);
  const [irrigationHistory, setIrrigationHistory] = useState<IrrigationEvent[]>([]);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [message, setMessage] = useState<string>('');
  const [errorMessage, setErrorMessage] = useState<string>('');

  const apiBaseUrl = (process.env.NEXT_PUBLIC_API_URL || API_BASE).replace(/\/$/, '');

  const fetchIrrigationHistory = useCallback(async () => {
    try {
      const response = await fetch(`${apiBaseUrl}/api/irrigation?limit=10`, {
        credentials: 'include',
        cache: 'no-store',
      });
      if (response.ok) {
        const data = await response.json();
        const sortedData = (data.results || data).sort((a: IrrigationEvent, b: IrrigationEvent) =>
          new Date(b.fecha_inicio).getTime() - new Date(a.fecha_inicio).getTime()
        );
        setIrrigationHistory(sortedData.slice(0, 10));
      } else {
        setErrorMessage('No se pudo cargar el historial de riego.');
      }
    } catch (error) {
      console.error('Error fetching irrigation history:', error);
      setErrorMessage('Error de conexión al cargar historial de riego.');
    } finally {
      setHistoryLoading(false);
    }
  }, [apiBaseUrl]);

  const fetchStatus = useCallback(async () => {
    try {
      const res = await fetch(`${apiBaseUrl}/api/irrigation/status`, {
        credentials: 'include',
        cache: 'no-store',
      });
      if (res.ok) {
        const data = await res.json();
        setStatus(data);
      } else {
        setErrorMessage('No se pudo obtener el estado actual del riego.');
      }
    } catch (error) {
      console.error('Error fetching status:', error);
      setErrorMessage('Error de conexión al consultar estado de riego.');
    } finally {
      setLoading(false);
    }
  }, [apiBaseUrl]);

  useEffect(() => {
    fetchStatus();
    fetchIrrigationHistory();
    const interval = setInterval(fetchStatus, 5000);
    return () => clearInterval(interval);
  }, [fetchStatus, fetchIrrigationHistory]);

  const getPlantDuration = (plantId: string, fallbackDuration: number) => {
    const plantDuration = status.automatic_config?.plants?.[plantId]?.tiempo_riego_segundos;
    if (typeof plantDuration === 'number' && Number.isFinite(plantDuration) && plantDuration > 0) {
      return plantDuration;
    }
    return fallbackDuration;
  };

  const getCsrfToken = (): string => {
    const name = 'csrftoken';
    let cookieValue = '';
    if (document.cookie && document.cookie !== '') {
      const cookies = document.cookie.split(';');
      for (let i = 0; i < cookies.length; i++) {
        const cookie = cookies[i].trim();
        if (cookie.substring(0, name.length + 1) === name + '=') {
          cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
          break;
        }
      }
    }
    return cookieValue;
  };

  const withCsrfHeaders = (headers: HeadersInit = {}): HeadersInit => {
    const csrfToken = getCsrfToken();
    if (csrfToken) {
      return { ...headers, 'X-CSRFToken': csrfToken };
    }
    return headers;
  };

  const handleStart = async () => {
    setActionLoading(true);
    setErrorMessage('');
    setMessage('');
    try {
      const relay = selectedPlant.id === 'fresa' ? 2 : 1;
      const normalizedDuration = Math.max(1, Math.round(Number(selectedDuration) || 0));
      const res = await fetch(`${apiBaseUrl}/api/irrigation/start`, {
        method: 'POST',
        headers: withCsrfHeaders({ 'Content-Type': 'application/json' }),
        credentials: 'include',
        body: JSON.stringify({ plant_type: selectedPlant.id, relay, duration: normalizedDuration }),
      });
      if (res.ok) {
        const data = await res.json().catch(() => ({}));
        const litrosCalculados = Number(data?.liters ?? 0);
        setMessage(
          `Riego manual solicitado para ${selectedPlant.name}: ${normalizedDuration}s (estimado ${litrosCalculados.toFixed(3)}L).`
        );
        await fetchStatus();
        await fetchIrrigationHistory();
      } else {
        const data = await res.json().catch(() => ({}));
        setErrorMessage(data.error || 'No se pudo iniciar el riego manual.');
      }
    } catch (error) {
      console.error('Error starting irrigation:', error);
      setErrorMessage('Error de conexión al iniciar riego manual.');
    } finally {
      setActionLoading(false);
    }
  };

  const handleStop = async () => {
    setActionLoading(true);
    setErrorMessage('');
    setMessage('');
    try {
      const res = await fetch(`${apiBaseUrl}/api/irrigation/stop`, {
        method: 'POST',
        headers: withCsrfHeaders({ 'Content-Type': 'application/json' }),
        credentials: 'include',
        body: JSON.stringify({ relay: status.relay ?? undefined }),
      });
      if (res.ok) {
        setMessage('Parada de riego solicitada correctamente.');
        await fetchStatus();
        await fetchIrrigationHistory();
      } else {
        const data = await res.json().catch(() => ({}));
        setErrorMessage(data.error || 'No se pudo detener el riego.');
      }
    } catch (error) {
      console.error('Error stopping irrigation:', error);
      setErrorMessage('Error de conexión al detener riego.');
    } finally {
      setActionLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <div className="animate-spin rounded-full h-16 w-16 border-t-4 border-b-4 border-green-500 mx-auto mb-4" />
          <p className="text-gray-600">Cargando estado del riego...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="p-8">

      {/* Header */}
      <div className="mb-8">
        <h1 className="text-4xl font-bold mb-2 flex items-center gap-2 text-gray-900">
          <TwemojiEmoji emoji="💧" size={36} />
          <span>Control de Riego</span>
        </h1>
        <p className="text-gray-600">Gestión manual del sistema de riego automatizado</p>
      </div>

      {errorMessage && (
        <div className="mb-6 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-red-800">
          {errorMessage}
        </div>
      )}

      {message && (
        <div className="mb-6 rounded-2xl border border-green-200 bg-green-50 px-4 py-3 text-green-800">
          {message}
        </div>
      )}

      {/* Estado actual */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
        <div className={`bg-gradient-to-br ${
          status.active ? 'from-green-500 to-green-600' : 'from-gray-400 to-gray-500'
        } rounded-3xl shadow-xl p-8 text-white`}>
          <div className="flex items-center gap-4 mb-4">
            <span className="material-icons text-5xl">
              {status.active ? 'check_circle' : 'cancel'}
            </span>
            <div>
              <h2 className="text-2xl font-bold">
                {status.active ? 'Riego Activo' : 'Riego Inactivo'}
              </h2>
              <p className="text-white/80">Estado del sistema</p>
            </div>
          </div>
          {status.active && (
            <div className="mt-4 pt-4 border-t border-white/20">
              <div className="flex items-center gap-2">
                <div className="h-3 w-3 bg-white rounded-full animate-pulse" />
                <p className="text-sm">Sistema regando actualmente</p>
              </div>
            </div>
          )}
        </div>

        <div className="bg-white/80 backdrop-blur-lg rounded-3xl shadow-xl p-8 border border-gray-100">
          <div className="flex items-center gap-4 mb-4">
              <div className="bg-gradient-to-br from-blue-500 to-blue-600 p-3 rounded-2xl flex items-center justify-center">
                <span className="material-icons text-2xl text-white">schedule</span>
              </div>
            <div>
              <h3 className="text-2xl font-bold text-gray-800">{status.total_activations}</h3>
              <p className="text-gray-600">Activaciones totales</p>
            </div>
          </div>
          {status.last_activation && (
            <div className="mt-4 pt-4 border-t border-gray-200">
              <p className="text-sm text-gray-500">Última activación:</p>
              <p className="text-gray-700 font-semibold">
                {new Date(status.last_activation).toLocaleString('es-ES')}
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Estado Riego Automático */}
      <div className="bg-white/80 backdrop-blur-lg rounded-3xl shadow-xl p-6 border border-gray-100 mb-8">
        <div className="flex items-center gap-3 mb-3">
          <TwemojiEmoji emoji="🤖" size={28} />
          <h2 className="text-xl font-bold text-gray-800">Estado del Riego Automático</h2>
        </div>
        <div className="mt-4">
          <p className="text-sm font-semibold text-gray-700 mb-3">Configuración por tipo de planta (solo lectura)</p>
          <div className="overflow-x-auto rounded-xl border border-gray-200">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-100 border-b border-gray-200">
                  <th className="px-4 py-3 text-left font-semibold text-gray-700">Planta</th>
                  <th className="px-4 py-3 text-left font-semibold text-gray-700">Umbral mín.</th>
                  <th className="px-4 py-3 text-left font-semibold text-gray-700">Máx/día</th>
                  <th className="px-4 py-3 text-left font-semibold text-gray-700">Mín entre riegos</th>
                </tr>
              </thead>
              <tbody>
                {PLANT_TYPES.map((plant, idx) => {
                  const plantConfig = status.automatic_config?.plants?.[plant.id];
                  const plantState = status.plants_active?.[plant.id];
                  const isActive = Boolean(plantState?.active);
                  return (
                    <tr
                      key={`config-${plant.id}`}
                      className={`border-b border-gray-200 ${idx % 2 === 0 ? 'bg-white' : 'bg-gray-50'} hover:bg-blue-50`}
                    >
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <TwemojiEmoji emoji={plant.emoji} size={20} />
                          <span className="font-semibold text-gray-800">{plant.name}</span>
                          {isActive && (
                            <span className="ml-2 inline-flex items-center rounded-full bg-green-100 px-2 py-1 text-xs font-semibold text-green-700">
                              Activo
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="px-4 py-3 text-gray-800">{plantConfig?.umbral_humedad_minimo ?? '--'}%</td>
                      <td className="px-4 py-3 text-gray-800">{plantConfig?.max_riegos_dia ?? '--'}</td>
                      <td className="px-4 py-3 text-gray-800">{plantConfig?.tiempo_minimo_entre_riegos ?? '--'} s</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* Selector tipo de planta */}
      <div className="bg-white/80 backdrop-blur-lg rounded-3xl shadow-xl p-8 border border-gray-100 mb-8">
        <div className="flex items-center gap-3 mb-6">
          <TwemojiEmoji emoji="🌱" size={32} />
          <h2 className="text-2xl font-bold text-gray-800">Selecciona el Tipo de Planta</h2>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {PLANT_TYPES.map((plant) => (
            <button
              key={plant.id}
              onClick={() => {
                setSelectedPlant(plant);
                setSelectedDuration(getPlantDuration(plant.id, plant.duration));
              }}
              disabled={status.active}
              className={`p-6 rounded-2xl border-2 transition-all duration-300 text-left ${
                selectedPlant.id === plant.id
                  ? `bg-gradient-to-br ${plant.color} text-white border-transparent shadow-xl scale-105`
                  : `${plant.colorLight} hover:shadow-lg hover:scale-102 ${status.active ? 'opacity-50 cursor-not-allowed' : ''}`
              }`}
            >
              <div className="flex items-start gap-4">
                <TwemojiEmoji emoji={plant.emoji} size={48} />
                <div className="flex-1">
                  <h3 className={`text-xl font-bold mb-1 ${selectedPlant.id === plant.id ? 'text-white' : 'text-gray-800'}`}>
                    {plant.name}
                  </h3>
                  <p className={`text-sm mb-3 ${selectedPlant.id === plant.id ? 'text-white/80' : 'text-gray-600'}`}>
                    {plant.description}
                  </p>
                  <div className="flex flex-wrap gap-2">
                    <span className={`px-3 py-1 rounded-full text-xs font-semibold flex items-center gap-1 ${
                      selectedPlant.id === plant.id ? 'bg-white/20 text-white' : 'bg-gray-200 text-gray-700'
                    }`}>
                      <TwemojiEmoji emoji="💧" size={12} /> Necesidad: {plant.waterNeeds}
                    </span>
                    <span className={`px-3 py-1 rounded-full text-xs font-semibold flex items-center gap-1 ${
                      selectedPlant.id === plant.id ? 'bg-white/20 text-white' : 'bg-gray-200 text-gray-700'
                    }`}>
                      <TwemojiEmoji emoji="⏱️" size={12} /> {getPlantDuration(plant.id, plant.duration)} segundos
                    </span>
                  </div>
                </div>
              </div>
              {selectedPlant.id === plant.id && (
                <div className="mt-4 pt-4 border-t border-white/20 flex items-center gap-2">
                  <span className="material-icons text-xl">check_circle</span>
                  <span className="text-sm font-semibold">Seleccionado</span>
                </div>
              )}
            </button>
          ))}
        </div>
      </div>

      {/* Selector duración */}
      <div className="bg-white/80 backdrop-blur-lg rounded-3xl shadow-xl p-8 border border-gray-100 mb-8">
        <div className="flex items-center gap-3 mb-6">
          <TwemojiEmoji emoji="⏱️" size={32} />
          <h2 className="text-2xl font-bold text-gray-800">Selecciona la Duración del Riego</h2>
        </div>
        <div className="flex flex-wrap gap-3 mb-4">
          {DURATION_OPTIONS.map((seconds) => (
            <button
              key={seconds}
              onClick={() => setSelectedDuration(seconds)}
              disabled={status.active}
              className={`px-6 py-4 rounded-2xl font-bold transition-all duration-300 ${
                selectedDuration === seconds
                  ? 'bg-gradient-to-br from-blue-500 to-cyan-500 text-white shadow-xl scale-105'
                  : `bg-blue-50 border-2 border-blue-200 text-blue-700 hover:shadow-lg hover:scale-102 ${status.active ? 'opacity-50 cursor-not-allowed' : ''}`
              }`}
            >
              <div className="flex flex-col items-center gap-1">
                <span className="text-2xl">{seconds}</span>
                <span className="text-xs">segundos</span>
              </div>
            </button>
          ))}
        </div>
        <div className="flex items-center gap-3">
          <label htmlFor="manual-duration" className="text-sm font-semibold text-gray-700">
            Duración personalizada:
          </label>
          <input
            id="manual-duration"
            type="number"
            min={1}
            step={1}
            value={selectedDuration}
            onChange={(e) => setSelectedDuration(Number(e.target.value) || 1)}
            disabled={status.active}
            className="w-28 rounded-lg border border-gray-300 px-3 py-2 text-gray-800"
          />
          <span className="text-sm text-gray-600">segundos</span>
        </div>
      </div>

      {/* Control Manual */}
      <div className="bg-white/80 backdrop-blur-lg rounded-3xl shadow-xl p-8 border border-gray-100">
        <div className="flex items-center gap-3 mb-6">
          <span className="material-icons text-2xl text-green-600">science</span>
          <h2 className="text-2xl font-bold text-gray-800">Control Manual</h2>
          <span className={`ml-auto px-4 py-2 rounded-full text-sm font-bold flex items-center gap-2 bg-gradient-to-r ${selectedPlant.color} text-white`}>
            <TwemojiEmoji emoji={selectedPlant.emoji} size={16} /> {selectedPlant.name} - {selectedDuration}s
          </span>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <button
            onClick={handleStart}
            disabled={status.active || actionLoading}
            className={`p-8 rounded-2xl font-bold text-xl transition-all duration-300 ${
              status.active || actionLoading
                ? 'bg-gray-200 text-gray-400 cursor-not-allowed'
                : `bg-gradient-to-r ${selectedPlant.color} text-white hover:shadow-2xl hover:scale-105`
            }`}
          >
            <div className="flex flex-col items-center gap-4">
              <span className="material-icons text-6xl">play_arrow</span>
              <span>Regar {selectedPlant.name}</span>
              <span className="text-sm font-normal opacity-80 flex items-center gap-1 justify-center flex-wrap">
                <TwemojiEmoji emoji="⏱️" size={14} /> {selectedDuration}s &nbsp;•&nbsp;
                <TwemojiEmoji emoji="💧" size={14} /> Litros calculados automáticamente
              </span>
              {actionLoading && (
                <div className="animate-spin rounded-full h-6 w-6 border-t-2 border-b-2 border-white" />
              )}
            </div>
          </button>

          <button
            onClick={handleStop}
            disabled={!status.active || actionLoading}
            className={`p-8 rounded-2xl font-bold text-xl transition-all duration-300 ${
              !status.active || actionLoading
                ? 'bg-gray-200 text-gray-400 cursor-not-allowed'
                : 'bg-gradient-to-r from-red-500 to-red-600 text-white hover:shadow-2xl hover:scale-105'
            }`}
          >
            <div className="flex flex-col items-center gap-4">
              <span className="material-icons text-6xl">stop</span>
              <span>Detener Riego</span>
              {actionLoading && (
                <div className="animate-spin rounded-full h-6 w-6 border-t-2 border-b-2 border-white" />
              )}
            </div>
          </button>
        </div>
      </div>

      {/* Historial de Riego */}
      <div className="mt-8 bg-white/90 backdrop-blur-md rounded-3xl shadow-xl p-6 border border-white/20">
        <div className="flex items-center gap-3 mb-6">
          <div className="p-3 bg-gradient-to-br from-blue-500 to-cyan-500 rounded-xl flex items-center justify-center">
            <span className="material-icons text-xl text-white">schedule</span>
          </div>
          <div>
            <h2 className="text-xl font-bold text-gray-800 flex items-center gap-2">
              <TwemojiEmoji emoji="📋" size={20} /> Historial de Riego
            </h2>
            <p className="text-sm text-gray-600">Últimos 10 eventos de riego</p>
          </div>
        </div>

        {historyLoading ? (
          <div className="flex items-center justify-center py-8">
            <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-blue-500" />
            <span className="ml-3 text-gray-600">Cargando historial...</span>
          </div>
        ) : irrigationHistory.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            <span className="material-icons text-5xl text-gray-400 block mb-3">science</span>
            <p>No hay eventos de riego registrados</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gradient-to-r from-blue-50 to-cyan-50 border-b border-blue-200">
                  <th className="px-4 py-3 text-left font-semibold text-gray-700">
                    <span className="flex items-center gap-1"><TwemojiEmoji emoji="📅" size={14} /> Fecha Inicio</span>
                  </th>
                  <th className="px-4 py-3 text-left font-semibold text-gray-700">
                    <span className="flex items-center gap-1"><TwemojiEmoji emoji="🏁" size={14} /> Fecha Fin</span>
                  </th>
                  <th className="px-4 py-3 text-center font-semibold text-gray-700">
                    <span className="flex items-center justify-center gap-1"><TwemojiEmoji emoji="💧" size={14} /> Litros</span>
                  </th>
                  <th className="px-4 py-3 text-center font-semibold text-gray-700">
                    <span className="flex items-center justify-center gap-1"><TwemojiEmoji emoji="⏱️" size={14} /> Duración</span>
                  </th>
                  <th className="px-4 py-3 text-center font-semibold text-gray-700">
                    <span className="flex items-center justify-center gap-1"><TwemojiEmoji emoji="🤖" size={14} /> Modo</span>
                  </th>
                  <th className="px-4 py-3 text-left font-semibold text-gray-700">
                    <span className="flex items-center gap-1"><TwemojiEmoji emoji="📝" size={14} /> Razón</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {irrigationHistory.map((event, index) => {
                  const fechaInicio = new Date(event.fecha_inicio);
                  const fechaFin = event.fecha_fin ? new Date(event.fecha_fin) : null;

                  const formatDate = (date: Date) => {
                    const year = date.getFullYear();
                    const month = String(date.getMonth() + 1).padStart(2, '0');
                    const day = String(date.getDate()).padStart(2, '0');
                    const hours = String(date.getHours()).padStart(2, '0');
                    const minutes = String(date.getMinutes()).padStart(2, '0');
                    const secs = String(date.getSeconds()).padStart(2, '0');
                    return `${year}-${month}-${day} ${hours}:${minutes}:${secs}`;
                  };

                  const litros = event.litros ||
                    (event.duracion_real_segundos
                      ? (event.duracion_real_segundos / 60 * 0.5).toFixed(2)
                      : (event.duracion_planificada_segundos / 60 * 0.5).toFixed(2));

                  return (
                    <tr
                      key={event.id}
                      className={`border-b border-gray-100 hover:bg-blue-50/50 transition-colors ${
                        index % 2 === 0 ? 'bg-white' : 'bg-gray-50/50'
                      }`}
                    >
                      <td className="px-4 py-3">
                        <div className="font-mono text-xs text-gray-900 bg-gray-100 rounded px-2 py-1 inline-block">
                          {formatDate(fechaInicio)}
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        {fechaFin ? (
                          <div className="font-mono text-xs bg-green-100 text-green-700 rounded px-2 py-1 inline-block">
                            {formatDate(fechaFin)}
                          </div>
                        ) : (
                          <span className="text-xs bg-yellow-100 text-yellow-700 rounded px-2 py-1">
                            En progreso...
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-center">
                        <span className="inline-flex items-center gap-1 bg-blue-100 text-blue-700 font-semibold rounded-full px-3 py-1">
                          <TwemojiEmoji emoji="💧" size={14} /> {litros}L
                        </span>
                      </td>
                      <td className="px-4 py-3 text-center">
                        <span className="text-gray-700">
                          {event.duracion_real_segundos
                            ? `${event.duracion_real_segundos}s`
                            : `${event.duracion_planificada_segundos}s (plan)`}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-center">
                        <span className={`inline-flex items-center gap-1 rounded-full px-2 py-1 text-xs font-medium ${
                          event.automatico ? 'bg-purple-100 text-purple-700' : 'bg-orange-100 text-orange-700'
                        }`}>
                          <TwemojiEmoji emoji={event.automatico ? '🤖' : '👤'} size={14} />
                          {event.automatico ? 'Auto' : 'Manual'}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <span className="text-gray-600 text-xs">
                          {event.razon || 'Sin razón especificada'}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        <div className="mt-4 flex justify-end">
          <button
            onClick={() => {
              setHistoryLoading(true);
              fetchIrrigationHistory();
            }}
            className="flex items-center gap-2 px-4 py-2 bg-blue-100 hover:bg-blue-200 text-blue-700 rounded-lg transition-colors text-sm font-medium"
          >
            <span className="material-icons text-base">refresh</span>
            Actualizar historial
          </button>
        </div>
      </div>

    </div>
  );
}