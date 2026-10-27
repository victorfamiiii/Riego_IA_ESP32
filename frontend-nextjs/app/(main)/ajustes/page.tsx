'use client';

import { useEffect, useState } from 'react';
import { useFCM, setNotificationsEnabled, registerNotifications } from '../../../lib/useFCM';
import TwemojiEmoji from '../../components/TwemojiEmoji';

const API_BASE = 'https://riegoesp32.victorfg.work';

interface IrrigationConfig {
  id?: number;
  tipo_planta?: string;
  activo?: boolean;
  riego_automatico_activo?: boolean;
  modo_riego?: string;
  mediciones_para_media?: number;
  umbral_humedad_minimo?: number;
  tiempo_riego_segundos?: number;
  max_riegos_dia?: number;
  tiempo_minimo_entre_riegos?: number;
}

type PlantId = 'lechuga' | 'fresa';

interface PlantInfo {
  id: PlantId;
  name: string;
  emoji: string;
  accentSoft: string;
  iconClass: string;
  buttonClass: string;
  buttonLoadingClass: string;
}

const PLANTS: PlantInfo[] = [
  {
    id: 'lechuga',
    name: 'Lechugas',
    emoji: '🥬',
    accentSoft: 'bg-emerald-50 border-emerald-200',
    iconClass: 'bg-emerald-100 text-emerald-700',
    buttonClass:
      'bg-emerald-700 hover:bg-emerald-800 text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-emerald-700',
    buttonLoadingClass: 'bg-gray-400 text-white cursor-not-allowed opacity-75',
  },
  {
    id: 'fresa',
    name: 'Fresas',
    emoji: '🍓',
    accentSoft: 'bg-rose-50 border-rose-200',
    iconClass: 'bg-rose-100 text-rose-700',
    buttonClass:
      'bg-rose-700 hover:bg-rose-800 text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-rose-700',
    buttonLoadingClass: 'bg-gray-400 text-white cursor-not-allowed opacity-75',
  },
];

