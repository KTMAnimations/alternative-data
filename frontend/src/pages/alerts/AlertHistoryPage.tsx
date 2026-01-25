import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Bell, Check, CheckCheck, Calendar } from 'lucide-react';
import { alertsApi } from '../../services/api';
import type { AlertHistory } from '../../types';
import clsx from 'clsx';
import { format, formatDistanceToNow } from 'date-fns';

export function AlertHistoryPage() {
  const queryClient = useQueryClient();
  const [filter, setFilter] = useState<'all' | 'unread'>('all');
  const [dateRange, setDateRange] = useState('7d');

  const { data: historyData, isLoading } = useQuery({
    queryKey: ['alert-history'],
    queryFn: () => alertsApi.getAlertHistory(),
  });

  const history: AlertHistory[] = historyData?.data?.history || [];

  const markReadMutation = useMutation({
    mutationFn: (ids: string[]) =>
      Promise.all(ids.map((id) => alertsApi.updateAlert(id, {}))),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['alert-history'] }),
  });

  const filteredHistory = history.filter((item) => {
    if (filter === 'unread') return !item.read;
    return true;
  });

  const unreadCount = history.filter((h) => !h.read).length;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Alert History</h1>
          <p className="text-gray-500">View past alert triggers and notifications</p>
        </div>
        {unreadCount > 0 && (
          <button
            onClick={() => markReadMutation.mutate(history.filter((h) => !h.read).map((h) => h.id))}
            className="btn-outline flex items-center gap-2"
          >
            <CheckCheck className="h-4 w-4" />
            Mark all as read
          </button>
        )}
      </div>

      {/* Filters */}
      <div className="flex items-center justify-between">
        <div className="flex gap-2">
          <button
            onClick={() => setFilter('all')}
            className={clsx(
              'px-4 py-2 rounded-lg text-sm font-medium',
              filter === 'all' ? 'bg-primary-100 text-primary-700' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            )}
          >
            All
          </button>
          <button
            onClick={() => setFilter('unread')}
            className={clsx(
              'px-4 py-2 rounded-lg text-sm font-medium flex items-center gap-2',
              filter === 'unread' ? 'bg-primary-100 text-primary-700' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            )}
          >
            Unread
            {unreadCount > 0 && (
              <span className="px-1.5 py-0.5 rounded-full bg-danger-500 text-white text-xs">
                {unreadCount}
              </span>
            )}
          </button>
        </div>

        <div className="flex items-center gap-2">
          <Calendar className="h-4 w-4 text-gray-400" />
          <select
            value={dateRange}
            onChange={(e) => setDateRange(e.target.value)}
            className="select"
          >
            <option value="1d">Last 24 hours</option>
            <option value="7d">Last 7 days</option>
            <option value="30d">Last 30 days</option>
            <option value="all">All time</option>
          </select>
        </div>
      </div>

      {/* History List */}
      {isLoading ? (
        <div className="flex items-center justify-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600" />
        </div>
      ) : filteredHistory.length === 0 ? (
        <div className="card p-12 text-center">
          <Bell className="h-12 w-12 text-gray-300 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-900 mb-2">No alerts triggered</h3>
          <p className="text-gray-500">
            {filter === 'unread' ? 'All alerts have been read' : 'Your alert history will appear here'}
          </p>
        </div>
      ) : (
        <div className="space-y-2">
          {filteredHistory.map((item) => (
            <div
              key={item.id}
              className={clsx(
                'card p-4 flex items-center gap-4',
                !item.read && 'border-l-4 border-l-primary-500 bg-primary-50/30'
              )}
            >
              {/* Status Icon */}
              <div
                className={clsx(
                  'w-10 h-10 rounded-full flex items-center justify-center',
                  item.read ? 'bg-gray-100' : 'bg-primary-100'
                )}
              >
                <Bell className={clsx('h-5 w-5', item.read ? 'text-gray-400' : 'text-primary-600')} />
              </div>

              {/* Info */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <span className="font-medium text-gray-900">{item.ticker}</span>
                  <span className="text-gray-500">•</span>
                  <span className="text-sm text-gray-600">
                    Value: {item.factor_value.toFixed(4)} (threshold: {item.threshold_value.toFixed(4)})
                  </span>
                </div>
                <p className="text-sm text-gray-500">
                  {formatDistanceToNow(new Date(item.triggered_at), { addSuffix: true })}
                  <span className="mx-2">•</span>
                  {format(new Date(item.triggered_at), 'MMM d, yyyy h:mm a')}
                </p>
              </div>

              {/* Read Status */}
              <div className="flex items-center gap-2">
                {item.notification_sent && (
                  <span className="text-xs text-success-500 flex items-center gap-1">
                    <Check className="h-3 w-3" />
                    Notified
                  </span>
                )}
                {!item.read && (
                  <span className="w-2 h-2 rounded-full bg-primary-500" />
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
