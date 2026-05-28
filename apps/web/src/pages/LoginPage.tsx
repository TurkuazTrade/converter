import { FormEvent, useState } from 'react';
import { useNavigate } from 'react-router-dom';

const identityApiUrl = import.meta.env.VITE_IDENTITY_API_URL || 'http://localhost:8020/api/v1';

export function LoginPage() {
  const navigate = useNavigate();
  const [email, setEmail] = useState('user');
  const [password, setPassword] = useState('password');
  const [error, setError] = useState('');

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError('');
    try {
      const response = await fetch(`${identityApiUrl}/auth/login`, {
        method: 'POST',
        headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      });
      const data = await response.json().catch(() => null);
      if (!response.ok) {
        throw new Error(data?.detail || `HTTP ${response.status}`);
      }
      localStorage.setItem('access_token', data.access_token);
      navigate('/upload');
    } catch {
      setError('Не удалось войти. Проверьте логин и пароль.');
    }
  }

  return (
    <main className="page flex min-h-screen items-center justify-center">
      <form onSubmit={submit} className="panel w-full max-w-md space-y-4">
        <div>
          <h1 className="text-xl font-semibold">Вход в Turkuaz Converter</h1>
          <p className="mt-1 text-sm text-slate-400">Вход через единый модуль пользователей.</p>
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
