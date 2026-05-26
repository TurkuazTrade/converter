import { useEffect, useRef, useState } from 'react';
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

type ProductColumnId =
  | 'name'
  | 'item_code'
  | 'exchange_code'
  | 'barcode'
  | 'article'
  | 'stock'
  | 'trade_mark'
  | 'brand'
  | 'product_type'
  | 'conversion_multiplier'
  | 'exclude_from_export'
  | 'is_active'
  | 'actions';

type ProductTableColumn = {
  id: ProductColumnId;
  label: string;
  defaultWidth: number;
  minWidth: number;
};

type ProductTableSettings = {
  order: ProductColumnId[];
  widths: Partial<Record<ProductColumnId, number>>;
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

const PRODUCT_TABLE_STORAGE_KEY = 'turkuaz:products-table-columns:v1';
const MAX_PRODUCT_COLUMN_WIDTH = 640;
const PRODUCT_TABLE_COLUMNS: ProductTableColumn[] = [
  { id: 'name', label: 'Наименование', defaultWidth: 260, minWidth: 180 },
  { id: 'item_code', label: 'Номер товара', defaultWidth: 140, minWidth: 100 },
  { id: 'exchange_code', label: 'Код обмена', defaultWidth: 140, minWidth: 100 },
  { id: 'barcode', label: 'Штрихкод', defaultWidth: 260, minWidth: 140 },
  { id: 'article', label: 'Артикул', defaultWidth: 140, minWidth: 100 },
  { id: 'stock', label: 'Остаток', defaultWidth: 100, minWidth: 80 },
  { id: 'trade_mark', label: 'Торговая марка', defaultWidth: 140, minWidth: 110 },
  { id: 'brand', label: 'Бренд', defaultWidth: 140, minWidth: 110 },
  { id: 'product_type', label: 'Тип', defaultWidth: 140, minWidth: 100 },
  { id: 'conversion_multiplier', label: 'Множитель', defaultWidth: 100, minWidth: 90 },
  { id: 'exclude_from_export', label: 'Excel', defaultWidth: 120, minWidth: 100 },
  { id: 'is_active', label: 'Активен', defaultWidth: 100, minWidth: 90 },
  { id: 'actions', label: '', defaultWidth: 220, minWidth: 180 },
];
const PRODUCT_TABLE_COLUMN_IDS = PRODUCT_TABLE_COLUMNS.map((column) => column.id);

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
  const resizeCleanupRef = useRef<(() => void) | null>(null);
  const columnDragCleanupRef = useRef<(() => void) | null>(null);
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
  const [productTableSettings, setProductTableSettings] = useState<ProductTableSettings>(() => readProductTableSettings());
  const [draggingColumnId, setDraggingColumnId] = useState<ProductColumnId | null>(null);
  const [dragOverColumnId, setDragOverColumnId] = useState<ProductColumnId | null>(null);
  const [resizingColumnId, setResizingColumnId] = useState<ProductColumnId | null>(null);
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
  const orderedColumns = getOrderedProductColumns(productTableSettings.order);
  const tableWidth = orderedColumns.reduce((total, column) => total + getProductColumnWidth(productTableSettings, column), 0);
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

  function startColumnResize(event: React.PointerEvent<HTMLButtonElement>, column: ProductTableColumn) {
    event.preventDefault();
    event.stopPropagation();
    resizeCleanupRef.current?.();
    const pointerId = event.pointerId;
    const startX = event.clientX;
    const startWidth = getProductColumnWidth(productTableSettings, column);
    setResizingColumnId(column.id);

    const moveColumnResize = (moveEvent: PointerEvent) => {
      if (moveEvent.pointerId !== pointerId) return;
      moveEvent.preventDefault();
      const nextWidth = clampProductColumnWidth(startWidth + moveEvent.clientX - startX, column);
      setProductTableSettings((prev) => ({
        ...prev,
        widths: {
          ...prev.widths,
          [column.id]: nextWidth,
        },
      }));
    };
    const stopColumnResize = (upEvent: PointerEvent) => {
      if (upEvent.pointerId !== pointerId) return;
      window.removeEventListener('pointermove', moveColumnResize);
      window.removeEventListener('pointerup', stopColumnResize);
      window.removeEventListener('pointercancel', stopColumnResize);
      resizeCleanupRef.current = null;
      setResizingColumnId(null);
    };
    resizeCleanupRef.current = () => {
      window.removeEventListener('pointermove', moveColumnResize);
      window.removeEventListener('pointerup', stopColumnResize);
      window.removeEventListener('pointercancel', stopColumnResize);
      setResizingColumnId(null);
    };
    window.addEventListener('pointermove', moveColumnResize);
    window.addEventListener('pointerup', stopColumnResize);
    window.addEventListener('pointercancel', stopColumnResize);
  }

  function startColumnDrag(event: React.PointerEvent<HTMLDivElement>, column: ProductTableColumn) {
    if (event.button !== 0) return;
    event.preventDefault();
    event.stopPropagation();
    columnDragCleanupRef.current?.();
    const pointerId = event.pointerId;
    const startX = event.clientX;
    const startY = event.clientY;
    let moved = false;

    const moveColumnDrag = (moveEvent: PointerEvent) => {
      if (moveEvent.pointerId !== pointerId) return;
      const deltaX = moveEvent.clientX - startX;
      const deltaY = moveEvent.clientY - startY;
      if (!moved && Math.hypot(deltaX, deltaY) > 6) {
        moved = true;
        setDraggingColumnId(column.id);
      }
      if (!moved) return;
      moveEvent.preventDefault();
      const target = document.elementFromPoint(moveEvent.clientX, moveEvent.clientY);
      const targetColumnId = target instanceof HTMLElement ? target.closest<HTMLElement>('[data-product-column-id]')?.dataset.productColumnId : undefined;
      setDragOverColumnId(isProductColumnId(targetColumnId) ? targetColumnId : null);
    };
    const stopColumnDrag = (upEvent: PointerEvent) => {
      if (upEvent.pointerId !== pointerId) return;
      const target = document.elementFromPoint(upEvent.clientX, upEvent.clientY);
      const targetColumnId = target instanceof HTMLElement ? target.closest<HTMLElement>('[data-product-column-id]')?.dataset.productColumnId : undefined;
      if (moved && isProductColumnId(targetColumnId)) {
        moveColumn(column.id, targetColumnId);
      }
      window.removeEventListener('pointermove', moveColumnDrag);
      window.removeEventListener('pointerup', stopColumnDrag);
      window.removeEventListener('pointercancel', stopColumnDrag);
      columnDragCleanupRef.current = null;
      setDraggingColumnId(null);
      setDragOverColumnId(null);
    };
    columnDragCleanupRef.current = () => {
      window.removeEventListener('pointermove', moveColumnDrag);
      window.removeEventListener('pointerup', stopColumnDrag);
      window.removeEventListener('pointercancel', stopColumnDrag);
      setDraggingColumnId(null);
      setDragOverColumnId(null);
    };
    window.addEventListener('pointermove', moveColumnDrag);
    window.addEventListener('pointerup', stopColumnDrag);
    window.addEventListener('pointercancel', stopColumnDrag);
  }

  function moveColumn(sourceId: ProductColumnId, targetId: ProductColumnId) {
    if (sourceId === targetId) return;
    setProductTableSettings((prev) => {
      const currentOrder = getOrderedProductColumns(prev.order).map((column) => column.id);
      const sourceIndex = currentOrder.indexOf(sourceId);
      const targetIndex = currentOrder.indexOf(targetId);
      if (sourceIndex < 0 || targetIndex < 0) return prev;
      const nextOrder = [...currentOrder];
      const [movedColumn] = nextOrder.splice(sourceIndex, 1);
      nextOrder.splice(targetIndex, 0, movedColumn);
      return { ...prev, order: nextOrder };
    });
  }

  function resetProductTableLayout() {
    setProductTableSettings(createDefaultProductTableSettings());
    setDragOverColumnId(null);
    setDraggingColumnId(null);
  }

  function renderProductTableCell(columnId: ProductColumnId, product: any) {
    if (columnId === 'name') {
      const productName = getProductDisplayName(product);
      return (
        <span
          className={`products-table__name-text ${productName.isMissing ? 'text-slate-500' : ''}`}
          title={productName.isMissing ? undefined : productName.name}
        >
          {productName.name}
        </span>
      );
    }
    if (columnId === 'item_code') return formatProductTableText(product.item_code);
    if (columnId === 'exchange_code') return formatProductTableText(product.exchange_code);
    if (columnId === 'barcode') return formatBarcodeList(product);
    if (columnId === 'article') return formatProductTableText(product.article);
    if (columnId === 'stock') return formatProductTableText(product.stock);
    if (columnId === 'trade_mark') return formatProductTableText(product.trade_mark);
    if (columnId === 'brand') return formatProductTableText(product.brand);
    if (columnId === 'product_type') return formatProductTableText(product.product_type);
    if (columnId === 'conversion_multiplier') return formatProductTableText(formatMultiplier(product.conversion_multiplier));
    if (columnId === 'exclude_from_export') return formatProductTableText(product.exclude_from_export ? 'Не выгружать' : 'Выгружать');
    if (columnId === 'is_active') return formatProductTableText(product.is_active ? 'Да' : 'Нет');
    return (
      <div className="flex flex-wrap gap-2">
        <button type="button" className="button-secondary" onClick={() => toggleExportExclusion(product)}>
          {product.exclude_from_export ? 'Вернуть в Excel' : 'Исключить'}
        </button>
        <button type="button" className="button-secondary" onClick={() => editProduct(product)}>
          Редактировать
        </button>
      </div>
    );
  }

  useEffect(() => {
    writeProductTableSettings(productTableSettings);
  }, [productTableSettings]);

  useEffect(() => () => {
    resizeCleanupRef.current?.();
    columnDragCleanupRef.current?.();
  }, []);

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
          <div className="flex flex-wrap gap-2">
            <button type="button" className="button-secondary" onClick={resetProductTableLayout}>
              Сбросить колонки
            </button>
            <button type="button" className="button-secondary" onClick={() => setFiltersOpen((value) => !value)}>
              {filtersOpen ? 'Скрыть фильтры' : 'Открыть фильтры'}
            </button>
          </div>
        )}
      />
      <section
        ref={tableScrollRef}
        className={`panel overflow-auto p-0 ${tableDragging ? 'cursor-grabbing select-none' : 'cursor-grab'} ${resizingColumnId ? 'products-table--resizing' : ''}`}
        onPointerDown={startTableDrag}
        onPointerMove={moveTableDrag}
        onPointerUp={stopTableDrag}
        onPointerCancel={stopTableDrag}
      >
        {isLoading ? (
          <p className="p-5 text-slate-400">Загрузка...</p>
        ) : (
          <table className="table products-table" style={{ minWidth: tableWidth, width: tableWidth }}>
            <colgroup>
              {orderedColumns.map((column) => (
                <col key={column.id} style={{ width: getProductColumnWidth(productTableSettings, column) }} />
              ))}
            </colgroup>
            <thead>
              <tr>
                {orderedColumns.map((column) => (
                  <th
                    key={column.id}
                    data-product-column-id={column.id}
                    className={dragOverColumnId === column.id && draggingColumnId !== column.id ? 'products-table__header--drag-over' : undefined}
                  >
                    <div
                      className="products-table__header-content"
                      data-table-control="true"
                      title={column.label ? 'Перетащить столбец' : 'Перетащить столбец действий'}
                      onPointerDown={(event) => startColumnDrag(event, column)}
                    >
                      <span className="products-table__header-label">{column.label}</span>
                    </div>
                    <button
                      type="button"
                      className={`products-table__resize-handle ${resizingColumnId === column.id ? 'products-table__resize-handle--active' : ''}`}
                      data-table-control="true"
                      aria-label={column.label ? `Изменить ширину столбца ${column.label}` : 'Изменить ширину столбца действий'}
                      title="Изменить ширину"
                      onPointerDown={(event) => startColumnResize(event, column)}
                    />
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {products.map((product: any) => (
                <tr key={product.id}>
                  {orderedColumns.map((column) => (
                    <td key={column.id}>{renderProductTableCell(column.id, product)}</td>
                  ))}
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

function createDefaultProductTableSettings(): ProductTableSettings {
  return {
    order: [...PRODUCT_TABLE_COLUMN_IDS],
    widths: Object.fromEntries(PRODUCT_TABLE_COLUMNS.map((column) => [column.id, column.defaultWidth])) as Partial<Record<ProductColumnId, number>>,
  };
}

function readProductTableSettings(): ProductTableSettings {
  if (typeof window === 'undefined') return createDefaultProductTableSettings();
  try {
    const rawValue = window.localStorage.getItem(PRODUCT_TABLE_STORAGE_KEY);
    if (!rawValue) return createDefaultProductTableSettings();
    return normalizeProductTableSettings(JSON.parse(rawValue));
  } catch {
    return createDefaultProductTableSettings();
  }
}

function writeProductTableSettings(settings: ProductTableSettings) {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(PRODUCT_TABLE_STORAGE_KEY, JSON.stringify(normalizeProductTableSettings(settings)));
  } catch {
    // Layout settings are a convenience; table rendering should not depend on storage availability.
  }
}

function normalizeProductTableSettings(value: unknown): ProductTableSettings {
  if (!value || typeof value !== 'object') return createDefaultProductTableSettings();
  const settings = value as Partial<ProductTableSettings>;
  const savedOrder = Array.isArray(settings.order) ? settings.order.filter(isProductColumnId) : [];
  const order = [
    ...savedOrder,
    ...PRODUCT_TABLE_COLUMN_IDS.filter((columnId) => !savedOrder.includes(columnId)),
  ];
  const widths: Partial<Record<ProductColumnId, number>> = {};
  for (const column of PRODUCT_TABLE_COLUMNS) {
    const savedWidth = settings.widths?.[column.id];
    widths[column.id] = clampProductColumnWidth(typeof savedWidth === 'number' ? savedWidth : column.defaultWidth, column);
  }
  return { order, widths };
}

function getOrderedProductColumns(order: ProductColumnId[]) {
  return order
    .map((columnId) => PRODUCT_TABLE_COLUMNS.find((column) => column.id === columnId))
    .filter((column): column is ProductTableColumn => Boolean(column));
}

function getProductColumnWidth(settings: ProductTableSettings, column: ProductTableColumn) {
  return clampProductColumnWidth(settings.widths[column.id] ?? column.defaultWidth, column);
}

function clampProductColumnWidth(width: number, column: ProductTableColumn) {
  if (!Number.isFinite(width)) return column.defaultWidth;
  return Math.min(MAX_PRODUCT_COLUMN_WIDTH, Math.max(column.minWidth, Math.round(width)));
}

function isProductColumnId(value: unknown): value is ProductColumnId {
  return typeof value === 'string' && PRODUCT_TABLE_COLUMN_IDS.includes(value as ProductColumnId);
}

function getProductDisplayName(product: any) {
  const name = String(product.name ?? '').trim();
  const code = String(product.item_code ?? '').trim();
  if (!name || name === code) {
    return { name: 'Название не задано', isMissing: true };
  }
  return { name, isMissing: false };
}

function formatBarcodeList(product: any) {
  const value = (product.barcodes ?? []).map((barcode: any) => barcode.barcode).join(', ');
  if (!value) return null;
  return (
    <span className="products-table__cell-text products-table__barcode-text" title={value}>
      {value}
    </span>
  );
}

function formatProductTableText(value: unknown) {
  const text = String(value ?? '').trim();
  if (!text) return null;
  return (
    <span className="products-table__cell-text" title={text}>
      {text}
    </span>
  );
}

function formatMultiplier(value: unknown) {
  const numberValue = Number(value ?? 1);
  if (!Number.isFinite(numberValue)) return '1';
  return numberValue.toLocaleString(undefined, { maximumFractionDigits: 3 });
}

function isInteractiveTarget(target: EventTarget) {
  return target instanceof HTMLElement && Boolean(target.closest('button, input, select, textarea, a, label, [data-table-control="true"]'));
}
