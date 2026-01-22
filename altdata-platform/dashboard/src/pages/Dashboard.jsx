import { Link } from 'react-router-dom'
import { useFactors, useCategories } from '../hooks/useFactors'
import { useEntities } from '../hooks/useEntities'
import { useSources, useHealth } from '../hooks/useSources'

function Dashboard() {
  const { data: factors } = useFactors()
  const { data: categories } = useCategories()
  const { data: entities } = useEntities()
  const { data: sources } = useSources()
  const { data: health } = useHealth()

  const stats = [
    {
      name: 'Total Factors',
      value: factors?.total || 0,
      href: '/factors',
    },
    {
      name: 'Categories',
      value: categories?.categories?.length || 0,
      href: '/factors',
    },
    {
      name: 'Entities',
      value: entities?.total || 0,
      href: '/entities',
    },
    {
      name: 'Data Sources',
      value: sources?.sources?.length || 0,
      href: '/sources',
    },
  ]

  const activeSourcesCount = sources?.sources?.filter(s => s.status === 'active').length || 0
  const totalSources = sources?.sources?.length || 0

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
        <p className="mt-1 text-sm text-gray-500">
          Overview of the Alternative Data Platform
        </p>
      </div>

      {/* Health Status */}
      {health && (
        <div className={`rounded-lg p-4 ${
          health.status === 'healthy' ? 'bg-green-50' : 'bg-red-50'
        }`}>
          <div className="flex items-center">
            <span className={`h-3 w-3 rounded-full mr-3 ${
              health.status === 'healthy' ? 'bg-green-400' : 'bg-red-400'
            }`} />
            <div>
              <p className={`text-sm font-medium ${
                health.status === 'healthy' ? 'text-green-800' : 'text-red-800'
              }`}>
                System Status: {health.status === 'healthy' ? 'All Systems Operational' : 'System Issues Detected'}
              </p>
              <p className={`text-sm ${
                health.status === 'healthy' ? 'text-green-600' : 'text-red-600'
              }`}>
                Database: {health.database} | Cache: {health.redis} | Version: {health.version}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Stats */}
      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
        {stats.map((stat) => (
          <Link
            key={stat.name}
            to={stat.href}
            className="bg-white overflow-hidden shadow rounded-lg hover:shadow-md transition-shadow"
          >
            <div className="px-4 py-5 sm:p-6">
              <dt className="text-sm font-medium text-gray-500 truncate">
                {stat.name}
              </dt>
              <dd className="mt-1 text-3xl font-semibold text-indigo-600">
                {stat.value}
              </dd>
            </div>
          </Link>
        ))}
      </div>

      {/* Categories Overview */}
      <div className="bg-white shadow rounded-lg overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-200">
          <h2 className="text-lg font-semibold text-gray-900">Factor Categories</h2>
        </div>
        <div className="p-6">
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
            {categories?.categories?.map((category) => (
              <Link
                key={category.id}
                to={`/factors?category=${category.id}`}
                className="p-4 border rounded-lg hover:bg-gray-50 transition-colors"
              >
                <p className="text-sm font-medium text-gray-900">{category.name}</p>
                <p className="text-2xl font-bold text-indigo-600">{category.count}</p>
                <p className="text-xs text-gray-500">factors</p>
              </Link>
            ))}
          </div>
        </div>
      </div>

      {/* Data Source Status */}
      <div className="bg-white shadow rounded-lg overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-200 flex justify-between items-center">
          <h2 className="text-lg font-semibold text-gray-900">Data Source Status</h2>
          <span className="text-sm text-gray-500">
            {activeSourcesCount}/{totalSources} active
          </span>
        </div>
        <div className="p-6">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {sources?.sources?.map((source) => (
              <div
                key={source.id}
                className="flex items-center justify-between p-3 border rounded-lg"
              >
                <div>
                  <p className="text-sm font-medium text-gray-900">{source.name}</p>
                  <p className="text-xs text-gray-500">{source.update_frequency}</p>
                </div>
                <span
                  className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                    source.status === 'active'
                      ? 'bg-green-100 text-green-800'
                      : source.status === 'degraded'
                      ? 'bg-yellow-100 text-yellow-800'
                      : 'bg-red-100 text-red-800'
                  }`}
                >
                  {source.status}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Recent Entities */}
      <div className="bg-white shadow rounded-lg overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-200 flex justify-between items-center">
          <h2 className="text-lg font-semibold text-gray-900">Sample Entities</h2>
          <Link to="/entities" className="text-sm text-indigo-600 hover:text-indigo-900">
            View all
          </Link>
        </div>
        <div className="divide-y divide-gray-200">
          {entities?.entities?.slice(0, 5).map((entity) => (
            <Link
              key={entity.id}
              to={`/entities/${entity.id}`}
              className="block px-6 py-4 hover:bg-gray-50"
            >
              <div className="flex justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-900">{entity.name}</p>
                  <p className="text-xs text-gray-500">{entity.ticker}</p>
                </div>
                <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800">
                  {entity.entity_type}
                </span>
              </div>
            </Link>
          ))}
        </div>
      </div>
    </div>
  )
}

export default Dashboard
