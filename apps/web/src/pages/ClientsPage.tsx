import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../api/client';
import { FormModal } from '../components/FormModal';
import { PaginationControls } from '../components/PaginationControls';

type ClientForm = {
  id?: number;
  client_code: string;
  name: string;
  name_2: string;
  is_active: boolean;
};

const emptyClientForm: ClientForm = {
  client_code: '',
  name: '',
  name_2: '',
  is_active: true,
};

export function ClientsPage() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(0);
  const [limit, setLimit] = useState(50);
  const [form, setForm] = useState<ClientForm>(emptyClientForm);
  const [formOpen, setFormOpen] = useState(false);
  const [formError, setFormError] = useState('');
  const { data, isLoading } = useQuery({
    queryKey: ['clients', search, page, limit],
    queryFn: async () => (
      await api.get('/clients', { params: { search, limit, offset: page * limit } })
    ).data,
  });
  const clients = data ?? [];

  function updateSearch(value: string) {
    setSearch(value);
    setPage(0);
  }

  function updateLimit(value: number) {
    setLimit(value);
    setPage(0);
  }

  function openCreateClient() {
    setForm(emptyClientForm);
    setFormError('');
    setFormOpen(true);
  }

  function editClient(client: any) {
    setForm({
      id: client.id,
      client_code: client.client_code ?? '',
      name: client.name ?? '',
      name_2: client.name_2 ?? '',
      is_active: client.is_active,
    });
    setFormError('');
    setFormOpen(true);
  }

  function closeForm() {
    setFormOpen(false);
    setForm(emptyClientForm);
    setFormError('');
  }

  async function saveClient() {
    setFormError('');
    try {
      const payload = {
        client_code: form.client_code,
        name: form.name,
        name_2: form.name_2,
        is_active: form.is_active,
      };
      if (form.id) {
        await api.patch(`/clients/${form.id}`, payload);
      } else {
        await api.post('/clients', payload);
      }
      closeForm();
      await queryClient.invalidateQueries({ queryKey: ['clients'] });
    } catch (err: any) {
      setFormError(err.response?.data?.detail ?? 'Не удалось сохранить клиента');
    }
  }

  return (
    <main className="page space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">Клиенты</h1>
          <p className="mt-1 text-sm text-slate-400">Справочник клиентов для определения получателя заказа.</p>
        </div>
        <button type="button" className="button" onClick={openCreateClient}>Добавить клиента</button>
      </div>
      <div className="flex flex-wrap gap-3">
        <input className="input w-full md:w-96" placeholder="Поиск по коду или названию клиента" value={search} onChange={(event) => updateSearch(event.target.value)} />
      </div>
      <PaginationControls
        page={page}
        limit={limit}
        itemCount={clients.length}
        onPageChange={setPage}
        onLimitChange={updateLimit}
      />
      <section className="panel overflow-auto p-0">
        {isLoading ? (
          <p className="p-5 text-slate-400">Загрузка...</p>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>№</th>
                <th>Код клиента панорама</th>
                <th>Название клиента панорама</th>
                <th>Название клиента питон</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {clients.map((client: any, index: number) => (
                <tr key={client.id}>
                  <td>{page * limit + index + 1}</td>
                  <td>{client.client_code}</td>
                  <td>{client.name}</td>
                  <td>{client.name_2}</td>
                  <td>
                    <button type="button" className="button-secondary" onClick={() => editClient(client)}>
                      Редактировать
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      {formOpen && (
        <FormModal
          title={form.id ? 'Редактировать клиента' : 'Добавить клиента'}
          description="Поля соответствуют клиентскому Excel-файлу."
          onClose={closeForm}
          actions={(
            <>
              <label className="flex items-center gap-2 text-sm text-slate-300">
                <input type="checkbox" checked={form.is_active} onChange={(event) => setForm((prev) => ({ ...prev, is_active: event.target.checked }))} />
                Активен
              </label>
              <button type="button" className="button" disabled={!form.client_code.trim() || !form.name.trim()} onClick={saveClient}>
                Сохранить
              </button>
              <button type="button" className="button-secondary" onClick={closeForm}>Отмена</button>
              {formError && <span className="text-sm text-red-400">{formError}</span>}
            </>
          )}
        >
          <div className="grid gap-3 md:grid-cols-2">
            <label className="space-y-2">
              <span className="text-sm text-slate-400">Код клиента панорама</span>
              <input className="input w-full" value={form.client_code} onChange={(event) => setForm((prev) => ({ ...prev, client_code: event.target.value }))} />
            </label>
            <label className="space-y-2">
              <span className="text-sm text-slate-400">Название клиента панорама</span>
              <input className="input w-full" value={form.name} onChange={(event) => setForm((prev) => ({ ...prev, name: event.target.value }))} />
            </label>
            <label className="space-y-2 md:col-span-2">
              <span className="text-sm text-slate-400">Название клиента питон</span>
              <input className="input w-full" value={form.name_2} onChange={(event) => setForm((prev) => ({ ...prev, name_2: event.target.value }))} />
            </label>
          </div>
        </FormModal>
      )}
    </main>
  );
}
