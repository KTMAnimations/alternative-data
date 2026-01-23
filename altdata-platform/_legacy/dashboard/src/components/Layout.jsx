import { Outlet, Link, useLocation } from 'react-router-dom'
import { useHealth } from '../hooks/useSources'

const navigation = [
  { name: 'Dashboard', href: '/' },
  { name: 'Factors', href: '/factors' },
  { name: 'Entities', href: '/entities' },
  { name: 'Sources', href: '/sources' },
  { name: 'Alerts', href: '/alerts' },
  { name: 'Backtest', href: '/backtest' },
]

function Layout() {
  const location = useLocation()
  const { data: health } = useHealth()

  return (
    <div className="min-h-screen">
      {/* Navigation */}
      <nav className="bg-indigo-600">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="flex h-16 items-center justify-between">
            <div className="flex items-center">
              <Link to="/" className="text-white font-bold text-xl">
                AltData Platform
              </Link>
              <div className="ml-10 flex items-baseline space-x-4">
                {navigation.map((item) => {
                  const isActive = location.pathname === item.href ||
                    (item.href !== '/' && location.pathname.startsWith(item.href))
                  return (
                    <Link
                      key={item.name}
                      to={item.href}
                      className={`px-3 py-2 rounded-md text-sm font-medium ${
                        isActive
                          ? 'bg-indigo-700 text-white'
                          : 'text-indigo-200 hover:bg-indigo-500 hover:text-white'
                      }`}
                    >
                      {item.name}
                    </Link>
                  )
                })}
              </div>
            </div>
            <div className="flex items-center space-x-4">
              {health && (
                <div className="flex items-center space-x-2">
                  <span
                    className={`h-2 w-2 rounded-full ${
                      health.status === 'healthy' ? 'bg-green-400' : 'bg-red-400'
                    }`}
                  />
                  <span className="text-indigo-200 text-sm">
                    {health.status === 'healthy' ? 'API Connected' : 'API Offline'}
                  </span>
                </div>
              )}
            </div>
          </div>
        </div>
      </nav>

      {/* Main content */}
      <main className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-8">
        <Outlet />
      </main>

      {/* Footer */}
      <footer className="bg-white border-t">
        <div className="mx-auto max-w-7xl px-4 py-4 sm:px-6 lg:px-8">
          <p className="text-center text-sm text-gray-500">
            Alternative Data Platform v1.0
          </p>
        </div>
      </footer>
    </div>
  )
}

export default Layout
