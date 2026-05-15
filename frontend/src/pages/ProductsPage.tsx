import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '../api/client';
import { PaginationControls } from '../components/PaginationControls';

export function ProductsPage() {
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(0);
  const [limit, setLimit] = useState(50);
  const { data, isLoading } = useQuery({
    queryKey: ['products', search, page, limit],
    queryFn: async () => (
      await api.get('/products', { params: { search, limit, offset: page * limit } })
    ).data,
  });
  const products = data ?? [];

  function updateSearch(value: string) {
    setSearch(value);
    setPage(0);
  }

  function updateLimit(value: number) {
    setLimit(value);
    setPage(0);
  }

  return (
    <main className="page space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">Товары</h1>
          <p className="mt-1 text-sm text-slate-400">Справочник для сопоставления заказов.</p>
        </div>
      </div>
      <div className="flex flex-wrap gap-3">
        <input className="input w-full md:w-96" placeholder="Поиск по коду, barcode или названию" value={search} onChange={(event) => updateSearch(event.target.value)} />
      </div>
      <PaginationControls
        page={page}
        limit={limit}
        itemCount={products.length}
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
                <th>Код товара</th>
                <th>Название</th>
                <th>Barcode</th>
                <th>Price code</th>
                <th>Активен</th>
              </tr>
            </thead>
            <tbody>
              {products.map((product: any) => (
                <tr key={product.id}>
                  <td>{product.id}</td>
                  <td>{product.item_code}</td>
                  <td>{displayProductName(product)}</td>
                  <td>{(product.barcodes ?? []).map((barcode: any) => barcode.barcode).join(', ')}</td>
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

function displayProductName(product: any) {
  const name = String(product.name ?? '').trim();
  const code = String(product.item_code ?? '').trim();
  if (!name || name === code) {
    return <span className="text-slate-500">Название не задано</span>;
  }
  return name;
}
