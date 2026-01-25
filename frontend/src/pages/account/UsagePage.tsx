import { useQuery } from '@tanstack/react-query';
import { BarChart3, TrendingUp, Calendar, AlertTriangle } from 'lucide-react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, BarChart, Bar } from 'recharts';
import { userApi } from '../../services/api';
import type { UserUsage } from '../../types';
import clsx from 'clsx';
import { format, subDays } from 'date-fns';

export function UsagePage() {
  const { data: usageData, isLoading } = useQuery({
    queryKey: ['user-usage'],
    queryFn: () => userApi.getUsage(),
  });

  const usage: UserUsage | undefined = usageData?.data;

  // Generate mock daily usage data for chart
  const dailyUsageData = Array.from({ length: 30 }, (_, i) => ({
    date: format(subDays(new Date(), 29 - i), 'MMM d'),
    api_calls: Math.floor(Math.random() * 500) + 100,
    data_downloaded: Math.floor(Math.random() * 50) + 10,
  }));

  // Generate endpoint breakdown data
  const endpointData = [
    { endpoint: '/factors', calls: 2450, pct: 35 },
    { endpoint: '/catalog', calls: 1820, pct: 26 },
    { endpoint: '/backtest', calls: 1190, pct: 17 },
    { endpoint: '/alerts', calls: 840, pct: 12 },
    { endpoint: '/geo', calls: 700, pct: 10 },
  ];

  const getUsagePercent = (used: number, limit: number) => {
    return Math.min((used / limit) * 100, 100);
  };

  const getProgressColor = (percent: number) => {
    if (percent >= 90) return 'bg-danger-500';
    if (percent >= 75) return 'bg-warning-500';
    return 'bg-primary-500';
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600" />
      </div>
    );
  }

  const apiPercent = usage ? getUsagePercent(usage.api_calls_used, usage.api_calls_limit) : 0;
  const dataPercent = usage ? getUsagePercent(usage.data_downloaded_mb, usage.data_limit_mb) : 0;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Usage Dashboard</h1>
        <p className="text-gray-500">Monitor your API usage and data consumption</p>
      </div>

      {/* Usage Overview */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* API Calls */}
        <div className="card p-5">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <BarChart3 className="h-5 w-5 text-primary-500" />
              <h3 className="font-semibold text-gray-900">API Calls</h3>
            </div>
            <span className="text-sm text-gray-500">This billing period</span>
          </div>

          <div className="mb-2">
            <div className="flex justify-between text-sm mb-1">
              <span className="font-medium text-gray-700">
                {usage?.api_calls_used.toLocaleString()} / {usage?.api_calls_limit.toLocaleString()}
              </span>
              <span className={clsx(
                'font-medium',
                apiPercent >= 90 ? 'text-danger-600' : apiPercent >= 75 ? 'text-warning-600' : 'text-gray-600'
              )}>
                {apiPercent.toFixed(1)}%
              </span>
            </div>
            <div className="w-full h-3 bg-gray-200 rounded-full overflow-hidden">
              <div
                className={clsx('h-full rounded-full transition-all', getProgressColor(apiPercent))}
                style={{ width: `${apiPercent}%` }}
              />
            </div>
          </div>

          {apiPercent >= 75 && (
            <div className="flex items-center gap-2 text-warning-600 text-sm mt-3">
              <AlertTriangle className="h-4 w-4" />
              <span>Approaching limit. Consider upgrading your plan.</span>
            </div>
          )}
        </div>

        {/* Data Downloaded */}
        <div className="card p-5">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <TrendingUp className="h-5 w-5 text-success-500" />
              <h3 className="font-semibold text-gray-900">Data Downloaded</h3>
            </div>
            <span className="text-sm text-gray-500">This billing period</span>
          </div>

          <div className="mb-2">
            <div className="flex justify-between text-sm mb-1">
              <span className="font-medium text-gray-700">
                {usage?.data_downloaded_mb.toLocaleString()} MB / {usage?.data_limit_mb.toLocaleString()} MB
              </span>
              <span className={clsx(
                'font-medium',
                dataPercent >= 90 ? 'text-danger-600' : dataPercent >= 75 ? 'text-warning-600' : 'text-gray-600'
              )}>
                {dataPercent.toFixed(1)}%
              </span>
            </div>
            <div className="w-full h-3 bg-gray-200 rounded-full overflow-hidden">
              <div
                className={clsx('h-full rounded-full transition-all', getProgressColor(dataPercent))}
                style={{ width: `${dataPercent}%` }}
              />
            </div>
          </div>

          {dataPercent >= 75 && (
            <div className="flex items-center gap-2 text-warning-600 text-sm mt-3">
              <AlertTriangle className="h-4 w-4" />
              <span>High data usage. Consider optimizing queries.</span>
            </div>
          )}
        </div>
      </div>

      {/* Current Plan */}
      <div className="card p-5">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="font-semibold text-gray-900 mb-1">Current Plan: {usage?.tier_name || 'Free'}</h3>
            <p className="text-sm text-gray-500">
              Billing period: {usage?.billing_period_start && format(new Date(usage.billing_period_start), 'MMM d')} - {usage?.billing_period_end && format(new Date(usage.billing_period_end), 'MMM d, yyyy')}
            </p>
          </div>
          <a href="/account/upgrade" className="btn-primary">
            Upgrade Plan
          </a>
        </div>
      </div>

      {/* Usage Over Time */}
      <div className="card p-5">
        <h3 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
          <Calendar className="h-5 w-5" />
          Daily API Usage (Last 30 Days)
        </h3>
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={dailyUsageData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
              <XAxis dataKey="date" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 12 }} />
              <Tooltip />
              <Area
                type="monotone"
                dataKey="api_calls"
                stroke="#3b82f6"
                fill="#3b82f6"
                fillOpacity={0.2}
                name="API Calls"
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Endpoint Breakdown */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="card p-5">
          <h3 className="font-semibold text-gray-900 mb-4">Usage by Endpoint</h3>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={endpointData} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis type="number" tick={{ fontSize: 12 }} />
                <YAxis type="category" dataKey="endpoint" tick={{ fontSize: 11 }} width={80} />
                <Tooltip formatter={(value) => [(value as number).toLocaleString(), 'Calls']} />
                <Bar dataKey="calls" fill="#3b82f6" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="card p-5">
          <h3 className="font-semibold text-gray-900 mb-4">Top Endpoints</h3>
          <div className="space-y-4">
            {endpointData.map((endpoint) => (
              <div key={endpoint.endpoint}>
                <div className="flex justify-between text-sm mb-1">
                  <span className="font-medium text-gray-700">{endpoint.endpoint}</span>
                  <span className="text-gray-500">{endpoint.calls.toLocaleString()} calls ({endpoint.pct}%)</span>
                </div>
                <div className="w-full h-2 bg-gray-200 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-primary-500 rounded-full"
                    style={{ width: `${endpoint.pct}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Usage Tips */}
      <div className="card p-5 bg-blue-50 border-blue-200">
        <h3 className="font-semibold text-blue-900 mb-3">Tips to Optimize Usage</h3>
        <ul className="space-y-2 text-sm text-blue-800">
          <li>• Use date range filters to request only the data you need</li>
          <li>• Cache frequently accessed data locally when possible</li>
          <li>• Use bulk endpoints instead of making multiple individual requests</li>
          <li>• Set up webhooks for real-time updates instead of polling</li>
          <li>• Consider using compressed formats (Parquet) for large data downloads</li>
        </ul>
      </div>
    </div>
  );
}
