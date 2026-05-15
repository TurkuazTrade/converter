import { Link, Navigate, NavLink, Route, Routes } from 'react-router-dom';
import { ClientsPage } from '../pages/ClientsPage';
import { LoginPage } from '../pages/LoginPage';
import { OrderPreviewPage } from '../pages/OrderPreviewPage';
import { OrdersHistoryPage } from '../pages/OrdersHistoryPage';
import { ProductsPage } from '../pages/ProductsPage';
import { ReferenceImportPage } from '../pages/ReferenceImportPage';
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
    isActive ? 'rounded-md bg-slate-800 px-3 py-2 text-white' : 'rounded-md px-3 py-2 text-slate-400 hover:bg-slate-800 hover:text-white';

  return (
    <div>
      <nav className="border-b border-slate-800 bg-slate-900">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-2 px-6 py-3 text-sm">
          <Link to="/upload" className="mr-3 font-semibold text-white">Bishkek CRM</Link>
          <NavLink to="/upload" className={navClass}>Загрузка</NavLink>
          <NavLink to="/references" className={navClass}>Справочники</NavLink>
          <NavLink to="/orders" className={navClass}>История</NavLink>
          <NavLink to="/products" className={navClass}>Товары</NavLink>
          <NavLink to="/clients" className={navClass}>Клиенты</NavLink>
          <button className="ml-auto rounded-md px-3 py-2 text-slate-400 hover:bg-slate-800 hover:text-white" onClick={logout}>Выйти</button>
        </div>
      </nav>
      <Routes>
        <Route path="/" element={<Navigate to="/upload" replace />} />
        <Route path="/upload" element={<UploadOrderPage />} />
        <Route path="/references" element={<ReferenceImportPage />} />
        <Route path="/orders" element={<OrdersHistoryPage />} />
        <Route path="/orders/:orderId/preview" element={<OrderPreviewPage />} />
        <Route path="/orders/:orderId/unresolved" element={<UnresolvedItemsPage />} />
        <Route path="/products" element={<ProductsPage />} />
        <Route path="/clients" element={<ClientsPage />} />
      </Routes>
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
