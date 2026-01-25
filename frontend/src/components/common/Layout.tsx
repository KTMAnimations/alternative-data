import { Link, useLocation } from 'react-router-dom';
import { useState } from 'react';
import {
  Database,
  TrendingUp,
  Bell,
  Map,
  FlaskConical,
  Settings,
  Users,
  Menu,
  X,
  ChevronDown,
  BarChart3,
  Globe,
  Zap,
  FileText,
} from 'lucide-react';
import clsx from 'clsx';

interface LayoutProps {
  children: React.ReactNode;
}

const navigation = [
  {
    name: 'Data Catalog',
    href: '/catalog',
    icon: Database,
    children: [
      { name: 'Browse Sources', href: '/catalog' },
      { name: 'AI Search', href: '/catalog/search' },
    ],
  },
  {
    name: 'Factor Analysis',
    href: '/factors',
    icon: TrendingUp,
    children: [
      { name: 'Factor Graph', href: '/factors/graph' },
      { name: 'Compare Factors', href: '/factors/compare' },
      { name: 'Blend Factors', href: '/factors/blend' },
    ],
  },
  {
    name: 'Alerts',
    href: '/alerts',
    icon: Bell,
    children: [
      { name: 'My Alerts', href: '/alerts' },
      { name: 'Create Alert', href: '/alerts/create' },
      { name: 'Alert History', href: '/alerts/history' },
    ],
  },
  {
    name: 'Geographic',
    href: '/geo',
    icon: Map,
    children: [
      { name: 'Earthquake Map', href: '/geo/earthquakes' },
      { name: 'Power Grid', href: '/geo/power-grid' },
      { name: 'Regional Thresholds', href: '/geo/thresholds' },
    ],
  },
  {
    name: 'Backtesting',
    href: '/backtest',
    icon: FlaskConical,
    children: [
      { name: 'Run Backtest', href: '/backtest' },
      { name: 'Decay Analysis', href: '/backtest/decay' },
      { name: 'Seasonality', href: '/backtest/seasonality' },
      { name: 'Experiments', href: '/backtest/experiments' },
    ],
  },
  {
    name: 'Admin',
    href: '/admin',
    icon: Settings,
    children: [
      { name: 'Entity Mappings', href: '/admin/mappings' },
      { name: 'Collector Health', href: '/admin/health' },
      { name: 'Data Requests', href: '/admin/requests' },
    ],
  },
  {
    name: 'Account',
    href: '/account',
    icon: Users,
    children: [
      { name: 'Usage', href: '/account/usage' },
      { name: 'API Keys', href: '/account/api-keys' },
      { name: 'Upgrade', href: '/account/upgrade' },
    ],
  },
];

export function Layout({ children }: LayoutProps) {
  const location = useLocation();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [expandedItem, setExpandedItem] = useState<string | null>(null);

  const isActive = (href: string) => location.pathname.startsWith(href);

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Mobile sidebar backdrop */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-40 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={clsx(
          'fixed inset-y-0 left-0 z-50 w-64 bg-white border-r border-gray-200 transform transition-transform duration-200 lg:translate-x-0',
          sidebarOpen ? 'translate-x-0' : '-translate-x-full'
        )}
      >
        <div className="flex items-center justify-between h-16 px-4 border-b border-gray-200">
          <Link to="/" className="flex items-center gap-2">
            <BarChart3 className="h-8 w-8 text-primary-600" />
            <span className="text-lg font-semibold text-gray-900">AltData</span>
          </Link>
          <button
            className="lg:hidden p-2 text-gray-500 hover:text-gray-700"
            onClick={() => setSidebarOpen(false)}
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <nav className="p-4 space-y-1 overflow-y-auto h-[calc(100vh-4rem)]">
          {navigation.map((item) => (
            <div key={item.name}>
              <button
                onClick={() =>
                  setExpandedItem(expandedItem === item.name ? null : item.name)
                }
                className={clsx(
                  'w-full flex items-center justify-between px-3 py-2 text-sm font-medium rounded-md transition-colors',
                  isActive(item.href)
                    ? 'bg-primary-50 text-primary-700'
                    : 'text-gray-700 hover:bg-gray-100'
                )}
              >
                <div className="flex items-center gap-3">
                  <item.icon className="h-5 w-5" />
                  {item.name}
                </div>
                {item.children && (
                  <ChevronDown
                    className={clsx(
                      'h-4 w-4 transition-transform',
                      expandedItem === item.name && 'rotate-180'
                    )}
                  />
                )}
              </button>

              {item.children && expandedItem === item.name && (
                <div className="mt-1 ml-8 space-y-1">
                  {item.children.map((child) => (
                    <Link
                      key={child.href}
                      to={child.href}
                      className={clsx(
                        'block px-3 py-2 text-sm rounded-md transition-colors',
                        location.pathname === child.href
                          ? 'bg-primary-100 text-primary-700 font-medium'
                          : 'text-gray-600 hover:bg-gray-100'
                      )}
                    >
                      {child.name}
                    </Link>
                  ))}
                </div>
              )}
            </div>
          ))}
        </nav>
      </aside>

      {/* Main content */}
      <div className="lg:pl-64">
        {/* Top bar */}
        <header className="sticky top-0 z-30 flex items-center h-16 px-4 bg-white border-b border-gray-200">
          <button
            className="lg:hidden p-2 text-gray-500 hover:text-gray-700"
            onClick={() => setSidebarOpen(true)}
          >
            <Menu className="h-5 w-5" />
          </button>

          <div className="flex-1 flex items-center justify-end gap-4">
            <div className="flex items-center gap-2 text-sm text-gray-500">
              <Globe className="h-4 w-4" />
              <span>API Status:</span>
              <span className="flex items-center gap-1 text-success-500">
                <Zap className="h-3 w-3" />
                Operational
              </span>
            </div>

            <Link
              to="/docs"
              className="flex items-center gap-1 text-sm text-gray-600 hover:text-gray-900"
            >
              <FileText className="h-4 w-4" />
              Docs
            </Link>
          </div>
        </header>

        {/* Page content */}
        <main className="p-6">{children}</main>
      </div>
    </div>
  );
}
