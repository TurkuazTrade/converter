import { useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../api/client';
import { FormModal } from '../components/FormModal';
import { PaginationControls } from '../components/PaginationControls';
import { ReferenceImportModal } from '../components/ReferenceImportModal';

type ProductForm = {
  id?: number;
  item_code: string;
  name: string;
  barcode: string;
  price_code: string;
  exchange_code: string;
  article: string;
  stock: string;
  trade_mark: string;
  brand: string;
  product_type: string;
  conversion_multiplier: string;
  exclude_from_export: boolean;
  is_active: boolean;
};

type ProductFilterOptions = {
  product_types: string[];
  brands: string[];
  trade_marks: string[];
};

const sortOptions = [
  ['name', 'Наименование'],
  ['item_code', 'Номер товара'],
  ['exchange_code', 'Код обмена'],
  ['article', 'Артикул'],
  ['trade_mark', 'Торговая марка'],
  ['brand', 'Бренд'],
  ['product_type', 'Тип'],
  ['conversion_multiplier', 'Множитель'],
  ['exclude_from_export', 'Excel'],
  ['is_active', 'Активность'],
] as const;

const emptyProductForm: ProductForm = {
  item_code: '',
  name: '',
  barcode: '',
  price_code: '',
  exchange_code: '',
  article: '',
  stock: '',
  trade_mark: '',
  brand: '',
  product_type: '',
  conversion_multiplier: '1',
  exclude_from_export: false,
  is_active: true,
};

export function ProductsPage() {
  const queryClient = useQueryClient();
  const tableScrollRef = useRef<HTMLElement | null>(null);
  const dragScrollRef = useRef<{
    pointerId: number;
    startX: number;
    startY: number;
    scrollLeft: number;
    scrollTop: number;
    dragged: boolean;
  } | null>(null);
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(0);
  const [limit, setLimit] = useState(50);
  const [exportFilter, setExportFilter] = useState('all');
  const [activeFilter, setActiveFilter] = useState('all');
  const [productTypeFilter, setProductTypeFilter] = useState('');
  const [brandFilter, setBrandFilter] = useState('');
  const [tradeMarkFilter, setTradeMarkFilter] = useState('');
  const [sortBy, setSortBy] = useState('name');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc');
  const [form, setForm] = useState<ProductForm>(emptyProductForm);
  const [formOpen, setFormOpen] = useState(false);
  const [importOpen, setImportOpen] = useState(false);
  const [formError, setFormError] = useState('');
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [tableDragging, setTableDragging] = useState(false);
  const { data, isLoading } = useQuery({
    queryKey: [
      'products',
      search,
      page,
      limit,
      exportFilter,
      activeFilter,
      productTypeFilter,
      brandFilter,
      tradeMarkFilter,
      sortBy,
      sortDir,
    ],
    queryFn: async () => (
      await api.get('/products', {
        params: {
          ...productQueryParams,
          limit,
          offset: page * limit,
        },
      })
    ).data,
  });
  const products = data ?? [];
  const { data: filterOptions } = useQuery<ProductFilterOptions>({
    queryKey: ['product-filter-options'],
    queryFn: async () => (await api.get('/products/filter-options')).data,
  });
  const productQueryParams = {
    search,
    sort_by: sortBy,
    sort_dir: sortDir,
    ...(exportFilter !== 'all' ? { exclude_from_export: exportFilter === 'excluded' } : {}),
    ...(activeFilter !== 'all' ? { is_active: activeFilter === 'active' } : {}),
    ...(productTypeFilter ? { product_type: productTypeFilter } : {}),
    ...(brandFilter ? { brand: brandFilter } : {}),
    ...(tradeMarkFilter ? { trade_mark: tradeMarkFilter } : {}),
  };
  function updateSearch(value: string) {
    setSearch(value);
    setPage(0);
  }

  function updateLimit(value: number) {
    setLimit(value);
    setPage(0);
  }

  function resetFilters() {
    setSearch('');
    setExportFilter('all');
    setActiveFilter('all');
    setProductTypeFilter('');
    setBrandFilter('');
    setTradeMarkFilter('');
    setSortBy('name');
    setSortDir('asc');
    setPage(0);
  }

  function updateFilter(callback: () => void) {
    callback();
    setPage(0);
  }

  function openCreateProduct() {
    setForm(emptyProductForm);
    setFormError('');
    setFormOpen(true);
  }

  function editProduct(product: any) {
    setForm({
      id: product.id,
      item_code: product.item_code ?? '',
      name: product.name ?? '',
      barcode: product.barcodes?.find((barcode: any) => barcode.is_primary)?.barcode ?? product.barcodes?.[0]?.barcode ?? '',
      price_code: product.price_code ?? '',
      exchange_code: product.exchange_code ?? '',
      article: product.article ?? '',
      stock: product.stock ?? '',
      trade_mark: product.trade_mark ?? '',
      brand: product.brand ?? '',
      product_type: product.product_type ?? '',
      conversion_multiplier: String(product.conversion_multiplier ?? 1),
      exclude_from_export: Boolean(product.exclude_from_export),
      is_active: product.is_active,
    });
    setFormError('');
    setFormOpen(true);
  }

  function closeForm() {
    setFormOpen(false);
    setForm(emptyProductForm);
    setFormError('');
  }

  async function saveProduct() {
    setFormError('');
    const multiplier = Number(form.conversion_multiplier || 1);
    if (!Number.isFinite(multiplier) || multiplier <= 0) {
      setFormError('Множитель должен быть больше нуля');
      return;
    }
    try {
      const payload = {
        item_code: form.item_code,
        name: form.name,
        barcode: form.barcode,
        price_code: form.price_code,
        exchange_code: form.exchange_code,
        article: form.article,
        stock: form.stock,
        trade_mark: form.trade_mark,
        brand: form.brand,
        product_type: form.product_type,
        conversion_multiplier: multiplier,
        exclude_from_export: form.exclude_from_export,
        is_active: form.is_active,
      };
      if (form.id) {
        await api.patch(`/products/${form.id}`, payload);
      } else {
        await api.post('/products', payload);
      }
      closeForm();
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['products'] }),
        queryClient.invalidateQueries({ queryKey: ['product-filter-options'] }),
      ]);
    } catch (err: any) {
      setFormError(err.response?.data?.detail ?? 'Не удалось сохранить товар');
    }
  }

  async function toggleExportExclusion(product: any) {
    try {
      await api.patch(`/products/${product.id}`, {
        exclude_from_export: !product.exclude_from_export,
      });
      await queryClient.invalidateQueries({ queryKey: ['products'] });
    } catch (err: any) {
      setFormError(err.response?.data?.detail ?? 'Не удалось обновить исключение из Excel');
    }
  }

  function startTableDrag(event: React.PointerEvent<HTMLElement>) {
    if (event.button !== 0 || isInteractiveTarget(event.target)) return;
    const container = tableScrollRef.current;
    if (!container) return;
    dragScrollRef.current = {
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      scrollLeft: container.scrollLeft,
      scrollTop: container.scrollTop,
      dragged: false,
    };
    container.setPointerCapture(event.pointerId);
  }

  function moveTableDrag(event: React.PointerEvent<HTMLElement>) {
    const drag = dragScrollRef.current;
    const container = tableScrollRef.current;
    if (!drag || !container || drag.pointerId !== event.pointerId) return;
    const deltaX = event.clientX - drag.startX;
    const deltaY = event.clientY - drag.startY;
    if (!drag.dragged && Math.hypot(deltaX, deltaY) > 4) {
      drag.dragged = true;
      setTableDragging(true);
    }
    if (!drag.dragged) return;
    event.preventDefault();
    container.scrollLeft = drag.scrollLeft - deltaX;
    container.scrollTop = drag.scrollTop - deltaY;
  }

  function stopTableDrag(event: React.PointerEvent<HTMLElement>) {
    const drag = dragScrollRef.current;
    const container = tableScrollRef.current;
    if (drag?.pointerId === event.pointerId && container?.hasPointerCapture(event.pointerId)) {
      container.releasePointerCapture(event.pointerId);
    }
    dragScrollRef.current = null;
    setTableDragging(false);
  }

  return (
    <main className="page space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">Товары</h1>
          <p className="mt-1 text-sm text-slate-400">Справочник для сопоставления заказов.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button type="button" className="button-secondary" onClick={() => setImportOpen(true)}>
            Импорт товаров
          </button>
          <button type="button" className="button" onClick={openCreateProduct}>Добавить товар</button>
        </div>
      </div>
      <div className="flex flex-wrap gap-3">
        <input className="input w-full md:w-96" placeholder="Поиск по названию, коду, бренду, типу или barcode" value={search} onChange={(event) => updateSearch(event.target.value)} />
      </div>
      {filtersOpen && (
        <section className="compact-panel space-y-3">
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            <label className="space-y-2">
              <span className="text-sm text-slate-400">Тип</span>
              <select className="input w-full" value={productTypeFilter} onChange={(event) => updateFilter(() => setProductTypeFilter(event.target.value))}>
                <option value="">Все типы</option>
                {(filterOptions?.product_types ?? []).map((value) => <option key={value} value={value}>{value}</option>)}
              </select>
            </label>
            <label className="space-y-2">
              <span className="text-sm text-slate-400">Бренд</span>
              <select className="input w-full" value={brandFilter} onChange={(event) => updateFilter(() => setBrandFilter(event.target.value))}>
                <option value="">Все бренды</option>
                {(filterOptions?.brands ?? []).map((value) => <option key={value} value={value}>{value}</option>)}
              </select>
            </label>
            <label className="space-y-2">
              <span className="text-sm text-slate-400">Торговая марка</span>
              <select className="input w-full" value={tradeMarkFilter} onChange={(event) => updateFilter(() => setTradeMarkFilter(event.target.value))}>
                <option value="">Все марки</option>
                {(filterOptions?.trade_marks ?? []).map((value) => <option key={value} value={value}>{value}</option>)}
              </select>
            </label>
            <label className="space-y-2">
              <span className="text-sm text-slate-400">Excel</span>
              <select className="input w-full" value={exportFilter} onChange={(event) => updateFilter(() => setExportFilter(event.target.value))}>
                <option value="all">Все товары</option>
                <option value="included">Выгружать</option>
                <option value="excluded">Не выгружать</option>
              </select>
            </label>
            <label className="space-y-2">
              <span className="text-sm text-slate-400">Активность</span>
              <select className="input w-full" value={activeFilter} onChange={(event) => updateFilter(() => setActiveFilter(event.target.value))}>
                <option value="all">Все</option>
                <option value="active">Активные</option>
                <option value="inactive">Неактивные</option>
              </select>
            </label>
            <label className="space-y-2">
              <span className="text-sm text-slate-400">Сортировать по</span>
              <select className="input w-full" value={sortBy} onChange={(event) => updateFilter(() => setSortBy(event.target.value))}>
                {sortOptions.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
              </select>
            </label>
            <label className="space-y-2">
              <span className="text-sm text-slate-400">Порядок</span>
              <select className="input w-full" value={sortDir} onChange={(event) => updateFilter(() => setSortDir(event.target.value as 'asc' | 'desc'))}>
                <option value="asc">По возрастанию</option>
                <option value="desc">По убыванию</option>
              </select>
            </label>
            <div className="flex items-end">
              <button type="button" className="button-secondary w-full" onClick={resetFilters}>Сбросить фильтры</button>
            </div>
          </div>
        </section>
      )}
      {formError && !formOpen && <p className="text-sm text-red-400">{formError}</p>}
      <PaginationControls
        page={page}
        limit={limit}
        itemCount={products.length}
        onPageChange={setPage}
        onLimitChange={updateLimit}
        extraInfo={(
          <div>
            <h2 className="text-sm font-semibold">Фильтры и сортировка</h2>
            <p className="mt-1 text-xs text-slate-400">{activeFilterCount({ productTypeFilter, brandFilter, tradeMarkFilter, exportFilter, activeFilter })} фильтров, сортировка: {sortLabel(sortBy)} · {sortDir === 'asc' ? 'возрастание' : 'убывание'}</p>
          </div>
        )}
        extraControls={(
          <button type="button" className="button-secondary" onClick={() => setFiltersOpen((value) => !value)}>
            {filtersOpen ? 'Скрыть фильтры' : 'Открыть фильтры'}
          </button>
        )}
      />
      <section
        ref={tableScrollRef}
        className={`panel overflow-auto p-0 ${tableDragging ? 'cursor-grabbing select-none' : 'cursor-grab'}`}
        onPointerDown={startTableDrag}
        onPointerMove={moveTableDrag}
        onPointerUp={stopTableDrag}
        onPointerCancel={stopTableDrag}
      >
        {isLoading ? (
          <p className="p-5 text-slate-400">Загрузка...</p>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>Наименование</th>
                <th>Номер товара</th>
                <th>Код обмена</th>
                <th>Штрихкод</th>
                <th>Артикул</th>
                <th>Остаток</th>
                <th>Торговая марка</th>
                <th>Бренд</th>
                <th>Тип</th>
                <th>Множитель</th>
                <th>Excel</th>
                <th>Активен</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {products.map((product: any) => (
                <tr key={product.id}>
                  <td>{displayProductName(product)}</td>
                  <td>{product.item_code}</td>
                  <td>{product.exchange_code}</td>
                  <td>{(product.barcodes ?? []).map((barcode: any) => barcode.barcode).join(', ')}</td>
                  <td>{product.article}</td>
                  <td>{product.stock}</td>
                  <td>{product.trade_mark}</td>
                  <td>{product.brand}</td>
                  <td>{product.product_type}</td>
                  <td>{formatMultiplier(product.conversion_multiplier)}</td>
                  <td>{product.exclude_from_export ? 'Не выгружать' : 'Выгружать'}</td>
                  <td>{product.is_active ? 'Да' : 'Нет'}</td>
                  <td>
                    <div className="flex flex-wrap gap-2">
                      <button type="button" className="button-secondary" onClick={() => toggleExportExclusion(product)}>
                        {product.exclude_from_export ? 'Вернуть в Excel' : 'Исключить'}
                      </button>
                      <button type="button" className="button-secondary" onClick={() => editProduct(product)}>
                        Редактировать
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      {formOpen && (
        <FormModal
          title={form.id ? 'Редактировать товар' : 'Добавить товар'}
          description="Множитель хранится в карточке товара и применяется при сопоставлении."
          onClose={closeForm}
          actions={(
            <>
              <label className="flex items-center gap-2 text-sm text-slate-300">
                <input type="checkbox" checked={form.is_active} onChange={(event) => setForm((prev) => ({ ...prev, is_active: event.target.checked }))} />
                Активен
              </label>
              <label className="flex items-center gap-2 text-sm text-slate-300">
                <input type="checkbox" checked={form.exclude_from_export} onChange={(event) => setForm((prev) => ({ ...prev, exclude_from_export: event.target.checked }))} />
                Не выгружать в Excel
              </label>
              <button type="button" className="button" disabled={!form.name.trim()} onClick={saveProduct}>
                Сохранить
              </button>
              <button type="button" className="button-secondary" onClick={closeForm}>Отмена</button>
              {formError && <span className="text-sm text-red-400">{formError}</span>}
            </>
          )}
        >
          <datalist id="product-trade-mark-options">
            {(filterOptions?.trade_marks ?? []).map((value) => <option key={value} value={value} />)}
          </datalist>
          <datalist id="product-brand-options">
            {(filterOptions?.brands ?? []).map((value) => <option key={value} value={value} />)}
          </datalist>
          <datalist id="product-type-options">
            {(filterOptions?.product_types ?? []).map((value) => <option key={value} value={value} />)}
          </datalist>
          <div className="grid gap-3 md:grid-cols-2">
            <label className="space-y-2">
              <span className="text-sm text-slate-400">Номер товара</span>
              <input className="input w-full" value={form.item_code} onChange={(event) => setForm((prev) => ({ ...prev, item_code: event.target.value }))} />
            </label>
            <label className="space-y-2">
              <span className="text-sm text-slate-400">Штрихкод</span>
              <input className="input w-full" value={form.barcode} onChange={(event) => setForm((prev) => ({ ...prev, barcode: event.target.value }))} />
            </label>
            <label className="space-y-2 md:col-span-2">
              <span className="text-sm text-slate-400">Название</span>
              <input className="input w-full" value={form.name} onChange={(event) => setForm((prev) => ({ ...prev, name: event.target.value }))} />
            </label>
            <label className="space-y-2">
              <span className="text-sm text-slate-400">Код обмена</span>
              <input className="input w-full" value={form.exchange_code} onChange={(event) => setForm((prev) => ({ ...prev, exchange_code: event.target.value }))} />
            </label>
            <label className="space-y-2">
              <span className="text-sm text-slate-400">Артикул</span>
              <input className="input w-full" value={form.article} onChange={(event) => setForm((prev) => ({ ...prev, article: event.target.value }))} />
            </label>
            <label className="space-y-2">
              <span className="text-sm text-slate-400">Остаток</span>
              <input className="input w-full" value={form.stock} onChange={(event) => setForm((prev) => ({ ...prev, stock: event.target.value }))} />
            </label>
            <label className="space-y-2">
              <span className="text-sm text-slate-400">Торговая марка</span>
              <input className="input w-full" list="product-trade-mark-options" value={form.trade_mark} onChange={(event) => setForm((prev) => ({ ...prev, trade_mark: event.target.value }))} />
            </label>
            <label className="space-y-2">
              <span className="text-sm text-slate-400">Бренд</span>
              <input className="input w-full" list="product-brand-options" value={form.brand} onChange={(event) => setForm((prev) => ({ ...prev, brand: event.target.value }))} />
            </label>
            <label className="space-y-2">
              <span className="text-sm text-slate-400">Тип</span>
              <input className="input w-full" list="product-type-options" value={form.product_type} onChange={(event) => setForm((prev) => ({ ...prev, product_type: event.target.value }))} />
            </label>
            <label className="space-y-2">
              <span className="text-sm text-slate-400">Множитель</span>
              <input
                className="input w-full"
                min="0.001"
                step="0.001"
                type="number"
                value={form.conversion_multiplier}
                onChange={(event) => setForm((prev) => ({ ...prev, conversion_multiplier: event.target.value }))}
              />
            </label>
            <label className="space-y-2">
              <span className="text-sm text-slate-400">Price code</span>
              <input className="input w-full" value={form.price_code} onChange={(event) => setForm((prev) => ({ ...prev, price_code: event.target.value }))} />
            </label>
          </div>
        </FormModal>
      )}
      {importOpen && (
        <ReferenceImportModal
          kind="products"
          title="Импорт товаров"
          filledDownloadParams={productQueryParams}
          onClose={() => setImportOpen(false)}
        />
      )}
    </main>
  );
}

function activeFilterCount(filters: {
  productTypeFilter: string;
  brandFilter: string;
  tradeMarkFilter: string;
  exportFilter: string;
  activeFilter: string;
}) {
  return [
    filters.productTypeFilter,
    filters.brandFilter,
    filters.tradeMarkFilter,
    filters.exportFilter !== 'all' ? filters.exportFilter : '',
    filters.activeFilter !== 'all' ? filters.activeFilter : '',
  ].filter(Boolean).length;
}

function sortLabel(sortBy: string) {
  return sortOptions.find(([value]) => value === sortBy)?.[1] ?? 'Наименование';
}

function displayProductName(product: any) {
  const name = String(product.name ?? '').trim();
  const code = String(product.item_code ?? '').trim();
  if (!name || name === code) {
    return <span className="text-slate-500">Название не задано</span>;
  }
  return name;
}

function formatMultiplier(value: unknown) {
  const numberValue = Number(value ?? 1);
  if (!Number.isFinite(numberValue)) return '1';
  return numberValue.toLocaleString(undefined, { maximumFractionDigits: 3 });
}

function isInteractiveTarget(target: EventTarget) {
  return target instanceof HTMLElement && Boolean(target.closest('button, input, select, textarea, a, label'));
}
