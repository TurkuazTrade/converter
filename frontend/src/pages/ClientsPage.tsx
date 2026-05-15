import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../api/client';
import { PaginationControls } from '../components/PaginationControls';

type ClientForm = {
  id?: number;
  client_code: string;
  client_code_2: string;
  name: string;
  name_2: string;
  address: string;
  network_name: string;
  is_active: boolean;
};

const emptyClientForm: ClientForm = {
  client_code: '',
  client_code_2: '',
  name: '',
  name_2: '',
  address: '',
  network_name: '',
  is_active: true,
};

export function ClientsPage() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(0);
  const [limit, setLimit] = useState(50);
  const [form, setForm] = useState<ClientForm>(emptyClientForm);
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

  function editClient(client: any) {
    setForm({
      id: client.id,
      client_code: client.client_code ?? '',
      client_code_2: client.client_code_2 ?? '',
      name: client.name ?? '',
      name_2: client.name_2 ?? '',
      address: client.address ?? '',
      network_name: client.network_name ?? '',
      is_active: client.is_active,
    });
    setFormError('');
  }

  async function saveClient() {
    setFormError('');
    try {
      const payload = {
        client_code: form.client_code,
        client_code_2: form.client_code_2,
        name: form.name,
        name_2: form.name_2,
        address: form.address,
        network_name: form.network_name,
        is_active: form.is_active,
      };
      if (form.id) {
        await api.patch(`/clients/${form.id}`, payload);
      } else {
        await api.post('/clients', payload);
      }
      setForm(emptyClientForm);
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
      </div>
      <div className="flex flex-wrap gap-3">
        <input className="input w-full md:w-96" placeholder="Поиск по коду, названию или адресу" value={search} onChange={(event) => updateSearch(event.target.value)} />
      </div>
      <section className="panel space-y-4">
        <div className="grid gap-3 md:grid-cols-3">
          <input className="input" placeholder="Код" value={form.client_code} onChange={(event) => setForm((prev) => ({ ...prev, client_code: event.target.value }))} />
          <input className="input" placeholder="Код 2" value={form.client_code_2} onChange={(event) => setForm((prev) => ({ ...prev, client_code_2: event.target.value }))} />
          <input className="input" placeholder="Сеть" value={form.network_name} onChange={(event) => setForm((prev) => ({ ...prev, network_name: event.target.value }))} />
          <input className="input" placeholder="Название 1" value={form.name} onChange={(event) => setForm((prev) => ({ ...prev, name: event.target.value }))} />
          <input className="input" placeholder="Название 2" value={form.name_2} onChange={(event) => setForm((prev) => ({ ...prev, name_2: event.target.value }))} />
          <input className="input" placeholder="Адрес" value={form.address} onChange={(event) => setForm((prev) => ({ ...prev, address: event.target.value }))} />
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <label className="flex items-center gap-2 text-sm text-slate-300">
            <input type="checkbox" checked={form.is_active} onChange={(event) => setForm((prev) => ({ ...prev, is_active: event.target.checked }))} />
            Активен
          </label>
          <button type="button" className="button" disabled={!form.client_code.trim() || !form.name.trim()} onClick={saveClient}>
            {form.id ? 'Сохранить клиента' : 'Добавить клиента'}
          </button>
          {form.id && <button type="button" className="button-secondary" onClick={() => setForm(emptyClientForm)}>Отмена</button>}
          {formError && <span className="text-sm text-red-400">{formError}</span>}
        </div>
      </section>
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
                <th>ID</th>
                <th>Код</th>
                <th>Название 1</th>
                <th>Название 2</th>
                <th>Адрес</th>
                <th>Сеть</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {clients.map((client: any) => (
                <tr key={client.id}>
                  <td>{client.id}</td>
                  <td>{client.client_code}</td>
                  <td>{client.name}</td>
                  <td>{client.name_2}</td>
                  <td>{client.address}</td>
                  <td>{client.network_name}</td>
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
    </main>
  );
}
