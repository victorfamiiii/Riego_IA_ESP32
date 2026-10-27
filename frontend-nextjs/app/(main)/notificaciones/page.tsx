'use client';

import { useState, useEffect, useCallback } from 'react';
import { useUser } from '../../../lib/UserContext';
import TwemojiEmoji from '../../components/TwemojiEmoji';

const API_BASE = 'https://riegoesp32.victorfg.work';

interface Notification {
  id: number;
  user: {
    id: number;
    username: string;
    email: string;
  };
  title: string;
  body: string;
  status: 'pending' | 'sent' | 'failed' | 'read';
  created_at: string;
  sent_at: string | null;
  num_tokens_sent: number;
  num_tokens_failed: number;
  sent_by: string;
  error_message: string;
}

const STATUS_COLORS: Record<string, { bg: string; text: string; iconName: string }> = {
  pending: { bg: 'bg-yellow-50', text: 'text-yellow-700', iconName: 'schedule' },
  sent:    { bg: 'bg-green-50',  text: 'text-green-700',  iconName: 'check_circle' },
  failed:  { bg: 'bg-red-50',    text: 'text-red-700',    iconName: 'error' },
  read:    { bg: 'bg-blue-50',   text: 'text-blue-700',   iconName: 'check_circle' },
};

// Elimina emojis Unicode del texto para evitar que se rendericen a tamaño gigante
function stripEmojis(text: string): string {
  return text.replace(/[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}\u{FE00}-\u{FEFF}]/gu, '').trim();
}

