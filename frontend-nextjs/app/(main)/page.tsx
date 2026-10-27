'use client';

import { useState, useEffect } from 'react';
import Image from 'next/image';

// ─── Twemoji helper ──────────────────────────────────────────────────────────
function TwemojiEmoji({ emoji, size = 20, className = '' }: { emoji: string; size?: number; className?: string }) {
  const codePoint = [...emoji]
    .map((c) => c.codePointAt(0)!.toString(16).padStart(4, '0'))
    .filter((c) => c !== 'fe0f')
    .join('-');
  return (
    <Image
      src={`https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/svg/${codePoint}.svg`}
      alt={emoji}
      width={size}
      height={size}
      className={className}
      style={{ display: 'inline-block', verticalAlign: 'middle' }}
      loading="lazy"
      unoptimized
    />
  );
}
// ─────────────────────────────────────────────────────────────────────────────

interface SoilReading {
  id: number;
  device?: number;
  device_name?: string;
  tipo_planta?: string | null;
  humedad_suelo: number;
  humedad_suelo_raw?: number;
  created_at: string;
  fecha?: string;
}

interface Stats {
  total_mediciones: number;
  temperatura_promedio: number;
  humedad_promedio: number;
  luminosidad_promedio?: number;
  mediciones_24h: number;
  ultima_medicion?: {
    temperatura: number;
    humedad: number;
    luminosidad?: number;
    fecha: string;
  };
}

interface IrrigationEvent {
  id: number;
  fecha_inicio: string;
  fecha_fin?: string | null;
  tipo_planta?: string | null;
  duracion_planificada_segundos?: number;
  duracion_real_segundos?: number | null;
  automatico?: boolean;
  razon?: string;
}

interface IrrigationConfig {
  riego_automatico_activo?: boolean;
  riego_ia_activo?: boolean;
  ia_activo?: boolean;
  modo_riego?: string | null;
  mediciones_para_media?: number;
  umbral_humedad_minimo?: number;
  tiempo_riego_segundos?: number;
  max_riegos_dia?: number;
  tiempo_minimo_entre_riegos?: number;
}

type IrrigationMode = 'automatico' | 'desactivado' | 'ia';

interface PlantTypeSummary {
  id: string;
  name: string;
  emoji: string;
  accent: string;
  accentSoft: string;
}

interface PlantSummary {
  plant: PlantTypeSummary;
  readingsCount: number;
  soilAverage: number | null;
  lastIrrigation: IrrigationEvent | null;
  irrigationMode: IrrigationMode;
  threshold: number | null;
  readingsWindow: number;
}

interface WaterTank {
  percentage: number;
  liters: number;
  capacity: number;
  distancia: number | null;
  distancia_minima: number;
  distancia_maxima: number;
  last_update: string;
}

interface WeatherHourBlock {
  hora: string;
  periodo?: string | null;
  prob_lluvia?: number | null;
  cielo?: string;
  temperatura?: number | null;
  humedad?: number | null;
  viento?: number | null;
}

interface WeatherDayForecast {
  fecha: string;
  dia_semana?: string;
  temperatura_maxima?: number | null;
  temperatura_minima?: number | null;
  humedad_maxima?: number | null;
  humedad_minima?: number | null;
  probabilidad_lluvia_maxima?: number | null;
  cielo_resumen: string;
  bloques: WeatherHourBlock[];
}

interface WeatherForecast {
  municipio_id: string;
  municipio_nombre: string;
  elaborado?: string;
  version?: string;
  dias: WeatherDayForecast[];
  bloques_hoy: WeatherHourBlock[];
}

const PLANT_TYPES: PlantTypeSummary[] = [
  {
    id: 'lechuga',
    name: 'Lechugas',
    emoji: '🥬',
    accent: 'from-emerald-500 to-lime-500',
    accentSoft: 'bg-emerald-50 border-emerald-200',
  },
  {
    id: 'fresa',
    name: 'Fresas',
    emoji: '🍓',
    accent: 'from-rose-500 to-pink-500',
    accentSoft: 'bg-rose-50 border-rose-200',
  },
];

const API_BASE = 'https://riegoesp32.victorfg.work';
const MEASUREMENTS_STATS_ENDPOINT = `${API_BASE}/api/measurements/stats`;
const FORECAST_CACHE_KEY = 'weather_forecast_cache_v1';

const STATS_REFRESH_INTERVAL = 60 * 1000;
const FORECAST_REFRESH_INTERVAL = 60 * 60 * 1000;

const STATS_INITIAL_DELAY = 0;
const PLANT_SUMMARY_INITIAL_DELAY = 1500;
const WATER_TANK_INITIAL_DELAY = 3000;
const FORECAST_INITIAL_DELAY = 4500;

