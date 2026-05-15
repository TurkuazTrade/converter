import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '../api/client';

export function ClientsPage() {
  const [search, setSearch] = useState('');
  const { data, isLoading } = useQuery({
    queryKey: ['clients', search],
    queryFn: async () => (await api.get('/clients', { params: { search } })).data,
  });

  return (
    <main className="page space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">Клиенты</h1>
          <p className="mt-1 text-sm text-slate-400">Справочник клиентов для определения получателя заказа.</p>
        </div>
      </div>
      <div className="flex flex-wrap gap-3">
        <input className="input w-full md:w-96" placeholder="Поиск по коду, названию или адресу" value={search} onChange={(event) => setSearch(event.target.value)} />
      </div>
      <section className="panel overflow-auto p-0">
        {isLoading ? (
          <p className="p-5 text-slate-400">Загрузка...</p>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Код</th>
                <th>Название</th>
                <th>Адрес</th>
                <th>Сеть</th>
              </tr>
            </thead>
            <tbody>
              {(data ?? []).map((client: any) => (
                <tr key={client.id}>
                  <td>{client.id}</td>
                  <td>{client.client_code}</td>
                  <td>{client.name}</td>
                  <td>{client.address}</td>
                  <td>{client.network_name}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </main>
  );
}
