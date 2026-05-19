import { useParams } from 'react-router-dom';

const reportTitles: Record<string, string> = {
  panorama: 'Отчеты Panorama',
  tiger: 'Отчеты Tiger',
  ocean: 'Отчеты Ocean/WMS',
};

export function ReportsPlaceholderPage() {
  const { reportType } = useParams();
  const title = reportTitles[reportType ?? ''] ?? 'Отчеты';

  return (
    <main className="page">
      <section className="panel overflow-hidden p-0">
        <div className="grid items-center gap-6 p-6 md:grid-cols-[1fr_280px]">
          <div>
            <span className="status-pill">Ведутся работы</span>
            <h1 className="mt-4 text-2xl font-semibold">{title}</h1>
            <p className="mt-2 max-w-xl text-sm leading-6 text-slate-400">
              Раздел готовится. Здесь появятся отчеты, фильтры и выгрузки для регулярной работы команды.
            </p>
          </div>
          <ConstructionPreview />
        </div>
      </section>
    </main>
  );
}

function ConstructionPreview() {
  return (
    <div className="rounded-md border border-slate-800 bg-slate-950 p-4">
      <svg className="h-44 w-full" viewBox="0 0 280 176" role="img" aria-label="Дорожное заграждение">
        <rect x="0" y="0" width="280" height="176" rx="12" fill="var(--app-surface-muted)" />
        <path d="M38 134h204" stroke="#64748b" strokeWidth="2" strokeDasharray="9 9" opacity="0.65" />
        <rect x="48" y="68" width="184" height="36" rx="7" fill="#f59e0b" />
        <path d="M62 68h34l-24 36H48l14-36Z" fill="#fff7ed" opacity="0.92" />
        <path d="M124 68h34l-24 36h-34l24-36Z" fill="#fff7ed" opacity="0.92" />
        <path d="M186 68h34l-24 36h-34l24-36Z" fill="#fff7ed" opacity="0.92" />
        <rect x="54" y="104" width="16" height="34" rx="3" fill="#334155" />
        <rect x="210" y="104" width="16" height="34" rx="3" fill="#334155" />
        <rect x="42" y="136" width="40" height="10" rx="5" fill="#1e293b" />
        <rect x="198" y="136" width="40" height="10" rx="5" fill="#1e293b" />
        <path d="M132 42h16v26h-16V42Z" fill="#fb923c" />
        <path d="M118 42h44l-8-14h-28l-8 14Z" fill="#f97316" />
        <circle cx="140" cy="86" r="12" fill="#0f172a" opacity="0.16" />
        <path d="M137 78h6v16h-6V78Z" fill="#78350f" />
        <path d="M132 83h16v6h-16v-6Z" fill="#78350f" />
      </svg>
    </div>
  );
}
