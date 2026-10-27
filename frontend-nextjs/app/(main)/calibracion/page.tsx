'use client';

import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useUser } from '../../../lib/UserContext';

const API_BASE = 'https://riegoesp32.victorfg.work';

interface CalibrationData {
  distancia_minima_tanque: number;
  distancia_maxima_tanque: number;
  ev1_litros_1s: number;
  ev1_litros_5s: number;
  ev1_litros_10s: number;
  ev2_litros_1s: number;
  ev2_litros_5s: number;
  ev2_litros_10s: number;
  suelo1_valor_seco: number;
  suelo1_valor_mojado: number;
  suelo2_valor_seco: number;
  suelo2_valor_mojado: number;
  updated_at?: string;
}

interface SoilSampleReading {
  second: number;
  value: number | null;
  value_raw: number | null;
  timestamp: string | null;
}

interface SoilSampleResult {
  average: number | null;
  average_raw: number | null;
  readings: SoilSampleReading[];
  captured: number;
}

interface TankSampleReading {
  second: number;
  value_raw: number | null;
  percentage: number | null;
  liters: number | null;
  timestamp: string | null;
}

interface TankSampleResult {
  average_raw: number | null;
  average_percentage: number | null;
  average_liters: number | null;
  readings: TankSampleReading[];
  captured: number;
}

const DEFAULT_VALUES: CalibrationData = {
  distancia_minima_tanque: 5,
  distancia_maxima_tanque: 100,
  ev1_litros_1s: 0.05,
  ev1_litros_5s: 0.25,
  ev1_litros_10s: 0.5,
  ev2_litros_1s: 0.05,
  ev2_litros_5s: 0.25,
  ev2_litros_10s: 0.5,
  suelo1_valor_seco: 4095,
  suelo1_valor_mojado: 1200,
  suelo2_valor_seco: 4095,
  suelo2_valor_mojado: 1200,
};

