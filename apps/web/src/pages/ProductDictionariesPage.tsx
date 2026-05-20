import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../api/client';

type DictionaryItem = {
  id: number;
  name: string;
  warehouse_no?: string | null;
  is_active: boolean;
  created_at: string;
};

type DictionaryConfig = {
  key: string;
  title: string;
  endpoint: string;
  placeholder: string;
  hasWarehouseNo?: boolean;
};

const dictionaries: DictionaryConfig[] = [
  {
    key: 'brands',
    title: 'Бренды',
    endpoint: '/products/brands',
    placeholder: 'Новый бренд',
  },
  {
    key: 'trade-marks',
    title: 'Торговые марки',
    endpoint: '/products/trade-marks',
    placeholder: 'Новая торговая марка',
  },
  {
    key: 'catalog-types',
    title: 'Типы товаров',
    endpoint: '/products/catalog-types',
    placeholder: 'Новый тип',
    hasWarehouseNo: true,
  },
];

export function ProductDictionariesPage() {
  const [activeKey, setActiveKey] = useState(dictionaries[0].key);
  const activeDictionary = dictionaries.find((dictionary) => dictionary.key === activeKey) ?? dictionaries[0];

  return (
    <main className="page space-y-4">
      <div>
        <h1 className="text-xl font-semibold">Бренды и типы</h1>
        <p className="mt-1 text-sm text-slate-400">Справочники для карточек товаров, импорта и фильтров.</p>
      </div>
      <div className="compact-panel flex flex-wrap gap-2" role="tablist" aria-label="Справочники товаров">
        {dictionaries.map((dictionary) => (
          <button
            key={dictionary.key}
            type="button"
            role="tab"
            aria-selected={dictionary.key === activeKey}
            className={dictionary.key === activeKey ? 'button' : 'button-secondary'}
            onClick={() => setActiveKey(dictionary.key)}
          >
            {dictionary.title}
          </button>
        ))}
      </div>
      <DictionaryPanel key={activeDictionary.key} config={activeDictionary} />
    </main>
  );
}

