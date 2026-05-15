import { FormEvent, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/client';

export function LoginPage() {
  const navigate = useNavigate();
  const [email, setEmail] = useState('user');
  const [password, setPassword] = useState('password');
  const [error, setError] = useState('');

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError('');
    try {
      const response = await api.post('/auth/login', { email, password });
      localStorage.setItem('access_token', response.data.access_token);
      navigate('/upload');
    } catch {
      setError('Не удалось войти. Проверьте логин и пароль.');
    }
  }

  return (
    <main className="page flex min-h-screen items-center justify-center">
      <form onSubmit={submit} className="panel w-full max-w-md space-y-4">
        <div>
          <h1 className="text-xl font-semibold">Вход в Turkuaz CRM</h1>
          <p className="mt-1 text-sm text-slate-400">Введите тестовый логин и пароль.</p>
        </div>
        <label className="block space-y-2">
          <span className="text-sm text-slate-400">Email или логин</span>
          <input className="input w-full" value={email} onChange={(e) => setEmail(e.target.value)} />
        </label>
        <label className="block space-y-2">
          <span className="text-sm text-slate-400">Пароль</span>
          <input className="input w-full" type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
        </label>
        {error && <p className="text-sm text-red-400">{error}</p>}
        <button className="button w-full">Войти</button>
      </form>
    </main>
  );
}
