import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Plus, Bell, BellOff, Trash2, Play, Settings, Clock, Zap } from 'lucide-react';
import { alertsApi } from '../../services/api';
import type { Alert } from '../../types';
import clsx from 'clsx';

export function AlertsListPage() {
  const queryClient = useQueryClient();
  const [filter, setFilter] = useState<'all' | 'enabled' | 'disabled'>('all');

  const { data: alertsData, isLoading } = useQuery({
    queryKey: ['alerts'],
    queryFn: () => alertsApi.getAlerts(),
  });

  const alerts: Alert[] = alertsData?.data?.alerts || [];

  const toggleMutation = useMutation({
    mutationFn: ({ alertId, enabled }: { alertId: string; enabled: boolean }) =>
      alertsApi.updateAlert(alertId, { enabled }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['alerts'] }),
  });

  const deleteMutation = useMutation({
    mutationFn: (alertId: string) => alertsApi.deleteAlert(alertId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['alerts'] }),
  });

  const testMutation = useMutation({
    mutationFn: (alertId: string) => alertsApi.testAlert(alertId),
  });

  const filteredAlerts = alerts.filter((alert) => {
    if (filter === 'enabled') return alert.enabled;
    if (filter === 'disabled') return !alert.enabled;
    return true;
  });

  const getAlertTypeIcon = (alert: Alert) => {
    if (alert.alert_type === 'anomaly') return <Zap className="h-4 w-4" />;
    if (alert.alert_type === 'event') return <Bell className="h-4 w-4" />;
    return <Settings className="h-4 w-4" />;
  };

  const getAlertTypeBadge = (alert: Alert) => {
    const type = alert.alert_type || 'threshold';
    const colors: Record<string, string> = {
      threshold: 'bg-blue-100 text-blue-700',
      anomaly: 'bg-purple-100 text-purple-700',
      event: 'bg-orange-100 text-orange-700',
    };
    return (
      <span className={clsx('px-2 py-0.5 rounded-full text-xs font-medium capitalize', colors[type])}>
        {type}
      </span>
    );
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">My Alerts</h1>
          <p className="text-gray-500">Manage your factor and event alerts</p>
        </div>
        <Link to="/alerts/create" className="btn-primary flex items-center gap-2">
          <Plus className="h-4 w-4" />
          Create Alert
        </Link>
      </div>

      {/* Filters */}
      <div className="flex gap-2">
        {(['all', 'enabled', 'disabled'] as const).map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={clsx(
              'px-4 py-2 rounded-lg text-sm font-medium transition-colors capitalize',
              filter === f
                ? 'bg-primary-100 text-primary-700'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            )}
          >
            {f}
          </button>
        ))}
      </div>

      {/* Alerts List */}
      {isLoading ? (
        <div className="flex items-center justify-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600" />
        </div>
      ) : filteredAlerts.length === 0 ? (
        <div className="card p-12 text-center">
          <Bell className="h-12 w-12 text-gray-300 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-900 mb-2">No alerts yet</h3>
          <p className="text-gray-500 mb-4">Create your first alert to get started</p>
          <Link to="/alerts/create" className="btn-primary">
            Create Alert
          </Link>
        </div>
      ) : (
        <div className="space-y-3">
          {filteredAlerts.map((alert) => (
            <div
              key={alert.id}
              className={clsx(
                'card p-4 flex items-center gap-4',
                !alert.enabled && 'opacity-60'
              )}
            >
              {/* Icon */}
              <div
                className={clsx(
                  'w-10 h-10 rounded-full flex items-center justify-center',
                  alert.enabled ? 'bg-primary-100 text-primary-600' : 'bg-gray-100 text-gray-400'
                )}
              >
                {getAlertTypeIcon(alert)}
              </div>

              {/* Info */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <h3 className="font-medium text-gray-900 truncate">{alert.name}</h3>
                  {getAlertTypeBadge(alert)}
                  {alert.digest_enabled && (
                    <span className="px-2 py-0.5 rounded-full bg-gray-100 text-gray-600 text-xs">
                      Digest
                    </span>
                  )}
                </div>
                <p className="text-sm text-gray-500 truncate">
                  {alert.factor_id} • {alert.direction} {alert.threshold_value} •{' '}
                  {alert.ticker_list.join(', ')}
                </p>
                {alert.quiet_hours_start && (
                  <p className="text-xs text-gray-400 flex items-center gap-1 mt-1">
                    <Clock className="h-3 w-3" />
                    Quiet hours: {alert.quiet_hours_start} - {alert.quiet_hours_end}
                  </p>
                )}
              </div>

              {/* Actions */}
              <div className="flex items-center gap-2">
                <button
                  onClick={() => testMutation.mutate(alert.id)}
                  disabled={testMutation.isPending}
                  className="p-2 text-gray-400 hover:text-primary-600 hover:bg-primary-50 rounded"
                  title="Test Alert"
                >
                  <Play className="h-4 w-4" />
                </button>
                <button
                  onClick={() =>
                    toggleMutation.mutate({ alertId: alert.id, enabled: !alert.enabled })
                  }
                  className={clsx(
                    'p-2 rounded',
                    alert.enabled
                      ? 'text-success-500 hover:bg-success-50'
                      : 'text-gray-400 hover:bg-gray-100'
                  )}
                  title={alert.enabled ? 'Disable' : 'Enable'}
                >
                  {alert.enabled ? (
                    <Bell className="h-4 w-4" />
                  ) : (
                    <BellOff className="h-4 w-4" />
                  )}
                </button>
                <button
                  onClick={() => {
                    if (confirm('Are you sure you want to delete this alert?')) {
                      deleteMutation.mutate(alert.id);
                    }
                  }}
                  className="p-2 text-gray-400 hover:text-danger-500 hover:bg-danger-50 rounded"
                  title="Delete"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
