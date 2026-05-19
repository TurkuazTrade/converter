import { ChangeEvent, DragEvent, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { api } from '../api/client';

type ImportSummary = {
  inserted: number;
  updated: number;
  skipped: number;
  mappings_inserted?: number;
};

function SummaryCard({ title, summary }: { title: string; summary: ImportSummary | null | undefined }) {
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
  const [productFile, setProductFile] = useState<File | null>(null);
  const [clientFile, setClientFile] = useState<File | null>(null);
  const [productLoading, setProductLoading] = useState(false);
  const [clientLoading, setClientLoading] = useState(false);
  const [productError, setProductError] = useState('');
  const [clientError, setClientError] = useState('');
  const [productResult, setProductResult] = useState<ImportSummary | null>(null);
  const [clientResult, setClientResult] = useState<ImportSummary | null>(null);

  function onFile(kind: 'products' | 'clients', event: ChangeEvent<HTMLInputElement>) {
    setImportFile(kind, event.target.files?.[0] ?? null);
  }

  function onDrop(kind: 'products' | 'clients', event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setImportFile(kind, event.dataTransfer.files?.[0] ?? null);
  }

  function setImportFile(kind: 'products' | 'clients', nextFile: File | null) {
    if (kind === 'products') {
      setProductFile(nextFile);
      setProductResult(null);
      setProductError('');
    } else {
      setClientFile(nextFile);
      setClientResult(null);
      setClientError('');
    }
  }

  async function upload(kind: 'products' | 'clients') {
    const selectedFile = kind === 'products' ? productFile : clientFile;
    if (!selectedFile) return;
    if (kind === 'products') {
      setProductLoading(true);
      setProductError('');
      setProductResult(null);
    } else {
      setClientLoading(true);
      setClientError('');
      setClientResult(null);
    }
    try {
      const form = new FormData();
      form.append('file', selectedFile);
      const response = await api.post(`/${kind}/import`, form);
      if (kind === 'products') {
        setProductResult(response.data);
        await Promise.all([
          queryClient.invalidateQueries({ queryKey: ['products'] }),
          queryClient.invalidateQueries({ queryKey: ['product-types'] }),
        ]);
      } else {
        setClientResult(response.data);
        await queryClient.invalidateQueries({ queryKey: ['clients'] });
      }
    } catch (err: any) {
      const message = err.response?.data?.detail ?? 'Не удалось импортировать справочник';
      if (kind === 'products') {
        setProductError(message);
      } else {
        setClientError(message);
      }
    } finally {
      if (kind === 'products') {
        setProductLoading(false);
      } else {
        setClientLoading(false);
      }
    }
  }

  return (
    <main className="page space-y-6">
      <section className="panel space-y-5">
        <div>
          <h1 className="text-xl font-semibold">Справочники</h1>
          <p className="mt-1 text-sm text-slate-400">Импорт товаров и клиентов из отдельных Excel-файлов.</p>
        </div>

        <div className="grid gap-4 lg:grid-cols-2">
          <ImportBox
            title="Товары"
            file={productFile}
            loading={productLoading}
            error={productError}
            result={productResult}
            onDrop={(event) => onDrop('products', event)}
            onFile={(event) => onFile('products', event)}
            onUpload={() => upload('products')}
          />
          <ImportBox
            title="Клиенты"
            file={clientFile}
            loading={clientLoading}
            error={clientError}
            result={clientResult}
            onDrop={(event) => onDrop('clients', event)}
            onFile={(event) => onFile('clients', event)}
            onUpload={() => upload('clients')}
          />
        </div>
      </section>

      {(productResult || clientResult) && (
        <section className="panel space-y-4">
          <div className="flex flex-wrap gap-2 text-sm">
            <span className="status-pill-ok">Импорт завершен</span>
          </div>
          <SummaryCard title="Товары" summary={productResult} />
          <SummaryCard title="Клиенты" summary={clientResult} />
        </section>
      )}
    </main>
  );
}

function ImportBox({
  title,
  file,
  loading,
  error,
  result,
  onDrop,
  onFile,
  onUpload,
}: {
  title: string;
  file: File | null;
  loading: boolean;
  error: string;
  result: ImportSummary | null;
  onDrop: (event: DragEvent<HTMLDivElement>) => void;
  onFile: (event: ChangeEvent<HTMLInputElement>) => void;
  onUpload: () => void;
}) {
  return (
    <div className="space-y-4 rounded-md border border-slate-800 bg-slate-950 p-4">
      <div>
        <h2 className="text-base font-semibold">{title}</h2>
        {result && <p className="mt-1 text-sm text-emerald-300">Импортировано</p>}
      </div>
      <div
        onDrop={onDrop}
        onDragOver={(event) => event.preventDefault()}
        className="rounded-lg border border-dashed border-slate-600 p-6 text-center"
      >
        <p className="font-medium">{file ? file.name : 'Перетащите Excel сюда'}</p>
        <input className="input mt-4 w-full" type="file" accept=".xlsx,.xls" onChange={onFile} />
      </div>
      {error && <p className="text-sm text-red-400">{error}</p>}
      <button type="button" className="button w-fit" onClick={onUpload} disabled={!file || loading}>
        {loading ? 'Импорт...' : `Импортировать ${title.toLowerCase()}`}
      </button>
    </div>
  );
}
