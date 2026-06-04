import axios from 'axios';

const IDENTITY_API_BASE_URL = import.meta.env.VITE_IDENTITY_API_BASE_URL || '/identity-api';
const IDENTITY_API_FALLBACK_BASE_URL =
  import.meta.env.VITE_IDENTITY_API_FALLBACK_BASE_URL || `${localApiUrl(8500)}/api/v1`;
const TOKEN_KEY = 'identity_access_token';
const FALLBACK_TOKEN_KEY = 'access_token';

function apiBaseURL() {
  const configured = import.meta.env.VITE_API_URL;
  if (!configured) return '/api/v1';
  const externalHost = window.location.hostname !== 'localhost' && window.location.hostname !== '127.0.0.1';
  if (externalHost && (configured.includes('localhost') || configured.includes('127.0.0.1'))) {
    return '/api/v1';
  }
  return configured;
}

export const api = axios.create({
  baseURL: apiBaseURL(),
});

api.interceptors.request.use((config) => {
  const token = getToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      clearToken();
      if (window.location.pathname !== '/login') {
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  },
);

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY) || localStorage.getItem(FALLBACK_TOKEN_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(FALLBACK_TOKEN_KEY, token);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(FALLBACK_TOKEN_KEY);
}

export async function loginViaIdentity(email: string, password: string): Promise<void> {
  const data = await requestIdentityJson<{ access_token: string }>('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  });
  setToken(data.access_token);
}

async function requestIdentityJson<T>(path: string, init: RequestInit = {}): Promise<T> {
  const bases = uniqueBaseUrls([IDENTITY_API_BASE_URL, IDENTITY_API_FALLBACK_BASE_URL]);
  let lastError: Error | null = null;

  for (const baseUrl of bases) {
    try {
      return await requestIdentityJsonFromBase<T>(baseUrl, path, init);
    } catch (error) {
      if (!shouldRetryIdentityRequest(error) || baseUrl === bases[bases.length - 1]) {
        throw error;
      }
      lastError = error instanceof Error ? error : new Error(String(error));
    }
  }

  throw lastError ?? new Error('Identity API request failed');
}

async function requestIdentityJsonFromBase<T>(
  baseUrl: string,
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const token = getToken();
  const url = `${baseUrl}${path}`;
  let response: Response;
  try {
    response = await fetch(url, {
      ...init,
      headers: {
        Accept: 'application/json',
        ...(init.body ? { 'Content-Type': 'application/json' } : {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...init.headers,
      },
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    throw new Error(
      `Identity API недоступен по ${url}. Проверьте адрес, порт и CORS. ${message}`,
    );
  }
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    if (response.status === 401) clearToken();
    throw new HttpError(response.status, data?.detail || data?.message || `HTTP ${response.status}`);
  }
  if (!isJsonObject(data)) {
    throw new Error(`Identity returned non-JSON response from ${baseUrl}`);
  }
  return data as T;
}

function uniqueBaseUrls(values: string[]): string[] {
  return values.filter((value, index) => value && values.indexOf(value) === index);
}

function shouldRetryIdentityRequest(error: unknown): boolean {
  return (
    !(error instanceof HttpError) ||
    error.status === 404 ||
    error.status === 405 ||
    error.status >= 500
  );
}

function isJsonObject(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

class HttpError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

function localApiUrl(port: number): string {
  if (typeof window === 'undefined') return `http://localhost:${port}`;
  return `${window.location.protocol}//${window.location.hostname}:${port}`;
}
