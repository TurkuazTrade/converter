import { ChangeEvent, DragEvent, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import { downloadBlob, filenameFromContentDisposition } from '../shared/download';
import { converters } from '../shared/converters';

type ProductTypeRule = {
  product_type: string;
  exclude_from_export: boolean;
};

export function UploadOrderPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [file, setFile] = useState<File | null>(null);
  const [converterType, setConverterType] = useState('');
  const [force, setForce] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [typeSettingsOpen, setTypeSettingsOpen] = useState(false);
  const [typeMessage, setTypeMessage] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const { data: productTypes = [] } = useQuery<ProductTypeRule[]>({
    queryKey: ['product-types'],
    queryFn: async () => (await api.get('/products/types')).data,
  });

  async function upload() {
    if (!file) return;
    setLoading(true);
    setError('');
    setMessage('');
    try {
      const form = new FormData();
      form.append('file', file);
      const params = new URLSearchParams();
      params.set('force', String(force));
      if (converterType) {
        params.set('converter_type', converterType);
      }
      const response = await api.post(`/orders/upload?${params.toString()}`, form);
      if (response.data.duplicate && response.data.existing_order_id) {
        setMessage(`Файл уже был загружен. Открываю существующий заказ #${response.data.existing_order_id}.`);
        navigate(`/orders/${response.data.existing_order_id}/preview`);
        return;
      }
      const orderId = response.data.order?.id;
      if (orderId) {
        navigate(`/orders/${orderId}/preview`);
      }
    } catch (err: any) {
      setError(err.response?.data?.detail ?? 'Не удалось загрузить файл');
    } finally {
      setLoading(false);
    }
  }

  function onFile(event: ChangeEvent<HTMLInputElement>) {
    setFile(event.target.files?.[0] ?? null);
  }

  function onDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setFile(event.dataTransfer.files?.[0] ?? null);
  }

  async function toggleTypeExportExclusion(typeRule: ProductTypeRule) {
    setTypeMessage('');
    try {
      await api.patch('/products/types/export-exclusion', {
        product_type: typeRule.product_type,
        exclude_from_export: !typeRule.exclude_from_export,
      });
      await queryClient.invalidateQueries({ queryKey: ['product-types'] });
      setTypeMessage('Настройка типа обновлена.');
    } catch (err: any) {
      setTypeMessage(err.response?.data?.detail ?? 'Не удалось обновить тип товара');
    }
  }

  async function downloadOrderTemplate() {
    setError('');
    try {
      const response = await api.get('/orders/templates/import', {
        params: converterType ? { converter_type: converterType } : undefined,
        responseType: 'blob',
      });
      const fallback = `order_template_${converterType || 'asia_retail'}.xlsx`;
      const filename = filenameFromContentDisposition(response.headers['content-disposition'], fallback);
      downloadBlob(response.data, filename);
    } catch (err: any) {
      setError(err.response?.data?.detail ?? 'Не удалось скачать шаблон заказа');
    }
  }

  return (
    <main className="page space-y-6">
      <section className="panel space-y-5">
        <div>
          <h1 className="text-xl font-semibold">Конвертер</h1>
          <p className="mt-1 text-sm text-slate-400">Выберите источник и Excel-файл. Если источник не выбран, система определит его автоматически.</p>
        </div>

        <label className="block max-w-md space-y-2">
          <span className="text-sm text-slate-400">Источник</span>
          <select className="input w-full" value={converterType} onChange={(event) => setConverterType(event.target.value)}>
            <option value="">Автовыбор</option>
            {converters.filter(([value]) => value !== 'auto').map(([value, label]) => (
              <option key={value} value={value}>{label}</option>
            ))}
          </select>
        </label>

        <div
          onDrop={onDrop}
          onDragOver={(event) => event.preventDefault()}
          className="rounded-lg border border-dashed border-slate-600 bg-slate-950 p-8 text-center"
        >
          <p className="font-medium">{file ? file.name : 'Перетащите Excel сюда'}</p>
          <p className="mt-1 text-sm text-slate-500">или выберите файл вручную</p>
          <input className="input mt-4" type="file" accept=".xlsx,.xls" onChange={onFile} />
        </div>

        <button type="button" className="text-left text-sm text-slate-400 hover:text-white" onClick={() => setShowAdvanced((value) => !value)}>
          {showAdvanced ? 'Скрыть дополнительные настройки' : 'Дополнительные настройки'}
        </button>

        {showAdvanced && (
          <div className="grid gap-4 rounded-md border border-slate-800 bg-slate-950 p-4 md:grid-cols-3">
            <label className="flex items-end gap-2 pb-2 text-sm text-slate-300">
              <input type="checkbox" checked={force} onChange={(event) => setForce(event.target.checked)} />
              Загрузить повторно
            </label>
          </div>
        )}

        {error && <p className="text-sm text-red-400">{error}</p>}
        {message && <p className="text-sm text-amber-300">{message}</p>}
        <div className="flex flex-wrap gap-2">
          <button type="button" className="button" onClick={upload} disabled={!file || loading}>
            {loading ? 'Обработка...' : 'Загрузить заказ'}
          </button>
        </div>
      </section>
      {productTypes.length > 0 && (
        <section className="compact-panel space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="text-base font-semibold">Исключение типов из финального Excel</h2>
              <p className="mt-1 text-sm text-slate-400">{excludedTypeCount(productTypes)} отмечено</p>
            </div>
            <button type="button" className="button-ghost" onClick={() => setTypeSettingsOpen((value) => !value)}>
              {typeSettingsOpen ? 'Скрыть' : 'Открыть'}
            </button>
          </div>
          {typeSettingsOpen && (
            <>
              <div className="flex flex-wrap items-center justify-between gap-3">
                <p className="text-sm text-slate-400">Отмеченные типы не попадут в итоговую выгрузку.</p>
                <button type="button" className="button-secondary" onClick={downloadOrderTemplate}>
                  Скачать шаблон заказа
                </button>
              </div>
              <div className="export-type-list">
                {productTypes.map((typeRule) => (
                  <label
                    key={typeRule.product_type}
                    className={`export-type-option${typeRule.exclude_from_export ? ' export-type-option--checked' : ''}`}
                  >
                    <input
                      type="checkbox"
                      checked={typeRule.exclude_from_export}
                      onChange={() => toggleTypeExportExclusion(typeRule)}
                    />
                    <span className="export-type-option__box" aria-hidden="true" />
                    <span className="export-type-option__label">{typeRule.product_type}</span>
                  </label>
                ))}
              </div>
              {typeMessage && <p className="text-sm text-slate-400">{typeMessage}</p>}
            </>
          )}
        </section>
      )}
    </main>
  );
}

function excludedTypeCount(productTypes: ProductTypeRule[]) {
  return productTypes.filter((typeRule) => typeRule.exclude_from_export).length;
}
