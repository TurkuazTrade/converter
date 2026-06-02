import { useEffect, useState } from 'react';
import { Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom';
import { AppShell } from '@turkuaz/ui';
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

const IDENTITY_API_BASE_URL = import.meta.env.VITE_IDENTITY_API_BASE_URL || '/identity-api';

type ServiceRegistryItem = {
  code: string;
  name: string;
  base_url: string | null;
  is_active?: boolean;
};

type ServiceLink = {
  code?: string;
  href: string;
  label: string;
  icon: 'banknote' | 'building' | 'database' | 'file' | 'users';
  permissions?: string[];
};

const defaultServiceLinks: ServiceLink[] = [
  {
    code: 'identity',
    href: 'http://localhost:7500',
    label: 'Identity',
    icon: 'users',
    permissions: ['identity.users.read', 'identity.users.manage'],
  },
  {
    code: 'payments',
    href: 'http://localhost:7502',
    label: 'Payments',
    icon: 'banknote',
    permissions: ['payments.transactions.read', 'payments.qr.create'],
  },
  {
    code: 'market_parser',
    href: 'http://localhost:7503',
    label: 'Market Parser',
    icon: 'database',
    permissions: ['market_parser.products.read', 'market_parser.runs.read'],
  },
];

const servicePermissions: Record<string, string[]> = {
  identity: ['identity.users.read', 'identity.users.manage'],
  payments: ['payments.transactions.read', 'payments.qr.create'],
  market_parser: ['market_parser.products.read', 'market_parser.runs.read'],
};

async function fetchServiceRegistry(): Promise<ServiceRegistryItem[]> {
  const token = localStorage.getItem('identity_access_token') || localStorage.getItem('access_token');
  const response = await fetch(`${IDENTITY_API_BASE_URL}/services/my`, {
    headers: {
      Accept: 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    throw new Error(data?.detail || data?.message || `HTTP ${response.status}`);
  }
  return data as ServiceRegistryItem[];
}

function serviceLinksFromRegistry(services: ServiceRegistryItem[], currentServiceCode: string): ServiceLink[] {
  if (services.length === 0) return defaultServiceLinks;
  return services
    .filter((service) => (
      service.is_active !== false &&
      service.code !== currentServiceCode &&
      Boolean(service.base_url)
    ))
    .map((service) => ({
      code: service.code,
      href: service.base_url || '',
      label: service.name,
      icon: iconForServiceCode(service.code),
      permissions: servicePermissions[service.code] || [`${service.code}.*`],
    }));
}

function iconForServiceCode(code: string): ServiceLink['icon'] {
  if (code.includes('pay') || code.includes('cash') || code.includes('billing')) return 'banknote';
  if (code.includes('user') || code.includes('identity') || code.includes('staff')) return 'users';
  if (code.includes('branch') || code.includes('warehouse') || code.includes('office')) return 'building';
  if (code.includes('doc') || code.includes('file') || code.includes('report')) return 'file';
  return 'database';
}

function Layout() {
  const navigate = useNavigate();
  const location = useLocation();
  const accessToken = localStorage.getItem('access_token');
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

  function logout() {
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
  const serviceLinks = serviceLinksFromRegistry(registeredServices, 'converter');

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
        { href: 'http://localhost:8501/docs', label: 'Swagger', icon: 'file', permissions: ['converter.orders.read'] },
      ]}
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
      footerLinks={[{ href: 'http://localhost:8501/docs', label: 'Swagger' }]}
      tokenStorageKeys={['access_token']}
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
