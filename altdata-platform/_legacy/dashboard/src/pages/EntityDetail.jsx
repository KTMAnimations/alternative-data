import { useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useEntity } from '../hooks/useEntities'
import { useFactors, useFactorValues } from '../hooks/useFactors'
import FactorChart from '../components/FactorChart'

function EntityDetail() {
  const { id } = useParams()
  const { data: entity, isLoading: entityLoading, error: entityError } = useEntity(id)
  const { data: factors } = useFactors()
  const [selectedFactor, setSelectedFactor] = useState('insider_transaction_momentum')

  const { data: factorData, isLoading: factorLoading } = useFactorValues(
    selectedFactor,
    id
  )

  if (entityLoading) {
    return (
      <div className="text-center py-12">
        <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-indigo-600 border-r-transparent"></div>
        <p className="mt-2 text-gray-500">Loading entity...</p>
      </div>
    )
  }

  if (entityError) {
    return (
      <div className="text-center py-12">
        <p className="text-red-500">Error loading entity: {entityError.message}</p>
        <Link to="/entities" className="mt-4 text-indigo-600 hover:text-indigo-900">
          Back to entities
        </Link>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Breadcrumb */}
      <nav className="flex" aria-label="Breadcrumb">
        <ol className="flex items-center space-x-4">
          <li>
            <Link to="/entities" className="text-gray-400 hover:text-gray-500">
              Entities
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

      {/* Entity Header */}
      <div className="bg-white shadow rounded-lg p-6">
        <div className="flex justify-between items-start">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">{entity?.name}</h1>
            {entity?.ticker && (
              <p className="text-lg text-indigo-600 font-medium">{entity.ticker}</p>
            )}
          </div>
          <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-gray-100 text-gray-800">
            {entity?.entity_type}
          </span>
        </div>

        <dl className="mt-6 grid grid-cols-1 gap-x-4 gap-y-6 sm:grid-cols-2 lg:grid-cols-4">
          <div>
            <dt className="text-sm font-medium text-gray-500">ID</dt>
            <dd className="mt-1 text-sm text-gray-900">{entity?.id}</dd>
          </div>
          {entity?.sector && (
            <div>
              <dt className="text-sm font-medium text-gray-500">Sector</dt>
              <dd className="mt-1 text-sm text-gray-900">{entity.sector}</dd>
            </div>
          )}
          {entity?.industry && (
            <div>
              <dt className="text-sm font-medium text-gray-500">Industry</dt>
              <dd className="mt-1 text-sm text-gray-900">{entity.industry}</dd>
            </div>
          )}
        </dl>
      </div>

      {/* Factor Selector */}
      <div className="bg-white shadow rounded-lg p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Available Factors</h2>
        <div className="flex flex-wrap gap-2">
          {factors?.factors?.slice(0, 12).map((factor) => (
            <button
              key={factor.id}
              onClick={() => setSelectedFactor(factor.id)}
              className={`px-3 py-1 rounded-full text-sm font-medium transition-colors ${
                selectedFactor === factor.id
                  ? 'bg-indigo-600 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              {factor.name}
            </button>
          ))}
        </div>
        {factors?.factors?.length > 12 && (
          <p className="mt-2 text-sm text-gray-500">
            +{factors.factors.length - 12} more factors available
          </p>
        )}
      </div>

      {/* Factor Chart */}
      {factorLoading ? (
        <div className="bg-white shadow rounded-lg p-6 text-center">
          <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-indigo-600 border-r-transparent"></div>
          <p className="mt-2 text-gray-500">Loading factor data...</p>
        </div>
      ) : (
        <FactorChart
          data={factorData?.values}
          title={`${selectedFactor} for ${entity?.name || id}`}
        />
      )}

      {/* Links */}
      <div className="bg-white shadow rounded-lg p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Explore Factors</h2>
        <div className="space-y-2">
          {factors?.factors?.slice(0, 5).map((factor) => (
            <Link
              key={factor.id}
              to={`/factors/${factor.id}`}
              className="block p-3 rounded-lg border hover:bg-gray-50 transition-colors"
            >
              <p className="text-sm font-medium text-indigo-600">{factor.name}</p>
              <p className="text-xs text-gray-500">{factor.description}</p>
            </Link>
          ))}
        </div>
      </div>
    </div>
  )
}

export default EntityDetail
