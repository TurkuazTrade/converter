import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, useParams } from 'react-router-dom';
import { api } from '../api/client';

type ProductOption = {
  id: number;
  item_code: string | null;
  name: string;
  barcodes?: { barcode: string; is_active: boolean }[];
};

export function UnresolvedItemsPage() {
  const { orderId } = useParams();
  const queryClient = useQueryClient();
  const [productSearch, setProductSearch] = useState('');
  const [selected, setSelected] = useState<Record<number, string>>({});
  const [multipliers, setMultipliers] = useState<Record<number, string>>({});
  const { data, isLoading } = useQuery({
    queryKey: ['unresolved', orderId],
    queryFn: async () => (await api.get(`/orders/${orderId}/unresolved`)).data,
    enabled: Boolean(orderId),
  });
  const { data: products } = useQuery({
    queryKey: ['product-search', productSearch],
    queryFn: async () => (await api.get('/products', { params: { search: productSearch, limit: 50 } })).data,
    enabled: productSearch.trim().length >= 2,
  });
  const searchReady = productSearch.trim().length >= 2;
  const productOptions = searchReady ? (products ?? []) as ProductOption[] : [];

  async function resolveProduct(orderItemId: number) {
    const productId = selected[orderItemId];
    if (!productId) return;
    await api.post(`/orders/${orderId}/resolve-product`, {
      order_item_id: orderItemId,
      product_id: Number(productId),
      conversion_multiplier: Number(multipliers[orderItemId] || 1),
    });
    setSelected((prev) => {
      const next = { ...prev };
      delete next[orderItemId];
      return next;
    });
    setMultipliers((prev) => {
      const next = { ...prev };
      delete next[orderItemId];
      return next;
    });
    await queryClient.invalidateQueries({ queryKey: ['unresolved', orderId] });
    await queryClient.invalidateQueries({ queryKey: ['order-preview', orderId] });
  }

  async function skipProduct(orderItemId: number) {
    await api.post(`/orders/${orderId}/skip-product`, {
      order_item_id: orderItemId,
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
          Введите barcode, код выгрузки или часть названия, затем выберите найденный товар.
        </p>
        <p className="text-xs text-slate-500">
          {searchReady ? `Найдено товаров: ${productOptions.length}` : 'Список появится после поиска.'}
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
                <th>Множ.</th>
                <th>Итог</th>
                <th>Товар в справочнике</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((item: any) => {
                const sourceQuantity = Number(item.source_quantity ?? item.quantity ?? 0);
                const multiplierValue = multipliers[item.id] ?? String(item.conversion_multiplier ?? 1);
                const multiplier = Number(multiplierValue) > 0 ? Number(multiplierValue) : 1;
                const finalQuantity = Number((sourceQuantity * multiplier).toFixed(3));
                return (
                  <tr key={item.id}>
                    <td>{item.row_number}</td>
                    <td>{item.raw_barcode}</td>
                    <td>{item.raw_item_code}</td>
                    <td>{item.raw_name}</td>
                    <td>{sourceQuantity}</td>
                    <td>
                      <input
                        className="input w-24"
                        min="0.001"
                        step="0.001"
                        type="number"
                        value={multiplierValue}
                        onChange={(event) => setMultipliers((prev) => ({ ...prev, [item.id]: event.target.value }))}
                      />
                    </td>
                    <td>{finalQuantity}</td>
                    <td>
                      <select
                        className="input w-72"
                        value={selected[item.id] ?? ''}
                        onChange={(event) => setSelected((prev) => ({ ...prev, [item.id]: event.target.value }))}
                      >
                        <option value="">
                          {searchReady ? productOptions.length ? 'Выберите товар' : 'Товары не найдены' : 'Введите поиск выше'}
                        </option>
                        {productOptions.map((product) => (
                          <option key={product.id} value={product.id}>
                            {formatProductOption(product)}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td>
                      <div className="flex flex-wrap gap-2">
                        <button type="button" className="button" disabled={!selected[item.id]} onClick={() => resolveProduct(item.id)}>
                          Сохранить
                        </button>
                        <button type="button" className="button-secondary" onClick={() => skipProduct(item.id)}>
                          Пропустить
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
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

function formatProductOption(product: ProductOption): string {
  const code = product.item_code?.trim();
  const name = product.name?.trim();
  const activeBarcodes = (product.barcodes ?? [])
    .filter((barcode) => barcode.is_active)
    .map((barcode) => barcode.barcode)
    .slice(0, 2);
  const parts: string[] = [];

  if (name && name !== code) {
    parts.push(name);
  }
  if (code) {
    parts.push(`код выгрузки: ${code}`);
  }
  if (activeBarcodes.length) {
    parts.push(`barcode: ${activeBarcodes.join(', ')}`);
  }

  return parts.join(' · ') || `товар #${product.id}`;
}
