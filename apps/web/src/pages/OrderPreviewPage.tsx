import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, useParams } from 'react-router-dom';
import { useEffect, useRef, useState } from 'react';
import { api } from '../api/client';
import { downloadBlob, filenameFromContentDisposition } from '../shared/download';

type PreviewItem = {
  id: number;
  row_number: number;
  raw_barcode: string | null;
  raw_item_code: string | null;
  item_code: string | null;
  raw_name: string | null;
  source_quantity: number | null;
  conversion_multiplier: number;
  quantity: number;
  status: string;
  error_message: string | null;
  product_id: number | null;
  product_type: string | null;
  product_exclude_from_export: boolean;
};

type ExportDownloadInfo = {
  downloaded_at?: string;
  user_name?: string;
};

const orderStatusLabels: Record<string, string> = {
  uploaded: 'Загружен',
  processing: 'Обработка',
  needs_review: 'Нужно исправить',
  ready_to_export: 'Готов к выгрузке',
  exported: 'Excel готов',
  failed: 'Ошибка',
};

const itemStatusLabels: Record<string, string> = {
  resolved: 'Готово',
  unresolved: 'Не сопоставлено',
  invalid_quantity: 'Ошибка количества',
  duplicate: 'Дубль',
  skipped: 'Пропущено',
};

