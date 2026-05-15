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
    <main className="page space-y-4">
      <section className="panel">
        <h1 className="text-xl font-semibold">{title}</h1>
        <p className="mt-2 text-sm text-slate-400">Раздел в подготовке.</p>
      </section>
    </main>
  );
}
