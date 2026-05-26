import { useEffect, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, useParams } from 'react-router-dom';
import { api } from '../api/client';

type ProductOption = {
  id: number;
  item_code: string | null;
  name: string;
  barcodes?: { barcode: string; is_active: boolean }[];
};

type MatchingColumnId =
  | 'row_number'
  | 'raw_barcode'
  | 'raw_item_code'
  | 'raw_name'
  | 'source_quantity'
  | 'conversion_multiplier'
  | 'final_quantity'
  | 'product'
  | 'actions';

type MatchingTableColumn = {
  id: MatchingColumnId;
  label: string;
  defaultWidth: number;
  minWidth: number;
};

type MatchingTableSettings = {
  order: MatchingColumnId[];
  widths: Partial<Record<MatchingColumnId, number>>;
};

const MATCHING_TABLE_STORAGE_KEY = 'turkuaz:unresolved-items-table-columns:v1';
const MAX_MATCHING_COLUMN_WIDTH = 640;
const MATCHING_TABLE_COLUMNS: MatchingTableColumn[] = [
  { id: 'row_number', label: 'Строка', defaultWidth: 90, minWidth: 80 },
  { id: 'raw_barcode', label: 'Barcode', defaultWidth: 150, minWidth: 110 },
  { id: 'raw_item_code', label: 'Код сети', defaultWidth: 150, minWidth: 110 },
  { id: 'raw_name', label: 'Товар из заказа', defaultWidth: 320, minWidth: 180 },
  { id: 'source_quantity', label: 'Кол-во', defaultWidth: 100, minWidth: 90 },
  { id: 'conversion_multiplier', label: 'Множ.', defaultWidth: 110, minWidth: 100 },
  { id: 'final_quantity', label: 'Итог', defaultWidth: 100, minWidth: 90 },
  { id: 'product', label: 'Товар в справочнике', defaultWidth: 320, minWidth: 240 },
  { id: 'actions', label: '', defaultWidth: 220, minWidth: 190 },
];
const MATCHING_TABLE_COLUMN_IDS = MATCHING_TABLE_COLUMNS.map((column) => column.id);

