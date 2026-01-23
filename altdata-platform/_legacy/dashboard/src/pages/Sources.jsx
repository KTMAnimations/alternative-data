import { useSources, useHealth } from '../hooks/useSources'
import SourceStatus from '../components/SourceStatus'

function Sources() {
  const { data: sources, isLoading, error } = useSources()
  const { data: health } = useHealth()

  if (error) {
    return (
      <div className="text-center py-12">
        <p className="text-red-500">Error loading sources: {error.message}</p>
      </div>
    )
  }

  const activeCount = sources?.sources?.filter((s) => s.status === 'active').length || 0
  const degradedCount = sources?.sources?.filter((s) => s.status === 'degraded').length || 0
  const offlineCount = sources?.sources?.filter((s) => s.status === 'offline').length || 0

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Data Sources</h1>
        <p className="mt-1 text-sm text-gray-500">
          Monitor the status of {sources?.sources?.length || 0} data sources
        </p>
      </div>

      {/* System Status */}
      {health && (
        <div className={`rounded-lg p-4 ${
          health.status === 'healthy' ? 'bg-green-50' : 'bg-red-50'
        }`}>
          <div className="flex items-center justify-between">
            <div className="flex items-center">
              <span className={`h-3 w-3 rounded-full mr-3 ${
                health.status === 'healthy' ? 'bg-green-400' : 'bg-red-400'
              }`} />
              <div>
                <p className={`text-sm font-medium ${
                  health.status === 'healthy' ? 'text-green-800' : 'text-red-800'
                }`}>
                  System Status: {health.status === 'healthy' ? 'Healthy' : 'Issues Detected'}
                </p>
                <p className={`text-xs ${
                  health.status === 'healthy' ? 'text-green-600' : 'text-red-600'
                }`}>
                  Database: {health.database} | Redis: {health.redis}
                </p>
              </div>
            </div>
            <span className={`text-sm font-medium ${
              health.status === 'healthy' ? 'text-green-800' : 'text-red-800'
            }`}>
              v{health.version}
            </span>
          </div>
        </div>
      )}

      {/* Stats */}
      <div className="grid grid-cols-1 gap-5 sm:grid-cols-3">
        <div className="bg-white overflow-hidden shadow rounded-lg">
          <div className="px-4 py-5 sm:p-6">
            <dt className="text-sm font-medium text-gray-500 truncate">Active Sources</dt>
            <dd className="mt-1 text-3xl font-semibold text-green-600">{activeCount}</dd>
          </div>
        </div>
        <div className="bg-white overflow-hidden shadow rounded-lg">
          <div className="px-4 py-5 sm:p-6">
            <dt className="text-sm font-medium text-gray-500 truncate">Degraded Sources</dt>
            <dd className="mt-1 text-3xl font-semibold text-yellow-600">{degradedCount}</dd>
          </div>
        </div>
        <div className="bg-white overflow-hidden shadow rounded-lg">
          <div className="px-4 py-5 sm:p-6">
            <dt className="text-sm font-medium text-gray-500 truncate">Offline Sources</dt>
            <dd className="mt-1 text-3xl font-semibold text-red-600">{offlineCount}</dd>
          </div>
        </div>
      </div>

      {/* Source List */}
      {isLoading ? (
        <div className="text-center py-12">
          <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-indigo-600 border-r-transparent"></div>
          <p className="mt-2 text-gray-500">Loading sources...</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <SourceStatus sources={sources?.sources?.filter((s) => s.status === 'active')} />
          {(degradedCount > 0 || offlineCount > 0) && (
            <div className="bg-white shadow rounded-lg overflow-hidden">
              <div className="px-6 py-4 border-b border-gray-200 bg-yellow-50">
                <h3 className="text-lg font-semibold text-yellow-800">Issues Detected</h3>
              </div>
              <ul className="divide-y divide-gray-200">
                {sources?.sources
                  ?.filter((s) => s.status !== 'active')
                  .map((source) => (
                    <li key={source.id} className="px-6 py-4">
                      <div className="flex items-center justify-between">
                        <div>
                          <p className="text-sm font-medium text-gray-900">{source.name}</p>
                          <p className="text-xs text-gray-500">{source.category}</p>
                        </div>
                        <span
                          className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                            source.status === 'degraded'
                              ? 'bg-yellow-100 text-yellow-800'
                              : 'bg-red-100 text-red-800'
                          }`}
                        >
                          {source.status}
                        </span>
                      </div>
                    </li>
                  ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* Source Details Table */}
      <div className="bg-white shadow rounded-lg overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-200">
          <h3 className="text-lg font-semibold text-gray-900">All Sources</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Source
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Category
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Update Frequency
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Factors
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Status
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {sources?.sources?.map((source) => (
                <tr key={source.id}>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <p className="text-sm font-medium text-gray-900">{source.name}</p>
                    <p className="text-xs text-gray-500">{source.id}</p>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {source.category}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {source.update_frequency}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {source.factors?.length || 0}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
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
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

export default Sources
