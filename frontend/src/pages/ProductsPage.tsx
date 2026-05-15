import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../api/client';
import { PaginationControls } from '../components/PaginationControls';

type ProductForm = {
  id?: number;
  item_code: string;
  name: string;
  barcode: string;
  price_code: string;
  is_active: boolean;
};

const emptyProductForm: ProductForm = {
  item_code: '',
  name: '',
  barcode: '',
  price_code: '',
  is_active: true,
};

export function ProductsPage() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(0);
  const [limit, setLimit] = useState(50);
  const [form, setForm] = useState<ProductForm>(emptyProductForm);
  const [formError, setFormError] = useState('');
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

  function editProduct(product: any) {
    setForm({
      id: product.id,
      item_code: product.item_code ?? '',
      name: product.name ?? '',
      barcode: product.barcodes?.find((barcode: any) => barcode.is_primary)?.barcode ?? product.barcodes?.[0]?.barcode ?? '',
      price_code: product.price_code ?? '',
      is_active: product.is_active,
    });
    setFormError('');
  }

  async function saveProduct() {
    setFormError('');
    try {
      const payload = {
        item_code: form.item_code,
        name: form.name,
        barcode: form.barcode,
        price_code: form.price_code,
        is_active: form.is_active,
      };
      if (form.id) {
        await api.patch(`/products/${form.id}`, payload);
      } else {
        await api.post('/products', payload);
      }
      setForm(emptyProductForm);
      await queryClient.invalidateQueries({ queryKey: ['products'] });
    } catch (err: any) {
      setFormError(err.response?.data?.detail ?? 'Не удалось сохранить товар');
    }
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
      <section className="panel space-y-4">
        <div className="grid gap-3 md:grid-cols-5">
          <input className="input" placeholder="Код товара" value={form.item_code} onChange={(event) => setForm((prev) => ({ ...prev, item_code: event.target.value }))} />
          <input className="input md:col-span-2" placeholder="Название" value={form.name} onChange={(event) => setForm((prev) => ({ ...prev, name: event.target.value }))} />
          <input className="input" placeholder="Barcode" value={form.barcode} onChange={(event) => setForm((prev) => ({ ...prev, barcode: event.target.value }))} />
          <input className="input" placeholder="Price code" value={form.price_code} onChange={(event) => setForm((prev) => ({ ...prev, price_code: event.target.value }))} />
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <label className="flex items-center gap-2 text-sm text-slate-300">
            <input type="checkbox" checked={form.is_active} onChange={(event) => setForm((prev) => ({ ...prev, is_active: event.target.checked }))} />
            Активен
          </label>
          <button type="button" className="button" disabled={!form.name.trim()} onClick={saveProduct}>
            {form.id ? 'Сохранить товар' : 'Добавить товар'}
          </button>
          {form.id && <button type="button" className="button-secondary" onClick={() => setForm(emptyProductForm)}>Отмена</button>}
          {formError && <span className="text-sm text-red-400">{formError}</span>}
        </div>
      </section>
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
                <th></th>
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
                  <td>
                    <button type="button" className="button-secondary" onClick={() => editProduct(product)}>
                      Редактировать
                    </button>
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

function displayProductName(product: any) {
  const name = String(product.name ?? '').trim();
  const code = String(product.item_code ?? '').trim();
  if (!name || name === code) {
    return <span className="text-slate-500">Название не задано</span>;
  }
  return name;
}
