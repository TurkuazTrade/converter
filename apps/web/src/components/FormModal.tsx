import { ReactNode } from 'react';

type FormModalProps = {
  title: string;
  description?: string;
  children: ReactNode;
  actions: ReactNode;
  onClose: () => void;
};

export function FormModal({ title, description, children, actions, onClose }: FormModalProps) {
  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/50 px-4 py-6">
      <section className="panel w-full max-w-2xl space-y-4">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-lg font-semibold">{title}</h2>
            {description && <p className="mt-1 text-sm text-slate-400">{description}</p>}
          </div>
          <button type="button" className="button-ghost" onClick={onClose}>Закрыть</button>
        </div>

        {children}

        <div className="flex flex-wrap items-center gap-3">
          {actions}
        </div>
      </section>
    </div>
  );
}
