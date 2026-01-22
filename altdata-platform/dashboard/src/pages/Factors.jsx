import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useFactors, useCategories } from '../hooks/useFactors'
import FactorCard from '../components/FactorCard'
import SearchBar from '../components/SearchBar'

function Factors() {
  const [searchParams, setSearchParams] = useSearchParams()
  const categoryParam = searchParams.get('category') || ''
  const [search, setSearch] = useState('')

  const { data: factors, isLoading, error } = useFactors(categoryParam || undefined)
  const { data: categories } = useCategories()

  const handleCategoryChange = (category) => {
    if (category) {
      setSearchParams({ category })
    } else {
      setSearchParams({})
    }
  }

  // Filter factors by search
  const filteredFactors = factors?.factors?.filter((factor) => {
    if (!search) return true
    const searchLower = search.toLowerCase()
    return (
      factor.name.toLowerCase().includes(searchLower) ||
      factor.description?.toLowerCase().includes(searchLower) ||
      factor.id.toLowerCase().includes(searchLower)
    )
  })

  if (error) {
    return (
      <div className="text-center py-12">
        <p className="text-red-500">Error loading factors: {error.message}</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Factors</h1>
        <p className="mt-1 text-sm text-gray-500">
          Browse {factors?.total || 0} quantitative factors across {categories?.categories?.length || 0} categories
        </p>
      </div>

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-4">
        <div className="sm:w-64">
          <SearchBar
            value={search}
            onChange={setSearch}
            placeholder="Search factors..."
          />
        </div>
        <div>
          <select
            value={categoryParam}
            onChange={(e) => handleCategoryChange(e.target.value)}
            className="block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
          >
            <option value="">All Categories</option>
            {categories?.categories?.map((cat) => (
              <option key={cat.id} value={cat.id}>
                {cat.name} ({cat.count})
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Factor Grid */}
      {isLoading ? (
        <div className="text-center py-12">
          <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-indigo-600 border-r-transparent"></div>
          <p className="mt-2 text-gray-500">Loading factors...</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredFactors?.map((factor) => (
            <FactorCard key={factor.id} factor={factor} />
          ))}
        </div>
      )}

      {/* Empty State */}
      {!isLoading && filteredFactors?.length === 0 && (
        <div className="text-center py-12">
          <p className="text-gray-500">No factors found matching your criteria.</p>
        </div>
      )}
    </div>
  )
}

export default Factors
