import type { ReactNode } from 'react';

const limitOptions = [25, 50, 100, 200];

type PaginationControlsProps = {
  page: number;
  limit: number;
  itemCount: number;
  onPageChange: (page: number) => void;
  onLimitChange: (limit: number) => void;
  extraInfo?: ReactNode;
  extraControls?: ReactNode;
};

export function PaginationControls({
  page,
  limit,
  itemCount,
  onPageChange,
  onLimitChange,
  extraInfo,
  extraControls,
}: PaginationControlsProps) {
  const canGoBack = page > 0;
  const canGoForward = itemCount >= limit;
  const from = itemCount ? page * limit + 1 : 0;
  const to = page * limit + itemCount;

  return (
    <div className="compact-panel flex flex-col gap-3 text-sm">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="text-slate-400">
          Страница {page + 1} · строки {from}-{to}
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            className="button-secondary min-w-24"
            disabled={!canGoBack}
            onClick={() => onPageChange(page - 1)}
          >
            Назад
          </button>
          <button
            type="button"
            className="button-secondary min-w-24"
            disabled={!canGoForward}
            onClick={() => onPageChange(page + 1)}
          >
            Вперед
          </button>
        </div>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-700/40 pt-3">
        {extraInfo && <div className="min-w-0">{extraInfo}</div>}
        <div className="flex min-w-0 flex-wrap items-center gap-2">
          {extraControls}
        </div>
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
      </div>
    </div>
  );
}
