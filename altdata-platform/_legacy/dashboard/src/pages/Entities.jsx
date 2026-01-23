import { useState } from 'react'
import { useEntities } from '../hooks/useEntities'
import EntityTable from '../components/EntityTable'
import SearchBar from '../components/SearchBar'

function Entities() {
  const [search, setSearch] = useState('')
  const [entityType, setEntityType] = useState('')
  const [page, setPage] = useState(1)
  const pageSize = 50

  const { data, isLoading, error } = useEntities(
    search || undefined,
    entityType || undefined,
    page,
    pageSize
  )

  const entityTypes = ['company', 'region', 'port', 'airport', 'commodity']

  if (error) {
    return (
      <div className="text-center py-12">
        <p className="text-red-500">Error loading entities: {error.message}</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Entities</h1>
        <p className="mt-1 text-sm text-gray-500">
          Browse and search {data?.total || 0} entities
        </p>
      </div>

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-4">
        <div className="sm:w-64">
          <SearchBar
            value={search}
            onChange={(value) => {
              setSearch(value)
              setPage(1)
            }}
            placeholder="Search by name or ticker..."
          />
        </div>
        <div>
          <select
            value={entityType}
            onChange={(e) => {
              setEntityType(e.target.value)
              setPage(1)
            }}
            className="block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
          >
            <option value="">All Types</option>
            {entityTypes.map((type) => (
              <option key={type} value={type}>
                {type.charAt(0).toUpperCase() + type.slice(1)}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Table */}
      {isLoading ? (
        <div className="text-center py-12">
          <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-indigo-600 border-r-transparent"></div>
          <p className="mt-2 text-gray-500">Loading entities...</p>
        </div>
      ) : (
        <EntityTable
          entities={data?.entities}
          total={data?.total || 0}
          page={page}
          pageSize={pageSize}
          onPageChange={setPage}
        />
      )}

      {/* Empty State */}
      {!isLoading && data?.entities?.length === 0 && (
        <div className="text-center py-12">
          <p className="text-gray-500">No entities found matching your criteria.</p>
        </div>
      )}
    </div>
  )
}

export default Entities
