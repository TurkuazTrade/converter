import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { api } from '../api/client';
import { PaginationControls } from '../components/PaginationControls';
import { downloadBlob, filenameFromContentDisposition } from '../shared/download';

type Order = {
  id: number;
  order_number: string | null;
  converter_type: string | null;
  client_id: number | null;
  status: string;
  created_at: string;
  export_file_id?: number | null;
  export_downloaded_at?: string | null;
  export_downloads?: Record<string, string> | null;
};

const statusLabels: Record<string, string> = {
  uploaded: 'Загружен',
  processing: 'Обработка',
  needs_review: 'Нужно исправить',
  ready_to_export: 'Готов к выгрузке',
  exported: 'Excel готов',
  failed: 'Ошибка',
};

function statusClass(status: string) {
  if (status === 'exported' || status === 'ready_to_export') return 'text-emerald-300';
  if (status === 'failed') return 'text-red-300';
  return 'text-amber-300';
}

export function OrdersHistoryPage() {
  const queryClient = useQueryClient();
  const [downloadError, setDownloadError] = useState('');
  const [page, setPage] = useState(0);
  const [limit, setLimit] = useState(50);
  const { data, isLoading } = useQuery({
    queryKey: ['orders', page, limit],
    queryFn: async () => (
      await api.get('/orders', { params: { limit, offset: page * limit } })
    ).data as Order[],
  });
  const orders = data ?? [];

  function updateLimit(value: number) {
    setLimit(value);
    setPage(0);
  }

  async function downloadExport(orderId: number) {
    setDownloadError('');
    try {
      const response = await api.get(`/orders/${orderId}/download-export`, { responseType: 'blob' });
      const filename = filenameFromContentDisposition(response.headers['content-disposition'], `order-${orderId}.xlsx`);
      downloadBlob(response.data, filename);
      await queryClient.invalidateQueries({ queryKey: ['orders'] });
    } catch (err: any) {
      setDownloadError(err.response?.data?.detail ?? 'Excel можно скачать только после сопоставления клиента и товаров.');
    }
  }

  return (
    <main className="page space-y-4">
      <div>
        <h1 className="text-xl font-semibold">История заказов</h1>
        <p className="mt-1 text-sm text-slate-400">Открывайте последние обработки, проверяйте статус и скачивайте готовые выгрузки.</p>
        {downloadError && <p className="mt-2 text-sm text-red-400">{downloadError}</p>}
      </div>
      <PaginationControls
        page={page}
        limit={limit}
        itemCount={orders.length}
        onPageChange={setPage}
        onLimitChange={updateLimit}
      />
      <section className="panel overflow-auto p-0">
        {isLoading ? (
          <p className="p-5 text-slate-400">Загрузка...</p>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Сеть</th>
                <th>Номер</th>
                <th>Статус</th>
                <th>Дата</th>
                <th>Файлы</th>
              </tr>
            </thead>
            <tbody>
              {orders.map((order) => (
                <tr key={order.id}>
                  <td>{order.id}</td>
                  <td>{order.converter_type ?? 'не определена'}</td>
                  <td>{order.order_number}</td>
                  <td className={statusClass(order.status)}>{statusLabels[order.status] ?? order.status}</td>
                  <td>{new Date(order.created_at).toLocaleString()}</td>
                  <td className="space-x-3 whitespace-nowrap">
                    <Link className="text-blue-300 hover:text-blue-200" to={`/orders/${order.id}/preview`}>
                      Открыть
                    </Link>
                    {(order.status === 'ready_to_export' || order.status === 'exported' || (order.status === 'needs_review' && order.client_id)) && (
                      <button type="button" className="text-emerald-300 hover:text-emerald-200" onClick={() => downloadExport(order.id)}>
                        Excel
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </main>
  );
}