export default function Home() {
  const [mounted, setMounted] = useState(false);

  const [stats, setStats] = useState<Stats | null>(null);
  const [statsError, setStatsError] = useState<Error | null>(null);
  const [statsLoading, setStatsLoading] = useState(true);

  const [soilReadings, setSoilReadings] = useState<SoilReading[]>([]);
  const [soilError, setSoilError] = useState<Error | null>(null);
  const [soilLoading, setSoilLoading] = useState(true);

  const [irrigationEvents, setIrrigationEvents] = useState<IrrigationEvent[]>([]);
  const [irrigationError, setIrrigationError] = useState<Error | null>(null);
  const [irrigationLoading, setIrrigationLoading] = useState(true);

  const [plantConfigs, setPlantConfigs] = useState<Record<string, IrrigationConfig | null>>({
    lechuga: null,
    fresa: null,
  });
  const [configError, setConfigError] = useState<Error | null>(null);
  const [configLoading, setConfigLoading] = useState(true);

  const [waterTank, setWaterTank] = useState<WaterTank | null>(null);
  const [forecast, setForecast] = useState<WeatherForecast | null>(null);
  const [forecastLoading, setForecastLoading] = useState(true);
  const [forecastError, setForecastError] = useState<Error | null>(null);

  const normalizePlantType = (value?: string | null) => {
    const raw = (value || '').trim().toLowerCase();
    if (raw === 'fresa' || raw === 'fresas') return 'fresa';
    if (raw === 'lechuga' || raw === 'lechugas') return 'lechuga';
    return raw;
  };

  const formatDateTime = (value?: string | null) => {
    if (!value) return 'Sin datos';
    return new Date(value).toLocaleString('es-ES', {
      dateStyle: 'short',
      timeStyle: 'short',
    });
  };

  const canPollNow = () => {
    if (typeof document === 'undefined') return true;
    return document.visibilityState === 'visible';
  };

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (!mounted) return;
    let isFetching = false;
    const fetchStats = async () => {
      if (!canPollNow() || isFetching) return;
      isFetching = true;
      try {
        const measurementsRes = await fetch(MEASUREMENTS_STATS_ENDPOINT, { cache: 'no-store' });
        if (!measurementsRes.ok) throw new Error(`Measurements API error: ${measurementsRes.status}`);
        const measurementsData = await measurementsRes.json();
        setStats({ ...measurementsData });
        setStatsError(null);
      } catch (error) {
        setStatsError(error as Error);
      } finally {
        isFetching = false;
        setStatsLoading(false);
      }
    };
    const initialTimeout = setTimeout(fetchStats, STATS_INITIAL_DELAY);
    const interval = setInterval(fetchStats, STATS_REFRESH_INTERVAL);
    const onVisibilityChange = () => { if (document.visibilityState === 'visible') fetchStats(); };
    document.addEventListener('visibilitychange', onVisibilityChange);
    return () => {
      clearTimeout(initialTimeout);
      clearInterval(interval);
      document.removeEventListener('visibilitychange', onVisibilityChange);
    };
  }, [mounted]);

  useEffect(() => {
    if (!mounted) return;
    let isFetching = false;
    const fetchPlantSummary = async () => {
      if (!canPollNow() || isFetching) return;
      isFetching = true;
      try {
        const [soilResult, irrigationResult, lechugaConfigResult, fresaConfigResult] = await Promise.allSettled([
          fetch(`${API_BASE}/api/soil`, { cache: 'no-store' }),
          fetch(`${API_BASE}/api/irrigation/recent?limit=20`, { cache: 'no-store' }),
          fetch(`${API_BASE}/api/irrigation-config/active?tipo_planta=lechuga`, { cache: 'no-store' }),
          fetch(`${API_BASE}/api/irrigation-config/active?tipo_planta=fresa`, { cache: 'no-store' }),
        ]);
        if (soilResult.status === 'fulfilled') {
          const response = soilResult.value;
          if (!response.ok) throw new Error(`Soil API error: ${response.status}`);
          const data = await response.json();
          setSoilReadings(Array.isArray(data) ? data : data?.results || []);
          setSoilError(null);
        }
        if (irrigationResult.status === 'fulfilled') {
          const response = irrigationResult.value;
          if (!response.ok) throw new Error(`Irrigation API error: ${response.status}`);
          const data = await response.json();
          setIrrigationEvents(Array.isArray(data) ? data : data?.results || data?.eventos || []);
          setIrrigationError(null);
        }
        const configs: Record<string, IrrigationConfig | null> = { lechuga: null, fresa: null };
        if (lechugaConfigResult.status === 'fulfilled' && lechugaConfigResult.value.ok)
          configs.lechuga = await lechugaConfigResult.value.json();
        if (fresaConfigResult.status === 'fulfilled' && fresaConfigResult.value.ok)
          configs.fresa = await fresaConfigResult.value.json();
        setPlantConfigs(configs);
        setConfigError(null);
      } catch (error) {
        const err = error as Error;
        if (!soilReadings.length) setSoilError(err);
        if (!irrigationEvents.length) setIrrigationError(err);
        setConfigError(err);
      } finally {
        isFetching = false;
        setSoilLoading(false);
        setIrrigationLoading(false);
        setConfigLoading(false);
      }
    };
    const initialTimeout = setTimeout(fetchPlantSummary, PLANT_SUMMARY_INITIAL_DELAY);
    const interval = setInterval(fetchPlantSummary, STATS_REFRESH_INTERVAL);
    const onVisibilityChange = () => { if (document.visibilityState === 'visible') fetchPlantSummary(); };
    document.addEventListener('visibilitychange', onVisibilityChange);
    return () => {
      clearTimeout(initialTimeout);
      clearInterval(interval);
      document.removeEventListener('visibilitychange', onVisibilityChange);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mounted]);

  useEffect(() => {
    if (!mounted) return;
    let isFetching = false;
    const fetchWaterTank = async () => {
      if (!canPollNow() || isFetching) return;
      isFetching = true;
      try {
        const res = await fetch(`${API_BASE}/api/water-tank/status`, { cache: 'no-store', credentials: 'include' });
        if (res.ok) setWaterTank(await res.json());
      } catch (error) {
        console.error('❌ Water tank error:', error);
      } finally {
        isFetching = false;
      }
    };
    const initialTimeout = setTimeout(fetchWaterTank, WATER_TANK_INITIAL_DELAY);
    const interval = setInterval(fetchWaterTank, STATS_REFRESH_INTERVAL);
    const onVisibilityChange = () => { if (document.visibilityState === 'visible') fetchWaterTank(); };
    document.addEventListener('visibilitychange', onVisibilityChange);
    return () => {
      clearTimeout(initialTimeout);
      clearInterval(interval);
      document.removeEventListener('visibilitychange', onVisibilityChange);
    };
  }, [mounted]);

  useEffect(() => {
    if (!mounted) return;
    let isFetching = false;
    const fetchForecast = async () => {
      if (!canPollNow() || isFetching) return;
      isFetching = true;
      try {
        const cachedRaw = window.localStorage.getItem(FORECAST_CACHE_KEY);
        if (cachedRaw && !forecast) {
          try {
            const cached = JSON.parse(cachedRaw) as WeatherForecast;
            if (cached?.dias?.length) { setForecast(cached); setForecastLoading(false); }
          } catch { /* ignorar cache corrupta */ }
        }
        const res = await fetch(
          `${API_BASE}/api/weather/forecast?municipio_id=49275&municipio_nombre=Zamora&days=5`,
          { cache: 'no-store' }
        );
        if (res.status === 503) {
          if (forecast) { setForecastError(null); return; }
          const staleRaw = window.localStorage.getItem(FORECAST_CACHE_KEY);
          if (staleRaw) {
            try {
              const stale = JSON.parse(staleRaw) as WeatherForecast;
              if (stale?.dias?.length) { setForecast(stale); setForecastError(null); return; }
            } catch { /* ignorar */ }
          }
        }
        if (!res.ok) throw new Error(`Forecast API error: ${res.status}`);
        const data = await res.json();
        setForecast(data);
        window.localStorage.setItem(FORECAST_CACHE_KEY, JSON.stringify(data));
        setForecastError(null);
      } catch (error) {
        setForecastError(error as Error);
      } finally {
        isFetching = false;
        setForecastLoading(false);
      }
    };
    const initialTimeout = setTimeout(fetchForecast, FORECAST_INITIAL_DELAY);
    const interval = setInterval(fetchForecast, FORECAST_REFRESH_INTERVAL);
    const onVisibilityChange = () => { if (document.visibilityState === 'visible') fetchForecast(); };
    document.addEventListener('visibilitychange', onVisibilityChange);
    return () => {
      clearTimeout(initialTimeout);
      clearInterval(interval);
      document.removeEventListener('visibilitychange', onVisibilityChange);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mounted]);

  if (!mounted) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gradient-to-br from-green-50 to-blue-50">
        <div className="text-center">
          <div className="animate-spin rounded-full h-16 w-16 border-t-4 border-b-4 border-green-500 mx-auto mb-4" />
          <p className="text-gray-600">Cargando aplicación...</p>
        </div>
      </div>
    );
  }

  if (statsLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gradient-to-br from-green-50 to-blue-50">
        <div className="text-center">
          <div className="animate-spin rounded-full h-16 w-16 border-t-4 border-b-4 border-green-500 mx-auto mb-4" />
          <p className="text-gray-600">Cargando datos...</p>
        </div>
      </div>
    );
  }

  if (statsError) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gradient-to-br from-red-50 to-orange-50">
        <div className="text-center p-8 bg-white rounded-2xl shadow-xl">
          <p className="text-2xl text-red-600 mb-4 flex items-center justify-center gap-2">
            <TwemojiEmoji emoji="❌" size={28} /> Error al cargar datos
          </p>
          <p className="text-gray-600 mb-4">Stats Error: {statsError?.message || 'N/A'}</p>
          <button
            onClick={() => window.location.reload()}
            className="px-6 py-3 bg-red-500 hover:bg-red-600 text-white rounded-xl flex items-center gap-2 mx-auto"
          >
            <TwemojiEmoji emoji="🔄" size={18} /> Reintentar
          </button>
        </div>
      </div>
    );
  }

  const getWeatherVisual = (text: string = '', probability: number | null = null) => {
    const lower = text.toLowerCase();
    if (lower.includes('torment')) return { iconName: 'bolt', gradientClass: 'from-violet-500 to-indigo-600' };
    if ((probability ?? 0) >= 70 || (lower.includes('lluv') && !lower.includes('escas')))
      return { iconName: 'cloud_download', gradientClass: 'from-sky-500 to-blue-600' };
    if (lower.includes('lluv') || lower.includes('interval') || lower.includes('nub'))
      return { iconName: 'cloud_queue', gradientClass: 'from-gray-500 to-slate-600' };
    if (lower.includes('despej') || lower.includes('soleado'))
      return { iconName: 'wb_sunny', gradientClass: 'from-amber-400 to-orange-500' };
    return { iconName: 'cloud', gradientClass: 'from-gray-500 to-slate-600' };
  };

  const isMeaningfulWeatherText = (text?: string | null) => {
    if (!text) return false;
    return text.trim().toLowerCase() !== 'sin datos';
  };

  const getDailyWeatherVisual = (day: WeatherDayForecast) => {
    const forecastText =
      day.bloques.find((block) => isMeaningfulWeatherText(block.cielo))?.cielo || day.cielo_resumen || '';
    const forecastProbability = Math.max(
      day.probabilidad_lluvia_maxima ?? 0,
      ...day.bloques.map((block) => block.prob_lluvia ?? 0)
    );
    return getWeatherVisual(forecastText, forecastProbability > 0 ? forecastProbability : null);
  };

  const resolveIrrigationMode = (config: IrrigationConfig | null): IrrigationMode => {
    const modeRaw = String(config?.modo_riego || '').trim().toLowerCase();
    const modeIsIA = modeRaw === 'ia' || modeRaw === 'ai' || modeRaw === 'inteligente';
    const iaEnabled = modeIsIA || config?.riego_ia_activo === true || config?.ia_activo === true;
    if (iaEnabled) return 'ia';
    if (config?.riego_automatico_activo === true) return 'automatico';
    return 'desactivado';
  };

  const plantSummaries: PlantSummary[] = PLANT_TYPES.map((plant) => {
    const config = plantConfigs[plant.id];
    const readingsWindow = Math.max(1, Number(config?.mediciones_para_media ?? 4));
    const plantReadings = soilReadings
      .filter((reading) => normalizePlantType(reading.tipo_planta) === plant.id)
      .slice(0, readingsWindow);
    const soilAverage = plantReadings.length
      ? plantReadings.reduce((sum, reading) => sum + Number(reading.humedad_suelo || 0), 0) / plantReadings.length
      : null;
    const lastIrrigation = irrigationEvents.find((event) => normalizePlantType(event.tipo_planta) === plant.id) || null;
    return {
      plant,
      readingsCount: plantReadings.length,
      soilAverage,
      lastIrrigation,
      irrigationMode: resolveIrrigationMode(config),
      threshold: config?.umbral_humedad_minimo ?? null,
      readingsWindow,
    };
  });

  return (
    <main className="min-h-screen">
      <div className="px-4 py-8">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">

          {/* ── Tarjeta Temperatura ── */}
          <div className="bg-white/80 backdrop-blur-lg rounded-3xl shadow-xl p-6 border border-red-100 hover:shadow-2xl transition-all duration-300 hover:scale-105 group relative overflow-hidden">
            {stats && (
              <div
                className={`absolute bottom-0 left-0 right-0 transition-all duration-1000 ease-out ${
                  stats.temperatura_promedio > 35
                    ? 'bg-gradient-to-t from-red-500/40 to-red-400/10'
                    : stats.temperatura_promedio > 25
                      ? 'bg-gradient-to-t from-orange-400/35 to-orange-300/10'
                      : stats.temperatura_promedio > 15
                        ? 'bg-gradient-to-t from-yellow-400/30 to-yellow-300/10'
                        : 'bg-gradient-to-t from-blue-400/30 to-blue-300/10'
                }`}
                style={{ height: `${Math.min(Math.max((stats.temperatura_promedio / 50) * 100, 10), 100)}%` }}
              >
                <svg className="absolute top-0 left-0 w-full h-3" viewBox="0 0 100 10" preserveAspectRatio="none">
                  <path d="M0,5 Q12.5,0 25,5 T50,5 T75,5 T100,5 V10 H0 Z" fill="rgba(255,255,255,0.3)" className="animate-pulse" />
                </svg>
              </div>
            )}
            <div className="flex items-center justify-between mb-4 relative z-10">
              <div className={`p-4 rounded-2xl shadow-lg group-hover:scale-110 transition-transform flex items-center justify-center ${
                stats && stats.temperatura_promedio > 35
                  ? 'bg-gradient-to-br from-red-600 to-red-500'
                  : stats && stats.temperatura_promedio > 25
                    ? 'bg-gradient-to-br from-orange-500 to-red-500'
                    : 'bg-gradient-to-br from-red-500 to-orange-500'
              }`}>{/* ── 🔥🌡️ ── */}
                <TwemojiEmoji emoji="🌡️" size={32} />
              </div>
              <div className="text-right">
                <p className="text-sm text-gray-600 font-semibold uppercase tracking-wide">Temperatura</p>
                <p className={`text-4xl font-bold bg-clip-text text-transparent ${
                  stats && stats.temperatura_promedio > 35
                    ? 'bg-gradient-to-r from-red-700 to-red-500'
                    : stats && stats.temperatura_promedio > 25
                      ? 'bg-gradient-to-r from-orange-600 to-red-500'
                      : 'bg-gradient-to-r from-red-600 to-orange-600'
                }`}>
                  {stats ? `${stats.temperatura_promedio.toFixed(1)}°C` : '---'}
                </p>
              </div>
            </div>
          </div>

          {/* ── Tarjeta Humedad ── */}
          <div className="bg-white/80 backdrop-blur-lg rounded-3xl shadow-xl p-6 border border-blue-100 hover:shadow-2xl transition-all duration-300 hover:scale-105 group relative overflow-hidden">
            {stats && (
              <div
                className={`absolute bottom-0 left-0 right-0 transition-all duration-1000 ease-out ${
                  stats.humedad_promedio > 80
                    ? 'bg-gradient-to-t from-blue-500/40 to-blue-400/10'
                    : stats.humedad_promedio > 50
                      ? 'bg-gradient-to-t from-cyan-400/35 to-cyan-300/10'
                      : stats.humedad_promedio > 30
                        ? 'bg-gradient-to-t from-sky-400/30 to-sky-300/10'
                        : 'bg-gradient-to-t from-indigo-400/30 to-blue-300/10'
                }`}
                style={{ height: `${stats.humedad_promedio}%` }}
              >
                <svg className="absolute top-0 left-0 w-full h-3" viewBox="0 0 100 10" preserveAspectRatio="none">
                  <path d="M0,5 Q12.5,0 25,5 T50,5 T75,5 T100,5 V10 H0 Z" fill="rgba(255,255,255,0.3)" className="animate-pulse" />
                </svg>
              </div>
            )}
            <div className="flex items-center justify-between mb-4 relative z-10">
              <div className={`p-4 rounded-2xl shadow-lg group-hover:scale-110 transition-transform flex items-center justify-center ${
                stats && stats.humedad_promedio > 80
                  ? 'bg-gradient-to-br from-blue-600 to-blue-500'
                  : stats && stats.humedad_promedio < 30
                    ? 'bg-gradient-to-br from-orange-500 to-yellow-500'
                    : 'bg-gradient-to-br from-blue-500 to-cyan-500'
              }`}>
                <span className="material-icons text-2xl leading-none text-white">cloud</span>
              </div>
              <div className="text-right">
                <p className="text-sm text-gray-600 font-semibold uppercase tracking-wide">Humedad</p>
                <p className={`text-4xl font-bold bg-clip-text text-transparent ${
                  stats && stats.humedad_promedio > 80
                    ? 'bg-gradient-to-r from-blue-700 to-blue-500'
                    : stats && stats.humedad_promedio < 30
                      ? 'bg-gradient-to-r from-orange-600 to-yellow-500'
                      : 'bg-gradient-to-r from-blue-600 to-cyan-600'
                }`}>
                  {stats ? `${stats.humedad_promedio.toFixed(1)}%` : '---'}
                </p>
              </div>
            </div>
          </div>

          {/* ── Tarjeta Luminosidad ── */}
          <div className="bg-white/80 backdrop-blur-lg rounded-3xl shadow-xl p-6 border border-yellow-100 hover:shadow-2xl transition-all duration-300 hover:scale-105 group relative overflow-hidden">
            {stats && stats.luminosidad_promedio !== undefined && (
              <div
                className={`absolute bottom-0 left-0 right-0 transition-all duration-1000 ease-out ${
                  stats.luminosidad_promedio > 50000
                    ? 'bg-gradient-to-t from-yellow-400/50 to-yellow-200/20'
                    : stats.luminosidad_promedio > 10000
                      ? 'bg-gradient-to-t from-amber-400/40 to-amber-300/10'
                      : stats.luminosidad_promedio > 1000
                        ? 'bg-gradient-to-t from-orange-300/30 to-orange-200/10'
                        : 'bg-gradient-to-t from-gray-400/25 to-gray-300/10'
                }`}
                style={{ height: `${Math.min((stats.luminosidad_promedio / 100000) * 100, 100)}%` }}
              >
                <svg className="absolute top-0 left-0 w-full h-3" viewBox="0 0 100 10" preserveAspectRatio="none">
                  <path d="M0,5 Q12.5,0 25,5 T50,5 T75,5 T100,5 V10 H0 Z" fill="rgba(255,255,255,0.4)" className="animate-pulse" />
                </svg>
              </div>
            )}
            <div className="flex items-center justify-between mb-4 relative z-10">
              {/* CORREGIDO: TwemojiEmoji en lugar de <span>☀️</span> */}
              <div className={`p-4 rounded-2xl shadow-lg group-hover:scale-110 transition-transform flex items-center justify-center ${
                stats?.luminosidad_promedio !== undefined && stats.luminosidad_promedio > 50000
                  ? 'bg-gradient-to-br from-yellow-400 to-orange-400'
                  : stats?.luminosidad_promedio !== undefined && stats.luminosidad_promedio > 10000
                    ? 'bg-gradient-to-br from-amber-500 to-yellow-500'
                    : stats?.luminosidad_promedio !== undefined && stats.luminosidad_promedio > 1000
                      ? 'bg-gradient-to-br from-orange-500 to-amber-500'
                      : 'bg-gradient-to-br from-gray-500 to-gray-400'
              }`}>
                <TwemojiEmoji emoji="☀️" size={32} />
              </div>
              <div className="text-right">
                <p className="text-sm text-gray-600 font-semibold uppercase tracking-wide">Luminosidad</p>
                <p className={`text-4xl font-bold bg-clip-text text-transparent ${
                  stats?.luminosidad_promedio !== undefined && stats.luminosidad_promedio > 50000
                    ? 'bg-gradient-to-r from-yellow-500 to-orange-500'
                    : stats?.luminosidad_promedio !== undefined && stats.luminosidad_promedio > 10000
                      ? 'bg-gradient-to-r from-amber-600 to-yellow-500'
                      : 'bg-gradient-to-r from-orange-600 to-amber-600'
                }`}>
                  {stats?.luminosidad_promedio !== undefined ? `${(stats.luminosidad_promedio / 1000).toFixed(1)}k` : '---'}
                </p>
              </div>
            </div>
          </div>

          {/* ── Tarjeta Depósito ── */}
          <div className="bg-white/80 backdrop-blur-lg rounded-3xl shadow-xl p-6 border border-cyan-100 hover:shadow-2xl transition-all duration-300 hover:scale-105 group relative overflow-hidden">
            {waterTank && (
              <div
                className={`absolute bottom-0 left-0 right-0 transition-all duration-1000 ease-out ${
                  waterTank.percentage < 20
                    ? 'bg-gradient-to-t from-red-400/30 to-red-300/10'
                    : waterTank.percentage < 50
                      ? 'bg-gradient-to-t from-yellow-400/30 to-yellow-300/10'
                      : 'bg-gradient-to-t from-cyan-400/40 to-cyan-300/10'
                }`}
                style={{ height: `${waterTank.percentage}%` }}
              >
                <svg className="absolute top-0 left-0 w-full h-3" viewBox="0 0 100 10" preserveAspectRatio="none">
                  <path d="M0,5 Q12.5,0 25,5 T50,5 T75,5 T100,5 V10 H0 Z" fill="rgba(255,255,255,0.3)" className="animate-pulse" />
                </svg>
              </div>
            )}
            <div className="flex items-center justify-between mb-4 relative z-10">
              {/* CORREGIDO: TwemojiEmoji en lugar de <span>🪣</span> */}
              <div className={`p-4 rounded-2xl shadow-lg group-hover:scale-110 transition-transform flex items-center justify-center ${
                waterTank && waterTank.percentage < 20
                  ? 'bg-gradient-to-br from-red-500 to-red-600'
                  : waterTank && waterTank.percentage < 50
                    ? 'bg-gradient-to-br from-yellow-500 to-orange-500'
                    : 'bg-gradient-to-br from-cyan-500 to-blue-500'
              }`}>
                <TwemojiEmoji emoji="🪣" size={32} />
              </div>
              <div className="text-right">
                <p className="text-sm text-gray-600 font-semibold uppercase tracking-wide">Depósito</p>
                <p className={`text-4xl font-bold bg-clip-text text-transparent ${
                  waterTank && waterTank.percentage < 20
                    ? 'bg-gradient-to-r from-red-600 to-red-500'
                    : waterTank && waterTank.percentage < 50
                      ? 'bg-gradient-to-r from-yellow-600 to-orange-500'
                      : 'bg-gradient-to-r from-cyan-600 to-blue-600'
                }`}>
                  {waterTank ? `${waterTank.percentage.toFixed(0)}%` : '---'}
                </p>
              </div>
            </div>
            <div className="mt-4 pt-4 border-t border-gray-200/50 flex items-center justify-between relative z-10">
              <p className="text-xs text-gray-600 font-medium">
                {waterTank ? `${waterTank.liters.toFixed(1)}L de ${waterTank.capacity}L` : 'Sin datos'}
              </p>
            </div>
          </div>
        </div>

        {/* ── Resumen de plantas ── */}
        <div className="bg-white/80 backdrop-blur-lg rounded-3xl shadow-xl p-6 border border-gray-100">
          <div className="flex flex-col lg:flex-row lg:items-end lg:justify-between gap-4 mb-6">
            <div>
              <h2 className="text-2xl font-bold flex items-center gap-2 text-gray-900">
                <TwemojiEmoji emoji="🌱" size={28} />
                <span>Resumen de plantas</span>
              </h2>
              <p className="text-sm text-gray-600 mt-1">
                Media de humedad del suelo, último riego y estado del riego automático para cada planta.
              </p>
            </div>
            {(soilLoading || irrigationLoading || configLoading) && (
              <div className="rounded-2xl bg-gray-100 px-4 py-2 text-sm font-medium text-gray-600">
                Actualizando resumen...
              </div>
            )}
          </div>

          {(soilError || irrigationError || configError) && (
            <div className="mb-6 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-amber-800">
              El resumen se está mostrando con los datos disponibles; alguna fuente no respondió a tiempo.
            </div>
          )}

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {plantSummaries.map((summary) => {
              const hasData = summary.soilAverage !== null;
              const autoLabel =
                summary.irrigationMode === 'ia' ? 'IA'
                : summary.irrigationMode === 'automatico' ? 'Automático'
                : 'Desactivado';
              const autoBadge =
                summary.irrigationMode === 'ia' ? 'bg-blue-100 text-blue-700'
                : summary.irrigationMode === 'automatico' ? 'bg-green-100 text-green-700'
                : 'bg-red-100 text-red-700';

              return (
                <article key={summary.plant.id} className={`rounded-3xl border shadow-lg p-6 ${summary.plant.accentSoft}`}>
                  <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4 mb-5">
                    <div className="flex items-center gap-4 min-w-0">
                      <div className={`h-14 w-14 rounded-2xl bg-gradient-to-br ${summary.plant.accent} flex items-center justify-center shadow-md`}>
                        <TwemojiEmoji emoji={summary.plant.emoji} size={36} />
                      </div>
                      <div className="min-w-0">
                        <h3 className="text-2xl font-bold text-gray-900">{summary.plant.name}</h3>
                        <p className="text-sm text-gray-600">Últimas {summary.readingsWindow} lecturas de suelo disponibles</p>
                      </div>
                    </div>
                    <span className={`inline-flex w-fit shrink-0 items-center rounded-full px-3 py-1 text-xs font-semibold whitespace-nowrap ${autoBadge}`}>
                      Riego: {autoLabel}
                    </span>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="rounded-2xl bg-white/85 p-4 border border-white/60 shadow-sm">
                      <p className="text-xs font-semibold uppercase tracking-wide text-gray-500 mb-2">Humedad media</p>
                      <div className="flex items-end gap-2">
                        <p className="text-4xl font-bold text-gray-900">
                          {hasData ? `${summary.soilAverage!.toFixed(1)}%` : '---'}
                        </p>
                        <p className="pb-1 text-sm text-gray-500">
                          {summary.readingsCount ? `basado en ${summary.readingsCount} valores` : 'sin lecturas'}
                        </p>
                      </div>
                      <div className="mt-4 h-2 w-full rounded-full bg-gray-100 overflow-hidden">
                        <div
                          className={`h-full rounded-full bg-gradient-to-r ${summary.plant.accent}`}
                          style={{ width: hasData ? `${Math.min(summary.soilAverage!, 100)}%` : '0%' }}
                        />
                      </div>
                      {summary.threshold !== null && (
                        <p className="mt-3 text-sm text-gray-600">
                          Umbral automático: <span className="font-semibold text-gray-800">{summary.threshold.toFixed(1)}%</span>
                        </p>
                      )}
                    </div>

                    <div className="rounded-2xl bg-white/85 p-4 border border-white/60 shadow-sm space-y-3">
                      <div>
                        <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">Último riego</p>
                        <p className="mt-1 text-sm font-semibold text-gray-900">
                          {summary.lastIrrigation ? formatDateTime(summary.lastIrrigation.fecha_inicio) : 'Sin riegos registrados'}
                        </p>
                      </div>
                      <div>
                        <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">Tipo</p>
                        <p className="mt-1 text-sm text-gray-800">
                          {summary.lastIrrigation ? (summary.lastIrrigation.automatico ? 'Automático' : 'Manual') : 'Sin historial'}
                        </p>
                      </div>
                      <div>
                        <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">Motivo</p>
                        <p className="mt-1 text-sm text-gray-700 line-clamp-3">
                          {summary.lastIrrigation?.razon || 'Sin datos de riego recientes'}
                        </p>
                      </div>
                    </div>
                  </div>
                </article>
              );
            })}
          </div>
        </div>

        {/* ── Previsión meteorológica ── */}
        <div className="mt-6 bg-white/80 backdrop-blur-lg rounded-3xl shadow-xl p-6 border border-gray-100 overflow-hidden">
          <div className="flex flex-col lg:flex-row lg:items-end lg:justify-between gap-4 mb-6">
            <div>
              <h2 className="text-2xl font-bold flex items-center gap-2 text-gray-900">
                <TwemojiEmoji emoji="🌦️" size={28} />
                <span>Previsión del tiempo</span>
              </h2>
              <p className="text-sm text-gray-600 mt-1">
                Franja de hoy por horas y previsión de 5 días para {forecast?.municipio_nombre || 'tu zona'}
              </p>
            </div>
          </div>

          {forecastLoading && (
            <div className="py-16 flex items-center justify-center">
              <div className="text-center">
                <div className="animate-spin rounded-full h-12 w-12 border-t-4 border-b-4 border-sky-500 mx-auto mb-3" />
                <p className="text-gray-600">Cargando previsión meteorológica...</p>
              </div>
            </div>
          )}

          {!forecastLoading && forecastError && (
            <div className="rounded-2xl border border-amber-200 bg-amber-50 p-4 text-amber-800">
              No se pudo cargar la previsión de AEMET ahora mismo. El resto del panel sigue funcionando.
            </div>
          )}

          {!forecastLoading && forecast && (
            <>
              <div className="mb-8">
                <div className="flex items-center justify-between mb-3">
                  <h3 className="text-lg font-bold text-gray-800">Hoy por horas</h3>
                  <span className="text-xs font-semibold uppercase tracking-wide text-gray-500 bg-gray-100 px-3 py-1 rounded-full">24h</span>
                </div>
                <div className="overflow-x-auto pb-2 -mx-2 px-2">
                  <div className="flex gap-3 min-w-max">
                    {forecast.bloques_hoy.map((bloque, index) => {
                      const visual = getWeatherVisual(bloque.cielo || '', bloque.prob_lluvia ?? null);
                      return (
                        <div key={`${bloque.hora}-${index}`} className="w-28 rounded-2xl bg-gradient-to-br from-white to-gray-50 border border-gray-200 shadow-sm p-3 shrink-0">
                          <div className={`rounded-xl bg-gradient-to-br ${visual.gradientClass} text-white p-3 flex flex-col items-center justify-center gap-1 shadow-md`}>
                            <span className="material-icons text-2xl">{visual.iconName}</span>
                            <span className="text-[11px] font-semibold uppercase tracking-wide">{bloque.hora}</span>
                          </div>
                          <div className="mt-3 space-y-1 text-center">
                            <p className="text-sm font-bold text-gray-800">
                              {bloque.temperatura !== null && bloque.temperatura !== undefined ? `${bloque.temperatura.toFixed(1)}°` : '--'}
                            </p>
                            <p className="text-[11px] text-gray-500 line-clamp-2 min-h-[2.5rem]">{bloque.cielo || 'Sin datos'}</p>
                            <p className="text-xs font-semibold text-sky-700">
                              {bloque.prob_lluvia !== null && bloque.prob_lluvia !== undefined ? `${bloque.prob_lluvia.toFixed(0)}% lluvia` : 'Sin lluvia'}
                            </p>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>

              <div>
                <div className="flex items-center justify-between mb-3">
                  <h3 className="text-lg font-bold text-gray-800">Próximos 5 días</h3>
                  <span className="text-xs text-gray-500">
                    Actualizado {forecast.elaborado ? new Date(forecast.elaborado).toLocaleString('es-ES', { dateStyle: 'short', timeStyle: 'short' }) : 'recientemente'}
                  </span>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-5 gap-4">
                  {forecast.dias.map((dia) => {
                    const dateLabel = dia.fecha
                      ? new Date(dia.fecha).toLocaleDateString('es-ES', { weekday: 'short', day: '2-digit', month: 'short' })
                      : 'Día';
                    const visual = getDailyWeatherVisual(dia);
                    const dayDescription =
                      dia.bloques.find((block) => isMeaningfulWeatherText(block.cielo))?.cielo || dia.cielo_resumen || 'Sin datos';
                    return (
                      <div key={dia.fecha} className="rounded-3xl border border-gray-200 bg-white p-4 shadow-sm hover:shadow-lg transition-all duration-300">
                        <div className="flex items-start justify-between gap-3 mb-4">
                          <div>
                            <p className="text-sm font-semibold text-gray-500 uppercase tracking-wide">{dateLabel}</p>
                            <p className="text-lg font-bold text-gray-800 capitalize">{dayDescription}</p>
                          </div>
                          <div className={`h-12 w-12 shrink-0 aspect-square rounded-2xl bg-gradient-to-br ${visual.gradientClass} text-white flex items-center justify-center shadow-md`}>
                            <span className="material-icons text-2xl">{visual.iconName}</span>
                          </div>
                        </div>
                        <div className="grid grid-cols-2 gap-3 text-sm mb-4">
                          <div className="rounded-2xl bg-red-50 p-3">
                            <p className="text-xs uppercase tracking-wide text-red-500 font-semibold">Máx.</p>
                            <p className="text-xl font-bold text-red-700">
                              {dia.temperatura_maxima !== null && dia.temperatura_maxima !== undefined ? `${dia.temperatura_maxima.toFixed(0)}°` : '--'}
                            </p>
                          </div>
                          <div className="rounded-2xl bg-blue-50 p-3">
                            <p className="text-xs uppercase tracking-wide text-blue-500 font-semibold">Mín.</p>
                            <p className="text-xl font-bold text-blue-700">
                              {dia.temperatura_minima !== null && dia.temperatura_minima !== undefined ? `${dia.temperatura_minima.toFixed(0)}°` : '--'}
                            </p>
                          </div>
                        </div>
                        <div className="space-y-2 text-sm">
                          <div className="flex items-center justify-between rounded-xl bg-gray-50 px-3 py-2">
                            <span className="text-gray-600">Lluvia</span>
                            <span className="font-semibold text-sky-700">
                              {dia.probabilidad_lluvia_maxima !== null && dia.probabilidad_lluvia_maxima !== undefined ? `${dia.probabilidad_lluvia_maxima.toFixed(0)}%` : '--'}
                            </span>
                          </div>
                          <div className="flex items-center justify-between rounded-xl bg-gray-50 px-3 py-2">
                            <span className="text-gray-600">Humedad</span>
                            <span className="font-semibold text-gray-800">
                              {dia.humedad_maxima !== null && dia.humedad_maxima !== undefined ? `${dia.humedad_maxima.toFixed(0)}%` : '--'}
                            </span>
                          </div>
                        </div>
                        <div className="mt-4 pt-4 border-t border-gray-100 text-xs text-gray-500">
                          <p className="line-clamp-2">{dayDescription}</p>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </>
          )}
        </div>

        <footer className="mt-12 text-center text-gray-600">
          <p className="text-sm flex items-center justify-center gap-2">
            <TwemojiEmoji emoji="🌱" size={16} />
            Sistema de Riego Inteligente - TFG 2025
          </p>
          <p className="text-xs mt-2 text-gray-400">
            Desarrollado con Next.js + PWA + Django + ESP32
          </p>
        </footer>
      </div>
    </main>
  );
}