export function OrderPreviewPage() {
  const { orderId } = useParams();
  const queryClient = useQueryClient();
  const [clientSearch, setClientSearch] = useState('');
  const [clientId, setClientId] = useState('');
  const [newClientCode, setNewClientCode] = useState('');
  const [newClientName, setNewClientName] = useState('');
  const [multiplierDrafts, setMultiplierDrafts] = useState<Record<number, string>>({});
  const [actionError, setActionError] = useState('');
  const [downloadNotice, setDownloadNotice] = useState('');
  const [downloadMenuOpen, setDownloadMenuOpen] = useState(false);
  const autoResolvedClientId = useRef<number | null>(null);
  const downloadMenuRef = useRef<HTMLDivElement | null>(null);
  const { data, isLoading, error } = useQuery({
    queryKey: ['order-preview', orderId],
    queryFn: async () => (await api.get(`/orders/${orderId}/preview`)).data,
    enabled: Boolean(orderId),
  });
  const { data: clients } = useQuery({
    queryKey: ['client-search', clientSearch || data?.client_hint?.raw_name || ''],
    queryFn: async () => (await api.get('/clients', { params: { search: clientSearch || data?.client_hint?.raw_name || '', limit: 20 } })).data,
    enabled: !data?.client && (clientSearch || data?.client_hint?.raw_name || '').length >= 2,
  });
  const onlyClient = !data?.client && clients?.length === 1 ? clients[0] : null;

  useEffect(() => {
    if (!data?.client && data?.client_hint?.raw_name) {
      setClientSearch((value) => value || data.client_hint.raw_name);
      setNewClientName((value) => value || data.client_hint.raw_name);
    }
  }, [data?.client, data?.client_hint?.raw_name]);

  useEffect(() => {
    if (!onlyClient || autoResolvedClientId.current === onlyClient.id) return;

    autoResolvedClientId.current = onlyClient.id;
    setActionError('');
    api.post(`/orders/${orderId}/resolve-client`, { client_id: onlyClient.id })
      .then(() => queryClient.invalidateQueries({ queryKey: ['order-preview', orderId] }))
      .catch((err: any) => {
        autoResolvedClientId.current = null;
        setActionError(err.response?.data?.detail ?? 'Не удалось автоматически выбрать клиента');
      });
  }, [onlyClient, orderId, queryClient]);

  useEffect(() => {
    function closeDownloadMenu(event: MouseEvent) {
      if (!downloadMenuRef.current?.contains(event.target as Node)) {
        setDownloadMenuOpen(false);
      }
    }

    document.addEventListener('mousedown', closeDownloadMenu);
    return () => document.removeEventListener('mousedown', closeDownloadMenu);
  }, []);

  useEffect(() => {
    if (!downloadNotice) return;
    const timeoutId = window.setTimeout(() => setDownloadNotice(''), 4500);
    return () => window.clearTimeout(timeoutId);
  }, [downloadNotice]);

  async function downloadExport(productType?: string) {
    setActionError('');
    setDownloadMenuOpen(false);
    const downloadKey = productType || '__full__';
    const previousDownload = normalizeDownloadInfo(data?.order?.export_downloads?.[downloadKey]);
    if (previousDownload) {
      setDownloadNotice(
        `Файл уже скачан${previousDownload.user_name ? `: ${previousDownload.user_name}` : ''}. Загрузка повторится.`,
      );
    }
    try {
      const response = await api.get(`/orders/${orderId}/download-export`, {
        params: productType ? { product_type: productType } : undefined,
        responseType: 'blob',
      });
      const filename = filenameFromContentDisposition(response.headers['content-disposition'], `order-${orderId}.xlsx`);
      downloadBlob(response.data, filename);
      const previouslyDownloadedBy = response.headers['x-export-previously-downloaded-by'];
      if (previouslyDownloadedBy) {
        setDownloadNotice(`Файл уже скачан: ${decodeURIComponent(previouslyDownloadedBy)}. Загрузка повторится.`);
      }
      await queryClient.invalidateQueries({ queryKey: ['order-preview', orderId] });
    } catch (err: any) {
      setActionError(err.response?.data?.detail ?? 'Не удалось сформировать Excel');
    }
  }

  async function resolveClient() {
    if (!clientId) return;
    setActionError('');
    await api.post(`/orders/${orderId}/resolve-client`, { client_id: Number(clientId) });
    setClientId('');
    await queryClient.invalidateQueries({ queryKey: ['order-preview', orderId] });
  }

  async function createAndResolveClient() {
    if (!newClientCode || !newClientName) return;
    setActionError('');
    try {
      const response = await api.post('/clients', {
        client_code: newClientCode,
        name: newClientName,
        network_name: data?.order?.converter_type ?? null,
      });
      await api.post(`/orders/${orderId}/resolve-client`, { client_id: response.data.id });
      setClientId('');
      await queryClient.invalidateQueries({ queryKey: ['order-preview', orderId] });
    } catch (err: any) {
      setActionError(err.response?.data?.detail ?? 'Не удалось создать клиента');
    }
  }

  async function updateMultiplier(orderItemId: number, fallbackValue: number) {
    setActionError('');
    const value = Number(multiplierDrafts[orderItemId] ?? fallbackValue);
    if (!Number.isFinite(value) || value <= 0) {
      setActionError('Множитель должен быть больше нуля');
      return;
    }
    try {
      await api.post(`/orders/${orderId}/update-multiplier`, {
        order_item_id: orderItemId,
        conversion_multiplier: value,
      });
      await queryClient.invalidateQueries({ queryKey: ['order-preview', orderId] });
    } catch (err: any) {
      setActionError(err.response?.data?.detail ?? 'Не удалось сохранить множитель');
    }
  }

  if (isLoading) {
    return <main className="page">Загрузка...</main>;
  }

  if (error || !data) {
    return <main className="page text-red-400">Не удалось открыть заказ.</main>;
  }

  const order = data.order;
  const items = data.items as PreviewItem[];
  const unresolved = items.filter((item) => item.status !== 'resolved' && item.status !== 'skipped').length;
  const exportable = items.filter((item) => item.status === 'resolved' && item.product_id && !item.product_exclude_from_export).length;
  const exportTypes = Array.from(
    new Set(
      items
        .filter((item) => item.status === 'resolved' && item.product_id && item.product_type)
        .map((item) => item.product_type as string),
    ),
  ).sort((first, second) => first.localeCompare(second));
  const skipped = items.filter((item) => item.status === 'skipped').length;
  const clientResolved = Boolean(data.client);
  const readyToExport = order.status === 'ready_to_export';
  const exported = order.status === 'exported';
  const exportDownloads = (order.export_downloads ?? {}) as Record<string, ExportDownloadInfo | string>;
  const failed = order.status === 'failed';
  const downloadable = clientResolved && exportable > 0 && !failed;
  const canOpenDownloadMenu = clientResolved && !failed && (downloadable || exportTypes.length > 0);
  const clientOptions = clients ?? [];
  const fullExportDownload = normalizeDownloadInfo(exportDownloads.__full__);

  return (
    <main className="page space-y-6">
      {downloadNotice && (
        <div className="fixed right-5 top-20 z-50 max-w-sm rounded-md border border-amber-600 bg-amber-950/90 px-4 py-3 text-sm text-amber-100 shadow-lg">
          {downloadNotice}
        </div>
      )}
      <section className="panel space-y-4">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-xl font-semibold">Заказ #{order.id}</h1>
            <div className="mt-2 flex flex-wrap gap-2 text-sm">
              <span className="status-pill">{order.converter_type ?? 'Сеть не определена'}</span>
              <span className={failed ? 'status-pill-danger' : exported || readyToExport ? 'status-pill-ok' : 'status-pill-warn'}>
                {orderStatusLabels[order.status] ?? order.status}
              </span>
              <span className="status-pill">{items.length} строк</span>
              {unresolved > 0 && <span className="status-pill-warn">{unresolved} не сопоставлено</span>}
              {skipped > 0 && <span className="status-pill">{skipped} пропущено</span>}
            </div>
            <p className="mt-3 text-sm text-slate-400">
              Клиент: {clientResolved ? `${data.client.client_code} · ${data.client.name}` : data.client_hint?.raw_name || 'не определен'}
            </p>
            {order.error_message && <p className="mt-2 text-sm text-amber-300">{order.error_message}</p>}
          </div>
          <div className="flex flex-wrap gap-2">
            {unresolved > 0 && <Link className="button" to={`/orders/${order.id}/unresolved`}>Сопоставить товары</Link>}
            {canOpenDownloadMenu && (
              <div className="relative" ref={downloadMenuRef}>
                <button
                  type="button"
                  className="button"
                  onClick={() => setDownloadMenuOpen((value) => !value)}
                >
                  Скачать Excel
                </button>
                {downloadMenuOpen && (
                  <div className="absolute right-0 z-20 mt-2 w-72 overflow-hidden rounded-md border border-slate-700 bg-slate-950 py-1 shadow-xl">
                    <button
                      type="button"
                      className="block w-full px-4 py-2 text-left text-sm text-slate-100 hover:bg-slate-800 disabled:cursor-not-allowed disabled:text-slate-500 disabled:hover:bg-transparent"
                      disabled={!downloadable}
                      title={downloadTitle(fullExportDownload)}
                      onClick={() => downloadExport()}
                    >
                      Полный Excel по страницам{fullExportDownload ? ' ✓' : ''}
                    </button>
                    {exportTypes.length > 0 && (
                      <div className="border-t border-slate-800 py-1">
                        {exportTypes.map((productType) => {
                          const downloadInfo = normalizeDownloadInfo(exportDownloads[productType]);
                          return (
                            <button
                              key={productType}
                              type="button"
                              className="block w-full px-4 py-2 text-left text-sm text-slate-100 hover:bg-slate-800"
                              title={downloadTitle(downloadInfo)}
                              onClick={() => downloadExport(productType)}
                            >
                              Скачать только {productType}{downloadInfo ? ' ✓' : ''}
                            </button>
                          );
                        })}
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
        {data.warnings?.length > 0 && (
          <div className="rounded-md border border-amber-700 bg-amber-950/40 p-3 text-sm text-amber-200">
            {data.warnings.slice(0, 5).map((warning: string) => <div key={warning}>{warning}</div>)}
          </div>
        )}
        {!clientResolved && (
          <div className="space-y-4 rounded-md border border-amber-700 bg-amber-950/30 p-4">
            <div className="grid gap-3 md:grid-cols-[1fr_1fr_auto]">
              <input
                className="input"
                placeholder="Найти клиента по коду, названию или адресу"
                value={clientSearch}
                onChange={(event) => setClientSearch(event.target.value)}
              />
              <select className="input" value={clientId} onChange={(event) => setClientId(event.target.value)}>
                <option value="">{clientOptions.length ? 'Выберите клиента' : 'Клиенты не найдены'}</option>
                {clientOptions.map((client: any) => (
                  <option key={client.id} value={client.id}>
                    {client.client_code} · {client.name}
                  </option>
                ))}
              </select>
              <button type="button" className="button" disabled={!clientId} onClick={resolveClient}>Сохранить клиента</button>
            </div>
            {clientOptions.length === 0 && (
              <div className="grid gap-3 border-t border-amber-800 pt-4 md:grid-cols-[180px_1fr_auto]">
                <input
                  className="input"
                  placeholder="Код клиента"
                  value={newClientCode}
                  onChange={(event) => setNewClientCode(event.target.value)}
                />
                <input
                  className="input"
                  placeholder="Название клиента"
                  value={newClientName}
                  onChange={(event) => setNewClientName(event.target.value)}
                />
                <button type="button" className="button-secondary" disabled={!newClientCode || !newClientName} onClick={createAndResolveClient}>
                  Создать клиента
                </button>
              </div>
            )}
          </div>
        )}
        {actionError && <p className="text-sm text-red-400">{actionError}</p>}
      </section>

      <section className="panel overflow-auto p-0">
        <table className="table">
          <thead>
            <tr>
              <th>Строка</th>
              <th>Barcode</th>
              <th>Код сети</th>
              <th>Код выгрузки</th>
              <th>Товар</th>
              <th>Кол-во</th>
              <th>Множ.</th>
              <th>Итог</th>
              <th>Статус</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <tr key={item.id}>
                <td>{item.row_number}</td>
                <td>{item.raw_barcode}</td>
                <td>{item.raw_item_code}</td>
                <td>{item.item_code}</td>
                <td>{item.raw_name}</td>
                <td>{item.source_quantity ?? item.quantity}</td>
                <td>
                  <div className="flex min-w-36 items-center gap-2">
                    <input
                      className="input w-24"
                      min="0.001"
                      step="0.001"
                      type="number"
                      value={multiplierDrafts[item.id] ?? String(item.conversion_multiplier)}
                      onChange={(event) => setMultiplierDrafts((prev) => ({ ...prev, [item.id]: event.target.value }))}
                    />
                    <button type="button" className="button-secondary" onClick={() => updateMultiplier(item.id, item.conversion_multiplier)}>
                      OK
                    </button>
                  </div>
                </td>
                <td>{item.quantity}</td>
                <td className={item.status === 'resolved' && !item.product_exclude_from_export ? 'text-emerald-300' : 'text-amber-300'}>
                  {item.product_exclude_from_export ? 'Исключено из Excel' : itemStatusLabels[item.status] ?? item.status}{item.error_message ? `: ${item.error_message}` : ''}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </main>
  );
}

function normalizeDownloadInfo(value: ExportDownloadInfo | string | undefined): ExportDownloadInfo | null {
  if (!value) return null;
  if (typeof value === 'string') return { downloaded_at: value };
  return value;
}

function downloadTitle(downloadInfo: ExportDownloadInfo | null) {
  if (!downloadInfo) return undefined;
  const parts = ['Уже скачан'];
  if (downloadInfo.user_name) parts.push(downloadInfo.user_name);
  if (downloadInfo.downloaded_at) parts.push(new Date(downloadInfo.downloaded_at).toLocaleString());
  return parts.join(' · ');
}
