import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, useParams } from 'react-router-dom';
import { api } from '../api/client';

export function UnresolvedItemsPage() {
  const { orderId } = useParams();
  const queryClient = useQueryClient();
  const [productSearch, setProductSearch] = useState('');
  const [selected, setSelected] = useState<Record<number, string>>({});
  const { data, isLoading } = useQuery({
    queryKey: ['unresolved', orderId],
    queryFn: async () => (await api.get(`/orders/${orderId}/unresolved`)).data,
    enabled: Boolean(orderId),
  });
  const { data: products } = useQuery({
    queryKey: ['product-search', productSearch],
    queryFn: async () => (await api.get('/products', { params: { search: productSearch, limit: 50 } })).data,
    enabled: true,
  });

  async function resolveProduct(orderItemId: number) {
    const productId = selected[orderItemId];
    if (!productId) return;
    await api.post(`/orders/${orderId}/resolve-product`, {
      order_item_id: orderItemId,
      product_id: Number(productId),
    });
    setSelected((prev) => {
      const next = { ...prev };
      delete next[orderItemId];
      return next;
    });
    await queryClient.invalidateQueries({ queryKey: ['unresolved', orderId] });
    await queryClient.invalidateQueries({ queryKey: ['order-preview', orderId] });
  }

  return (
    <main className="page space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Сопоставление товаров #{orderId}</h1>
        <Link className="text-sm text-slate-400 hover:text-white" to={`/orders/${orderId}/preview`}>К заказу</Link>
      </div>
      <section className="panel space-y-3">
        <input
          className="input w-full"
          placeholder="Найти товар по barcode, коду или названию"
          value={productSearch}
          onChange={(event) => setProductSearch(event.target.value)}
        />
        <p className="text-sm text-slate-400">
          Выберите товар из справочника для каждой строки. Поиск фильтрует список по barcode, коду или названию.
        </p>
        <p className="text-xs text-slate-500">
          Показано товаров: {(products ?? []).length}
        </p>
      </section>
      <section className="panel overflow-auto p-0">
        {isLoading ? (
          <p className="p-5 text-slate-400">Загрузка...</p>
        ) : data?.items?.length ? (
          <table className="table">
            <thead>
              <tr>
                <th>Строка</th>
                <th>Barcode</th>
                <th>Код сети</th>
                <th>Товар из заказа</th>
                <th>Кол-во</th>
                <th>Товар в справочнике</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((item: any) => (
                <tr key={item.id}>
                  <td>{item.row_number}</td>
                  <td>{item.raw_barcode}</td>
                  <td>{item.raw_item_code}</td>
                  <td>{item.raw_name}</td>
                  <td>{item.quantity}</td>
                  <td>
                    <select
                      className="input w-72"
                      value={selected[item.id] ?? ''}
                      onChange={(event) => setSelected((prev) => ({ ...prev, [item.id]: event.target.value }))}
                    >
                      <option value="">{(products ?? []).length ? 'Выберите товар' : 'Товары не найдены'}</option>
                      {(products ?? []).map((product: any) => (
                        <option key={product.id} value={product.id}>
                          {product.item_code} · {product.name}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td>
                    <button type="button" className="button" disabled={!selected[item.id]} onClick={() => resolveProduct(item.id)}>
                      Сохранить
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="space-y-3 p-5">
            <p className="text-emerald-300">Все товары сопоставлены.</p>
            <Link className="text-sm text-blue-300 hover:text-blue-200" to={`/orders/${orderId}/preview`}>Вернуться к заказу</Link>
          </div>
        )}
      </section>
    </main>
  );
}
