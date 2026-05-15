import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '../api/client';

export function ProductsPage() {
  const [search, setSearch] = useState('');
  const { data, isLoading } = useQuery({
    queryKey: ['products', search],
    queryFn: async () => (await api.get('/products', { params: { search } })).data,
  });

  return (
    <main className="page space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">Товары</h1>
          <p className="mt-1 text-sm text-slate-400">Справочник для сопоставления заказов.</p>
        </div>
      </div>
      <div className="flex flex-wrap gap-3">
        <input className="input w-full md:w-96" placeholder="Поиск по коду, barcode или названию" value={search} onChange={(event) => setSearch(event.target.value)} />
      </div>
      <section className="panel overflow-auto p-0">
        {isLoading ? (
          <p className="p-5 text-slate-400">Загрузка...</p>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Код товара</th>
                <th>Название</th>
                <th>Price code</th>
                <th>Активен</th>
              </tr>
            </thead>
            <tbody>
              {(data ?? []).map((product: any) => (
                <tr key={product.id}>
                  <td>{product.id}</td>
                  <td>{product.item_code}</td>
                  <td>{product.name}</td>
                  <td>{product.price_code}</td>
                  <td>{product.is_active ? 'Да' : 'Нет'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </main>
  );
}
