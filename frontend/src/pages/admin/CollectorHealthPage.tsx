import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { RefreshCw, CheckCircle, AlertTriangle, XCircle, Clock, Play } from 'lucide-react';
import { adminApi } from '../../services/api';
import type { CollectorHealth } from '../../types';
import clsx from 'clsx';
import { formatDistanceToNow } from 'date-fns';

export function CollectorHealthPage() {
  const queryClient = useQueryClient();

  const { data: healthData, isLoading, refetch } = useQuery({
    queryKey: ['collector-health'],
    queryFn: () => adminApi.getCollectorHealth(),
    refetchInterval: 30000, // Auto-refresh every 30s
  });

  const collectors: CollectorHealth[] = healthData?.data?.collectors || [];

  const triggerMutation = useMutation({
    mutationFn: (collectorId: string) => adminApi.triggerCollector(collectorId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['collector-health'] }),
  });

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'healthy':
        return <CheckCircle className="h-5 w-5 text-success-500" />;
      case 'degraded':
        return <AlertTriangle className="h-5 w-5 text-warning-500" />;
      case 'down':
        return <XCircle className="h-5 w-5 text-danger-500" />;
      default:
        return null;
    }
  };

  const getStatusBadge = (status: string) => {
    const colors: Record<string, string> = {
      healthy: 'bg-green-100 text-green-700',
      degraded: 'bg-yellow-100 text-yellow-700',
      down: 'bg-red-100 text-red-700',
    };
    return (
      <span className={clsx('px-2 py-1 rounded-full text-xs font-medium capitalize', colors[status])}>
        {status}
      </span>
    );
  };

  const healthyCount = collectors.filter((c) => c.status === 'healthy').length;
  const degradedCount = collectors.filter((c) => c.status === 'degraded').length;
  const downCount = collectors.filter((c) => c.status === 'down').length;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Collector Health</h1>
          <p className="text-gray-500">Monitor data collector status and freshness</p>
        </div>
        <button onClick={() => refetch()} className="btn-outline flex items-center gap-2">
          <RefreshCw className="h-4 w-4" />
          Refresh
        </button>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-3 gap-4">
        <div className="card p-4 flex items-center gap-4">
          <div className="w-12 h-12 rounded-full bg-success-100 flex items-center justify-center">
            <CheckCircle className="h-6 w-6 text-success-600" />
          </div>
          <div>
            <div className="text-2xl font-bold text-success-600">{healthyCount}</div>
            <div className="text-sm text-gray-500">Healthy</div>
          </div>
        </div>
        <div className="card p-4 flex items-center gap-4">
          <div className="w-12 h-12 rounded-full bg-warning-100 flex items-center justify-center">
            <AlertTriangle className="h-6 w-6 text-warning-600" />
          </div>
          <div>
            <div className="text-2xl font-bold text-warning-600">{degradedCount}</div>
            <div className="text-sm text-gray-500">Degraded</div>
          </div>
        </div>
        <div className="card p-4 flex items-center gap-4">
          <div className="w-12 h-12 rounded-full bg-danger-100 flex items-center justify-center">
            <XCircle className="h-6 w-6 text-danger-600" />
          </div>
          <div>
            <div className="text-2xl font-bold text-danger-600">{downCount}</div>
            <div className="text-sm text-gray-500">Down</div>
          </div>
        </div>
      </div>

      {/* Collectors List */}
      {isLoading ? (
        <div className="flex items-center justify-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600" />
        </div>
      ) : (
        <div className="card overflow-hidden">
          <table className="w-full">
            <thead className="bg-gray-50 border-b">
              <tr>
                <th className="px-4 py-3 text-left text-sm font-medium text-gray-700">Collector</th>
                <th className="px-4 py-3 text-left text-sm font-medium text-gray-700">Status</th>
                <th className="px-4 py-3 text-left text-sm font-medium text-gray-700">Last Success</th>
                <th className="px-4 py-3 text-left text-sm font-medium text-gray-700">Freshness</th>
                <th className="px-4 py-3 text-left text-sm font-medium text-gray-700">Errors (24h)</th>
                <th className="px-4 py-3 text-left text-sm font-medium text-gray-700">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {collectors.map((collector) => (
                <tr key={collector.collector_id} className="hover:bg-gray-50">
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-3">
                      {getStatusIcon(collector.status)}
                      <div>
                        <div className="font-medium text-gray-900">{collector.name}</div>
                        <div className="text-xs text-gray-500">{collector.collector_id}</div>
                      </div>
                    </div>
                  </td>
                  <td className="px-4 py-3">{getStatusBadge(collector.status)}</td>
                  <td className="px-4 py-3 text-sm text-gray-600">
                    {formatDistanceToNow(new Date(collector.last_success), { addSuffix: true })}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <Clock className="h-4 w-4 text-gray-400" />
                      <span className={clsx(
                        'text-sm',
                        collector.sla_breach ? 'text-danger-600 font-medium' : 'text-gray-600'
                      )}>
                        {collector.current_freshness_hours.toFixed(1)}h
                      </span>
                      <span className="text-xs text-gray-400">/ {collector.freshness_sla_hours}h SLA</span>
                    </div>
                    {collector.sla_breach && (
                      <span className="text-xs text-danger-600">SLA Breach!</span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <span className={clsx(
                      'text-sm',
                      collector.error_count_24h > 5 ? 'text-danger-600 font-medium' : 'text-gray-600'
                    )}>
                      {collector.error_count_24h}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <button
                      onClick={() => triggerMutation.mutate(collector.collector_id)}
                      disabled={triggerMutation.isPending}
                      className="p-2 text-primary-600 hover:bg-primary-50 rounded"
                      title="Manual Trigger"
                    >
                      <Play className="h-4 w-4" />
                    </button>
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