export default function CalibracionPage() {
  const router = useRouter();
  const { isAdmin, isLoading: userLoading } = useUser();

  const [form, setForm] = useState<CalibrationData>(DEFAULT_VALUES);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testingValve, setTestingValve] = useState<string>('');
  const [confirmingValve, setConfirmingValve] = useState<string>('');
  const [samplingSoil, setSamplingSoil] = useState<number | null>(null);
  const [samplingSoilLive, setSamplingSoilLive] = useState<number | null>(null);
  const [samplingTank, setSamplingTank] = useState(false);
  const [soilSampleResult, setSoilSampleResult] = useState<Record<number, SoilSampleResult>>({});
  const [tankSampleResult, setTankSampleResult] = useState<TankSampleResult | null>(null);
  const [error, setError] = useState<string>('');
  const [success, setSuccess] = useState<string>('');

  const apiBaseUrl = (process.env.NEXT_PUBLIC_API_URL || API_BASE).replace(/\/$/, '');

  const getCsrfToken = () => {
    if (typeof document === 'undefined') return '';
    const token = document.cookie
      .split('; ')
      .find((row) => row.startsWith('csrftoken='))
      ?.split('=')[1];
    return token || '';
  };

  const ensureCsrfToken = async () => {
    const current = getCsrfToken();
    if (current) return current;
    await fetch(`${apiBaseUrl}/api/auth/csrf`, {
      method: 'GET',
      credentials: 'include',
      cache: 'no-store',
    });
    return getCsrfToken();
  };

  const buildJsonHeaders = async () => {
    const csrfToken = await ensureCsrfToken();
    const headers: Record<string, string> = { 'Content-Type': 'application/json' };
    if (csrfToken) headers['X-CSRFToken'] = csrfToken;
    return headers;
  };

  const getApiErrorMessage = (data: Record<string, unknown>, fallback: string, status: number) => {
    if (typeof data?.error === 'string' && data.error) return data.error;
    if (typeof data?.detail === 'string' && data.detail) return data.detail;
    return `${fallback} (HTTP ${status})`;
  };

  const fetchCalibration = useCallback(async () => {
    try {
      setLoading(true);
      setError('');
      const res = await fetch(`${apiBaseUrl}/api/admin/sensor-calibration`, {
        credentials: 'include',
        cache: 'no-store',
      });
      if (!res.ok) throw new Error('No se pudo cargar la calibración');
      const data = await res.json();
      setForm({ ...DEFAULT_VALUES, ...(data.data || {}) });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error de conexión al cargar calibración');
    } finally {
      setLoading(false);
    }
  }, [apiBaseUrl]);

  useEffect(() => {
    if (!userLoading && !isAdmin) {
      router.push('/');
      return;
    }
    if (isAdmin) fetchCalibration();
  }, [userLoading, isAdmin, router, fetchCalibration]);

  const handleNumberChange = (field: keyof CalibrationData, value: string) => {
    setForm((prev) => ({
      ...prev,
      [field]: value === '' ? 0 : Number(value),
    }));
  };

  const handleSave = async () => {
    setSaving(true);
    setError('');
    setSuccess('');
    try {
      const headers = await buildJsonHeaders();
      const res = await fetch(`${apiBaseUrl}/api/admin/sensor-calibration`, {
        method: 'POST',
        headers,
        credentials: 'include',
        body: JSON.stringify(form),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(getApiErrorMessage(data, 'No se pudo guardar la calibración', res.status));
      setForm({ ...form, ...(data.data || {}) });
      setSuccess('Calibración guardada correctamente');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error de conexión al guardar calibración');
    } finally {
      setSaving(false);
    }
  };

  const handleValveTest = async (relay: 1 | 2, durationSeconds: 1 | 5 | 10) => {
    setConfirmingValve('');
    setTestingValve(`r${relay}-${durationSeconds}`);
    setError('');
    setSuccess('');
    try {
      const headers = await buildJsonHeaders();
      const res = await fetch(`${apiBaseUrl}/api/admin/sensor-calibration/valve-test`, {
        method: 'POST',
        headers,
        credentials: 'include',
        body: JSON.stringify({ relay, duration_seconds: durationSeconds }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(getApiErrorMessage(data, 'No se pudo lanzar la prueba de electroválvula', res.status));
      setSuccess(`Prueba EV${relay} (${durationSeconds}s) enviada. Litros estimados: ${data.data?.estimated_liters ?? '--'}L`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error de conexión al probar electroválvula');
    } finally {
      setTestingValve('');
    }
  };

  const handleSoilSample = async (relay: 1 | 2) => {
    setSamplingSoil(relay);
    setError('');
    setSuccess('');
    try {
      const headers = await buildJsonHeaders();
      const res = await fetch(`${apiBaseUrl}/api/admin/sensor-calibration/soil-sample`, {
        method: 'POST',
        headers,
        credentials: 'include',
        body: JSON.stringify({ relay }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(getApiErrorMessage(data, 'No se pudo tomar muestra de humedad', res.status));
      setSoilSampleResult((prev) => ({
        ...prev,
        [relay]: {
          average: data.data?.average ?? null,
          average_raw: data.data?.average_raw ?? null,
          readings: data.data?.readings ?? [],
          captured: data.data?.captured ?? 0,
        },
      }));
      const rawLabel = data.data?.average_raw != null ? ` (RAW: ${data.data.average_raw})` : '';
      setSuccess(`Ultimos valores de sensor ${relay} cargados. Media calibrada: ${data.data?.average ?? '--'}%${rawLabel}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error de conexión en muestreo de humedad');
    } finally {
      setSamplingSoil(null);
    }
  };

  const handleTankSample = async () => {
    setSamplingTank(true);
    setError('');
    setSuccess('');
    try {
      const headers = await buildJsonHeaders();
      const res = await fetch(`${apiBaseUrl}/api/admin/sensor-calibration/tank-sample`, {
        method: 'POST',
        headers,
        credentials: 'include',
        body: JSON.stringify({}),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(getApiErrorMessage(data, 'No se pudo tomar muestra de distancia del tanque', res.status));
      setTankSampleResult({
        average_raw: data.data?.average_raw ?? null,
        average_percentage: data.data?.average_percentage ?? null,
        average_liters: data.data?.average_liters ?? null,
        readings: data.data?.readings ?? [],
        captured: data.data?.captured ?? 0,
      });
      const avg = data.data?.average_raw ?? '--';
      setSuccess(`Ultimos valores del tanque cargados. Distancia media: ${avg} cm`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error de conexión en muestreo de tanque');
    } finally {
      setSamplingTank(false);
    }
  };

  const handleSoilLiveRead = async (relay: 1 | 2) => {
    setSamplingSoilLive(relay);
    setError('');
    setSuccess('');
    try {
      const headers = await buildJsonHeaders();
      const res = await fetch(`${apiBaseUrl}/api/admin/sensor-calibration/soil-live-read`, {
        method: 'POST',
        headers,
        credentials: 'include',
        body: JSON.stringify({ relay }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(getApiErrorMessage(data, 'No se pudo leer sensor en vivo', res.status));
      setSoilSampleResult((prev) => ({
        ...prev,
        [relay]: {
          average: data.data?.value ?? null,
          average_raw: data.data?.value_raw ?? null,
          readings: [{
            second: 1,
            value: data.data?.value ?? null,
            value_raw: data.data?.value_raw ?? null,
            timestamp: data.data?.timestamp ?? null,
          }],
          captured: 1,
        },
      }));
      const rawLabel = data.data?.value_raw != null ? ` (RAW: ${data.data.value_raw})` : '';
      const sourceLabel = data.pending ? ' (ultima lectura disponible)' : '';
      setSuccess(`Lectura sensor ${relay}: ${data.data?.value ?? '--'}%${rawLabel}${sourceLabel}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error de conexión en lectura en vivo');
    } finally {
      setSamplingSoilLive(null);
    }
  };

  const applyTankSampleToDistance = (field: 'distancia_minima_tanque' | 'distancia_maxima_tanque') => {
    const sampledRaw = tankSampleResult?.average_raw;
    if (sampledRaw === null || sampledRaw === undefined || Number.isNaN(sampledRaw)) {
      setError('No hay una distancia media valida para aplicar. Lee ultimos valores primero.');
      return;
    }
    setForm((prev) => ({ ...prev, [field]: Number(sampledRaw) }));
    setSuccess(
      field === 'distancia_maxima_tanque'
        ? `Distancia maxima actualizada a ${sampledRaw} cm desde la muestra del tanque`
        : `Distancia minima actualizada a ${sampledRaw} cm desde la muestra del tanque`
    );
  };

  const renderValveField = (
    relay: 1 | 2,
    field: keyof CalibrationData,
    label: string,
    durationSeconds: 1 | 5 | 10
  ) => {
    const key = `r${relay}-${durationSeconds}`;
    const isTesting = testingValve === key;
    const isConfirming = confirmingValve === key;
    const isDisabled = saving || testingValve.length > 0 || samplingSoil !== null || samplingSoilLive !== null || samplingTank;

    return (
      <label className="text-sm text-gray-700">
        {label}
        <div className="mt-1 flex items-center gap-2">
          <input
            id={`valve-${relay}-${durationSeconds}`}
            name={`valve-${relay}-${durationSeconds}`}
            type="number"
            step="0.001"
            className="w-full rounded-lg border border-gray-300 px-3 py-2"
            value={form[field]}
            onChange={(e) => handleNumberChange(field, e.target.value)}
          />
          {isConfirming ? (
            <>
              <button
                type="button"
                onClick={() => handleValveTest(relay, durationSeconds)}
                className="whitespace-nowrap rounded-lg border border-orange-400 bg-orange-500 px-3 py-2 font-semibold text-white hover:bg-orange-600"
              >
                ¿Activar EV{relay} {durationSeconds}s?
              </button>
              <button
                type="button"
                onClick={() => setConfirmingValve('')}
                className="whitespace-nowrap rounded-lg border border-gray-300 bg-gray-100 px-3 py-2 font-medium text-gray-600 hover:bg-gray-200"
              >
                Cancelar
              </button>
            </>
          ) : (
            <button
              type="button"
              onClick={() => setConfirmingValve(key)}
              disabled={isDisabled}
              className="whitespace-nowrap rounded-lg border border-blue-300 bg-blue-50 px-3 py-2 font-medium text-blue-700 hover:bg-blue-100 disabled:opacity-50"
            >
              {isTesting ? 'Probando...' : 'Probar'}
            </button>
          )}
        </div>
      </label>
    );
  };

  if (userLoading || loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-t-4 border-b-4 border-green-500 mx-auto mb-4" />
          <p className="text-gray-600">Cargando calibración...</p>
        </div>
      </div>
    );
  }

  if (!isAdmin) return null;

  return (
    <div className="p-8 max-w-6xl mx-auto">

      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-800 flex items-center gap-3">
          <span className="material-icons text-3xl text-green-600">settings</span>
          Calibración de Sensores
        </h1>
        <p className="text-gray-600 mt-2">
          Configuración avanzada para tanque, electroválvulas y sensores de humedad.
        </p>
      </div>

      {error && (
        <div className="mb-6 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-red-800">
          {error}
        </div>
      )}

      {success && (
        <div className="mb-6 rounded-xl border border-green-200 bg-green-50 px-4 py-3 text-green-800">
          {success}
        </div>
      )}

      <div className="grid grid-cols-1 gap-6">

        {/* Tanque */}
        <section className="bg-white rounded-2xl border border-gray-200 p-6 shadow-sm">
          <div className="mb-4 flex items-center justify-between gap-3">
            <h2 className="text-xl font-semibold text-gray-800">Tanque de agua (sensor distancia)</h2>
            <button
              type="button"
              onClick={handleTankSample}
              disabled={saving || samplingTank || samplingSoil !== null || samplingSoilLive !== null || testingValve.length > 0}
              className="rounded-lg border border-cyan-300 bg-cyan-50 px-3 py-1.5 text-xs font-medium text-cyan-800 hover:bg-cyan-100 disabled:opacity-50"
            >
              {samplingTank ? 'Leyendo...' : 'Leer ultimos valores'}
            </button>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <label htmlFor="tank-distance-min" className="text-sm text-gray-700">
              Distancia minima (cm, tanque lleno)
              <input
                id="tank-distance-min"
                name="distancia_minima_tanque"
                type="number"
                step="0.1"
                className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2"
                value={form.distancia_minima_tanque}
                onChange={(e) => handleNumberChange('distancia_minima_tanque', e.target.value)}
              />
            </label>
            <label htmlFor="tank-distance-max" className="text-sm text-gray-700">
              Distancia maxima (cm, tanque vacio)
              <input
                id="tank-distance-max"
                name="distancia_maxima_tanque"
                type="number"
                step="0.1"
                className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2"
                value={form.distancia_maxima_tanque}
                onChange={(e) => handleNumberChange('distancia_maxima_tanque', e.target.value)}
              />
            </label>
          </div>
          {tankSampleResult && (
            <div className="mt-4 rounded-lg border border-cyan-200 bg-cyan-50 p-3 text-sm text-cyan-900">
              <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
                <div>
                  <p className="font-semibold text-base">
                    Distancia media: <span className="text-cyan-700">{tankSampleResult.average_raw ?? '--'} cm</span>
                  </p>
                  <p className="text-xs text-cyan-700">
                    Nivel: {tankSampleResult.average_percentage ?? '--'}% · Litros: {tankSampleResult.average_liters ?? '--'}L · Lecturas: {tankSampleResult.captured}
                  </p>
                </div>
                {tankSampleResult.average_raw !== null && (
                  <div className="flex gap-2">
                    <button
                      type="button"
                      onClick={() => applyTankSampleToDistance('distancia_minima_tanque')}
                      className="rounded border border-emerald-400 bg-emerald-50 px-2 py-1 text-xs font-medium text-emerald-800 hover:bg-emerald-100"
                    >
                      Usar como lleno (min)
                    </button>
                    <button
                      type="button"
                      onClick={() => applyTankSampleToDistance('distancia_maxima_tanque')}
                      className="rounded border border-slate-400 bg-slate-50 px-2 py-1 text-xs font-medium text-slate-800 hover:bg-slate-100"
                    >
                      Usar como vacio (max)
                    </button>
                  </div>
                )}
              </div>
              <div className="mt-2 overflow-x-auto">
                <table className="min-w-full text-xs">
                  <thead>
                    <tr className="text-left">
                      <th className="px-2 py-1">Muestra</th>
                      <th className="px-2 py-1">Distancia (cm)</th>
                      <th className="px-2 py-1">%</th>
                      <th className="px-2 py-1">Litros</th>
                      <th className="px-2 py-1">Hora</th>
                    </tr>
                  </thead>
                  <tbody>
                    {tankSampleResult.readings.map((reading) => (
                      <tr key={`tank-${reading.second}`} className="border-t border-cyan-200/60">
                        <td className="px-2 py-1">{reading.second}</td>
                        <td className="px-2 py-1 font-mono font-semibold">{reading.value_raw ?? '--'}</td>
                        <td className="px-2 py-1">{reading.percentage !== null ? `${reading.percentage}%` : '--'}</td>
                        <td className="px-2 py-1">{reading.liters !== null ? `${reading.liters}L` : '--'}</td>
                        <td className="px-2 py-1">{reading.timestamp ? new Date(reading.timestamp).toLocaleTimeString('es-ES') : '--'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </section>

        {/* Electroválvula 1 */}
        <section className="bg-white rounded-2xl border border-gray-200 p-6 shadow-sm">
          <h2 className="text-xl font-semibold text-gray-800 mb-4">Electrovalvula 1 (litros por tiempo)</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {renderValveField(1, 'ev1_litros_1s', 'Litros en 1s', 1)}
            {renderValveField(1, 'ev1_litros_5s', 'Litros en 5s', 5)}
            {renderValveField(1, 'ev1_litros_10s', 'Litros en 10s', 10)}
          </div>
        </section>

        {/* Electroválvula 2 */}
        <section className="bg-white rounded-2xl border border-gray-200 p-6 shadow-sm">
          <h2 className="text-xl font-semibold text-gray-800 mb-4">Electrovalvula 2 (litros por tiempo)</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {renderValveField(2, 'ev2_litros_1s', 'Litros en 1s', 1)}
            {renderValveField(2, 'ev2_litros_5s', 'Litros en 5s', 5)}
            {renderValveField(2, 'ev2_litros_10s', 'Litros en 10s', 10)}
          </div>
        </section>

        {/* Humedad de suelo */}
        <section className="bg-white rounded-2xl border border-gray-200 p-6 shadow-sm">
          <h2 className="text-xl font-semibold text-gray-800 mb-4">Humedad de suelo (seco / mojado)</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">

            {/* Sensor 1 */}
            <div>
              <div className="mb-3 flex items-center justify-between gap-2">
                <h3 className="text-sm font-semibold text-gray-700">Sensor 1</h3>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => handleSoilLiveRead(1)}
                    disabled={saving || samplingSoilLive !== null || samplingSoil !== null || testingValve.length > 0 || samplingTank}
                    className="rounded-lg border border-indigo-300 bg-indigo-50 px-3 py-1.5 text-xs font-medium text-indigo-700 hover:bg-indigo-100 disabled:opacity-50"
                  >
                    {samplingSoilLive === 1 ? 'Pidiendo...' : 'Pedir valor ESP32'}
                  </button>
                  <button
                    type="button"
                    onClick={() => handleSoilSample(1)}
                    disabled={saving || samplingSoil !== null || samplingSoilLive !== null || testingValve.length > 0 || samplingTank}
                    className="rounded-lg border border-purple-300 bg-purple-50 px-3 py-1.5 text-xs font-medium text-purple-700 hover:bg-purple-100 disabled:opacity-50"
                  >
                    {samplingSoil === 1 ? 'Leyendo...' : 'Leer ultimos valores'}
                  </button>
                </div>
              </div>
              <div className="grid grid-cols-1 gap-4">
                <label htmlFor="soil1-dry" className="text-sm text-gray-700">
                  Valor en seco
                  <input id="soil1-dry" name="suelo1_valor_seco" type="number" step="1" className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2" value={form.suelo1_valor_seco} onChange={(e) => handleNumberChange('suelo1_valor_seco', e.target.value)} />
                </label>
                <label htmlFor="soil1-wet" className="text-sm text-gray-700">
                  Valor en mojado
                  <input id="soil1-wet" name="suelo1_valor_mojado" type="number" step="1" className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2" value={form.suelo1_valor_mojado} onChange={(e) => handleNumberChange('suelo1_valor_mojado', e.target.value)} />
                </label>
              </div>
              {soilSampleResult[1] && (
                <div className="mt-4 rounded-lg border border-purple-200 bg-purple-50 p-3 text-sm text-purple-900">
                  <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
                    <div>
                      <p className="font-semibold text-base">
                        RAW media: <span className="text-purple-700">{soilSampleResult[1].average_raw ?? '--'}</span>
                      </p>
                      <p className="text-xs text-purple-600">
                        Calibrado: {soilSampleResult[1].average ?? '--'}% &nbsp;·&nbsp; Lecturas: {soilSampleResult[1].captured}
                      </p>
                    </div>
                    {soilSampleResult[1].average_raw != null && (
                      <div className="flex gap-2">
                        <button type="button" onClick={() => handleNumberChange('suelo1_valor_seco', String(soilSampleResult[1].average_raw))} className="rounded border border-amber-400 bg-amber-50 px-2 py-1 text-xs font-medium text-amber-800 hover:bg-amber-100">
                          ↑ Usar como seco
                        </button>
                        <button type="button" onClick={() => handleNumberChange('suelo1_valor_mojado', String(soilSampleResult[1].average_raw))} className="rounded border border-blue-400 bg-blue-50 px-2 py-1 text-xs font-medium text-blue-800 hover:bg-blue-100">
                          ↑ Usar como mojado
                        </button>
                      </div>
                    )}
                  </div>
                  <div className="mt-2 overflow-x-auto">
                    <table className="min-w-full text-xs">
                      <thead>
                        <tr className="text-left">
                          <th className="px-2 py-1">Muestra</th>
                          <th className="px-2 py-1">RAW (ADC)</th>
                          <th className="px-2 py-1">%</th>
                          <th className="px-2 py-1">Hora</th>
                        </tr>
                      </thead>
                      <tbody>
                        {soilSampleResult[1].readings.map((reading) => (
                          <tr key={`s1-${reading.second}`} className="border-t border-purple-200/60">
                            <td className="px-2 py-1">{reading.second}</td>
                            <td className="px-2 py-1 font-mono font-semibold">{reading.value_raw ?? '--'}</td>
                            <td className="px-2 py-1">{reading.value != null ? `${reading.value}%` : '--'}</td>
                            <td className="px-2 py-1">{reading.timestamp ? new Date(reading.timestamp).toLocaleTimeString('es-ES') : '--'}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>

            {/* Sensor 2 */}
            <div>
              <div className="mb-3 flex items-center justify-between gap-2">
                <h3 className="text-sm font-semibold text-gray-700">Sensor 2</h3>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => handleSoilLiveRead(2)}
                    disabled={saving || samplingSoilLive !== null || samplingSoil !== null || testingValve.length > 0 || samplingTank}
                    className="rounded-lg border border-indigo-300 bg-indigo-50 px-3 py-1.5 text-xs font-medium text-indigo-700 hover:bg-indigo-100 disabled:opacity-50"
                  >
                    {samplingSoilLive === 2 ? 'Pidiendo...' : 'Pedir valor ESP32'}
                  </button>
                  <button
                    type="button"
                    onClick={() => handleSoilSample(2)}
                    disabled={saving || samplingSoil !== null || samplingSoilLive !== null || testingValve.length > 0 || samplingTank}
                    className="rounded-lg border border-purple-300 bg-purple-50 px-3 py-1.5 text-xs font-medium text-purple-700 hover:bg-purple-100 disabled:opacity-50"
                  >
                    {samplingSoil === 2 ? 'Leyendo...' : 'Leer ultimos valores'}
                  </button>
                </div>
              </div>
              <div className="grid grid-cols-1 gap-4">
                <label htmlFor="soil2-dry" className="text-sm text-gray-700">
                  Valor en seco
                  <input id="soil2-dry" name="suelo2_valor_seco" type="number" step="1" className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2" value={form.suelo2_valor_seco} onChange={(e) => handleNumberChange('suelo2_valor_seco', e.target.value)} />
                </label>
                <label htmlFor="soil2-wet" className="text-sm text-gray-700">
                  Valor en mojado
                  <input id="soil2-wet" name="suelo2_valor_mojado" type="number" step="1" className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2" value={form.suelo2_valor_mojado} onChange={(e) => handleNumberChange('suelo2_valor_mojado', e.target.value)} />
                </label>
              </div>
              {soilSampleResult[2] && (
                <div className="mt-4 rounded-lg border border-purple-200 bg-purple-50 p-3 text-sm text-purple-900">
                  <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
                    <div>
                      <p className="font-semibold text-base">
                        RAW media: <span className="text-purple-700">{soilSampleResult[2].average_raw ?? '--'}</span>
                      </p>
                      <p className="text-xs text-purple-600">
                        Calibrado: {soilSampleResult[2].average ?? '--'}% &nbsp;·&nbsp; Lecturas: {soilSampleResult[2].captured}
                      </p>
                    </div>
                    {soilSampleResult[2].average_raw != null && (
                      <div className="flex gap-2">
                        <button type="button" onClick={() => handleNumberChange('suelo2_valor_seco', String(soilSampleResult[2].average_raw))} className="rounded border border-amber-400 bg-amber-50 px-2 py-1 text-xs font-medium text-amber-800 hover:bg-amber-100">
                          ↑ Usar como seco
                        </button>
                        <button type="button" onClick={() => handleNumberChange('suelo2_valor_mojado', String(soilSampleResult[2].average_raw))} className="rounded border border-blue-400 bg-blue-50 px-2 py-1 text-xs font-medium text-blue-800 hover:bg-blue-100">
                          ↑ Usar como mojado
                        </button>
                      </div>
                    )}
                  </div>
                  <div className="mt-2 overflow-x-auto">
                    <table className="min-w-full text-xs">
                      <thead>
                        <tr className="text-left">
                          <th className="px-2 py-1">Muestra</th>
                          <th className="px-2 py-1">RAW (ADC)</th>
                          <th className="px-2 py-1">%</th>
                          <th className="px-2 py-1">Hora</th>
                        </tr>
                      </thead>
                      <tbody>
                        {soilSampleResult[2].readings.map((reading) => (
                          <tr key={`s2-${reading.second}`} className="border-t border-purple-200/60">
                            <td className="px-2 py-1">{reading.second}</td>
                            <td className="px-2 py-1 font-mono font-semibold">{reading.value_raw ?? '--'}</td>
                            <td className="px-2 py-1">{reading.value != null ? `${reading.value}%` : '--'}</td>
                            <td className="px-2 py-1">{reading.timestamp ? new Date(reading.timestamp).toLocaleTimeString('es-ES') : '--'}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>

          </div>
        </section>
      </div>

      {/* Botones guardar / recargar */}
      <div className="mt-8 flex items-center gap-3">
        <button
          onClick={handleSave}
          disabled={saving}
          className="px-6 py-3 rounded-xl bg-green-700 text-white font-semibold hover:bg-green-800 disabled:opacity-50 disabled:cursor-not-allowed focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-green-700"
        >
          {saving ? 'Guardando...' : 'Guardar calibracion'}
        </button>
        <button
          onClick={fetchCalibration}
          disabled={saving}
          className="px-4 py-3 rounded-xl border border-gray-300 text-gray-700 hover:bg-gray-50 disabled:opacity-50 inline-flex items-center gap-2"
        >
          <span className="material-icons text-xl">refresh</span>
          Recargar
        </button>
      </div>

      {form.updated_at && (
        <p className="mt-4 text-sm text-gray-500">
          Ultima actualizacion: {new Date(form.updated_at).toLocaleString('es-ES')}
        </p>
      )}
    </div>
  );
}