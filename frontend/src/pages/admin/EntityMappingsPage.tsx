import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Check, X } from 'lucide-react';
import { adminApi } from '../../services/api';
import type { EntityMapping, MappingCoverage } from '../../types';
import clsx from 'clsx';

export function EntityMappingsPage() {
  const queryClient = useQueryClient();
  const [filter, setFilter] = useState<'all' | 'needs_review' | 'approved'>('needs_review');
  const [selectedMappings, setSelectedMappings] = useState<string[]>([]);

  const { data: mappingsData, isLoading } = useQuery({
    queryKey: ['pending-mappings', filter],
    queryFn: () => adminApi.getPendingMappings({ status: filter === 'all' ? undefined : filter }),
  });

  const { data: coverageData } = useQuery({
    queryKey: ['mapping-coverage'],
    queryFn: () => adminApi.getMappingCoverage(),
  });

  const mappings: EntityMapping[] = mappingsData?.data?.mappings || [];
  const coverage: MappingCoverage[] = coverageData?.data?.coverage || [];

  const approveMutation = useMutation({
    mutationFn: (ids: string[]) => adminApi.approveMappings(ids),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pending-mappings'] });
      setSelectedMappings([]);
    },
  });

  const rejectMutation = useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) =>
      adminApi.rejectMapping(id, reason),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['pending-mappings'] }),
  });

  const toggleSelection = (id: string) => {
    setSelectedMappings((prev) =>
      prev.includes(id) ? prev.filter((m) => m !== id) : [...prev, id]
    );
  };

  const selectAll = () => {
    if (selectedMappings.length === mappings.length) {
      setSelectedMappings([]);
    } else {
      setSelectedMappings(mappings.map((m) => m.id));
    }
  };

  const getConfidenceBadge = (score: number) => {
    if (score >= 0.9) return <span className="px-2 py-0.5 rounded-full bg-green-100 text-green-700 text-xs">High</span>;
    if (score >= 0.7) return <span className="px-2 py-0.5 rounded-full bg-yellow-100 text-yellow-700 text-xs">Medium</span>;
    return <span className="px-2 py-0.5 rounded-full bg-red-100 text-red-700 text-xs">Low</span>;
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Entity Mappings</h1>
        <p className="text-gray-500">Review and manage entity to ticker mappings</p>
      </div>

      {/* Coverage Summary */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {coverage.slice(0, 4).map((cov) => (
          <div key={cov.source_id} className="card p-4">
            <div className="text-sm text-gray-500">{cov.source_name}</div>
            <div className="text-2xl font-bold text-gray-900">{cov.coverage_pct.toFixed(1)}%</div>
            <div className="text-xs text-gray-400">
              {cov.mapped_entities}/{cov.total_entities} mapped
            </div>
          </div>
        ))}
      </div>

      {/* Filters */}
      <div className="flex items-center justify-between">
        <div className="flex gap-2">
          {(['needs_review', 'approved', 'all'] as const).map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={clsx(
                'px-4 py-2 rounded-lg text-sm font-medium capitalize',
                filter === f ? 'bg-primary-100 text-primary-700' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              )}
            >
              {f.replace('_', ' ')}
            </button>
          ))}
        </div>

        {selectedMappings.length > 0 && (
          <button
            onClick={() => approveMutation.mutate(selectedMappings)}
            disabled={approveMutation.isPending}
            className="btn-primary flex items-center gap-2"
          >
            <Check className="h-4 w-4" />
            Bulk Approve ({selectedMappings.length})
          </button>
        )}
      </div>

      {/* Mappings Table */}
      {isLoading ? (
        <div className="flex items-center justify-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600" />
        </div>
      ) : mappings.length === 0 ? (
        <div className="card p-12 text-center">
          <Check className="h-12 w-12 text-success-500 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-900 mb-2">All caught up!</h3>
          <p className="text-gray-500">No mappings need review</p>
        </div>
      ) : (
        <div className="card overflow-hidden">
          <table className="w-full">
            <thead className="bg-gray-50 border-b">
              <tr>
                <th className="px-4 py-3 text-left">
                  <input
                    type="checkbox"
                    checked={selectedMappings.length === mappings.length}
                    onChange={selectAll}
                    className="rounded border-gray-300"
                  />
                </th>
                <th className="px-4 py-3 text-left text-sm font-medium text-gray-700">Source Entity</th>
                <th className="px-4 py-3 text-left text-sm font-medium text-gray-700">Suggested Ticker</th>
                <th className="px-4 py-3 text-left text-sm font-medium text-gray-700">Confidence</th>
                <th className="px-4 py-3 text-left text-sm font-medium text-gray-700">Alternatives</th>
                <th className="px-4 py-3 text-left text-sm font-medium text-gray-700">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {mappings.map((mapping) => (
                <tr key={mapping.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3">
                    <input
                      type="checkbox"
                      checked={selectedMappings.includes(mapping.id)}
                      onChange={() => toggleSelection(mapping.id)}
                      className="rounded border-gray-300"
                    />
                  </td>
                  <td className="px-4 py-3">
                    <div className="font-medium text-gray-900">{mapping.source_entity}</div>
                    <div className="text-xs text-gray-500">{mapping.source_type}</div>
                  </td>
                  <td className="px-4 py-3">
                    <span className="font-mono font-medium text-primary-600">{mapping.suggested_ticker}</span>
                  </td>
                  <td className="px-4 py-3">
                    {getConfidenceBadge(mapping.confidence_score)}
                    <span className="text-xs text-gray-500 ml-2">{(mapping.confidence_score * 100).toFixed(0)}%</span>
                  </td>
                  <td className="px-4 py-3">
                    {mapping.alternatives?.slice(0, 2).map((alt) => (
                      <span key={alt.ticker} className="text-xs text-gray-500 mr-2">
                        {alt.ticker} ({(alt.score * 100).toFixed(0)}%)
                      </span>
                    ))}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex gap-2">
                      <button
                        onClick={() => approveMutation.mutate([mapping.id])}
                        className="p-1.5 text-success-600 hover:bg-success-50 rounded"
                        title="Approve"
                      >
                        <Check className="h-4 w-4" />
                      </button>
                      <button
                        onClick={() => {
                          const reason = prompt('Rejection reason:');
                          if (reason) rejectMutation.mutate({ id: mapping.id, reason });
                        }}
                        className="p-1.5 text-danger-600 hover:bg-danger-50 rounded"
                        title="Reject"
                      >
                        <X className="h-4 w-4" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
