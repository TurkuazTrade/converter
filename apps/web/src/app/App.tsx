import { useEffect, useState, type KeyboardEvent } from 'react';
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

type SidebarIconName =
  | 'archive'
  | 'book'
  | 'box'
  | 'chevron'
  | 'database'
  | 'file'
  | 'history'
  | 'menu'
  | 'moon'
  | 'payment'
  | 'platform'
  | 'report'
  | 'sun'
  | 'upload'
  | 'users';

type AccessClaims = {
  permissions?: unknown;
  branch_permissions?: unknown;
};

type PlatformLink = {
  href: string;
  label: string;
  icon: SidebarIconName;
  permissions: string[];
};

const platformLinks: PlatformLink[] = [
  {
    href: 'http://localhost:5174',
    label: 'Platform',
    icon: 'platform',
    permissions: ['platform.dashboard.read'],
  },
  {
    href: 'http://localhost:5177',
    label: 'Users',
    icon: 'users',
    permissions: ['identity.users.read', 'identity.users.manage'],
  },
  {
    href: 'http://localhost:6750',
    label: 'Payments',
    icon: 'payment',
    permissions: ['payments.transactions.read', 'payments.qr.create', 'payments.branches.read'],
  },
  {
    href: 'http://localhost:8000/docs',
    label: 'Swagger',
    icon: 'file',
    permissions: ['converter.orders.read'],
  },
];

