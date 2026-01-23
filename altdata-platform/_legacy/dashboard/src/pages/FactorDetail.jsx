import { useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useFactors, useFactorValues } from '../hooks/useFactors'
import FactorChart from '../components/FactorChart'
import DateRangePicker from '../components/DateRangePicker'

function FactorDetail() {
  const { id } = useParams()
  const [entityId, setEntityId] = useState('AAPL')
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')

  const { data: factors } = useFactors()
  const { data: factorData, isLoading, error } = useFactorValues(
    id,
    entityId,
    startDate || undefined,
    endDate || undefined
  )

  // Find factor metadata
  const factor = factors?.factors?.find((f) => f.id === id)

  const commonEntities = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'NVDA', 'TSLA']

  return (
    <div className="space-y-6">
      {/* Breadcrumb */}
      <nav className="flex" aria-label="Breadcrumb">
        <ol className="flex items-center space-x-4">
          <li>
            <Link to="/factors" className="text-gray-400 hover:text-gray-500">
              Factors
            </Link>
          </li>
          <li>
            <div className="flex items-center">
              <svg
                className="flex-shrink-0 h-5 w-5 text-gray-300"
                fill="currentColor"
                viewBox="0 0 20 20"
              >
                <path d="M5.555 17.776l8-16 .894.448-8 16-.894-.448z" />
              </svg>
              <span className="ml-4 text-sm font-medium text-gray-500">{id}</span>
            </div>
          </li>
        </ol>
      </nav>

      {/* Header */}
      <div className="bg-white shadow rounded-lg p-6">
        <h1 className="text-2xl font-bold text-gray-900">
          {factor?.name || id}
        </h1>
        <p className="mt-2 text-gray-500">
          {factor?.description || 'No description available'}
        </p>
        <div className="mt-4 flex flex-wrap gap-2">
          {factor?.category && (
            <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-indigo-100 text-indigo-800">
              {factor.category}
            </span>
          )}
          {factor?.frequency && (
            <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-gray-100 text-gray-800">
              {factor.frequency}
            </span>
          )}
        </div>
      </div>

      {/* Controls */}
      <div className="bg-white shadow rounded-lg p-6">
        <div className="flex flex-col sm:flex-row gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700">Entity</label>
            <div className="mt-1 flex items-center gap-2">
              <input
                type="text"
                value={entityId}
                onChange={(e) => setEntityId(e.target.value.toUpperCase())}
                className="block w-32 rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
                placeholder="e.g., AAPL"
              />
              <div className="flex gap-1">
                {commonEntities.map((entity) => (
                  <button
                    key={entity}
                    onClick={() => setEntityId(entity)}
                    className={`px-2 py-1 text-xs rounded ${
                      entityId === entity
                        ? 'bg-indigo-600 text-white'
                        : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                    }`}
                  >
                    {entity}
                  </button>
                ))}
              </div>
            </div>
          </div>
          <DateRangePicker
            startDate={startDate}
            endDate={endDate}
            onStartChange={setStartDate}
            onEndChange={setEndDate}
          />
        </div>
      </div>

      {/* Chart */}
      {isLoading ? (
        <div className="bg-white shadow rounded-lg p-6 text-center">
          <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-indigo-600 border-r-transparent"></div>
          <p className="mt-2 text-gray-500">Loading data...</p>
        </div>
      ) : error ? (
        <div className="bg-white shadow rounded-lg p-6 text-center">
          <p className="text-red-500">Error loading data: {error.message}</p>
        </div>
      ) : (
        <FactorChart
          data={factorData?.values}
          title={`${factor?.name || id} for ${entityId}`}
        />
      )}

      {/* Data Table */}
      {factorData?.values && factorData.values.length > 0 && (
        <div className="bg-white shadow rounded-lg overflow-hidden">
          <div className="px-6 py-4 border-b border-gray-200">
            <h3 className="text-lg font-semibold text-gray-900">
              Recent Values ({factorData.values.length} records)
            </h3>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Date
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Value
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Version
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {factorData.values.slice(0, 20).map((value, idx) => (
                  <tr key={idx}>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {new Date(value.date).toLocaleDateString()}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                      {value.value?.toLocaleString(undefined, {
                        minimumFractionDigits: 2,
                        maximumFractionDigits: 4,
                      }) ?? '-'}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      v{value.version}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {factorData.values.length > 20 && (
            <div className="px-6 py-3 bg-gray-50 text-sm text-gray-500">
              Showing 20 of {factorData.values.length} records
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default FactorDetail
