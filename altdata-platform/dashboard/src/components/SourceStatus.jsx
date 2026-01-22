function SourceStatus({ sources }) {
  const statusColors = {
    active: 'bg-green-100 text-green-800',
    degraded: 'bg-yellow-100 text-yellow-800',
    maintenance: 'bg-blue-100 text-blue-800',
    offline: 'bg-red-100 text-red-800',
  }

  const statusIcons = {
    active: '●',
    degraded: '◐',
    maintenance: '◑',
    offline: '○',
  }

  return (
    <div className="bg-white shadow rounded-lg overflow-hidden">
      <div className="px-6 py-4 border-b border-gray-200">
        <h3 className="text-lg font-semibold text-gray-900">Data Sources</h3>
      </div>
      <ul className="divide-y divide-gray-200">
        {sources?.map((source) => (
          <li key={source.id} className="px-6 py-4 flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-900">{source.name}</p>
              <p className="text-sm text-gray-500">
                {source.category} | {source.update_frequency}
              </p>
            </div>
            <span
              className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                statusColors[source.status] || statusColors.offline
              }`}
            >
              <span className="mr-1">{statusIcons[source.status] || statusIcons.offline}</span>
              {source.status}
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}

export default SourceStatus