function Layout() {
  const [theme, setTheme] = useState<'dark' | 'light'>(() => {
    const saved = localStorage.getItem('theme');
    if (saved === 'dark' || saved === 'light') return saved;
    return window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  });
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => localStorage.getItem('sidebarCollapsed') === 'true');

  useEffect(() => {
    const root = document.documentElement;
    root.classList.toggle('theme-light', theme === 'light');
    root.classList.toggle('theme-dark', theme === 'dark');
    root.style.colorScheme = theme;
    localStorage.setItem('theme', theme);
  }, [theme]);

  useEffect(() => {
    localStorage.setItem('sidebarCollapsed', String(sidebarCollapsed));
  }, [sidebarCollapsed]);

  const accessToken = localStorage.getItem('access_token');
  const claims = decodeAccessClaims(accessToken);
  const visiblePlatformLinks = platformLinks.filter((link) =>
    link.permissions.some((permission) => hasPermission(claims, permission)),
  );

  if (!accessToken) {
    return <Navigate to="/login" replace />;
  }

  function logout() {
    localStorage.removeItem('access_token');
    window.location.href = '/login';
  }

  function toggleSidebar() {
    setSidebarCollapsed((value) => !value);
  }

  function toggleTheme() {
    setTheme((value) => (value === 'dark' ? 'light' : 'dark'));
  }

  function activateOnKey(event: KeyboardEvent<HTMLButtonElement>, action: () => void) {
    if (event.key !== 'Enter' && event.key !== ' ') return;
    event.preventDefault();
    action();
  }

  const navClass = ({ isActive }: { isActive: boolean }) =>
    isActive ? 'sidebar-link sidebar-link-active' : 'sidebar-link';

  return (
    <div className={sidebarCollapsed ? 'app-shell sidebar-collapsed' : 'app-shell'}>
      <header className="app-header">
        <div className="flex min-w-0 items-center gap-4">
          <Link to="/upload" className="brand-lockup">
            <span className="brand-mark" aria-hidden="true">C</span>
            <span className="brand-copy">
              <span className="brand-title">Turkuaz Converter</span>
              <span className="brand-subtitle">Order converter</span>
            </span>
          </Link>
        </div>
        <div className="flex items-center gap-3">
          <span className="environment-pill hidden sm:inline-flex">
            Тест
          </span>
          <button className="header-action" onClick={logout}>Выйти</button>
        </div>
      </header>

      <div className="app-body">
        <aside className="app-sidebar">
          <div className="sidebar-section">
            <details open>
              <summary className="sidebar-summary">
                <span className="sidebar-item-mark" aria-hidden="true"><SidebarIcon name="archive" /></span>
                <span className="sidebar-item-label">Конвертер</span>
                <span className="sidebar-chevron" aria-hidden="true"><SidebarIcon name="chevron" size={14} /></span>
              </summary>
              <nav className="mt-2 space-y-1">
                <NavLink to="/upload" className={navClass}>
                  <span className="sidebar-item-mark" aria-hidden="true"><SidebarIcon name="upload" /></span>
                  <span className="sidebar-item-label">Конвертер</span>
                </NavLink>
                <NavLink to="/orders" className={navClass}>
                  <span className="sidebar-item-mark" aria-hidden="true"><SidebarIcon name="history" /></span>
                  <span className="sidebar-item-label">История конвертера</span>
                </NavLink>
              </nav>
            </details>
          </div>

          <div className="sidebar-section">
            <details open>
              <summary className="sidebar-summary">
                <span className="sidebar-item-mark" aria-hidden="true"><SidebarIcon name="book" /></span>
                <span className="sidebar-item-label">Справочники</span>
                <span className="sidebar-chevron" aria-hidden="true"><SidebarIcon name="chevron" size={14} /></span>
              </summary>
              <nav className="mt-2 space-y-1">
                <NavLink to="/product-dictionaries" className={navClass}>
                  <span className="sidebar-item-mark" aria-hidden="true"><SidebarIcon name="database" /></span>
                  <span className="sidebar-item-label">Бренды и типы</span>
                </NavLink>
                <NavLink to="/products" className={navClass}>
                  <span className="sidebar-item-mark" aria-hidden="true"><SidebarIcon name="box" /></span>
                  <span className="sidebar-item-label">Товары</span>
                </NavLink>
                <NavLink to="/clients" className={navClass}>
                  <span className="sidebar-item-mark" aria-hidden="true"><SidebarIcon name="users" /></span>
                  <span className="sidebar-item-label">Клиенты</span>
                </NavLink>
              </nav>
            </details>
          </div>

          <div className="sidebar-section">
            <details>
              <summary className="sidebar-summary">
                <span className="sidebar-item-mark" aria-hidden="true"><SidebarIcon name="report" /></span>
                <span className="sidebar-item-label">Отчеты</span>
                <span className="sidebar-chevron" aria-hidden="true"><SidebarIcon name="chevron" size={14} /></span>
              </summary>
              <nav className="mt-2 space-y-1">
                <NavLink to="/reports/panorama" className={navClass}>
                  <span className="sidebar-item-mark" aria-hidden="true"><SidebarIcon name="report" /></span>
                  <span className="sidebar-item-label">Отчеты Panorama</span>
                </NavLink>
                <NavLink to="/reports/tiger" className={navClass}>
                  <span className="sidebar-item-mark" aria-hidden="true"><SidebarIcon name="report" /></span>
                  <span className="sidebar-item-label">Отчеты Tiger</span>
                </NavLink>
                <NavLink to="/reports/ocean" className={navClass}>
                  <span className="sidebar-item-mark" aria-hidden="true"><SidebarIcon name="report" /></span>
                  <span className="sidebar-item-label">Отчеты Ocean/WMS</span>
                </NavLink>
              </nav>
            </details>
          </div>

          {visiblePlatformLinks.length > 0 && (
            <div className="sidebar-platform-links" aria-label="Платформы">
              {visiblePlatformLinks.map((link) => (
                <a href={link.href} key={link.href} title={link.label}>
                  <span className="sidebar-item-mark" aria-hidden="true"><SidebarIcon name={link.icon} /></span>
                  <span className="sidebar-item-label">{link.label}</span>
                </a>
              ))}
            </div>
          )}

          <div className="sidebar-controls" aria-label="Настройки интерфейса">
            <button
              aria-label={sidebarCollapsed ? 'Развернуть меню' : 'Свернуть меню'}
              className="sidebar-control"
              type="button"
              title={sidebarCollapsed ? 'Показать меню' : 'Скрыть меню'}
              onKeyDown={(event) => activateOnKey(event, toggleSidebar)}
              onMouseDown={(event) => {
                event.preventDefault();
                toggleSidebar();
              }}
            >
              <span className="sidebar-item-mark" aria-hidden="true">
                <SidebarIcon name="menu" />
              </span>
              <span className="sidebar-item-label">{sidebarCollapsed ? 'Развернуть' : 'Свернуть'}</span>
            </button>
            <button
              aria-label={theme === 'dark' ? 'Включить светлую тему' : 'Включить темную тему'}
              className="sidebar-control"
              type="button"
              title={theme === 'dark' ? 'Светлая тема' : 'Темная тема'}
              onKeyDown={(event) => activateOnKey(event, toggleTheme)}
              onMouseDown={(event) => {
                event.preventDefault();
                toggleTheme();
              }}
            >
              <span className="sidebar-item-mark" aria-hidden="true">
                <SidebarIcon name={theme === 'dark' ? 'sun' : 'moon'} />
              </span>
              <span className="sidebar-item-label">{theme === 'dark' ? 'Светлая' : 'Темная'}</span>
            </button>
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
            <span className="font-medium">Turkuaz Converter</span>
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

function decodeAccessClaims(token: string | null): AccessClaims {
  if (!token) return {};
  const [, payload] = token.split('.');
  if (!payload) return {};
  try {
    const normalized = payload.replace(/-/g, '+').replace(/_/g, '/');
    const padded = normalized.padEnd(Math.ceil(normalized.length / 4) * 4, '=');
    return JSON.parse(window.atob(padded)) as AccessClaims;
  } catch {
    return {};
  }
}

function hasPermission(claims: AccessClaims, permission: string): boolean {
  if (Array.isArray(claims.permissions) && claims.permissions.includes(permission)) {
    return true;
  }
  if (!claims.branch_permissions || typeof claims.branch_permissions !== 'object') {
    return false;
  }
  return Object.values(claims.branch_permissions).some((values) => (
    Array.isArray(values) && values.includes(permission)
  ));
}

function SidebarIcon({ name, size = 17 }: { name: SidebarIconName; size?: number }) {
  const common = {
    fill: 'none',
    stroke: 'currentColor',
    strokeLinecap: 'round' as const,
    strokeLinejoin: 'round' as const,
    strokeWidth: 2,
  };

  return (
    <svg aria-hidden="true" width={size} height={size} viewBox="0 0 24 24" {...common}>
      {iconPath(name)}
    </svg>
  );
}

function iconPath(name: SidebarIconName) {
  switch (name) {
    case 'archive':
      return (
        <>
          <path d="M4 7h16" />
          <path d="M5 7l1 13h12l1-13" />
          <path d="M9 11h6" />
          <path d="M8 3h8l2 4H6l2-4Z" />
        </>
      );
    case 'book':
      return (
        <>
          <path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H20v16H6.5A2.5 2.5 0 0 0 4 21.5v-16Z" />
          <path d="M8 7h8M8 11h6" />
        </>
      );
    case 'box':
      return (
        <>
          <path d="M21 8.5 12 3 3 8.5l9 5.5 9-5.5Z" />
          <path d="M3 8.5V16l9 5 9-5V8.5" />
          <path d="M12 14v7" />
        </>
      );
    case 'chevron':
      return <path d="m8 10 4 4 4-4" />;
    case 'database':
      return (
        <>
          <ellipse cx="12" cy="5" rx="8" ry="3" />
          <path d="M4 5v6c0 1.7 3.6 3 8 3s8-1.3 8-3V5" />
          <path d="M4 11v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6" />
        </>
      );
    case 'file':
      return (
        <>
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z" />
          <path d="M14 2v6h6" />
          <path d="M8 13h8M8 17h5" />
        </>
      );
    case 'history':
      return (
        <>
          <path d="M3 12a9 9 0 1 0 3-6.7" />
          <path d="M3 4v5h5" />
          <path d="M12 7v5l3 2" />
        </>
      );
    case 'menu':
      return (
        <>
          <path d="M4 7h16" />
          <path d="M4 12h16" />
          <path d="M4 17h16" />
        </>
      );
    case 'moon':
      return <path d="M20.5 15.2A8.5 8.5 0 0 1 8.8 3.5 7 7 0 1 0 20.5 15.2Z" />;
    case 'payment':
      return (
        <>
          <rect x="3" y="6" width="18" height="12" rx="2" />
          <circle cx="12" cy="12" r="2.5" />
          <path d="M6 9h1M17 15h1" />
        </>
      );
    case 'platform':
      return (
        <>
          <rect x="3" y="3" width="7" height="8" rx="1" />
          <rect x="14" y="3" width="7" height="5" rx="1" />
          <rect x="14" y="12" width="7" height="9" rx="1" />
          <rect x="3" y="15" width="7" height="6" rx="1" />
        </>
      );
    case 'report':
      return (
        <>
          <path d="M4 19V5a2 2 0 0 1 2-2h9l5 5v11a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2Z" />
          <path d="M14 3v6h6" />
          <path d="M8 16v-4M12 16V9M16 16v-2" />
        </>
      );
    case 'sun':
      return (
        <>
          <circle cx="12" cy="12" r="4" />
          <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
        </>
      );
    case 'upload':
      return (
        <>
          <path d="M12 16V4" />
          <path d="m7 9 5-5 5 5" />
          <path d="M5 20h14" />
        </>
      );
    case 'users':
      return (
        <>
          <path d="M16 21v-2a4 4 0 0 0-4-4H7a4 4 0 0 0-4 4v2" />
          <circle cx="9.5" cy="7" r="4" />
          <path d="M17 11a3 3 0 0 0 0-6" />
          <path d="M21 21v-2a4 4 0 0 0-3-3.8" />
        </>
      );
  }
}
