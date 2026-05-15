import { ChangeEvent, DragEvent, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import { converters } from '../shared/converters';

export function UploadOrderPage() {
  const navigate = useNavigate();
  const [file, setFile] = useState<File | null>(null);
  const [converterType, setConverterType] = useState('auto');
  const [force, setForce] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

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
      if (converterType !== 'auto') {
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

  return (
    <main className="page space-y-6">
      <section className="panel space-y-5">
        <div>
          <h1 className="text-xl font-semibold">Загрузка заказа</h1>
          <p className="mt-1 text-sm text-slate-400">Выберите Excel-файл. Система сама определит сеть и покажет, что нужно исправить перед выгрузкой.</p>
        </div>

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
            <label className="space-y-2">
              <span className="text-sm text-slate-400">Сеть</span>
              <select className="input w-full" value={converterType} onChange={(event) => setConverterType(event.target.value)}>
                {converters.map(([value, label]) => (
                  <option key={value} value={value}>{label}</option>
                ))}
              </select>
            </label>
            <label className="flex items-end gap-2 pb-2 text-sm text-slate-300">
              <input type="checkbox" checked={force} onChange={(event) => setForce(event.target.checked)} />
              Загрузить повторно
            </label>
          </div>
        )}

        {error && <p className="text-sm text-red-400">{error}</p>}
        {message && <p className="text-sm text-amber-300">{message}</p>}
        <button type="button" className="button w-fit" onClick={upload} disabled={!file || loading}>
          {loading ? 'Обработка...' : 'Загрузить заказ'}
        </button>
      </section>
    </main>
  );
}
