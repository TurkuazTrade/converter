import axios from 'axios';

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
  const token = localStorage.getItem('identity_access_token') || localStorage.getItem('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('identity_access_token');
      localStorage.removeItem('access_token');
      if (window.location.pathname !== '/login') {
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  },
);
