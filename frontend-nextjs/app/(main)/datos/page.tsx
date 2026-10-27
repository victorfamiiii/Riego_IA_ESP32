'use client';

import { useState, useEffect } from 'react';
import {
  LineChart,
  Line,
  AreaChart,
  Area,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import TwemojiEmoji from '../../components/TwemojiEmoji';

interface Measurement {
  id: number;
  temperatura: number;
  humedad: number;
  esp32_ip: string;
  created_at: string;
}

interface SoilReading {
  id: number;
  device_name?: string;
  tipo_planta?: string;
  humedad_suelo: number;
  created_at: string;
}

interface LuminosityReading {
  id: number;
  device_name?: string;
  luminosidad: number;
  created_at: string;
}

interface PaginatedResponse<T> {
  results?: T[];
}

type ChartType = 'line' | 'area' | 'bar';
type DataType = 'environment' | 'soil' | 'luminosity';

const API_BASE = 'https://riegoesp32.victorfg.work';

export default function DatosPage() {
  const [measurements, setMeasurements] = useState<Measurement[]>([]);
  const [soilReadings, setSoilReadings] = useState<SoilReading[]>([]);
  const [luminosityReadings, setLuminosityReadings] = useState<LuminosityReading[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const [chartType, setChartType] = useState<ChartType>('area');
  const [dataType, setDataType] = useState<DataType>('environment');

  const normalizeList = <T,>(data: unknown): T[] => {
    if (Array.isArray(data)) return data as T[];
    if (data && typeof data === 'object') {
      const maybePaginated = data as PaginatedResponse<T>;
      if (Array.isArray(maybePaginated.results)) return maybePaginated.results;
    }
    return [];
  };

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [envRes, soilRes, luxRes] = await Promise.allSettled([
          fetch(`${API_BASE}/api/measurements/history`, { cache: 'no-store' }),
          fetch(`${API_BASE}/api/soil`, { cache: 'no-store' }),
          fetch(`${API_BASE}/api/luminosity`, { cache: 'no-store' }),
        ]);

        let hasAnyData = false;

        if (envRes.status === 'fulfilled' && envRes.value.ok) {
          setMeasurements(normalizeList<Measurement>(await envRes.value.json()));
          hasAnyData = true;
        } else {
          setMeasurements([]);
        }

        if (soilRes.status === 'fulfilled' && soilRes.value.ok) {
          setSoilReadings(normalizeList<SoilReading>(await soilRes.value.json()));
          hasAnyData = true;
        } else {
          setSoilReadings([]);
        }

        if (luxRes.status === 'fulfilled' && luxRes.value.ok) {
          setLuminosityReadings(normalizeList<LuminosityReading>(await luxRes.value.json()));
          hasAnyData = true;
        } else {
          setLuminosityReadings([]);
        }

        if (!hasAnyData) throw new Error('No se pudo cargar ningún tipo de dato');
        setError(null);
      } catch (err) {
        setError(err as Error);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
    const interval = setInterval(fetchData, 60000);
    return () => clearInterval(interval);
  }, []);

  const formatTime = (dateStr: string) =>
    new Date(dateStr).toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' });

  const chartData = (() => {
    if (dataType === 'soil') {
      const groupedByMinute = new Map<
        string,
        { timestamp: number; time: string; fullDate: string; lechuga: number | null; fresa: number | null }
      >();

      [...soilReadings]
        .slice(0, 50)
        .sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime())
        .forEach((item) => {
          const dt = new Date(item.created_at);
          dt.setSeconds(0, 0);
          const bucketKey = dt.toISOString();

          if (!groupedByMinute.has(bucketKey)) {
            groupedByMinute.set(bucketKey, {
              timestamp: dt.getTime(),
              time: formatTime(item.created_at),
              fullDate: dt.toLocaleString('es-ES'),
              lechuga: null,
              fresa: null,
            });
          }

          const row = groupedByMinute.get(bucketKey)!;
          const plant = (item.tipo_planta || '').toLowerCase();
          if (plant === 'lechuga') row.lechuga = item.humedad_suelo;
          if (plant === 'fresa') row.fresa = item.humedad_suelo;
        });

      return [...groupedByMinute.values()].sort((a, b) => a.timestamp - b.timestamp);
    }

    if (dataType === 'luminosity') {
      return [...luminosityReadings]
        .slice(0, 50)
        .sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime())
        .map((item) => ({
          time: formatTime(item.created_at),
          fullDate: new Date(item.created_at).toLocaleString('es-ES'),
          value1: item.luminosidad,
          device: item.device_name || '-',
        }));
    }

    return [...measurements]
      .slice(0, 50)
      .sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime())
      .map((item) => ({
        time: formatTime(item.created_at),
        fullDate: new Date(item.created_at).toLocaleString('es-ES'),
        value1: item.temperatura,
        value2: item.humedad,
        device: item.esp32_ip || '-',
      }));
  })();

  const chartMeta = {
    environment: {
      titleText: 'Temperatura y Humedad Ambiente',
      titleEmoji: '🌤️',
      series: [
        { key: 'value1', label: 'Temperatura (°C)', color: '#ef4444' },
        { key: 'value2', label: 'Humedad ambiente (%)', color: '#3b82f6' },
      ],
    },
    soil: {
      titleText: 'Humedad del Suelo',
      titleEmoji: '🌱',
      series: [
        { key: 'lechuga', label: 'Lechuga (%)', color: '#16a34a' },
        { key: 'fresa', label: 'Fresa (%)', color: '#ec4899' },
      ],
    },
    luminosity: {
      titleText: 'Luminosidad',
      titleEmoji: '☀️',
      series: [
        { key: 'value1', label: 'Luminosidad (lux)', color: '#f59e0b' },
      ],
    },
  } as const;

  const activeMeta = chartMeta[dataType];

  const renderChart = () => {
    const commonProps = {
      data: chartData,
      margin: { top: 10, right: 30, left: 0, bottom: 0 },
    };

    const chartComponents = (
      <>
        <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
        <XAxis dataKey="time" stroke="#6b7280" style={{ fontSize: '12px' }} />
        <YAxis stroke="#6b7280" style={{ fontSize: '12px' }} />
        <Tooltip
          contentStyle={{
            backgroundColor: 'rgba(255, 255, 255, 0.95)',
            border: '1px solid #e5e7eb',
            borderRadius: '12px',
            boxShadow: '0 4px 6px rgba(0, 0, 0, 0.1)',
          }}
        />
        <Legend />
      </>
    );

    if (chartType === 'line') {
      return (
        <LineChart {...commonProps}>
          {chartComponents}
          {activeMeta.series.map((series) => (
            <Line
              key={series.key}
              type="monotone"
              dataKey={series.key}
              name={series.label}
              stroke={series.color}
              strokeWidth={3}
              dot={{ fill: series.color, r: 4 }}
              connectNulls={dataType === 'soil'}
            />
          ))}
        </LineChart>
      );
    }

    if (chartType === 'bar') {
      return (
        <BarChart {...commonProps}>
          {chartComponents}
          {activeMeta.series.map((series) => (
            <Bar
              key={series.key}
              dataKey={series.key}
              name={series.label}
              fill={series.color}
              radius={[8, 8, 0, 0]}
            />
          ))}
        </BarChart>
      );
    }

    return (
      <AreaChart {...commonProps}>
        <defs>
          {activeMeta.series.map((series) => (
            <linearGradient key={series.key} id={`gradient-${series.key}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor={series.color} stopOpacity={0.8} />
              <stop offset="95%" stopColor={series.color} stopOpacity={0.1} />
            </linearGradient>
          ))}
        </defs>
        {chartComponents}
        {activeMeta.series.map((series) => (
          <Area
            key={series.key}
            type="monotone"
            dataKey={series.key}
            name={series.label}
            stroke={series.color}
            fill={`url(#gradient-${series.key})`}
            strokeWidth={2}
            connectNulls={dataType === 'soil'}
          />
        ))}
      </AreaChart>
    );
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <div className="animate-spin rounded-full h-16 w-16 border-t-4 border-b-4 border-green-500 mx-auto mb-4" />
          <p className="text-gray-600">Cargando datos...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-8">
        <div className="bg-red-50 border border-red-200 rounded-2xl p-6">
          <p className="text-red-600 font-semibold">Error: {error.message}</p>
        </div>
      </div>
    );
  }

  const tableRows =
    dataType === 'soil'
      ? soilReadings.slice(0, 20)
      : dataType === 'luminosity'
      ? luminosityReadings.slice(0, 20)
      : measurements.slice(0, 20);

  return (
    <div className="p-8">
      <div className="mb-8">
        <h1 className="text-4xl font-bold mb-2 flex items-center gap-3 text-gray-900">
          <TwemojiEmoji emoji="📊" size={36} />
          <span>Datos y Mediciones</span>
        </h1>
        <p className="text-gray-600">
          Visualización detallada de las mediciones del sistema
        </p>
      </div>

        {/* Selector tipo de gráfico */}
        <div className="bg-white/80 backdrop-blur-lg rounded-2xl shadow-xl p-6 mb-4 border border-gray-100">
          <div className="flex flex-wrap items-center gap-4">
            <span className="material-icons text-2xl text-green-600">bar_chart</span>
            <span className="font-semibold text-gray-700">Tipo de gráfico:</span>
            <div className="flex gap-2">
              {(['line', 'area', 'bar'] as ChartType[]).map((type) => (
                <button
                  key={type}
                  onClick={() => setChartType(type)}
                  className={`px-4 py-2 rounded-xl font-semibold transition-all ${
                    chartType === type
                      ? 'bg-green-700 text-white shadow-lg hover:bg-green-800'
                      : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                  }`}
                >
                  {type === 'line' ? 'Líneas' : type === 'area' ? 'Áreas' : 'Barras'}
                </button>
              ))}
            </div>
          </div>
        </div>

          {/* Selector tipo de dato */}
        <div className="bg-white/80 backdrop-blur-lg rounded-2xl shadow-xl p-6 mb-6 border border-gray-100">
      <div className="flex flex-wrap items-center gap-4">
        <span className="font-semibold text-gray-700">Tipo de dato:</span>
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => setDataType('environment')}
            className={`px-4 py-2 rounded-xl font-semibold transition-all flex items-center gap-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-blue-700 ${
              dataType === 'environment'
                ? 'bg-blue-700 text-white shadow-lg hover:bg-blue-800'
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
            }`}
          >
            <TwemojiEmoji emoji="🌤️" size={18} />
            Temperatura y humedad ambiente
          </button>

          <button
            onClick={() => setDataType('soil')}
            className={`px-4 py-2 rounded-xl font-semibold transition-all flex items-center gap-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-green-700 ${
              dataType === 'soil'
                ? 'bg-green-700 text-white shadow-lg hover:bg-green-800'
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
            }`}
          >
            <TwemojiEmoji emoji="🌱" size={18} />
            Humedad del suelo
          </button>

          <button
            onClick={() => setDataType('luminosity')}
            className={`px-4 py-2 rounded-xl font-semibold transition-all flex items-center gap-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-amber-700 ${
              dataType === 'luminosity'
                ? 'bg-amber-700 text-white shadow-lg hover:bg-amber-800'
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
            }`}
          >
            <TwemojiEmoji emoji="☀️" size={18} />
            Luminosidad
          </button>
        </div>
      </div>
    </div>

      {/* Gráfico */}
      <div className="bg-white/80 backdrop-blur-lg rounded-3xl shadow-xl p-6 mb-6 border border-gray-100">
        <h2 className="text-2xl font-bold mb-6 text-gray-800 flex items-center gap-2">
          <TwemojiEmoji emoji={activeMeta.titleEmoji} size={24} />
          {activeMeta.titleText} (últimos 50 registros)
        </h2>
        <ResponsiveContainer width="100%" height={400}>
          {renderChart()}
        </ResponsiveContainer>
      </div>

      {/* Tabla historial */}
      <div className="bg-white/80 backdrop-blur-lg rounded-3xl shadow-xl p-6 border border-gray-100">
        <div className="flex items-center gap-3 mb-6">
          <span className="material-icons text-2xl text-green-600">schedule</span>
          <h2 className="text-2xl font-bold text-gray-800">Historial de mediciones</h2>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              {dataType === 'environment' && (
                <tr className="border-b-2 border-gray-200">
                  <th className="text-left p-3 font-semibold text-gray-700">Fecha y Hora</th>
                  <th className="text-left p-3 font-semibold text-gray-700">Temperatura</th>
                  <th className="text-left p-3 font-semibold text-gray-700">Humedad</th>
                  <th className="text-left p-3 font-semibold text-gray-700">ESP32 IP</th>
                </tr>
              )}
              {dataType === 'soil' && (
                <tr className="border-b-2 border-gray-200">
                  <th className="text-left p-3 font-semibold text-gray-700">Fecha y Hora</th>
                  <th className="text-left p-3 font-semibold text-gray-700">Humedad suelo</th>
                  <th className="text-left p-3 font-semibold text-gray-700">Planta</th>
                  <th className="text-left p-3 font-semibold text-gray-700">Dispositivo</th>
                </tr>
              )}
              {dataType === 'luminosity' && (
                <tr className="border-b-2 border-gray-200">
                  <th className="text-left p-3 font-semibold text-gray-700">Fecha y Hora</th>
                  <th className="text-left p-3 font-semibold text-gray-700">Luminosidad</th>
                  <th className="text-left p-3 font-semibold text-gray-700">Dispositivo</th>
                </tr>
              )}
            </thead>
            <tbody>
              {dataType === 'environment' &&
                (tableRows as Measurement[]).map((m) => (
                  <tr key={m.id} className="border-b border-gray-100 hover:bg-green-50 transition-colors">
                    <td className="p-3 text-gray-600">{new Date(m.created_at).toLocaleString('es-ES')}</td>
                    <td className="p-3">
                      <span className="px-3 py-1 bg-red-100 text-red-700 rounded-lg font-semibold">
                        {m.temperatura.toFixed(1)}°C
                      </span>
                    </td>
                    <td className="p-3">
                      <span className="px-3 py-1 bg-blue-100 text-blue-700 rounded-lg font-semibold">
                        {m.humedad.toFixed(1)}%
                      </span>
                    </td>
                    <td className="p-3">
                      <div className="flex items-center gap-2">
                        <span className="material-icons text-base text-gray-400">storage</span>
                        <span className="text-gray-600 font-mono text-sm">{m.esp32_ip || '-'}</span>
                      </div>
                    </td>
                  </tr>
                ))}

              {dataType === 'soil' &&
                (tableRows as SoilReading[]).map((m) => (
                  <tr key={m.id} className="border-b border-gray-100 hover:bg-green-50 transition-colors">
                    <td className="p-3 text-gray-600">{new Date(m.created_at).toLocaleString('es-ES')}</td>
                    <td className="p-3">
                      <span className="px-3 py-1 bg-green-100 text-green-700 rounded-lg font-semibold">
                        {m.humedad_suelo.toFixed(1)}%
                      </span>
                    </td>
                    <td className="p-3 text-gray-700 capitalize">
                      <div className="flex items-center gap-2">
                        {m.tipo_planta?.toLowerCase() === 'fresa' && <TwemojiEmoji emoji="🍓" size={16} />}
                        {m.tipo_planta?.toLowerCase() === 'lechuga' && <TwemojiEmoji emoji="🥬" size={16} />}
                        {m.tipo_planta || '-'}
                      </div>
                    </td>
                    <td className="p-3 text-gray-700">{m.device_name || '-'}</td>
                  </tr>
                ))}

              {dataType === 'luminosity' &&
                (tableRows as LuminosityReading[]).map((m) => (
                  <tr key={m.id} className="border-b border-gray-100 hover:bg-green-50 transition-colors">
                    <td className="p-3 text-gray-600">{new Date(m.created_at).toLocaleString('es-ES')}</td>
                    <td className="p-3">
                      <span className="px-3 py-1 bg-amber-100 text-amber-700 rounded-lg font-semibold">
                        {m.luminosidad.toFixed(1)} lux
                      </span>
                    </td>
                    <td className="p-3 text-gray-700">{m.device_name || '-'}</td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}