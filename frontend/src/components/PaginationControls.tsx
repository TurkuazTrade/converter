const limitOptions = [25, 50, 100, 200];

type PaginationControlsProps = {
  page: number;
  limit: number;
  itemCount: number;
  onPageChange: (page: number) => void;
  onLimitChange: (limit: number) => void;
};

export function PaginationControls({
  page,
  limit,
  itemCount,
  onPageChange,
  onLimitChange,
}: PaginationControlsProps) {
  const canGoBack = page > 0;
  const canGoForward = itemCount >= limit;
  const from = itemCount ? page * limit + 1 : 0;
  const to = page * limit + itemCount;

  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-slate-800 bg-slate-950 px-4 py-3 text-sm">
      <div className="text-slate-400">
        Страница {page + 1} · строки {from}-{to}
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <label className="flex items-center gap-2 text-slate-400">
          <span>Показывать</span>
          <select
            className="input w-24"
            value={limit}
            onChange={(event) => onLimitChange(Number(event.target.value))}
          >
            {limitOptions.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </label>
        <button
          type="button"
          className="button-secondary"
          disabled={!canGoBack}
          onClick={() => onPageChange(page - 1)}
        >
          Назад
        </button>
        <button
          type="button"
          className="button-secondary"
          disabled={!canGoForward}
          onClick={() => onPageChange(page + 1)}
        >
          Вперед
        </button>
      </div>
    </div>
  );
}
