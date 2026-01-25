import { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Plus, X, Download, Info } from 'lucide-react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import { factorsApi } from '../../services/api';
import type { Factor, FactorComparison } from '../../types';
import clsx from 'clsx';

const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444'];

export function FactorComparePage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [selectedFactors, setSelectedFactors] = useState<string[]>(() => {
    const factors = searchParams.get('factors');
    return factors ? factors.split(',') : [];
  });
  const [searchQuery, setSearchQuery] = useState('');

  // Fetch all factors for selection
  const { data: factorsData } = useQuery({
    queryKey: ['factors-list'],
    queryFn: () => factorsApi.getFactors(),
  });

  const allFactors: Factor[] = factorsData?.data?.factors || [];

  // Fetch comparison data when factors are selected
  const { data: comparisonData, isLoading: comparisonLoading } = useQuery({
    queryKey: ['factors-compare', selectedFactors],
    queryFn: () => factorsApi.compareFactors(selectedFactors),
    enabled: selectedFactors.length >= 2,
  });

  const comparison: FactorComparison | undefined = comparisonData?.data;

  // Update URL when factors change
  useEffect(() => {
    if (selectedFactors.length > 0) {
      setSearchParams({ factors: selectedFactors.join(',') });
    } else {
      setSearchParams({});
    }
  }, [selectedFactors, setSearchParams]);

  const addFactor = (factorId: string) => {
    if (selectedFactors.length < 4 && !selectedFactors.includes(factorId)) {
      setSelectedFactors([...selectedFactors, factorId]);
    }
  };

  const removeFactor = (factorId: string) => {
    setSelectedFactors(selectedFactors.filter((f) => f !== factorId));
  };

  const filteredFactors = allFactors.filter(
    (f) =>
      !selectedFactors.includes(f.id) &&
      (f.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        f.domain.toLowerCase().includes(searchQuery.toLowerCase()))
  );

  const timeSeriesData = comparison?.time_series
    ? comparison.time_series.dates.map((date, idx) => ({
        date,
        ...Object.fromEntries(
          Object.entries(comparison.time_series.values).map(([factorId, values]) => [
            factorId,
            values[idx],
          ])
        ),
      }))
    : [];

  const exportComparison = () => {
    if (!comparison) return;
    const blob = new Blob([JSON.stringify(comparison, null, 2)], {
      type: 'application/json',
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'factor-comparison.json';
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Compare Factors</h1>
          <p className="text-gray-500">
            Select up to 4 factors to compare side-by-side
          </p>
        </div>
        {comparison && (
          <button onClick={exportComparison} className="btn-outline flex items-center gap-2">
            <Download className="h-4 w-4" />
            Export as Research Pack
          </button>
        )}
      </div>

      {/* Factor Selection */}
      <div className="card p-5">
        <h2 className="font-semibold text-gray-900 mb-4">Selected Factors</h2>

        <div className="flex flex-wrap gap-3 mb-4">
          {selectedFactors.map((factorId, idx) => {
            const factor = allFactors.find((f) => f.id === factorId);
            return (
              <div
                key={factorId}
                className="flex items-center gap-2 px-3 py-2 rounded-lg border"
                style={{ borderColor: COLORS[idx] }}
              >
                <div
                  className="w-3 h-3 rounded-full"
                  style={{ backgroundColor: COLORS[idx] }}
                />
                <span className="font-medium text-gray-900">
                  {factor?.name || factorId}
                </span>
                <button
                  onClick={() => removeFactor(factorId)}
                  className="text-gray-400 hover:text-gray-600"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
            );
          })}

          {selectedFactors.length < 4 && (
            <div className="relative">
              <input
                type="text"
                placeholder="Add factor..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="input pr-8"
              />
              <Plus className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />

              {searchQuery && (
                <div className="absolute top-full left-0 right-0 mt-1 bg-white border border-gray-200 rounded-lg shadow-lg max-h-48 overflow-y-auto z-10">
                  {filteredFactors.slice(0, 10).map((factor) => (
                    <button
                      key={factor.id}
                      onClick={() => {
                        addFactor(factor.id);
                        setSearchQuery('');
                      }}
                      className="w-full px-4 py-2 text-left hover:bg-gray-50 flex items-center justify-between"
                    >
                      <span className="font-medium text-gray-900">{factor.name}</span>
                      <span className="text-xs text-gray-500 capitalize">
                        {factor.domain.replace('_', ' ')}
                      </span>
                    </button>
                  ))}
                  {filteredFactors.length === 0 && (
                    <div className="px-4 py-2 text-gray-500 text-sm">
                      No factors found
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>

        {selectedFactors.length < 2 && (
          <div className="flex items-center gap-2 text-sm text-gray-500">
            <Info className="h-4 w-4" />
            Select at least 2 factors to compare
          </div>
        )}
      </div>

      {/* Comparison Results */}
      {comparisonLoading && (
        <div className="flex items-center justify-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600" />
        </div>
      )}

      {comparison && (
        <>
          {/* Metrics Comparison Table */}
          <div className="card overflow-hidden">
            <div className="p-5 border-b border-gray-200">
              <h2 className="font-semibold text-gray-900">Performance Metrics</h2>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-3 text-left text-sm font-medium text-gray-700">
                      Metric
                    </th>
                    {selectedFactors.map((factorId, idx) => {
                      const factor = allFactors.find((f) => f.id === factorId);
                      return (
                        <th
                          key={factorId}
                          className="px-4 py-3 text-left text-sm font-medium"
                          style={{ color: COLORS[idx] }}
                        >
                          {factor?.name || factorId}
                        </th>
                      );
                    })}
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  <tr>
                    <td className="px-4 py-3 text-sm text-gray-600">
                      Information Coefficient (IC)
                    </td>
                    {selectedFactors.map((factorId) => (
                      <td key={factorId} className="px-4 py-3 text-sm font-medium text-gray-900">
                        {comparison.metrics[factorId]?.ic
                          ? `${(comparison.metrics[factorId].ic * 100).toFixed(2)}%`
                          : '-'}
                      </td>
                    ))}
                  </tr>
                  <tr>
                    <td className="px-4 py-3 text-sm text-gray-600">
                      Information Ratio (IR)
                    </td>
                    {selectedFactors.map((factorId) => (
                      <td key={factorId} className="px-4 py-3 text-sm font-medium text-gray-900">
                        {comparison.metrics[factorId]?.ir?.toFixed(2) || '-'}
                      </td>
                    ))}
                  </tr>
                  <tr>
                    <td className="px-4 py-3 text-sm text-gray-600">T-Statistic</td>
                    {selectedFactors.map((factorId) => {
                      const tStat = comparison.metrics[factorId]?.t_stat;
                      const isSignificant = tStat && Math.abs(tStat) > 2;
                      return (
                        <td
                          key={factorId}
                          className={clsx(
                            'px-4 py-3 text-sm font-medium',
                            isSignificant ? 'text-success-500' : 'text-gray-900'
                          )}
                        >
                          {tStat?.toFixed(2) || '-'}
                          {isSignificant && ' *'}
                        </td>
                      );
                    })}
                  </tr>
                  <tr>
                    <td className="px-4 py-3 text-sm text-gray-600">Hit Rate</td>
                    {selectedFactors.map((factorId) => (
                      <td key={factorId} className="px-4 py-3 text-sm font-medium text-gray-900">
                        {comparison.metrics[factorId]?.hit_rate
                          ? `${(comparison.metrics[factorId].hit_rate * 100).toFixed(1)}%`
                          : '-'}
                      </td>
                    ))}
                  </tr>
                </tbody>
              </table>
            </div>
            <div className="p-3 bg-gray-50 text-xs text-gray-500">
              * Statistically significant at 95% confidence level (|t-stat| {'>'} 2)
            </div>
          </div>

          {/* Correlation Matrix */}
          <div className="card p-5">
            <h2 className="font-semibold text-gray-900 mb-4">Correlation Matrix</h2>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr>
                    <th className="px-4 py-2" />
                    {selectedFactors.map((factorId, idx) => {
                      const factor = allFactors.find((f) => f.id === factorId);
                      return (
                        <th
                          key={factorId}
                          className="px-4 py-2 text-sm font-medium text-center"
                          style={{ color: COLORS[idx] }}
                        >
                          {factor?.name?.slice(0, 15) || factorId}
                        </th>
                      );
                    })}
                  </tr>
                </thead>
                <tbody>
                  {comparison.correlation_matrix.map((row, i) => {
                    const factor = allFactors.find((f) => f.id === selectedFactors[i]);
                    return (
                      <tr key={i}>
                        <td
                          className="px-4 py-2 text-sm font-medium"
                          style={{ color: COLORS[i] }}
                        >
                          {factor?.name?.slice(0, 15) || selectedFactors[i]}
                        </td>
                        {row.map((corr, j) => {
                          const absCorr = Math.abs(corr);
                          const bgOpacity = absCorr * 0.3;
                          const bgColor =
                            corr > 0
                              ? `rgba(34, 197, 94, ${bgOpacity})`
                              : `rgba(239, 68, 68, ${bgOpacity})`;
                          return (
                            <td
                              key={j}
                              className="px-4 py-2 text-sm text-center font-medium"
                              style={{ backgroundColor: bgColor }}
                            >
                              {corr.toFixed(2)}
                            </td>
                          );
                        })}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>

          {/* Time Series Chart */}
          {timeSeriesData.length > 0 && (
            <div className="card p-5">
              <h2 className="font-semibold text-gray-900 mb-4">
                Time Series Comparison
              </h2>
              <div className="h-80">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={timeSeriesData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                    <XAxis
                      dataKey="date"
                      tick={{ fontSize: 12 }}
                      tickFormatter={(v) => v.slice(5)}
                    />
                    <YAxis tick={{ fontSize: 12 }} />
                    <Tooltip />
                    <Legend />
                    {selectedFactors.map((factorId, idx) => {
                      const factor = allFactors.find((f) => f.id === factorId);
                      return (
                        <Line
                          key={factorId}
                          type="monotone"
                          dataKey={factorId}
                          name={factor?.name || factorId}
                          stroke={COLORS[idx]}
                          strokeWidth={2}
                          dot={false}
                        />
                      );
                    })}
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
