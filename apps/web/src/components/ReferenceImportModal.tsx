import { ChangeEvent, DragEvent, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { api } from '../api/client';
import { downloadBlob, filenameFromContentDisposition } from '../shared/download';
import { FormModal } from './FormModal';

type ImportKind = 'products' | 'clients';

type ImportSummary = {
  inserted: number;
  updated: number;
  skipped: number;
  mappings_inserted?: number;
  skipped_file?: {
    filename: string;
    mime_type: string;
    content_base64: string;
  } | null;
};

type ReferenceImportModalProps = {
  kind: ImportKind;
  title: string;
  filledDownloadParams?: Record<string, string | boolean | number | undefined>;
  onClose: () => void;
};

const importLabels: Record<ImportKind, string> = {
  products: 'товары',
  clients: 'клиенты',
};

export function ReferenceImportModal({ kind, title, filledDownloadParams, onClose }: ReferenceImportModalProps) {
  const queryClient = useQueryClient();
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState<ImportSummary | null>(null);

  function setImportFile(nextFile: File | null) {
    setFile(nextFile);
    setResult(null);
    setError('');
  }

  function onFile(event: ChangeEvent<HTMLInputElement>) {
    setImportFile(event.target.files?.[0] ?? null);
  }

  function onDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setImportFile(event.dataTransfer.files?.[0] ?? null);
  }

  async function upload() {
    if (!file) return;
    setLoading(true);
    setError('');
    setResult(null);
    try {
      const form = new FormData();
      form.append('file', file);
      const response = await api.post(`/${kind}/import`, form);
      setResult(response.data);
      if (kind === 'products') {
        await Promise.all([
          queryClient.invalidateQueries({ queryKey: ['products'] }),
          queryClient.invalidateQueries({ queryKey: ['product-filter-options'] }),
          queryClient.invalidateQueries({ queryKey: ['product-dictionary'] }),
          queryClient.invalidateQueries({ queryKey: ['product-types'] }),
        ]);
      } else {
        await queryClient.invalidateQueries({ queryKey: ['clients'] });
      }
    } catch (err: any) {
      setError(err.response?.data?.detail ?? 'Не удалось импортировать справочник');
    } finally {
      setLoading(false);
    }
  }

  async function downloadWorkbook(mode: 'template' | 'filled') {
    setError('');
    try {
      const endpoint = mode === 'template' ? `/${kind}/import-template` : `/${kind}/export`;
      const response = await api.get(endpoint, {
        params: mode === 'filled' ? filledDownloadParams : undefined,
        responseType: 'blob',
      });
      const fallback = `${kind}_${mode === 'template' ? 'template' : 'filled'}.xlsx`;
      const filename = filenameFromContentDisposition(response.headers['content-disposition'], fallback);
      downloadBlob(response.data, filename);
    } catch (err: any) {
      setError(err.response?.data?.detail ?? 'Не удалось скачать Excel-файл');
    }
  }

  return (
    <FormModal
      title={title}
      description="Загрузите Excel-файл справочника."
      onClose={onClose}
      actions={(
        <>
          <button type="button" className="button-secondary" onClick={() => downloadWorkbook('template')}>
            Скачать шаблон
          </button>
          <button type="button" className="button-secondary" onClick={() => downloadWorkbook('filled')}>
            Скачать заполненный файл
          </button>
          <button type="button" className="button" onClick={upload} disabled={!file || loading}>
            {loading ? 'Импорт...' : `Импортировать ${importLabels[kind]}`}
          </button>
        </>
      )}
    >
      <div className="space-y-4">
        <div
          onDrop={onDrop}
          onDragOver={(event) => event.preventDefault()}
          className="rounded-lg border border-dashed border-slate-600 p-6 text-center"
        >
          <p className="font-medium">{file ? file.name : 'Перетащите Excel сюда'}</p>
          <input className="input mt-4 w-full" type="file" accept=".xlsx,.xls" onChange={onFile} />
        </div>
        {error && <p className="text-sm text-red-400">{error}</p>}
        {result && <ImportSummaryCard summary={result} />}
      </div>
    </FormModal>
  );
}

function ImportSummaryCard({ summary }: { summary: ImportSummary }) {
  function downloadSkippedRows() {
    const file = summary.skipped_file;
    if (!file) return;
    const binary = window.atob(file.content_base64);
    const bytes = new Uint8Array(binary.length);
    for (let index = 0; index < binary.length; index += 1) {
      bytes[index] = binary.charCodeAt(index);
    }
    downloadBlob(new Blob([bytes], { type: file.mime_type }), file.filename);
  }

  return (
    <div className="rounded-md border border-slate-800 bg-slate-950 p-4">
      <div className="flex flex-wrap gap-2 text-sm">
        <span className="status-pill-ok">Импорт завершен</span>
        {summary.skipped_file && (
          <button type="button" className="button-secondary" onClick={downloadSkippedRows}>
            Скачать пропущенные строки
          </button>
        )}
      </div>
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
