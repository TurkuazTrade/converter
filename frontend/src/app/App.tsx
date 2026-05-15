import { Link, Navigate, NavLink, Route, Routes } from 'react-router-dom';
import { ClientsPage } from '../pages/ClientsPage';
import { LoginPage } from '../pages/LoginPage';
import { OrderPreviewPage } from '../pages/OrderPreviewPage';
import { OrdersHistoryPage } from '../pages/OrdersHistoryPage';
import { ProductsPage } from '../pages/ProductsPage';
import { ReferenceImportPage } from '../pages/ReferenceImportPage';
import { ReportsPlaceholderPage } from '../pages/ReportsPlaceholderPage';
import { UnresolvedItemsPage } from '../pages/UnresolvedItemsPage';
import { UploadOrderPage } from '../pages/UploadOrderPage';

function Layout() {
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
          <Link to="/upload" className="brand-lockup">
            <span className="min-w-0">
              <span className="block truncate text-sm font-semibold text-white">Turkuaz CRM</span>
              <span className="block truncate text-xs text-slate-400">Order operations</span>
            </span>
          </Link>
        </div>
        <div className="flex items-center gap-3">
          <span className="hidden rounded-full border border-emerald-800 bg-emerald-950/40 px-3 py-1 text-xs text-emerald-200 sm:inline-flex">
            Testing
          </span>
          <button className="header-action" onClick={logout}>Выйти</button>
        </div>
      </header>

      <div className="app-body">
        <aside className="app-sidebar">
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
                <NavLink to="/products" className={navClass}>Товары</NavLink>
                <NavLink to="/clients" className={navClass}>Клиенты</NavLink>
                <NavLink to="/references" className={navClass}>Импорт</NavLink>
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

          <div className="mt-auto rounded-md border border-slate-800 bg-slate-950 px-3 py-3 text-xs text-slate-400">
            <div className="font-medium text-slate-300">Workspace</div>
            <div className="mt-1">Local testing</div>
          </div>
        </aside>

        <div className="app-main">
          <Routes>
            <Route path="/" element={<Navigate to="/upload" replace />} />
            <Route path="/upload" element={<UploadOrderPage />} />
            <Route path="/references" element={<ReferenceImportPage />} />
            <Route path="/orders" element={<OrdersHistoryPage />} />
            <Route path="/orders/:orderId/preview" element={<OrderPreviewPage />} />
            <Route path="/orders/:orderId/unresolved" element={<UnresolvedItemsPage />} />
            <Route path="/products" element={<ProductsPage />} />
            <Route path="/clients" element={<ClientsPage />} />
            <Route path="/reports/:reportType" element={<ReportsPlaceholderPage />} />
          </Routes>
          <footer className="app-footer">
            <span>Turkuaz CRM</span>
            <span>Converter module</span>
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
