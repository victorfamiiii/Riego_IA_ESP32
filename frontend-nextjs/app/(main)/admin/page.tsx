'use client';

import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { useUser } from '../../../lib/UserContext';

const API_BASE = 'https://riegoesp32.victorfg.work';

interface TableInfo {
  key: string;
  name: string;
  description: string;
  count: number;
}

interface FieldSchema {
  name: string;
  type: string;
  verbose_name: string;
  null: boolean;
  blank: boolean;
  editable: boolean;
  help_text: string;
  choices?: [string, string][];
  related_model?: string;
}

interface TableSchema {
  table: string;
  name: string;
  description: string;
  fields: FieldSchema[];
}

const HIDDEN_ADMIN_TABLE_KEYS = new Set(['training_datasets', 'model_versions']);

const PLANT_CONFIG_OPTIONS = [
  { value: 'lechuga', label: 'Lechuga' },
  { value: 'fresa', label: 'Fresa' },
] as const;

type PlantConfigOption = (typeof PLANT_CONFIG_OPTIONS)[number]['value'];

const isPlantConfigOption = (value: unknown): value is PlantConfigOption =>
  value === 'lechuga' || value === 'fresa';

export default function AdminPage() {
  const router = useRouter();
  const { isAdmin, isLoading: userLoading } = useUser();

  const [tables, setTables] = useState<TableInfo[]>([]);
  const [selectedTable, setSelectedTable] = useState<string | null>(null);
  const [tableSchema, setTableSchema] = useState<TableSchema | null>(null);
  const [tableData, setTableData] = useState<Array<Record<string, unknown>>>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [total, setTotal] = useState(0);
  const pageSize = 15;

  const [showModal, setShowModal] = useState(false);
  const [modalMode, setModalMode] = useState<'create' | 'edit'>('create');
  const [editingItem, setEditingItem] = useState<Record<string, unknown> | null>(null);
  const [formData, setFormData] = useState<Record<string, unknown>>({});
  const [plantConfigSnapshot, setPlantConfigSnapshot] = useState<Record<string, unknown>>({});
  const [saving, setSaving] = useState(false);

  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [itemToDelete, setItemToDelete] = useState<Record<string, unknown> | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [exportingCsv, setExportingCsv] = useState(false);

  const getCsrfToken = () => {
    if (typeof document === 'undefined') return '';
    const tokenRow = document.cookie
      .split(';')
      .map((row) => row.trim())
      .find((row) => row.startsWith('csrftoken='));
    return tokenRow ? decodeURIComponent(tokenRow.split('=')[1]) : '';
  };

  const ensureCsrfToken = async () => {
    const current = getCsrfToken();
    if (current) return current;
    await fetch(`${API_BASE}/api/auth/csrf`, { credentials: 'include', cache: 'no-store' });
    return getCsrfToken();
  };

  const withCsrfHeaders = async (baseHeaders: Record<string, string> = {}) => {
    const headers = { ...baseHeaders };
    const csrfToken = await ensureCsrfToken();
    if (csrfToken) headers['X-CSRFToken'] = csrfToken;
    return headers;
  };

  // Mover definiciones de funciones ANTES de useEffect
  const fetchTables = useCallback(async () => {
    try {
      setLoading(true);
      const res = await fetch(`${API_BASE}/api/admin/tables`, { credentials: 'include' });
      if (res.ok) {
        const data = await res.json();
        const visibleTables = (data.tables || []).filter(
          (table: TableInfo) => !HIDDEN_ADMIN_TABLE_KEYS.has(table.key)
        );
        setTables(visibleTables);
        if (selectedTable && HIDDEN_ADMIN_TABLE_KEYS.has(selectedTable)) setSelectedTable(null);
      } else if (res.status === 403) {
        setError('No tienes permisos de administrador');
      } else {
        setError('Error al cargar las tablas');
      }
    } catch {
      setError('Error de conexión');
    } finally {
      setLoading(false);
    }
  }, [selectedTable]);

  const fetchTableSchema = useCallback(async () => {
    if (!selectedTable) return;
    try {
      const res = await fetch(`${API_BASE}/api/admin/tables/${selectedTable}/schema`, { credentials: 'include' });
      if (res.ok) setTableSchema(await res.json());
    } catch (err) {
      console.error('Error fetching schema:', err);
    }
  }, [selectedTable]);

  const fetchTableData = useCallback(async () => {
    if (!selectedTable) return;
    try {
      setLoading(true);
      const res = await fetch(
        `${API_BASE}/api/admin/tables/${selectedTable}?page=${page}&page_size=${pageSize}`,
        { credentials: 'include' }
      );
      if (res.ok) {
        const data = await res.json();
        setTableData(data.data);
        setTotalPages(data.total_pages);
        setTotal(data.total);
      }
    } catch (err) {
      console.error('Error fetching data:', err);
    } finally {
      setLoading(false);
    }
  }, [selectedTable, page, pageSize]);

  useEffect(() => {
    if (!userLoading && !isAdmin) { router.push('/'); return; }
    if (isAdmin) fetchTables();
  }, [isAdmin, userLoading, router, fetchTables]);

  useEffect(() => {
    if (selectedTable) { fetchTableSchema(); fetchTableData(); }
  }, [selectedTable, page, fetchTableSchema, fetchTableData]);


  const handleCreate = () => {
    setModalMode('create');
    setEditingItem(null);
    setPlantConfigSnapshot({});
    const initialData: Record<string, unknown> = {};
    if (tableSchema) {
      const hasPlantConfigField = tableSchema.fields.some(
        (field) => field.name === 'configuracion_por_planta' && field.type === 'JSONField'
      );
      if (hasPlantConfigField) initialData.configuracion_por_planta = 'lechuga';
    }
    setFormData(initialData);
    setShowModal(true);
  };

  const getSelectedPlantFromConfig = (value: unknown): PlantConfigOption => {
    if (isPlantConfigOption(value)) return value;
    if (value && typeof value === 'object') {
      const config = value as Record<string, unknown>;
      if ('lechuga' in config) return 'lechuga';
      if ('fresa' in config) return 'fresa';
    }
    if (typeof value === 'string') {
      try {
        const parsed = JSON.parse(value);
        if (parsed && typeof parsed === 'object') {
          if ('lechuga' in parsed) return 'lechuga';
          if ('fresa' in parsed) return 'fresa';
        }
      } catch { return 'lechuga'; }
    }
    return 'lechuga';
  };

  const parsePlantConfigObject = (value: unknown): Record<string, unknown> => {
    if (value && typeof value === 'object' && !Array.isArray(value)) return value as Record<string, unknown>;
    if (typeof value === 'string') {
      try {
        const parsed = JSON.parse(value);
        if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) return parsed as Record<string, unknown>;
      } catch { return {}; }
    }
    return {};
  };

  const buildPlantConfigFromSelection = (selectedPlant: PlantConfigOption, baseConfig: Record<string, unknown>) => ({
    ...baseConfig,
    [selectedPlant]: {
      umbral_humedad_minimo: Number(formData.umbral_humedad_minimo ?? 40),
      tiempo_riego_segundos: Number(formData.tiempo_riego_segundos ?? 30),
      max_riegos_dia: Number(formData.max_riegos_dia ?? 6),
      tiempo_minimo_entre_riegos: Number(formData.tiempo_minimo_entre_riegos ?? 3600),
    },
  });

  const handleEdit = (item: Record<string, unknown>) => {
    setModalMode('edit');
    setEditingItem(item);
    const prepared = { ...item };
    setPlantConfigSnapshot(parsePlantConfigObject(prepared.configuracion_por_planta));
    if ('configuracion_por_planta' in prepared)
      prepared.configuracion_por_planta = getSelectedPlantFromConfig(prepared.configuracion_por_planta);
    setFormData(prepared);
    setShowModal(true);
  };

  const handleDelete = (item: Record<string, unknown>) => {
    setItemToDelete(item);
    setShowDeleteConfirm(true);
  };

  const confirmDelete = async () => {
    if (!itemToDelete || !selectedTable) return;
    try {
      setDeleting(true);
      const csrfHeaders = await withCsrfHeaders();
      const res = await fetch(`${API_BASE}/api/admin/tables/${selectedTable}/${itemToDelete.id}`, {
        method: 'DELETE',
        headers: csrfHeaders,
        credentials: 'include',
      });
      if (res.ok) {
        fetchTableData();
        fetchTables();
        setShowDeleteConfirm(false);
        setItemToDelete(null);
      } else {
        const data = await res.json();
        setError(data.error || 'Error al eliminar');
      }
    } catch { setError('Error de conexión'); }
    finally { setDeleting(false); }
  };

