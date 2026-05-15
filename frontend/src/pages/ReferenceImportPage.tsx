import { ChangeEvent, DragEvent, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { api } from '../api/client';
import { converters } from '../shared/converters';

type ImportSummary = {
  inserted: number;
  updated: number;
  skipped: number;
  mappings_inserted?: number;
};

type ImportResult = {
  converter_type: string | null;
  products: ImportSummary | null;
  clients: ImportSummary | null;
};

function SummaryCard({ title, summary }: { title: string; summary: ImportSummary | null }) {
  if (!summary) {
    return null;
  }
  return (
    <div className="rounded-md border border-slate-800 bg-slate-950 p-4">
      <h2 className="text-sm font-semibold text-white">{title}</h2>
      <div className="mt-3 grid grid-cols-2 gap-3 text-sm md:grid-cols-4">
        <div>
          <p className="text-slate-500">Добавлено</p>
          <p className="text-lg font-semibold text-emerald-300">{summary.inserted}</p>
        </div>
        <div>
          <p className="text-slate-500">Обновлено</p>
          <p className="text-lg font-semibold text-blue-300">{summary.updated}</p>
        </div>
        <div>
          <p className="text-slate-500">Mappings</p>
          <p className="text-lg font-semibold text-cyan-300">{summary.mappings_inserted ?? 0}</p>
        </div>
        <div>
          <p className="text-slate-500">Пропущено</p>
          <p className="text-lg font-semibold text-amber-300">{summary.skipped}</p>
        </div>
      </div>
    </div>
  );
}

export function ReferenceImportPage() {
  const queryClient = useQueryClient();
  const [file, setFile] = useState<File | null>(null);
  const [converterType, setConverterType] = useState('auto');
  const [includeProducts, setIncludeProducts] = useState(true);
  const [includeClients, setIncludeClients] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState<ImportResult | null>(null);

  function onFile(event: ChangeEvent<HTMLInputElement>) {
    setFile(event.target.files?.[0] ?? null);
    setResult(null);
    setError('');
  }

  function onDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setFile(event.dataTransfer.files?.[0] ?? null);
    setResult(null);
    setError('');
  }

  async function upload() {
    if (!file || (!includeProducts && !includeClients)) return;
    setLoading(true);
    setError('');
    setResult(null);
    try {
      const form = new FormData();
      form.append('file', file);
      const params = new URLSearchParams();
      params.set('import_products', String(includeProducts));
      params.set('import_clients', String(includeClients));
      if (converterType !== 'auto') {
        params.set('converter_type', converterType);
      }
      const response = await api.post(`/references/import?${params.toString()}`, form);
      setResult(response.data);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['products'] }),
        queryClient.invalidateQueries({ queryKey: ['clients'] }),
      ]);
    } catch (err: any) {
      setError(err.response?.data?.detail ?? 'Не удалось импортировать справочник');
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="page space-y-6">
      <section className="panel space-y-5">
        <div>
          <h1 className="text-xl font-semibold">Справочники</h1>
          <p className="mt-1 text-sm text-slate-400">Импорт клиентских и товарных mappings из Excel.</p>
        </div>

        <div
          onDrop={onDrop}
          onDragOver={(event) => event.preventDefault()}
          className="rounded-lg border border-dashed border-slate-600 bg-slate-950 p-8 text-center"
        >
          <p className="font-medium">{file ? file.name : 'Перетащите Excel сюда'}</p>
          <input className="input mt-4" type="file" accept=".xlsx,.xls" onChange={onFile} />
        </div>

        <div className="grid gap-4 md:grid-cols-[minmax(220px,320px)_1fr]">
          <label className="space-y-2">
            <span className="text-sm text-slate-400">Сеть</span>
            <select className="input w-full" value={converterType} onChange={(event) => setConverterType(event.target.value)}>
              {converters.map(([value, label]) => (
                <option key={value} value={value}>{label}</option>
              ))}
            </select>
          </label>

          <div className="grid gap-3 rounded-md border border-slate-800 bg-slate-950 p-4 md:grid-cols-2">
            <label className="flex items-center gap-3 text-sm text-slate-300">
              <input type="checkbox" checked={includeProducts} onChange={(event) => setIncludeProducts(event.target.checked)} />
              <span>convert: товары и коды сети</span>
            </label>
            <label className="flex items-center gap-3 text-sm text-slate-300">
              <input type="checkbox" checked={includeClients} onChange={(event) => setIncludeClients(event.target.checked)} />
              <span>client: клиенты и названия сети</span>
            </label>
          </div>
        </div>

        {error && <p className="text-sm text-red-400">{error}</p>}
        <button type="button" className="button w-fit" onClick={upload} disabled={!file || loading || (!includeProducts && !includeClients)}>
          {loading ? 'Импорт...' : 'Импортировать'}
        </button>
      </section>

      {result && (
        <section className="panel space-y-4">
          <div className="flex flex-wrap gap-2 text-sm">
            <span className="status-pill">Сеть: {result.converter_type ?? 'не определена'}</span>
            <span className="status-pill-ok">Импорт завершен</span>
          </div>
          <SummaryCard title="Товары / convert" summary={result.products} />
          <SummaryCard title="Клиенты / client" summary={result.clients} />
        </section>
      )}
    </main>
  );
}
