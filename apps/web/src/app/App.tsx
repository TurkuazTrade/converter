import { useEffect, useState } from 'react';
import { Link, Navigate, NavLink, Route, Routes } from 'react-router-dom';
import { ClientsPage } from '../pages/ClientsPage';
import { LoginPage } from '../pages/LoginPage';
import { OrderPreviewPage } from '../pages/OrderPreviewPage';
import { OrdersHistoryPage } from '../pages/OrdersHistoryPage';
import { ProductDictionariesPage } from '../pages/ProductDictionariesPage';
import { ProductsPage } from '../pages/ProductsPage';
import { ReportsPlaceholderPage } from '../pages/ReportsPlaceholderPage';
import { UnresolvedItemsPage } from '../pages/UnresolvedItemsPage';
import { UploadOrderPage } from '../pages/UploadOrderPage';

function Layout() {
  const [theme, setTheme] = useState<'dark' | 'light'>(() => {
    const saved = localStorage.getItem('theme');
    if (saved === 'dark' || saved === 'light') return saved;
    return window.matchMedia?.('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
  });
  const [sidebarHidden, setSidebarHidden] = useState(() => localStorage.getItem('sidebarHidden') === 'true');

  useEffect(() => {
    const root = document.documentElement;
    root.classList.toggle('theme-light', theme === 'light');
    root.classList.toggle('theme-dark', theme === 'dark');
    root.style.colorScheme = theme;
    localStorage.setItem('theme', theme);
  }, [theme]);

  useEffect(() => {
    localStorage.setItem('sidebarHidden', String(sidebarHidden));
  }, [sidebarHidden]);

  if (!localStorage.getItem('access_token')) {
    return <Navigate to="/login" replace />;
  }

  function logout() {
    localStorage.removeItem('access_token');
    window.location.href = '/login';
  }

  const navClass = ({ isActive }: { isActive: boolean }) =>
    isActive ? 'sidebar-link sidebar-link-active' : 'sidebar-link';

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="flex min-w-0 items-center gap-4">
          <button
            aria-label={sidebarHidden ? 'Показать боковое меню' : 'Скрыть боковое меню'}
            className="sidebar-toggle hidden md:inline-flex"
            title={sidebarHidden ? 'Показать меню' : 'Скрыть меню'}
            type="button"
            onClick={() => setSidebarHidden((value) => !value)}
          >
            <span className="sidebar-toggle-icon" aria-hidden="true">
              <span />
              <span />
              <span />
            </span>
          </button>
          <Link to="/upload" className="brand-lockup">
            <span className="brand-mark" aria-hidden="true">T</span>
            <span className="brand-copy">
              <span className="brand-title">Turkuaz CRM</span>
              <span className="brand-subtitle">Order operations</span>
            </span>
          </Link>
        </div>
        <div className="flex items-center gap-3">
          <span className="environment-pill hidden sm:inline-flex">
            Тест
          </span>
          <button
            aria-label={theme === 'dark' ? 'Включить светлую тему' : 'Включить темную тему'}
            className="theme-toggle"
            title={theme === 'dark' ? 'Светлая тема' : 'Темная тема'}
            type="button"
            onClick={() => setTheme((value) => (value === 'dark' ? 'light' : 'dark'))}
          >
            <span className={theme === 'light' ? 'theme-toggle-icon theme-toggle-icon-active' : 'theme-toggle-icon'} aria-hidden="true">☀</span>
            <span className={theme === 'dark' ? 'theme-toggle-icon theme-toggle-icon-active' : 'theme-toggle-icon'} aria-hidden="true">☾</span>
          </button>
          <button className="header-action" onClick={logout}>Выйти</button>
        </div>
      </header>

      <div className="app-body">
        <aside className={sidebarHidden ? 'app-sidebar app-sidebar-hidden' : 'app-sidebar'}>
          <div className="sidebar-section">
            <details open>
              <summary className="sidebar-summary">Конвертер</summary>
              <nav className="mt-2 space-y-1">
                <NavLink to="/upload" className={navClass}>Конвертер</NavLink>
                <NavLink to="/orders" className={navClass}>История конвертера</NavLink>
              </nav>
            </details>
          </div>

          <div className="sidebar-section">
            <details open>
              <summary className="sidebar-summary">Справочники</summary>
              <nav className="mt-2 space-y-1">
                <NavLink to="/product-dictionaries" className={navClass}>Бренды и типы</NavLink>
                <NavLink to="/products" className={navClass}>Товары</NavLink>
                <NavLink to="/clients" className={navClass}>Клиенты</NavLink>
              </nav>
            </details>
          </div>

          <div className="sidebar-section">
            <details>
              <summary className="sidebar-summary">Отчеты</summary>
              <nav className="mt-2 space-y-1">
                <NavLink to="/reports/panorama" className={navClass}>Отчеты Panorama</NavLink>
                <NavLink to="/reports/tiger" className={navClass}>Отчеты Tiger</NavLink>
                <NavLink to="/reports/ocean" className={navClass}>Отчеты Ocean/WMS</NavLink>
              </nav>
            </details>
          </div>

          <div className="sidebar-status">
            <div>
              <span className="sidebar-status-label">Среда</span>
              <span className="sidebar-status-value">Testing</span>
            </div>
            <span className="sidebar-status-dot" aria-hidden="true" />
          </div>
        </aside>

        <div className="app-main">
          <Routes>
            <Route path="/" element={<Navigate to="/upload" replace />} />
            <Route path="/upload" element={<UploadOrderPage />} />
            <Route path="/references" element={<Navigate to="/products" replace />} />
            <Route path="/orders" element={<OrdersHistoryPage />} />
            <Route path="/orders/:orderId/preview" element={<OrderPreviewPage />} />
            <Route path="/orders/:orderId/unresolved" element={<UnresolvedItemsPage />} />
            <Route path="/products" element={<ProductsPage />} />
            <Route path="/product-dictionaries" element={<ProductDictionariesPage />} />
            <Route path="/clients" element={<ClientsPage />} />
            <Route path="/reports/:reportType" element={<ReportsPlaceholderPage />} />
          </Routes>
          <footer className="app-footer">
            <span className="font-medium">Turkuaz CRM</span>
            <span>Модуль конвертера</span>
            <span>Development build</span>
          </footer>
        </div>
      </div>
    </div>
  );
}

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/*" element={<Layout />} />
    </Routes>
  );
}