const handleSave = async () => {
  if (!selectedTable) return;

  try {
    setSaving(true);

    let url: string;
    const method = modalMode === 'create' ? 'POST' : 'PUT';

    if (modalMode === 'create') {
      url = `${API_BASE}/api/admin/tables/${selectedTable}`;
    } else {
      if (!editingItem) {
        setError('No hay elemento para editar');
        setSaving(false);
        return;
      }

      url = `${API_BASE}/api/admin/tables/${selectedTable}/${editingItem.id}`;
    }

    const submitData = { ...formData };

    if (tableSchema) {
      tableSchema.fields.forEach((field) => {
        if (!field.editable || field.name === 'id') delete submitData[field.name];
      });

      const plantConfigField = tableSchema.fields.find(
        (field) => field.name === 'configuracion_por_planta' && field.type === 'JSONField'
      );

      if (plantConfigField && 'configuracion_por_planta' in submitData) {
        const selectedPlant = submitData.configuracion_por_planta;

        if (!isPlantConfigOption(selectedPlant)) {
          setError('Selecciona una planta válida (lechuga o fresa).');
          setSaving(false);
          return;
        }

        let currentConfig: Record<string, unknown> = {};

        if (modalMode === 'edit') {
          if (!editingItem) {
            setError('No hay elemento para editar');
            setSaving(false);
            return;
          }

          currentConfig = parsePlantConfigObject(editingItem.configuracion_por_planta);
        }

        const baseConfig = modalMode === 'edit' ? currentConfig : plantConfigSnapshot;

        submitData.configuracion_por_planta = buildPlantConfigFromSelection(
          selectedPlant,
          baseConfig
        );
      }
    }

    const csrfHeaders = await withCsrfHeaders({ 'Content-Type': 'application/json' });

    const res = await fetch(url, {
      method,
      headers: csrfHeaders,
      credentials: 'include',
      body: JSON.stringify(submitData),
    });

    if (res.ok) {
      fetchTableData();
      fetchTables();
      setShowModal(false);
      setFormData({});
      setEditingItem(null);
    } else {
      const data = await res.json();
      setError(data.error || (data.details ? JSON.stringify(data.details) : 'Error al guardar'));
    }
  } catch {
    setError('Error de conexión');
  } finally {
    setSaving(false);
  }
};

  const toCsvValue = (value: unknown): string => {
    if (value === null || value === undefined) return '';
    const text = typeof value === 'object' ? JSON.stringify(value) : String(value);
    return `"${text.replace(/"/g, '""')}"`;
  };

  const handleDownloadCsv = async () => {
    if (!selectedTable || !tableSchema) return;
    try {
      setExportingCsv(true);
      setError(null);
      const exportPageSize = 500;
      let exportPage = 1;
      let exportTotalPages = 1;
      const allRows: Array<Record<string, unknown>> = [];
      while (exportPage <= exportTotalPages) {
        const res = await fetch(
          `${API_BASE}/api/admin/tables/${selectedTable}?page=${exportPage}&page_size=${exportPageSize}`,
          { credentials: 'include' }
        );
        if (!res.ok) throw new Error(`No se pudo exportar CSV (status ${res.status})`);
        const data = await res.json();
        allRows.push(...(data.data || []));
        exportTotalPages = data.total_pages || 1;
        exportPage += 1;
      }
      const fields = tableSchema.fields
        .filter((f) => !f.name.endsWith('_set') && f.type !== 'ManyToOneRel')
        .map((f) => ({ name: f.name, label: String(f.verbose_name || f.name) }));
      const csvColumns = [...fields];
      if (selectedTable === 'soil_moisture') {
        const humedadCol = csvColumns.find((col) => col.name === 'humedad_suelo');
        if (humedadCol) humedadCol.label = 'humedad_suelo_porcentaje_calibrado';
        if (!csvColumns.some((col) => col.name === 'humedad_suelo_raw'))
          csvColumns.push({ name: 'humedad_suelo_raw', label: 'humedad_suelo_raw_adc' });
      }
      const header = csvColumns.map((f) => toCsvValue(f.label)).join(',');
      const rows = allRows.map((item) => csvColumns.map((f) => toCsvValue(item[f.name])).join(','));
      const csvContent = [header, ...rows].join('\n');
      const blob = new Blob([`\uFEFF${csvContent}`], { type: 'text/csv;charset=utf-8;' });
      const url = URL.createObjectURL(blob);
      const now = new Date();
      const timestamp = `${now.getFullYear()}${String(now.getMonth() + 1).padStart(2, '0')}${String(now.getDate()).padStart(2, '0')}_${String(now.getHours()).padStart(2, '0')}${String(now.getMinutes()).padStart(2, '0')}${String(now.getSeconds()).padStart(2, '0')}`;
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `${selectedTable}_${timestamp}.csv`);
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al exportar CSV');
    } finally {
      setExportingCsv(false);
    }
  };

  const renderFieldInput = (field: FieldSchema) => {
  const rawValue = formData[field.name];
  const value = rawValue ?? '';
  const fieldId = `admin-field-${field.name}`;

  const inputValue: string | number | readonly string[] | undefined =
    typeof value === 'string' || typeof value === 'number'
      ? value
      : Array.isArray(value)
        ? value.map(String)
        : value && typeof value === 'object'
          ? JSON.stringify(value)
          : '';

  if (!field.editable || field.name === 'id') {
    return (
      <input
        id={fieldId}
        name={field.name}
        type="text"
        value={inputValue}
        disabled
        className="w-full px-3 py-2 bg-gray-100 border border-gray-200 rounded-lg text-black"
      />
    );
  }

  if (field.choices && field.choices.length > 0) {
    return (
      <select
        id={fieldId}
        name={field.name}
        value={typeof value === 'string' || typeof value === 'number' ? String(value) : ''}
        onChange={(e) => setFormData({ ...formData, [field.name]: e.target.value })}
        className="w-full px-3 py-2 border border-gray-300 rounded-lg text-black focus:ring-2 focus:ring-green-500 focus:border-transparent"
      >
        <option value="">Seleccionar...</option>
        {field.choices.map(([val, label]) => (
          <option key={val} value={val}>
            {label}
          </option>
        ))}
      </select>
    );
  }

  if (field.type === 'BooleanField') {
    return (
      <button
        id={fieldId}
        type="button"
        onClick={() => setFormData({ ...formData, [field.name]: !formData[field.name] })}
        className={`relative w-14 h-8 rounded-full transition-colors ${formData[field.name] ? 'bg-green-500' : 'bg-gray-300'}`}
      >
        <div
          className={`absolute top-1 left-1 w-6 h-6 bg-white rounded-full transition-transform ${formData[field.name] ? 'translate-x-6' : ''}`}
        />
      </button>
    );
  }

  if (field.type === 'FloatField' || field.type === 'IntegerField') {
    return (
      <input
        id={fieldId}
        name={field.name}
        type="number"
        step={field.type === 'FloatField' ? '0.01' : '1'}
        value={typeof value === 'string' || typeof value === 'number' ? value : ''}
        onChange={(e) =>
          setFormData({
            ...formData,
            [field.name]: e.target.value === '' ? null : Number(e.target.value),
          })
        }
        className="w-full px-3 py-2 border border-gray-300 rounded-lg text-black focus:ring-2 focus:ring-green-500 focus:border-transparent"
      />
    );
  }

  if (field.type === 'DateTimeField' || field.type === 'DateField') {
    return (
      <input
        id={fieldId}
        name={field.name}
        type="datetime-local"
        value={typeof value === 'string' ? value.slice(0, 16) : ''}
        onChange={(e) => setFormData({ ...formData, [field.name]: e.target.value })}
        className="w-full px-3 py-2 border border-gray-300 rounded-lg text-black focus:ring-2 focus:ring-green-500 focus:border-transparent"
      />
    );
  }

  if (field.type === 'TextField') {
    return (
      <textarea
        id={fieldId}
        name={field.name}
        value={typeof value === 'string' ? value : String(inputValue ?? '')}
        onChange={(e) => setFormData({ ...formData, [field.name]: e.target.value })}
        rows={3}
        className="w-full px-3 py-2 border border-gray-300 rounded-lg text-black focus:ring-2 focus:ring-green-500 focus:border-transparent"
      />
    );
  }

  if (field.type === 'JSONField' && field.name === 'configuracion_por_planta') {
    const selected = getSelectedPlantFromConfig(value);

    return (
      <select
        id={fieldId}
        name={field.name}
        value={selected}
        onChange={(e) =>
          setFormData({ ...formData, [field.name]: e.target.value as PlantConfigOption })
        }
        className="w-full px-3 py-2 border border-gray-300 rounded-lg text-black focus:ring-2 focus:ring-green-500 focus:border-transparent"
      >
        {PLANT_CONFIG_OPTIONS.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    );
  }

  return (
    <input
      id={fieldId}
      name={field.name}
      type="text"
      value={inputValue}
      onChange={(e) => setFormData({ ...formData, [field.name]: e.target.value })}
      className="w-full px-3 py-2 border border-gray-300 rounded-lg text-black focus:ring-2 focus:ring-green-500 focus:border-transparent"
    />
  );
};

  if (userLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-16 w-16 border-t-4 border-b-4 border-green-500" />
      </div>
    );
  }

  if (!isAdmin) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          {/* CORREGIDO: text-6xl + leading-none en lugar de h-16 w-16 */}
          <span className="material-icons text-6xl leading-none text-red-500 block mb-4">error</span>
          <h2 className="text-2xl font-bold text-gray-800 mb-2">Acceso Denegado</h2>
          <p className="text-gray-600">No tienes permisos de administrador</p>
        </div>
      </div>
    );
  }

  return (
    <div className="p-8">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-4xl font-bold mb-2 flex items-center gap-2 text-gray-900">
          <span aria-hidden="true">🔧</span>
          <span>Panel de Administración</span>
        </h1>
        <p className="text-gray-600">Gestiona las tablas y datos del sistema</p>
      </div>

      {/* Error Alert */}
      {error && (
        <div className="mb-6 bg-red-50 border border-red-200 rounded-xl p-4 flex items-center gap-3">
          {/* CORREGIDO */}
          <span className="material-icons text-2xl leading-none text-red-500 shrink-0">error</span>
          <p className="text-red-700 flex-1">{error}</p>
          <button
            onClick={() => setError(null)}
            className="flex items-center justify-center p-1 hover:bg-red-100 rounded-lg transition-colors"
          >
            <span className="material-icons text-xl leading-none text-red-500">close</span>
          </button>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Lista de Tablas */}
        <div className="lg:col-span-1">
          <div className="bg-white/80 backdrop-blur-lg rounded-3xl shadow-xl p-6 border border-gray-100">
            <div className="flex items-center gap-3 mb-6">
              {/* CORREGIDO: flex items-center justify-center en el div del icono */}
              <div className="bg-gradient-to-br from-orange-500 to-red-600 p-3 rounded-2xl flex items-center justify-center">
                <span className="material-icons text-2xl leading-none text-white">table_chart</span>
              </div>
              <h2 className="text-xl font-bold text-gray-800">Tablas</h2>
            </div>
            <div className="space-y-2">
              {tables.map((table) => (
                <button key={table.key} onClick={() => { setSelectedTable(table.key); setPage(1); }}
                  className={`w-full text-left p-4 rounded-xl transition-all ${
                    selectedTable === table.key
                      ? 'bg-gradient-to-r from-orange-500 to-red-500 text-white shadow-lg'
                      : 'bg-gray-50 hover:bg-gray-100 text-gray-700'
                  }`}>
                  <p className="font-semibold">{table.name}</p>
                  <p className={`text-sm ${selectedTable === table.key ? 'text-orange-100' : 'text-gray-500'}`}>
                    {table.count} registros
                  </p>
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Vista de Tabla */}
        <div className="lg:col-span-3">
          {selectedTable ? (
            <div className="bg-white/80 backdrop-blur-lg rounded-3xl shadow-xl border border-gray-100 overflow-hidden">
              {/* Header tabla */}
              <div className="p-6 border-b border-gray-100">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-2xl font-bold text-gray-800">{tableSchema?.name || selectedTable}</h3>
                    <p className="text-gray-600 text-sm">{tableSchema?.description}</p>
                  </div>
                  <div className="flex gap-3">
                    {/* CORREGIDO: flex items-center justify-center en todos los botones */}
                    <button onClick={fetchTableData}
                      className="flex items-center justify-center p-3 bg-gray-100 hover:bg-gray-200 rounded-xl transition-colors"
                      title="Recargar">
                      <span className={`material-icons text-xl leading-none text-gray-600 ${loading ? 'animate-spin' : ''}`}>refresh</span>
                    </button>
                    <button onClick={handleDownloadCsv} disabled={exportingCsv || loading}
                      className="flex items-center gap-2 px-4 py-3 bg-blue-100 hover:bg-blue-200 disabled:opacity-50 disabled:cursor-not-allowed text-blue-700 rounded-xl transition-colors"
                      title="Descargar CSV">
                      <span className={`material-icons text-xl leading-none ${exportingCsv ? 'animate-pulse' : ''}`}>download</span>
                      {exportingCsv ? 'Exportando...' : 'Descargar CSV'}
                    </button>
                    <button onClick={handleCreate}
                      className="flex items-center gap-2 px-4 py-3 bg-gradient-to-r from-green-500 to-green-600 hover:from-green-600 hover:to-green-700 text-white rounded-xl shadow-lg transition-all">
                      <span className="material-icons text-xl leading-none">add</span>
                      Nuevo Registro
                    </button>
                  </div>
                </div>
              </div>

              {/* Datos */}
              <div className="overflow-x-auto scrollbar-thin">
                {loading ? (
                  <div className="flex items-center justify-center p-12">
                    <div className="animate-spin rounded-full h-10 w-10 border-t-4 border-b-4 border-green-500" />
                  </div>
                ) : tableData.length === 0 ? (
                  <div className="text-center p-12">
                    {/* CORREGIDO */}
                    <span className="material-icons text-6xl leading-none text-gray-300 block mb-4">table_chart</span>
                    <p className="text-gray-500">No hay registros</p>
                  </div>
                ) : (
                  <div className="min-w-max">
                    <table className="w-full">
                      <thead className="bg-gray-50">
                        <tr>
                          <th className="px-3 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider sticky left-0 bg-gray-50 z-10">ID</th>
                          {tableSchema?.fields
                            .filter((f) => f.name !== 'id' && !f.name.endsWith('_set') && f.type !== 'ManyToOneRel')
                            .map((field) => (
                              <th key={field.name} className="px-3 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider whitespace-nowrap">
                                {field.verbose_name}
                              </th>
                            ))}
                          <th className="px-3 py-3 text-right text-xs font-semibold text-gray-600 uppercase tracking-wider sticky right-0 bg-gray-50 z-10">Acciones</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-100">
                        {tableData.map((item) => (
                          <tr key={String(item.id)} className="hover:bg-gray-50 transition-colors">
                            <td className="px-3 py-3 text-sm text-gray-900 font-medium sticky left-0 bg-white z-10">{String(item.id)}</td>
                            {tableSchema?.fields
                              .filter((f) => f.name !== 'id' && !f.name.endsWith('_set') && f.type !== 'ManyToOneRel')
                              .map((field) => (
                                <td key={field.name} className="px-3 py-3 text-sm text-gray-600 whitespace-nowrap">
                                  {renderCellValue(item[field.name], field.type)}
                                </td>
                              ))}
                            <td className="px-3 py-3 text-right sticky right-0 bg-white z-10">
                              <div className="flex justify-end gap-2">
                                {/* CORREGIDO: flex items-center justify-center en botones de acción */}
                                <button onClick={() => handleEdit(item)}
                                  className="flex items-center justify-center p-2 bg-blue-50 hover:bg-blue-100 text-blue-600 rounded-lg transition-colors"
                                  title="Editar">
                                  <span className="material-icons text-lg leading-none">edit</span>
                                </button>
                                <button onClick={() => handleDelete(item)}
                                  className="flex items-center justify-center p-2 bg-red-50 hover:bg-red-100 text-red-600 rounded-lg transition-colors"
                                  title="Eliminar">
                                  <span className="material-icons text-lg leading-none">delete</span>
                                </button>
                              </div>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>

              {/* Paginación */}
              {totalPages > 1 && (
                <div className="p-4 border-t border-gray-100 flex items-center justify-between">
                  <p className="text-sm text-gray-600">
                    Mostrando {((page - 1) * pageSize) + 1} - {Math.min(page * pageSize, total)} de {total}
                  </p>
                  <div className="flex gap-2">
                    {/* CORREGIDO: flex items-center justify-center en botones paginación */}
                    <button onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page === 1}
                      className="flex items-center justify-center p-2 bg-gray-100 hover:bg-gray-200 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg transition-colors">
                      <span className="material-icons text-xl leading-none text-gray-600">chevron_left</span>
                    </button>
                    <span className="px-4 py-2 text-sm text-gray-700">Página {page} de {totalPages}</span>
                    <button onClick={() => setPage((p) => Math.min(totalPages, p + 1))} disabled={page === totalPages}
                      className="flex items-center justify-center p-2 bg-gray-100 hover:bg-gray-200 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg transition-colors">
                      <span className="material-icons text-xl leading-none text-gray-600">chevron_right</span>
                    </button>
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="bg-white/80 backdrop-blur-lg rounded-3xl shadow-xl p-12 border border-gray-100 text-center">
              {/* CORREGIDO */}
              <span className="material-icons text-7xl leading-none text-gray-300 block mb-6">build</span>
              <h3 className="text-2xl font-bold text-gray-800 mb-2">Selecciona una tabla</h3>
              <p className="text-gray-600">Elige una tabla de la lista para ver y gestionar sus registros</p>
            </div>
          )}
        </div>
      </div>

      {/* Modal Edición/Creación */}
      {showModal && tableSchema && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-3xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-hidden">
            <div className="p-6 border-b border-gray-100">
              <div className="flex items-center justify-between">
                <h3 className="text-2xl font-bold text-gray-800">
                  {modalMode === 'create' ? 'Nuevo Registro' : 'Editar Registro'}
                </h3>
                {/* CORREGIDO */}
                <button onClick={() => setShowModal(false)}
                  className="flex items-center justify-center p-2 hover:bg-gray-100 rounded-lg transition-colors">
                  <span className="material-icons text-2xl leading-none text-gray-500">close</span>
                </button>
              </div>
            </div>
            <div className="p-6 overflow-y-auto max-h-[60vh]">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {tableSchema.fields
                  .filter((f) => !f.name.endsWith('_set') && f.type !== 'ManyToOneRel')
                  .map((field) => (
                    <div key={field.name} className={field.type === 'TextField' ? 'md:col-span-2' : ''}>
                      <label htmlFor={`admin-field-${field.name}`} className="block text-sm font-semibold text-gray-700 mb-2">
                        {field.verbose_name}
                        {!field.null && !field.blank && field.editable && <span className="text-red-500 ml-1">*</span>}
                      </label>
                      {renderFieldInput(field)}
                      {field.help_text && <p className="mt-1 text-xs text-gray-500">{field.help_text}</p>}
                    </div>
                  ))}
              </div>
            </div>
            <div className="p-6 border-t border-gray-100 flex justify-end gap-3">
              <button onClick={() => setShowModal(false)}
                className="px-6 py-3 bg-gray-100 hover:bg-gray-200 text-gray-700 font-semibold rounded-xl transition-colors">
                Cancelar
              </button>
              <button onClick={handleSave} disabled={saving}
                className="flex items-center gap-2 px-6 py-3 bg-gradient-to-r from-green-500 to-green-600 hover:from-green-600 hover:to-green-700 text-white font-semibold rounded-xl shadow-lg transition-all disabled:opacity-50">
                {saving ? (
                  <>
                    <div className="animate-spin rounded-full h-5 w-5 border-t-2 border-b-2 border-white" />
                    Guardando...
                  </>
                ) : (
                  <>
                    {/* CORREGIDO */}
                    <span className="material-icons text-xl leading-none">check</span>
                    Guardar
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal Confirmación Eliminación */}
      {showDeleteConfirm && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-3xl shadow-2xl w-full max-w-md p-6">
            <div className="text-center">
              <div className="mx-auto w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mb-4">
                {/* CORREGIDO: el div ya tiene flex items-center justify-center */}
                <span className="material-icons text-3xl leading-none text-red-600">delete</span>
              </div>
              <h3 className="text-xl font-bold text-gray-800 mb-2">¿Eliminar registro?</h3>
              <p className="text-gray-600 mb-6">
                Esta acción no se puede deshacer. El registro con ID {String(itemToDelete?.id)} será eliminado permanentemente.
              </p>
              <div className="flex gap-3 justify-center">
                <button onClick={() => { setShowDeleteConfirm(false); setItemToDelete(null); }}
                  className="px-6 py-3 bg-gray-100 hover:bg-gray-200 text-gray-700 font-semibold rounded-xl transition-colors">
                  Cancelar
                </button>
                <button onClick={confirmDelete} disabled={deleting}
                  className="flex items-center gap-2 px-6 py-3 bg-red-500 hover:bg-red-600 text-white font-semibold rounded-xl transition-colors disabled:opacity-50">
                  {deleting ? (
                    <>
                      <div className="animate-spin rounded-full h-5 w-5 border-t-2 border-b-2 border-white" />
                      Eliminando...
                    </>
                  ) : (
                    <>
                      {/* CORREGIDO */}
                      <span className="material-icons text-xl leading-none">delete</span>
                      Eliminar
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function renderCellValue(value: unknown, type: string): string {
  if (value === null || value === undefined) return '-';
  if (typeof value === 'boolean') return value ? '✓ Sí' : '✗ No';
  if (type === 'DateTimeField' || type === 'DateField') {
    try {
      return new Date(String(value)).toLocaleString('es-ES', { dateStyle: 'short', timeStyle: 'short' });
    } catch { return String(value); }
  }
  if (typeof value === 'object') return JSON.stringify(value).slice(0, 50) + '...';
  const str = String(value);
  return str.length > 50 ? str.slice(0, 50) + '...' : str;
}