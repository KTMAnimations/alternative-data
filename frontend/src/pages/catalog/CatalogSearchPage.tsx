import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useMutation } from '@tanstack/react-query';
import { Search, Sparkles, Clock, ArrowRight, Lightbulb, History } from 'lucide-react';
import { catalogApi } from '../../services/api';

interface SearchResult {
  source_id: string;
  name: string;
  description: string;
  relevance_score: number;
  explanation: string;
  category: string;
}

interface SemanticSearchResponse {
  results: SearchResult[];
  related_sources: { id: string; name: string; reason: string }[];
  query_interpretation: string;
}

const SAMPLE_QUERIES = [
  'Show me consumer spending signals',
  'Real-time infrastructure monitoring data',
  'Leading indicators for housing market',
  'Alternative data for insurance companies',
  'Entertainment industry revenue predictors',
];

export function CatalogSearchPage() {
  const [query, setQuery] = useState('');
  const [recentSearches, setRecentSearches] = useState<string[]>(() => {
    const saved = localStorage.getItem('recent_searches');
    return saved ? JSON.parse(saved) : [];
  });

  const searchMutation = useMutation({
    mutationFn: (searchQuery: string) => catalogApi.semanticSearch(searchQuery),
    onSuccess: (_, searchQuery) => {
      const updated = [searchQuery, ...recentSearches.filter((s) => s !== searchQuery)].slice(0, 5);
      setRecentSearches(updated);
      localStorage.setItem('recent_searches', JSON.stringify(updated));
    },
  });

  const results: SemanticSearchResponse | undefined = searchMutation.data?.data;

  const handleSearch = (searchQuery: string) => {
    if (!searchQuery.trim()) return;
    setQuery(searchQuery);
    searchMutation.mutate(searchQuery);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    handleSearch(query);
  };

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      {/* Header */}
      <div className="text-center">
        <div className="flex items-center justify-center gap-2 mb-2">
          <Sparkles className="h-6 w-6 text-primary-600" />
          <h1 className="text-2xl font-bold text-gray-900">AI-Powered Data Discovery</h1>
        </div>
        <p className="text-gray-500">
          Ask natural language questions to find relevant data sources
        </p>
      </div>

      {/* Search Form */}
      <form onSubmit={handleSubmit} className="relative">
        <Search className="absolute left-4 top-1/2 -translate-y-1/2 h-5 w-5 text-gray-400" />
        <input
          type="text"
          placeholder="e.g., Show me consumer spending signals..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="w-full h-14 pl-12 pr-32 rounded-xl border border-gray-300 bg-white text-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
        />
        <button
          type="submit"
          disabled={!query.trim() || searchMutation.isPending}
          className="absolute right-2 top-1/2 -translate-y-1/2 btn-primary"
        >
          {searchMutation.isPending ? (
            <span className="flex items-center gap-2">
              <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white" />
              Searching...
            </span>
          ) : (
            'Search'
          )}
        </button>
      </form>

      {/* Sample Queries */}
      {!results && !searchMutation.isPending && (
        <div className="space-y-4">
          <div className="flex items-center gap-2 text-sm text-gray-500">
            <Lightbulb className="h-4 w-4" />
            Try these example queries:
          </div>
          <div className="flex flex-wrap gap-2">
            {SAMPLE_QUERIES.map((sampleQuery) => (
              <button
                key={sampleQuery}
                onClick={() => handleSearch(sampleQuery)}
                className="px-4 py-2 rounded-full bg-gray-100 text-gray-700 text-sm hover:bg-gray-200 transition-colors"
              >
                {sampleQuery}
              </button>
            ))}
          </div>

          {/* Recent Searches */}
          {recentSearches.length > 0 && (
            <div className="mt-8">
              <div className="flex items-center gap-2 text-sm text-gray-500 mb-3">
                <History className="h-4 w-4" />
                Recent searches:
              </div>
              <div className="space-y-2">
                {recentSearches.map((search) => (
                  <button
                    key={search}
                    onClick={() => handleSearch(search)}
                    className="flex items-center gap-2 text-gray-700 hover:text-primary-600"
                  >
                    <Clock className="h-4 w-4 text-gray-400" />
                    {search}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Query Interpretation */}
      {results?.query_interpretation && (
        <div className="card p-4 bg-primary-50 border-primary-200">
          <div className="flex items-start gap-2">
            <Sparkles className="h-5 w-5 text-primary-600 mt-0.5" />
            <div>
              <span className="text-sm font-medium text-primary-900">Understanding your query:</span>
              <p className="text-sm text-primary-700 mt-1">{results.query_interpretation}</p>
            </div>
          </div>
        </div>
      )}

      {/* Search Results */}
      {results?.results && results.results.length > 0 && (
        <div className="space-y-4">
          <h2 className="text-lg font-semibold text-gray-900">
            Found {results.results.length} relevant sources
          </h2>

          {results.results.map((result) => (
            <Link
              key={result.source_id}
              to={`/catalog/sources/${result.source_id}`}
              className="card p-5 hover:shadow-md transition-shadow block"
            >
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <h3 className="font-semibold text-gray-900">{result.name}</h3>
                    <span className="px-2 py-0.5 rounded-full bg-gray-100 text-gray-600 text-xs capitalize">
                      {result.category.replace('_', ' ')}
                    </span>
                  </div>
                  <p className="text-sm text-gray-600 mb-3">{result.description}</p>

                  {/* Why this matches */}
                  <div className="bg-green-50 rounded-lg p-3">
                    <div className="flex items-center gap-1 text-green-700 text-sm font-medium mb-1">
                      <Lightbulb className="h-4 w-4" />
                      Why this matches
                    </div>
                    <p className="text-sm text-green-600">{result.explanation}</p>
                  </div>
                </div>

                <div className="flex items-center gap-2 ml-4">
                  <div className="text-right">
                    <div className="text-2xl font-bold text-primary-600">
                      {Math.round(result.relevance_score * 100)}%
                    </div>
                    <div className="text-xs text-gray-500">relevance</div>
                  </div>
                  <ArrowRight className="h-5 w-5 text-gray-400" />
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}

      {/* Related Sources */}
      {results?.related_sources && results.related_sources.length > 0 && (
        <div className="space-y-4">
          <h2 className="text-lg font-semibold text-gray-900">Related Sources</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {results.related_sources.map((related) => (
              <Link
                key={related.id}
                to={`/catalog/sources/${related.id}`}
                className="card p-4 hover:shadow-md transition-shadow"
              >
                <h3 className="font-medium text-gray-900 mb-1">{related.name}</h3>
                <p className="text-sm text-gray-500">{related.reason}</p>
              </Link>
            ))}
          </div>
        </div>
      )}

      {/* No Results */}
      {results && results.results.length === 0 && (
        <div className="card p-12 text-center">
          <Search className="h-12 w-12 text-gray-300 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-900 mb-2">No matches found</h3>
          <p className="text-gray-500">
            Try rephrasing your query or using different keywords
          </p>
        </div>
      )}
    </div>
  );
}
