import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Calendar, Sun } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts';
import { factorsApi, backtestApi } from '../../services/api';
import type { Factor, SeasonalityAnalysis } from '../../types';
import clsx from 'clsx';

const DAYS_OF_WEEK = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'];
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

export function SeasonalityPage() {
  const [selectedFactor, setSelectedFactor] = useState('');

  const { data: factorsData } = useQuery({
    queryKey: ['factors-list'],
    queryFn: () => factorsApi.getFactors(),
  });

  const factors: Factor[] = factorsData?.data?.factors || [];

  const { data: seasonalityData, isLoading } = useQuery({
    queryKey: ['seasonality', selectedFactor],
    queryFn: () => backtestApi.getSeasonality(selectedFactor),
    enabled: !!selectedFactor,
  });

  const seasonality: SeasonalityAnalysis | undefined = seasonalityData?.data;

  const dayOfWeekData = seasonality?.day_of_week_ic
    ? DAYS_OF_WEEK.map((day) => ({
        day,
        ic: (seasonality.day_of_week_ic[day.toLowerCase()] || 0) * 100,
      }))
    : [];

  const monthlyData = seasonality?.monthly_ic
    ? MONTHS.map((month, idx) => ({
        month,
        ic: (seasonality.monthly_ic[String(idx + 1)] || 0) * 100,
      }))
    : [];

  const getBarColor = (value: number) => (value >= 0 ? '#22c55e' : '#ef4444');

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Seasonality Analysis</h1>
        <p className="text-gray-500">Understand seasonal patterns in factor performance</p>
      </div>

      {/* Factor Selection */}
      <div className="card p-5">
        <label className="label mb-2 block">Select Factor</label>
        <select
          value={selectedFactor}
          onChange={(e) => setSelectedFactor(e.target.value)}
          className="select w-full max-w-md"
        >
          <option value="">Select a factor...</option>
          {factors.map((factor) => (
            <option key={factor.id} value={factor.id}>{factor.name}</option>
          ))}
        </select>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600" />
        </div>
      ) : seasonality ? (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Day of Week */}
          <div className="card p-5">
            <h3 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
              <Calendar className="h-5 w-5" />
              Day of Week IC
            </h3>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={dayOfWeekData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                  <XAxis dataKey="day" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 12 }} tickFormatter={(v) => `${v.toFixed(1)}%`} />
                  <Tooltip formatter={(value) => [`${(value as number).toFixed(2)}%`, 'IC']} />
                  <Bar dataKey="ic" radius={[4, 4, 0, 0]}>
                    {dayOfWeekData.map((entry, index) => (
                      <Cell key={index} fill={getBarColor(entry.ic)} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Monthly */}
          <div className="card p-5">
            <h3 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
              <Sun className="h-5 w-5" />
              Monthly IC
            </h3>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={monthlyData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                  <XAxis dataKey="month" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 12 }} tickFormatter={(v) => `${v.toFixed(1)}%`} />
                  <Tooltip formatter={(value) => [`${(value as number).toFixed(2)}%`, 'IC']} />
                  <Bar dataKey="ic" radius={[4, 4, 0, 0]}>
                    {monthlyData.map((entry, index) => (
                      <Cell key={index} fill={getBarColor(entry.ic)} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Holiday Effects */}
          {seasonality.holiday_effects && seasonality.holiday_effects.length > 0 && (
            <div className="card p-5">
              <h3 className="font-semibold text-gray-900 mb-4">Holiday Effects</h3>
              <div className="space-y-3">
                {seasonality.holiday_effects.map((effect, idx) => (
                  <div key={idx} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                    <span className="font-medium text-gray-900">{effect.holiday}</span>
                    <span className={clsx(
                      'font-semibold',
                      effect.ic_impact >= 0 ? 'text-success-500' : 'text-danger-500'
                    )}>
                      {effect.ic_impact >= 0 ? '+' : ''}{(effect.ic_impact * 100).toFixed(2)}%
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Event Patterns */}
          {seasonality.event_patterns && seasonality.event_patterns.length > 0 && (
            <div className="card p-5">
              <h3 className="font-semibold text-gray-900 mb-4">Event-Based Patterns</h3>
              <div className="space-y-3">
                {seasonality.event_patterns.map((pattern, idx) => (
                  <div key={idx} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                    <span className="font-medium text-gray-900">{pattern.event}</span>
                    <span className={clsx(
                      'font-semibold',
                      pattern.ic_impact >= 0 ? 'text-success-500' : 'text-danger-500'
                    )}>
                      {pattern.ic_impact >= 0 ? '+' : ''}{(pattern.ic_impact * 100).toFixed(2)}%
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      ) : (
        <div className="card p-12 text-center">
          <Calendar className="h-12 w-12 text-gray-300 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-900 mb-2">Select a Factor</h3>
          <p className="text-gray-500">Choose a factor to analyze its seasonality patterns</p>
        </div>
      )}
    </div>
  );
}