export default function AjustesPage() {
  const { notificationsEnabled } = useFCM();

  const handleNotificationsToggle = async () => {
    const newState = !notificationsEnabled;
    if (newState) {
      try {
        const success = await registerNotifications();
        setMessage(success ? 'Notificaciones activadas correctamente.' : 'Error al activar notificaciones.');
      } catch (error) {
        console.error('Error activating notifications:', error);
        setMessage('Error al activar notificaciones.');
      }
    } else {
      setNotificationsEnabled(false);
      setMessage('Notificaciones pausadas.');
    }
    setTimeout(() => setMessage(''), 5000);
  };

  const [configs, setConfigs] = useState<Record<PlantId, IrrigationConfig | null>>({
    lechuga: null,
    fresa: null,
  });
  const [loadingConfigs, setLoadingConfigs] = useState(true);
  const [savingPlant, setSavingPlant] = useState<PlantId | null>(null);
  const [message, setMessage] = useState('');
  const [errorMessage, setErrorMessage] = useState('');

  const getCsrfToken = (): string => {
    if (typeof document === 'undefined') return '';
    const cookie = document.cookie
      .split(';')
      .map((row) => row.trim())
      .find((row) => row.startsWith('csrftoken='));
    return cookie ? decodeURIComponent(cookie.split('=')[1]) : '';
  };

  const ensureCsrfToken = async () => {
    const current = getCsrfToken();
    if (current) return current;
    await fetch(`${API_BASE}/api/auth/csrf`, {
      credentials: 'include',
      cache: 'no-store',
    });
    return getCsrfToken();
  };

  const withCsrfHeaders = async (baseHeaders: Record<string, string> = {}) => {
    const headers = { ...baseHeaders };
    const csrfToken = await ensureCsrfToken();
    if (csrfToken) headers['X-CSRFToken'] = csrfToken;
    return headers;
  };

  useEffect(() => {
    const fetchConfigs = async () => {
      try {
        const responses = await Promise.all(
          PLANTS.map((plant) =>
            fetch(`${API_BASE}/api/irrigation-config/active?tipo_planta=${plant.id}`, {
              credentials: 'include',
              cache: 'no-store',
            })
          )
        );

        const nextConfigs: Record<PlantId, IrrigationConfig | null> = {
          lechuga: null,
          fresa: null,
        };

        for (let index = 0; index < responses.length; index += 1) {
          const response = responses[index];
          if (response.ok) {
            const data = await response.json();
            nextConfigs[PLANTS[index].id] = data;
          }
        }

        setConfigs(nextConfigs);
        setErrorMessage('');
      } catch (error) {
        console.error('Error loading irrigation configs:', error);
        setErrorMessage('No se pudieron cargar las configuraciones de riego.');
      } finally {
        setLoadingConfigs(false);
      }
    };

    fetchConfigs();
  }, []);

  const updatePlantConfig = (plantId: PlantId, value: number) => {
    setConfigs((current) => ({
      ...current,
      [plantId]: {
        ...(current[plantId] || {}),
        tipo_planta: plantId,
        mediciones_para_media: value,
      },
    }));
  };

  const savePlantConfig = async (plantId: PlantId) => {
    const current = configs[plantId];
    const value = Number(current?.mediciones_para_media ?? 4);

    if (!Number.isFinite(value) || value < 1) {
      setErrorMessage('El número de mediciones debe ser mayor o igual a 1.');
      return;
    }

    try {
      setSavingPlant(plantId);
      setErrorMessage('');
      setMessage('');

      const csrfHeaders = await withCsrfHeaders({ 'Content-Type': 'application/json' });

      const res = await fetch(`${API_BASE}/api/measurements/irrigation_config`, {
        method: 'POST',
        credentials: 'include',
        headers: csrfHeaders,
        body: JSON.stringify({
          tipo_planta: plantId,
          mediciones_para_media: value,
        }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.error || 'No se pudo guardar la configuración.');
      }

      const payload = await res.json().catch(() => ({}));
      if (payload?.config) {
        setConfigs((current) => ({
          ...current,
          [plantId]: {
            ...(current[plantId] || {}),
            ...payload.config,
            tipo_planta: plantId,
          },
        }));
      }

      setMessage(`Configuración de ${plantId === 'lechuga' ? 'lechugas' : 'fresas'} guardada correctamente.`);
    } catch (error) {
      console.error('Error saving irrigation config:', error);
      setErrorMessage(error instanceof Error ? error.message : 'Error al guardar la configuración.');
    } finally {
      setSavingPlant(null);
    }
  };

  return (
    <div className="p-8">

      {/* Header */}
      <div className="mb-8">
        <h1 className="text-4xl font-bold mb-2 flex items-center gap-2 text-gray-900">
          <TwemojiEmoji emoji="⚙️" size={32} />
          <span>Ajustes</span>
        </h1>
        <p className="text-gray-600">Configuración del sistema y preferencias</p>
      </div>

      <div className="space-y-6">

        {errorMessage && (
          <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-red-800">
            {errorMessage}
          </div>
        )}

        {message && (
          <div className="rounded-2xl border border-green-200 bg-green-50 px-4 py-3 text-green-800">
            {message}
          </div>
        )}

        {/* Riego automático por planta */}
        <div className="bg-white/80 backdrop-blur-lg rounded-3xl shadow-xl p-6 border border-gray-100">
          <div className="flex items-center gap-4 mb-6">
            <div className="bg-emerald-500 p-3 rounded-2xl flex items-center justify-center">
              <span className="material-icons text-2xl text-white">science</span>
            </div>
            <div>
              <h2 className="text-2xl font-bold text-gray-800">Riego automático por planta</h2>
              <p className="text-gray-600 text-sm">
                Modifica cuántas mediciones se usan para calcular la media de riego automático.
              </p>
            </div>
          </div>

          {loadingConfigs ? (
            <div className="py-10 flex items-center justify-center">
              <div className="text-center">
                <div className="animate-spin rounded-full h-10 w-10 border-t-4 border-b-4 border-green-500 mx-auto mb-3" />
                <p className="text-gray-600">Cargando configuración de riego...</p>
              </div>
            </div>
          ) : (
            <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
              {PLANTS.map((plant) => {
                const config = configs[plant.id];
                const readingsWindow = Number(config?.mediciones_para_media ?? 4);

                return (
                  <section key={plant.id} className={`rounded-3xl border shadow-lg p-6 ${plant.accentSoft}`}>
                    <div className="flex items-start justify-between gap-4 mb-5">
                      <div className="flex items-center gap-4 min-w-0">
                        <div className={`h-14 w-14 rounded-2xl flex items-center justify-center shadow-md ${plant.iconClass}`}>
                          <TwemojiEmoji emoji={plant.emoji} size={32} />
                        </div>
                        <div className="min-w-0">
                          <h3 className="text-2xl font-bold text-gray-900">{plant.name}</h3>
                          <p className="text-sm text-gray-600">Configuración activa para el riego</p>
                        </div>
                      </div>
                    </div>

                    {/* Modo de riego (read-only) */}
                    <div className="rounded-2xl bg-white/85 p-4 border border-white/60 shadow-sm mb-4">
                      <p className="block text-xs font-semibold uppercase tracking-wide text-gray-500 mb-2">
                        Modo de riego
                      </p>
                      <div className="flex items-center gap-2">
                        {config?.modo_riego === 'ia' && (
                          <span className="inline-flex items-center gap-2 rounded-full px-4 py-2 text-sm font-semibold bg-purple-100 text-purple-800">
                            <TwemojiEmoji emoji="🤖" size={16} /> Inteligencia Artificial
                          </span>
                        )}
                        {config?.modo_riego === 'manual' && (
                          <span className="inline-flex items-center gap-2 rounded-full px-4 py-2 text-sm font-semibold bg-red-100 text-red-800">
                            <TwemojiEmoji emoji="✋" size={16} /> Manual
                          </span>
                        )}
                        {(config?.modo_riego === 'umbral' || !config?.modo_riego) && (
                          <span className="inline-flex items-center gap-2 rounded-full px-4 py-2 text-sm font-semibold bg-blue-100 text-blue-800">
                            <TwemojiEmoji emoji="🌊" size={16} /> Automático
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Selector de Mediciones */}
                    <div className="rounded-2xl bg-white/85 p-4 border border-white/60 shadow-sm mb-4">
                      <label
                        htmlFor={`mediciones-${plant.id}`}
                        className="block text-xs font-semibold uppercase tracking-wide text-gray-500 mb-2"
                      >
                        Mediciones para la media
                      </label>
                      <div className="flex flex-col md:flex-row md:items-center gap-3">
                        <input
                          id={`mediciones-${plant.id}`}
                          type="number"
                          min={1}
                          step={1}
                          value={readingsWindow}
                          onChange={(event) => updatePlantConfig(plant.id, Number(event.target.value) || 1)}
                          className="w-full md:w-40 rounded-2xl border border-gray-300 bg-white px-4 py-3 text-gray-900 focus:border-green-500 focus:outline-none focus:ring-2 focus:ring-green-500/20"
                        />
                        <p className="text-sm text-gray-600">
                          Este valor controla la media usada para decidir el riego y el número de lecturas que ves en el dashboard.
                        </p>
                      </div>
                    </div>

                    <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
                      <p className="text-sm text-gray-600">
                        Se mostrará como{' '}
                        <span className="font-semibold text-gray-800">basado en {readingsWindow} valores</span>{' '}
                        en la página principal.
                      </p>
                      <button
                        type="button"
                        onClick={() => savePlantConfig(plant.id)}
                        disabled={savingPlant === plant.id}
                        className={`inline-flex items-center justify-center gap-2 rounded-2xl px-6 py-3 font-semibold text-white shadow-lg transition-all active:scale-95 min-h-12 ${
                          savingPlant === plant.id
                            ? 'bg-gray-400 cursor-not-allowed opacity-75'
                            : plant.buttonClass
                        }`}
                      >
                        {savingPlant === plant.id ? (
                          <>
                            <span className="material-icons text-lg animate-spin">refresh</span>
                            Guardando...
                          </>
                        ) : (
                          <>
                            <span className="material-icons text-lg">check_circle</span>
                            Guardar configuración
                          </>
                        )}
                      </button>
                    </div>
                  </section>
                );
              })}
            </div>
          )}
        </div>

        {/* Notificaciones */}
        <div className="bg-white/80 backdrop-blur-lg rounded-3xl shadow-xl p-6 border border-gray-100">
          <div className="flex items-center gap-4 mb-6">
            <div className="bg-blue-500 p-3 rounded-2xl flex items-center justify-center">
              <span className="material-icons text-2xl text-white">notifications</span>
            </div>
            <div>
              <h2 className="text-2xl font-bold text-gray-800">Notificaciones</h2>
              <p className="text-gray-600 text-sm">Gestiona las alertas del sistema</p>
            </div>
          </div>

          <div className="space-y-4">
            <div className="flex items-center justify-between p-4 bg-gray-50 rounded-xl">
              <div className="flex-1">
                <p className="font-semibold text-gray-800">Activar notificaciones</p>
                <p className="text-sm text-gray-600">Recibe alertas sobre el estado del sistema</p>
              </div>
              <button
                type="button"
                onClick={handleNotificationsToggle}
                aria-label={notificationsEnabled ? 'Desactivar notificaciones' : 'Activar notificaciones'}
                className={`relative w-20 h-10 rounded-full transition-colors flex-shrink-0 ml-4 ${
                  notificationsEnabled ? 'bg-green-500' : 'bg-gray-300'
                }`}
              >
                <div
                  className={`absolute top-1 left-1 w-8 h-8 bg-white rounded-full transition-transform ${
                    notificationsEnabled ? 'translate-x-10' : ''
                  }`}
                />
              </button>
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}