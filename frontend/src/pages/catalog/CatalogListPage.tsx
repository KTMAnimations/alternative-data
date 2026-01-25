import { useState, useMemo } from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Search, Filter, Clock, Database, Calendar, TrendingUp, ChevronDown } from 'lucide-react';
import { catalogApi } from '../../services/api';
import type { DataSource } from '../../types';
import clsx from 'clsx';

const CATEGORIES = [
  { id: 'travel', label: 'Travel' },
  { id: 'real_estate', label: 'Real Estate' },
  { id: 'energy', label: 'Energy' },
  { id: 'gaming', label: 'Gaming' },
  { id: 'government', label: 'Government' },
  { id: 'infrastructure', label: 'Infrastructure' },
];

const FREQUENCIES = [
  { id: 'continuous', label: 'Continuous' },
  { id: 'hourly', label: 'Hourly' },
  { id: 'daily', label: 'Daily' },
  { id: 'weekly', label: 'Weekly' },
  { id: 'monthly', label: 'Monthly' },
];

const SORT_OPTIONS = [
  { id: 'name', label: 'Name' },
  { id: 'saturation_level', label: 'Saturation' },
  { id: 'latency_hours', label: 'Freshness' },
];

export function CatalogListPage() {
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategories, setSelectedCategories] = useState<string[]>([]);
  const [selectedFrequencies, setSelectedFrequencies] = useState<string[]>([]);
  const [sortBy, setSortBy] = useState('name');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('asc');
  const [filtersOpen, setFiltersOpen] = useState(true);

  const { data: sourcesData, isLoading, error } = useQuery({
    queryKey: ['catalog-sources', selectedCategories, selectedFrequencies, sortBy, sortOrder],
    queryFn: () =>
      catalogApi.getSources({
        category: selectedCategories.join(',') || undefined,
        frequency: selectedFrequencies.join(',') || undefined,
        sort_by: sortBy,
        sort_order: sortOrder,
      }),
  });

  const sources: DataSource[] = sourcesData?.data?.sources || [];

  const filteredSources = useMemo(() => {
    if (!searchQuery) return sources;
    const query = searchQuery.toLowerCase();
    return sources.filter(
      (source) =>
        source.name.toLowerCase().includes(query) ||
        source.description.toLowerCase().includes(query)
    );
  }, [sources, searchQuery]);

  const toggleCategory = (categoryId: string) => {
    setSelectedCategories((prev) =>
      prev.includes(categoryId)
        ? prev.filter((c) => c !== categoryId)
        : [...prev, categoryId]
    );
  };

  const toggleFrequency = (frequencyId: string) => {
    setSelectedFrequencies((prev) =>
      prev.includes(frequencyId)
        ? prev.filter((f) => f !== frequencyId)
        : [...prev, frequencyId]
    );
  };

  const getSaturationColor = (level: number) => {
    if (level < 30) return 'text-success-500 bg-success-50';
    if (level < 70) return 'text-warning-500 bg-warning-50';
    return 'text-danger-500 bg-danger-50';
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Data Catalog</h1>
        <p className="mt-1 text-gray-500">
          Browse and discover alternative data sources for your investment research
        </p>
      </div>

      {/* Search Bar */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-gray-400" />
        <input
          type="text"
          placeholder="Search data sources by name or description..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="input pl-10 w-full"
        />
      </div>

      <div className="flex gap-6">
        {/* Filter Sidebar */}
        <aside className={clsx('w-64 flex-shrink-0', !filtersOpen && 'hidden')}>
          <div className="card p-4 space-y-6">
            <div className="flex items-center justify-between">
              <h3 className="font-semibold text-gray-900 flex items-center gap-2">
                <Filter className="h-4 w-4" />
                Filters
              </h3>
              <button
                onClick={() => {
                  setSelectedCategories([]);
                  setSelectedFrequencies([]);
                }}
                className="text-sm text-primary-600 hover:text-primary-700"
              >
                Clear all
              </button>
            </div>

            {/* Category Filter */}
            <div>
              <h4 className="text-sm font-medium text-gray-700 mb-2">Category</h4>
              <div className="space-y-2">
                {CATEGORIES.map((category) => (
                  <label key={category.id} className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={selectedCategories.includes(category.id)}
                      onChange={() => toggleCategory(category.id)}
                      className="rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                    />
                    <span className="text-sm text-gray-600">{category.label}</span>
                  </label>
                ))}
              </div>
            </div>

            {/* Frequency Filter */}
            <div>
              <h4 className="text-sm font-medium text-gray-700 mb-2">Update Frequency</h4>
              <div className="space-y-2">
                {FREQUENCIES.map((frequency) => (
                  <label key={frequency.id} className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={selectedFrequencies.includes(frequency.id)}
                      onChange={() => toggleFrequency(frequency.id)}
                      className="rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                    />
                    <span className="text-sm text-gray-600">{frequency.label}</span>
                  </label>
                ))}
              </div>
            </div>
          </div>
        </aside>

        {/* Main Content */}
        <div className="flex-1">
          {/* Sort Controls */}
          <div className="flex items-center justify-between mb-4">
            <button
              onClick={() => setFiltersOpen(!filtersOpen)}
              className="btn-outline flex items-center gap-2 lg:hidden"
            >
              <Filter className="h-4 w-4" />
              Filters
            </button>

            <div className="flex items-center gap-4">
              <span className="text-sm text-gray-500">
                {filteredSources.length} sources found
              </span>

              <div className="flex items-center gap-2">
                <label className="text-sm text-gray-600">Sort by:</label>
                <select
                  value={sortBy}
                  onChange={(e) => setSortBy(e.target.value)}
                  className="select w-auto"
                >
                  {SORT_OPTIONS.map((option) => (
                    <option key={option.id} value={option.id}>
                      {option.label}
                    </option>
                  ))}
                </select>

                <button
                  onClick={() => setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc')}
                  className="btn-outline p-2"
                >
                  <ChevronDown
                    className={clsx(
                      'h-4 w-4 transition-transform',
                      sortOrder === 'desc' && 'rotate-180'
                    )}
                  />
                </button>
              </div>
            </div>
          </div>

          {/* Loading State */}
          {isLoading && (
            <div className="flex items-center justify-center py-12">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600" />
            </div>
          )}

          {/* Error State */}
          {error && (
            <div className="card p-6 text-center text-danger-500">
              Failed to load data sources. Please try again.
            </div>
          )}

          {/* Sources Grid */}
          {!isLoading && !error && (
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
              {filteredSources.map((source) => (
                <Link
                  key={source.id}
                  to={`/catalog/sources/${source.id}`}
                  className="card p-4 hover:shadow-md transition-shadow"
                >
                  <div className="flex items-start justify-between mb-3">
                    <div>
                      <h3 className="font-semibold text-gray-900">{source.name}</h3>
                      <span className="text-xs text-gray-500 capitalize">
                        {source.category.replace('_', ' ')}
                      </span>
                    </div>
                    <span
                      className={clsx(
                        'px-2 py-1 rounded-full text-xs font-medium',
                        getSaturationColor(source.saturation_level)
                      )}
                    >
                      {source.saturation_level}% saturated
                    </span>
                  </div>

                  <p className="text-sm text-gray-600 mb-4 line-clamp-2">
                    {source.description}
                  </p>

                  <div className="flex flex-wrap gap-2 text-xs text-gray-500">
                    <span className="flex items-center gap-1">
                      <Clock className="h-3 w-3" />
                      {source.update_frequency}
                    </span>
                    <span className="flex items-center gap-1">
                      <TrendingUp className="h-3 w-3" />
                      {source.latency_hours}h latency
                    </span>
                    <span className="flex items-center gap-1">
                      <Calendar className="h-3 w-3" />
                      {source.date_range_start} - {source.date_range_end}
                    </span>
                  </div>
                </Link>
              ))}
            </div>
          )}

          {/* Empty State */}
          {!isLoading && !error && filteredSources.length === 0 && (
            <div className="card p-12 text-center">
              <Database className="h-12 w-12 text-gray-300 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-gray-900 mb-2">No sources found</h3>
              <p className="text-gray-500">
                Try adjusting your filters or search query
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
