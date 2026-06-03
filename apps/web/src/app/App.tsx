import { useEffect, useState } from 'react';
import { Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom';
import { AppShell, fetchServiceRegistry, serviceLinksFromRegistry } from '@turkuaz/ui';
import type { ServiceRegistryItem } from '@turkuaz/ui';
import { ClientsPage } from '../pages/ClientsPage';
import { LoginPage } from '../pages/LoginPage';
import { OrderPreviewPage } from '../pages/OrderPreviewPage';
import { OrdersHistoryPage } from '../pages/OrdersHistoryPage';
import { ProductDictionariesPage } from '../pages/ProductDictionariesPage';
import { ProductsPage } from '../pages/ProductsPage';
import { UnresolvedItemsPage } from '../pages/UnresolvedItemsPage';
import { UploadOrderPage } from '../pages/UploadOrderPage';

const routeMeta = [
  {
    path: '/upload',
    key: 'upload',
    label: 'Конвертер',
    icon: 'file' as const,
    permissions: ['converter.orders.read'],
    title: 'Конвертер заказов',
    description: 'Загрузка и нормализация заказов для дальнейшей обработки.',
  },
  {
    path: '/orders',
    key: 'orders',
    label: 'История',
    icon: 'database' as const,
    permissions: ['converter.orders.read'],
    title: 'История конвертера',
    description: 'Ранее загруженные заказы, статусы и результаты обработки.',
  },
  {
    path: '/product-dictionaries',
    key: 'dictionaries',
    label: 'Бренды и типы',
    icon: 'sliders' as const,
    permissions: ['converter.references.read'],
    title: 'Справочники',
    description: 'Бренды, типы и правила сопоставления товарных данных.',
  },
  {
    path: '/products',
    key: 'products',
    label: 'Товары',
    icon: 'database' as const,
    permissions: ['converter.products.read'],
    title: 'Товары',
    description: 'Каталог товаров и нормализованные товарные позиции.',
  },
  {
    path: '/clients',
    key: 'clients',
    label: 'Клиенты',
    icon: 'users' as const,
    permissions: ['converter.clients.read'],
    title: 'Клиенты',
    description: 'Клиентские справочники и сопоставления для заказов.',
  },
];

type AccessClaims = {
  permissions?: string[];
  branch_permissions?: Record<string, string[]>;
  branch_permissions_by_id?: Record<string, string[]>;
};

const converterPermissions = [
  'converter.orders.read',
  'converter.references.read',
  'converter.products.read',
  'converter.clients.read',
];
const API_DOCS_URL = backendUrl(8501, '/docs');

function readShellClaims(token: string): AccessClaims {
  const claims = decodeTokenClaims(token);
  if (hasAnyPermission(claims)) return claims;
  return { ...claims, permissions: converterPermissions };
}

function decodeTokenClaims(token: string): AccessClaims {
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

function hasAnyPermission(claims: AccessClaims): boolean {
  if (Array.isArray(claims.permissions) && claims.permissions.length > 0) return true;
  const branchPermissions = Object.values(claims.branch_permissions ?? {});
  if (branchPermissions.some((items) => items.length > 0)) return true;
  const branchPermissionsById = Object.values(claims.branch_permissions_by_id ?? {});
  return branchPermissionsById.some((items) => items.length > 0);
}

function Layout() {
  const navigate = useNavigate();
  const location = useLocation();
  const accessToken = localStorage.getItem('identity_access_token') || localStorage.getItem('access_token');
  const [registeredServices, setRegisteredServices] = useState<ServiceRegistryItem[]>([]);

  useEffect(() => {
    if (!accessToken) {
      setRegisteredServices([]);
      return undefined;
    }
    let cancelled = false;
    void fetchServiceRegistry()
      .then((services) => {
        if (!cancelled) setRegisteredServices(services);
      })
      .catch(() => {
        if (!cancelled) setRegisteredServices([]);
      });
    return () => {
      cancelled = true;
    };
  }, [accessToken]);

  if (!accessToken) {
    return <Navigate to="/login" replace />;
  }
  const shellClaims = readShellClaims(accessToken);

  function logout() {
    localStorage.removeItem('identity_access_token');
    localStorage.removeItem('access_token');
    window.location.href = '/login';
  }

  const currentMeta =
    routeMeta.find((item) => (
      location.pathname === item.path ||
      location.pathname.startsWith(`${item.path}/`)
    )) ??
    routeMeta[0];

  const navItems = routeMeta.map((item) => ({
    key: item.key,
    label: item.label,
    icon: item.icon,
    permissions: item.permissions,
    active: currentMeta.key === item.key,
    onClick: () => navigate(item.path),
  }));
  const serviceLinks = serviceLinksFromRegistry(registeredServices, { currentServiceCode: 'converter' });

  return (
    <AppShell
      brand={{
        href: '/upload',
        mark: 'T',
        title: 'Turkuaz Converter',
        subtitle: 'Order converter',
      }}
      navItems={navItems}
      sideLinks={[
        ...serviceLinks,
        { href: API_DOCS_URL, label: 'Swagger', icon: 'file', permissions: ['converter.orders.read'] },
      ]}
      accessClaims={shellClaims}
      serviceName="Converter"
      pageTitle={currentMeta.title}
      pageDescription={currentMeta.description}
      breadcrumbs={[{ label: 'Converter' }, { label: currentMeta.label }]}
      user={{
        name: 'Converter User',
        role: 'Converter',
        actions: [{ key: 'logout', label: 'Выйти', icon: 'logout', onClick: logout }],
      }}
      environment="local"
      version="v0.1.0"
      apiStatus="online"
      footerLinks={[{ href: API_DOCS_URL, label: 'Swagger' }]}
      tokenStorageKeys={['identity_access_token', 'access_token']}
    >
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
        <Route path="/reports/:reportType" element={<Navigate to="/upload" replace />} />
      </Routes>
    </AppShell>
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

function backendUrl(port: number, path = ''): string {
  if (typeof window === 'undefined') return `http://localhost:${port}${path}`;
  return `${window.location.protocol}//${window.location.hostname}:${port}${path}`;
}