export default function NotificationsPage() {
  const { isAdmin, isLoading: userLoading } = useUser();

  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [total, setTotal] = useState(0);
  const pageSize = 15;

  const [statusFilter, setStatusFilter] = useState<string>('');
  const [userFilter, setUserFilter] = useState<string>('');

  const [showSendModal, setShowSendModal] = useState(false);
  const [sendMode, setSendMode] = useState<'user' | 'broadcast'>('user');
  const [formData, setFormData] = useState({ user_id: '', title: '', body: '' });
  const [sending, setSending] = useState(false);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

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

  const fetchNotifications = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);

      const params = new URLSearchParams({
        page: String(page),
        page_size: String(pageSize),
      });

      if (statusFilter) params.append('status', statusFilter);
      if (userFilter) params.append('user_id', userFilter);

      const res = await fetch(`${API_BASE}/api/notifications/history?${params}`, {
        credentials: 'include',
      });

      if (!res.ok) throw new Error(`Error fetching notifications (${res.status})`);

      const data = await res.json();
      setNotifications(data.data || []);
      setTotalPages(data.total_pages || 1);
      setTotal(data.total || 0);
    } catch (err) {
      console.error('Error fetching notifications:', err);
      setError(err instanceof Error ? err.message : 'Error al cargar notificaciones');
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, statusFilter, userFilter]);

  useEffect(() => {
    if (!userLoading && isAdmin) {
      fetchNotifications();
    }
  }, [userLoading, isAdmin, page, statusFilter, userFilter, fetchNotifications]);

  const handleSend = async () => {
    try {
      setSending(true);
      setError(null);
      setSuccessMessage(null);

      if (!formData.title.trim() || !formData.body.trim()) {
        setError('Título y cuerpo son requeridos');
        return;
      }

      let endpoint = '';
      const payload: Record<string, unknown> = {
        title: formData.title,
        body: formData.body,
      };

      if (sendMode === 'user') {
        if (!formData.user_id) {
          setError('Selecciona un usuario');
          return;
        }
        endpoint = '/api/notifications/send';
        payload.user_id = parseInt(formData.user_id);
      } else {
        endpoint = '/api/notifications/broadcast';
      }

      const res = await fetch(`${API_BASE}${endpoint}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCsrfToken(),
        },
        credentials: 'include',
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const errData = await res.json();
        if (res.status === 403) {
          throw new Error('Acceso denegado: Solo administradores pueden enviar notificaciones.');
        }
        throw new Error(errData.error || `Error al enviar (${res.status})`);
      }

      const result = await res.json();

      setFormData({ user_id: '', title: '', body: '' });
      setShowSendModal(false);
      setSuccessMessage(result.message || 'Notificación enviada correctamente.');
      setTimeout(() => setSuccessMessage(null), 5000);

      setPage(1);
      fetchNotifications();
    } catch (err) {
      console.error('Error sending notification:', err);
      setError(err instanceof Error ? err.message : 'Error al enviar');
    } finally {
      setSending(false);
    }
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
          <span className="material-icons text-6xl text-red-500 block mx-auto mb-4">error</span>
          <h2 className="text-2xl font-bold text-gray-800 mb-2">Acceso Denegado</h2>
          <p className="text-gray-600">No tienes permisos para acceder a notificaciones</p>
        </div>
      </div>
    );
  }

  return (
    <div className="p-8">

      {/* Header */}
      <div className="mb-8">
        <h1 className="text-4xl font-bold mb-2 flex items-center gap-2 text-gray-900">
          <TwemojiEmoji emoji="🔔" size={32} />
          <span>Notificaciones</span>
        </h1>
        <p className="text-gray-600">Historial de notificaciones y envío de mensajes push</p>
      </div>

      {/* Success Alert */}
      {successMessage && (
        <div className="mb-6 bg-green-50 border border-green-200 rounded-xl p-4 flex items-center gap-3">
          <span className="material-icons leading-none text-green-500" style={{ fontSize: '20px' }}>check_circle</span>
          <p className="text-green-700 flex-1">{successMessage}</p>
          <button onClick={() => setSuccessMessage(null)}>
            <span className="material-icons leading-none text-green-500" style={{ fontSize: '20px' }}>close</span>
          </button>
        </div>
      )}

      {/* Error Alert */}
      {error && (
        <div className="mb-6 bg-red-50 border border-red-200 rounded-xl p-4 flex items-center gap-3">
          <span className="material-icons leading-none text-red-500" style={{ fontSize: '20px' }}>error</span>
          <p className="text-red-700 flex-1">{error}</p>
          <button onClick={() => setError(null)}>
            <span className="material-icons leading-none text-red-500" style={{ fontSize: '20px' }}>close</span>
          </button>
        </div>
      )}

      {/* Acciones */}
      <div className="mb-6 flex gap-3">
        <button
          onClick={() => { setSendMode('user'); setShowSendModal(true); }}
          className="flex items-center gap-2 px-4 py-3 bg-gradient-to-r from-blue-500 to-blue-600 hover:from-blue-600 hover:to-blue-700 text-white rounded-xl shadow-lg transition-all"
        >
          <span className="material-icons leading-none" style={{ fontSize: '20px' }}>send</span>
          Enviar a Usuario
        </button>
        <button
          onClick={() => { setSendMode('broadcast'); setShowSendModal(true); }}
          className="flex items-center gap-2 px-4 py-3 bg-gradient-to-r from-purple-500 to-purple-600 hover:from-purple-600 hover:to-purple-700 text-white rounded-xl shadow-lg transition-all"
        >
          <span className="material-icons leading-none" style={{ fontSize: '20px' }}>notifications</span>
          Broadcast
        </button>
      </div>

      {/* Historial */}
      <div className="bg-white/80 backdrop-blur-lg rounded-3xl shadow-xl border border-gray-100 overflow-hidden">

        {/* Filtros */}
        <div className="p-6 border-b border-gray-100 grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label htmlFor="filter-status" className="block text-sm font-medium text-gray-700 mb-2">Estado</label>
            <select
              id="filter-status"
              name="filter-status"
              value={statusFilter}
              onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg text-black focus:ring-2 focus:ring-blue-500"
            >
              <option value="">Todos los estados</option>
              <option value="pending">Pendiente</option>
              <option value="sent">Enviada</option>
              <option value="failed">Fallida</option>
              <option value="read">Leída</option>
            </select>
          </div>
          <div>
            <label htmlFor="filter-user-id" className="block text-sm font-medium text-gray-700 mb-2">Usuario</label>
            <input
              id="filter-user-id"
              name="filter-user-id"
              type="number"
              value={userFilter}
              onChange={(e) => { setUserFilter(e.target.value); setPage(1); }}
              placeholder="ID de usuario"
              className="w-full px-4 py-2 border border-gray-300 rounded-lg text-black focus:ring-2 focus:ring-blue-500"
            />
          </div>
        </div>

        {/* Tabla */}
        <div className="overflow-x-auto">
          {loading ? (
            <div className="flex items-center justify-center p-12">
              <div className="animate-spin rounded-full h-10 w-10 border-t-4 border-b-4 border-blue-500" />
            </div>
          ) : notifications.length === 0 ? (
            <div className="text-center p-12">
              <span className="material-icons text-6xl text-gray-300 block mx-auto mb-4">notifications</span>
              <p className="text-gray-500">No hay notificaciones</p>
            </div>
          ) : (
            <table className="w-full">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase">Título</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase">Usuario</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase">Estado</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase">Tokens</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase">Fecha</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase">Detalles</th>
                </tr>
              </thead>
              <tbody>
                {notifications.map((notif) => {
                  const statusConfig = STATUS_COLORS[notif.status];
                  return (
                    <tr key={notif.id} className={`border-t border-gray-100 hover:brightness-95 transition-all ${statusConfig.bg}`}>

                      {/* Título */}
                      <td className="px-4 py-3" style={{ maxWidth: '220px' }}>
                        <span
                          className="block text-sm font-medium text-gray-900 truncate"
                          title={notif.title}
                        >
                          {stripEmojis(notif.title)}
                        </span>
                      </td>

                      {/* Usuario */}
                      <td className="px-4 py-3 text-sm text-gray-600 whitespace-nowrap">
                        <div className="inline-flex items-center gap-1">
                          <span className="material-icons leading-none" style={{ fontSize: '16px' }}>person</span>
                          {notif.user.username}
                        </div>
                      </td>

                      {/* Estado */}
                      <td className="px-4 py-3 text-sm whitespace-nowrap">
                        <div className={`inline-flex items-center gap-1 ${statusConfig.text}`}>
                          <span className="material-icons leading-none" style={{ fontSize: '16px' }}>
                            {statusConfig.iconName}
                          </span>
                          {notif.status}
                        </div>
                      </td>

                      {/* Tokens */}
                      <td className="px-4 py-3 text-sm text-gray-600">
                        {notif.num_tokens_sent > 0 ? (
                          <div>
                            <span className="text-green-600 font-medium">
                              {notif.num_tokens_sent - notif.num_tokens_failed}
                            </span>
                            {notif.num_tokens_failed > 0 && (
                              <span className="text-red-700 ml-2 font-medium">
                                ({notif.num_tokens_failed} fallos)
                              </span>
                            )}
                          </div>
                        ) : (
                          <span className="text-gray-400">-</span>
                        )}
                      </td>

                      {/* Fecha */}
                      <td className="px-4 py-3 text-sm text-gray-600 whitespace-nowrap">
                        {new Date(notif.created_at).toLocaleString('es-ES')}
                      </td>

                      {/* Detalles */}
                      <td className="px-4 py-3 text-sm">
                        <details>
                          <summary className="cursor-pointer text-blue-600 hover:text-blue-800 text-sm font-medium list-none flex items-center gap-1">
                            <span className="material-icons leading-none" style={{ fontSize: '14px' }}>expand_more</span>
                            Ver más
                          </summary>
                          <div
                            className="mt-2 p-3 bg-white border border-gray-200 rounded-lg text-gray-700 w-72"
                            style={{ fontSize: '12px', lineHeight: '1.5' }}
                          >
                            <p className="font-semibold text-gray-800 mb-1">Título completo:</p>
                            <p className="mb-3 break-words text-gray-600">{stripEmojis(notif.title)}</p>
                            <p className="font-semibold text-gray-800 mb-1">Cuerpo:</p>
                            <p className="mb-3 break-words text-gray-600 whitespace-pre-wrap">{stripEmojis(notif.body)}</p>
                            <p className="font-semibold text-gray-800 mb-1">Enviado por:</p>
                            <p className="mb-2 text-gray-600">{notif.sent_by}</p>
                            {notif.error_message && (
                              <>
                                <p className="font-semibold text-red-600 mb-1">Error:</p>
                                <p className="text-red-600 break-words">{notif.error_message}</p>
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
          )}
        </div>

        {/* Paginación */}
        {totalPages > 1 && (
          <div className="p-4 border-t border-gray-100 flex items-center justify-between">
            <p className="text-sm text-gray-600">
              Mostrando {(page - 1) * pageSize + 1} a {Math.min(page * pageSize, total)} de {total}
            </p>
            <div className="flex gap-2">
              <button
                onClick={() => setPage(Math.max(1, page - 1))}
                disabled={page === 1}
                className="px-3 py-1 bg-gray-100 hover:bg-gray-200 disabled:opacity-50 text-gray-700 rounded transition-colors"
              >
                Anterior
              </button>
              <span className="px-3 py-1 text-gray-700">{page} / {totalPages}</span>
              <button
                onClick={() => setPage(Math.min(totalPages, page + 1))}
                disabled={page === totalPages}
                className="px-3 py-1 bg-gray-100 hover:bg-gray-200 disabled:opacity-50 text-gray-700 rounded transition-colors"
              >
                Siguiente
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Modal de envío */}
      {showSendModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-2xl shadow-2xl max-w-md w-full p-6">
            <h2 className="text-2xl font-bold mb-4 text-gray-900">
              {sendMode === 'user' ? 'Enviar a Usuario' : 'Enviar Broadcast'}
            </h2>

            {sendMode === 'user' && (
              <div className="mb-4">
                <label htmlFor="notify-user-id" className="block text-sm font-medium text-gray-700 mb-2">
                  ID del Usuario
                </label>
                <input
                  id="notify-user-id"
                  name="user_id"
                  type="number"
                  value={formData.user_id}
                  onChange={(e) => setFormData({ ...formData, user_id: e.target.value })}
                  placeholder="Ej: 1"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-black focus:ring-2 focus:ring-blue-500"
                />
              </div>
            )}

            <div className="mb-4">
              <label htmlFor="notify-title" className="block text-sm font-medium text-gray-700 mb-2">
                Título
              </label>
              <input
                id="notify-title"
                name="title"
                type="text"
                value={formData.title}
                onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                placeholder="Título de la notificación"
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-black focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div className="mb-4">
              <label htmlFor="notify-body" className="block text-sm font-medium text-gray-700 mb-2">
                Cuerpo
              </label>
              <textarea
                id="notify-body"
                name="body"
                value={formData.body}
                onChange={(e) => setFormData({ ...formData, body: e.target.value })}
                placeholder="Contenido del mensaje"
                rows={4}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-black focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div className="flex gap-3">
              <button
                onClick={() => setShowSendModal(false)}
                disabled={sending}
                className="flex-1 px-4 py-2 bg-gray-200 hover:bg-gray-300 disabled:opacity-50 text-gray-700 rounded-lg transition-colors"
              >
                Cancelar
              </button>
              <button
                onClick={handleSend}
                disabled={sending}
                className="flex-1 px-4 py-2 bg-gradient-to-r from-blue-500 to-blue-600 hover:from-blue-600 hover:to-blue-700 disabled:opacity-50 text-white rounded-lg transition-colors"
              >
                {sending ? 'Enviando...' : 'Enviar'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