export function UnresolvedItemsPage() {
  const { orderId } = useParams();
  const queryClient = useQueryClient();
  const resizeCleanupRef = useRef<(() => void) | null>(null);
  const columnDragCleanupRef = useRef<(() => void) | null>(null);
  const [productSearch, setProductSearch] = useState('');
  const [selected, setSelected] = useState<Record<number, string>>({});
  const [multipliers, setMultipliers] = useState<Record<number, string>>({});
  const [matchingTableSettings, setMatchingTableSettings] = useState<MatchingTableSettings>(() => readMatchingTableSettings());
  const [draggingColumnId, setDraggingColumnId] = useState<MatchingColumnId | null>(null);
  const [dragOverColumnId, setDragOverColumnId] = useState<MatchingColumnId | null>(null);
  const [resizingColumnId, setResizingColumnId] = useState<MatchingColumnId | null>(null);
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
  const orderedColumns = getOrderedMatchingColumns(matchingTableSettings.order);
  const tableWidth = orderedColumns.reduce((total, column) => total + getMatchingColumnWidth(matchingTableSettings, column), 0);

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

  function startColumnResize(event: React.PointerEvent<HTMLButtonElement>, column: MatchingTableColumn) {
    event.preventDefault();
    event.stopPropagation();
    resizeCleanupRef.current?.();
    const pointerId = event.pointerId;
    const startX = event.clientX;
    const startWidth = getMatchingColumnWidth(matchingTableSettings, column);
    setResizingColumnId(column.id);

    const moveColumnResize = (moveEvent: PointerEvent) => {
      if (moveEvent.pointerId !== pointerId) return;
      moveEvent.preventDefault();
      const nextWidth = clampMatchingColumnWidth(startWidth + moveEvent.clientX - startX, column);
      setMatchingTableSettings((prev) => ({
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

  function startColumnDrag(event: React.PointerEvent<HTMLDivElement>, column: MatchingTableColumn) {
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
      const targetColumnId = target instanceof HTMLElement ? target.closest<HTMLElement>('[data-matching-column-id]')?.dataset.matchingColumnId : undefined;
      setDragOverColumnId(isMatchingColumnId(targetColumnId) ? targetColumnId : null);
    };
    const stopColumnDrag = (upEvent: PointerEvent) => {
      if (upEvent.pointerId !== pointerId) return;
      const target = document.elementFromPoint(upEvent.clientX, upEvent.clientY);
      const targetColumnId = target instanceof HTMLElement ? target.closest<HTMLElement>('[data-matching-column-id]')?.dataset.matchingColumnId : undefined;
      if (moved && isMatchingColumnId(targetColumnId)) {
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

  function moveColumn(sourceId: MatchingColumnId, targetId: MatchingColumnId) {
    if (sourceId === targetId) return;
    setMatchingTableSettings((prev) => {
      const currentOrder = getOrderedMatchingColumns(prev.order).map((column) => column.id);
      const sourceIndex = currentOrder.indexOf(sourceId);
      const targetIndex = currentOrder.indexOf(targetId);
      if (sourceIndex < 0 || targetIndex < 0) return prev;
      const nextOrder = [...currentOrder];
      const [movedColumn] = nextOrder.splice(sourceIndex, 1);
      nextOrder.splice(targetIndex, 0, movedColumn);
      return { ...prev, order: nextOrder };
    });
  }

  function resetMatchingTableLayout() {
    setMatchingTableSettings(createDefaultMatchingTableSettings());
    setDragOverColumnId(null);
    setDraggingColumnId(null);
  }

  function renderMatchingTableCell(columnId: MatchingColumnId, item: any) {
    const sourceQuantity = Number(item.source_quantity ?? item.quantity ?? 0);
    const multiplierValue = multipliers[item.id] ?? String(item.conversion_multiplier ?? 1);
    const multiplier = Number(multiplierValue) > 0 ? Number(multiplierValue) : 1;
    const finalQuantity = Number((sourceQuantity * multiplier).toFixed(3));

    if (columnId === 'row_number') return formatMatchingTableText(item.row_number);
    if (columnId === 'raw_barcode') return formatMatchingTableText(item.raw_barcode);
    if (columnId === 'raw_item_code') return formatMatchingTableText(item.raw_item_code);
    if (columnId === 'raw_name') return formatMatchingTableName(item.raw_name);
    if (columnId === 'source_quantity') return formatMatchingTableText(sourceQuantity);
    if (columnId === 'conversion_multiplier') {
      return (
        <input
          className="input w-full"
          min="0.001"
          step="0.001"
          type="number"
          value={multiplierValue}
          onChange={(event) => setMultipliers((prev) => ({ ...prev, [item.id]: event.target.value }))}
        />
      );
    }
    if (columnId === 'final_quantity') return formatMatchingTableText(finalQuantity);
    if (columnId === 'product') {
      return (
        <select
          className="input w-full"
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
      );
    }
    return (
      <div className="flex flex-wrap gap-2">
        <button type="button" className="button" disabled={!selected[item.id]} onClick={() => resolveProduct(item.id)}>
          Сохранить
        </button>
        <button type="button" className="button-secondary" onClick={() => skipProduct(item.id)}>
          Пропустить
        </button>
      </div>
    );
  }

  useEffect(() => {
    writeMatchingTableSettings(matchingTableSettings);
  }, [matchingTableSettings]);

  useEffect(() => () => {
    resizeCleanupRef.current?.();
    columnDragCleanupRef.current?.();
  }, []);

  return (
    <main className="page space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Сопоставление товаров #{orderId}</h1>
        <Link className="text-sm text-slate-400 hover:text-white" to={`/orders/${orderId}/preview`}>К заказу</Link>
      </div>
      <section className="panel space-y-3">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-sm text-slate-400">
              Введите barcode, код выгрузки или часть названия, затем выберите найденный товар.
            </p>
            <p className="mt-1 text-xs text-slate-500">
              {searchReady ? `Найдено товаров: ${productOptions.length}` : 'Список появится после поиска.'}
            </p>
          </div>
          <button type="button" className="button-secondary" onClick={resetMatchingTableLayout}>
            Сбросить колонки
          </button>
        </div>
        <input
          className="input w-full"
          placeholder="Найти товар по barcode, коду или названию"
          value={productSearch}
          onChange={(event) => setProductSearch(event.target.value)}
        />
      </section>
      <section className={`panel overflow-auto p-0 ${resizingColumnId ? 'adjustable-table--resizing' : ''}`}>
        {isLoading ? (
          <p className="p-5 text-slate-400">Загрузка...</p>
        ) : data?.items?.length ? (
          <table className="table adjustable-table matching-table" style={{ minWidth: tableWidth, width: tableWidth }}>
            <colgroup>
              {orderedColumns.map((column) => (
                <col key={column.id} style={{ width: getMatchingColumnWidth(matchingTableSettings, column) }} />
              ))}
            </colgroup>
            <thead>
              <tr>
                {orderedColumns.map((column) => (
                  <th
                    key={column.id}
                    data-matching-column-id={column.id}
                    className={dragOverColumnId === column.id && draggingColumnId !== column.id ? 'adjustable-table__header--drag-over' : undefined}
                  >
                    <div
                      className="adjustable-table__header-content"
                      data-table-control="true"
                      title={column.label ? 'Перетащить столбец' : 'Перетащить столбец действий'}
                      onPointerDown={(event) => startColumnDrag(event, column)}
                    >
                      <span className="adjustable-table__header-label">{column.label}</span>
                    </div>
                    <button
                      type="button"
                      className={`adjustable-table__resize-handle ${resizingColumnId === column.id ? 'adjustable-table__resize-handle--active' : ''}`}
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
              {data.items.map((item: any) => (
                <tr key={item.id}>
                  {orderedColumns.map((column) => (
                    <td key={column.id}>{renderMatchingTableCell(column.id, item)}</td>
                  ))}
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

function createDefaultMatchingTableSettings(): MatchingTableSettings {
  return {
    order: [...MATCHING_TABLE_COLUMN_IDS],
    widths: Object.fromEntries(MATCHING_TABLE_COLUMNS.map((column) => [column.id, column.defaultWidth])) as Partial<Record<MatchingColumnId, number>>,
  };
}

function readMatchingTableSettings(): MatchingTableSettings {
  if (typeof window === 'undefined') return createDefaultMatchingTableSettings();
  try {
    const rawValue = window.localStorage.getItem(MATCHING_TABLE_STORAGE_KEY);
    if (!rawValue) return createDefaultMatchingTableSettings();
    return normalizeMatchingTableSettings(JSON.parse(rawValue));
  } catch {
    return createDefaultMatchingTableSettings();
  }
}

function writeMatchingTableSettings(settings: MatchingTableSettings) {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(MATCHING_TABLE_STORAGE_KEY, JSON.stringify(normalizeMatchingTableSettings(settings)));
  } catch {
    // Layout preferences are optional; the matching flow should continue if storage is unavailable.
  }
}

function normalizeMatchingTableSettings(value: unknown): MatchingTableSettings {
  if (!value || typeof value !== 'object') return createDefaultMatchingTableSettings();
  const settings = value as Partial<MatchingTableSettings>;
  const savedOrder = Array.isArray(settings.order) ? settings.order.filter(isMatchingColumnId) : [];
  const order = [
    ...savedOrder,
    ...MATCHING_TABLE_COLUMN_IDS.filter((columnId) => !savedOrder.includes(columnId)),
  ];
  const widths: Partial<Record<MatchingColumnId, number>> = {};
  for (const column of MATCHING_TABLE_COLUMNS) {
    const savedWidth = settings.widths?.[column.id];
    widths[column.id] = clampMatchingColumnWidth(typeof savedWidth === 'number' ? savedWidth : column.defaultWidth, column);
  }
  return { order, widths };
}

function getOrderedMatchingColumns(order: MatchingColumnId[]) {
  return order
    .map((columnId) => MATCHING_TABLE_COLUMNS.find((column) => column.id === columnId))
    .filter((column): column is MatchingTableColumn => Boolean(column));
}

function getMatchingColumnWidth(settings: MatchingTableSettings, column: MatchingTableColumn) {
  return clampMatchingColumnWidth(settings.widths[column.id] ?? column.defaultWidth, column);
}

function clampMatchingColumnWidth(width: number, column: MatchingTableColumn) {
  if (!Number.isFinite(width)) return column.defaultWidth;
  return Math.min(MAX_MATCHING_COLUMN_WIDTH, Math.max(column.minWidth, Math.round(width)));
}

function isMatchingColumnId(value: unknown): value is MatchingColumnId {
  return typeof value === 'string' && MATCHING_TABLE_COLUMN_IDS.includes(value as MatchingColumnId);
}

function formatMatchingTableText(value: unknown) {
  const text = String(value ?? '').trim();
  if (!text) return null;
  return (
    <span className="adjustable-table__cell-text" title={text}>
      {text}
    </span>
  );
}

function formatMatchingTableName(value: unknown) {
  const text = String(value ?? '').trim();
  if (!text) return null;
  return (
    <span className="matching-table__name-text" title={text}>
      {text}
    </span>
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