function DictionaryPanel({ config }: { config: DictionaryConfig }) {
  const queryClient = useQueryClient();
  const [newName, setNewName] = useState('');
  const [newWarehouseNo, setNewWarehouseNo] = useState('');
  const [newActive, setNewActive] = useState(true);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editingName, setEditingName] = useState('');
  const [editingWarehouseNo, setEditingWarehouseNo] = useState('');
  const [editingActive, setEditingActive] = useState(true);
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);
  const { data, isLoading } = useQuery<DictionaryItem[]>({
    queryKey: ['product-dictionary', config.key],
    queryFn: async () => (await api.get(config.endpoint)).data,
  });
  const items = data ?? [];

  async function refreshDictionaries() {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['product-dictionary'] }),
      queryClient.invalidateQueries({ queryKey: ['product-filter-options'] }),
      queryClient.invalidateQueries({ queryKey: ['product-types'] }),
      queryClient.invalidateQueries({ queryKey: ['products'] }),
    ]);
  }

  async function createItem() {
    const name = newName.trim();
    if (!name) return;
    setSaving(true);
    setError('');
    try {
      await api.post(config.endpoint, {
        name,
        ...(config.hasWarehouseNo ? { warehouse_no: newWarehouseNo.trim() } : {}),
        is_active: newActive,
      });
      setNewName('');
      setNewWarehouseNo('');
      setNewActive(true);
      await refreshDictionaries();
    } catch (err: any) {
      setError(err.response?.data?.detail ?? 'Не удалось сохранить значение');
    } finally {
      setSaving(false);
    }
  }

  function startEdit(item: DictionaryItem) {
    setEditingId(item.id);
    setEditingName(item.name);
    setEditingWarehouseNo(item.warehouse_no ?? '');
    setEditingActive(item.is_active);
    setError('');
  }

  async function saveEdit() {
    if (!editingId || !editingName.trim()) return;
    setSaving(true);
    setError('');
    try {
      await api.patch(`${config.endpoint}/${editingId}`, {
        name: editingName.trim(),
        ...(config.hasWarehouseNo ? { warehouse_no: editingWarehouseNo.trim() } : {}),
        is_active: editingActive,
      });
      setEditingId(null);
      setEditingName('');
      setEditingWarehouseNo('');
      await refreshDictionaries();
    } catch (err: any) {
      setError(err.response?.data?.detail ?? 'Не удалось обновить значение');
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="panel space-y-4">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-base font-semibold">{config.title}</h2>
        <span className="status-pill">{items.length}</span>
      </div>

      <div className="space-y-3">
        <input
          className="input w-full"
          placeholder={config.placeholder}
          value={newName}
          onChange={(event) => setNewName(event.target.value)}
        />
        {config.hasWarehouseNo && (
          <input
            className="input w-full"
            placeholder="Номер склада"
            value={newWarehouseNo}
            onChange={(event) => setNewWarehouseNo(event.target.value)}
          />
        )}
        <div className="flex flex-wrap items-center gap-3">
          <label className="flex items-center gap-2 text-sm text-slate-300">
            <input
              type="checkbox"
              checked={newActive}
              onChange={(event) => setNewActive(event.target.checked)}
            />
            Активен
          </label>
          <button type="button" className="button" disabled={!newName.trim() || saving} onClick={createItem}>
            Добавить
          </button>
        </div>
      </div>

      {error && <p className="text-sm text-red-400">{error}</p>}

      <div className="overflow-auto">
        {isLoading ? (
          <p className="py-4 text-sm text-slate-400">Загрузка...</p>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>Название</th>
                {config.hasWarehouseNo && <th>Склад</th>}
                <th>Статус</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.id}>
                  <td>
                    {editingId === item.id ? (
                      <input
                        className="input w-56"
                        value={editingName}
                        onChange={(event) => setEditingName(event.target.value)}
                      />
                    ) : (
                      item.name
                    )}
                  </td>
                  {config.hasWarehouseNo && (
                    <td>
                      {editingId === item.id ? (
                        <input
                          className="input w-32"
                          value={editingWarehouseNo}
                          onChange={(event) => setEditingWarehouseNo(event.target.value)}
                        />
                      ) : (
                        item.warehouse_no || <span className="text-slate-500">Не задан</span>
                      )}
                    </td>
                  )}
                  <td>
                    {editingId === item.id ? (
                      <label className="flex items-center gap-2 text-sm text-slate-300">
                        <input
                          type="checkbox"
                          checked={editingActive}
                          onChange={(event) => setEditingActive(event.target.checked)}
                        />
                        Активен
                      </label>
                    ) : (
                      <span className={item.is_active ? 'status-pill-ok' : 'status-pill'}>
                        {item.is_active ? 'Активен' : 'Отключен'}
                      </span>
                    )}
                  </td>
                  <td>
                    {editingId === item.id ? (
                      <div className="flex flex-wrap gap-2">
                        <button type="button" className="button" disabled={!editingName.trim() || saving} onClick={saveEdit}>
                          Сохранить
                        </button>
                        <button
                          type="button"
                          className="button-secondary"
                          onClick={() => {
                            setEditingId(null);
                            setEditingWarehouseNo('');
                          }}
                        >
                          Отмена
                        </button>
                      </div>
                    ) : (
                      <button type="button" className="button-secondary" onClick={() => startEdit(item)}>
                        Редактировать
                      </button>
                    )}
                  </td>
                </tr>
              ))}
              {!items.length && (
                <tr>
                  <td className="text-slate-400" colSpan={config.hasWarehouseNo ? 4 : 3}>Пока пусто</td>
                </tr>
              )}
            </tbody>
          </table>
        )}
      </div>
    </section>
  );
}
