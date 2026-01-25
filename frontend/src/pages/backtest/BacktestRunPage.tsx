import { useState, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useQuery, useMutation } from '@tanstack/react-query';
import { Upload, Play, AlertTriangle, TrendingUp, Target, BarChart } from 'lucide-react';
import { LineChart, Line, BarChart as RechartsBarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { factorsApi, backtestApi } from '../../services/api';
import type { Factor, BacktestResult } from '../../types';
import clsx from 'clsx';
import { format } from 'date-fns';

export function BacktestRunPage() {
  const [searchParams] = useSearchParams();
  const preselectedFactor = searchParams.get('factor');
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [selectedFactor, setSelectedFactor] = useState(preselectedFactor || '');
  const [startDate, setStartDate] = useState('2020-01-01');
  const [endDate, setEndDate] = useState(format(new Date(), 'yyyy-MM-dd'));
  const [uploadedFile, setUploadedFile] = useState<File | null>(null);

  const { data: factorsData } = useQuery({
    queryKey: ['factors-list'],
    queryFn: () => factorsApi.getFactors(),
  });

  const factors: Factor[] = factorsData?.data?.factors || [];

  const backtestMutation = useMutation({
    mutationFn: () => {
      const formData = new FormData();
      formData.append('factor_id', selectedFactor);
      formData.append('start_date', startDate);
      formData.append('end_date', endDate);
      if (uploadedFile) {
        formData.append('returns_file', uploadedFile);
      }
      return backtestApi.runBacktest(formData);
    },
  });

  const result: BacktestResult | undefined = backtestMutation.data?.data;

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files?.[0]) {
      setUploadedFile(e.target.files[0]);
    }
  };

  const monthlyIcData = result?.monthly_ic
    ? result.monthly_ic.dates.map((date, idx) => ({
        date: date.slice(0, 7),
        ic: result.monthly_ic.values[idx],
      }))
    : [];

  const decileData = result?.decile_returns
    ? result.decile_returns.map((ret, idx) => ({
        decile: `D${idx + 1}`,
        return: ret * 100,
      }))
    : [];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Run Factor Backtest</h1>
        <p className="text-gray-500">Validate factor quality against your return data</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Configuration */}
        <div className="space-y-4">
          <div className="card p-5">
            <h2 className="font-semibold text-gray-900 mb-4">Configuration</h2>

            <div className="space-y-4">
              <div>
                <label className="label mb-1 block">Factor</label>
                <select
                  value={selectedFactor}
                  onChange={(e) => setSelectedFactor(e.target.value)}
                  className="select w-full"
                >
                  <option value="">Select a factor...</option>
                  {factors.map((factor) => (
                    <option key={factor.id} value={factor.id}>{factor.name}</option>
                  ))}
                </select>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="label mb-1 block">Start Date</label>
                  <input
                    type="date"
                    value={startDate}
                    onChange={(e) => setStartDate(e.target.value)}
                    className="input w-full"
                  />
                </div>
                <div>
                  <label className="label mb-1 block">End Date</label>
                  <input
                    type="date"
                    value={endDate}
                    onChange={(e) => setEndDate(e.target.value)}
                    className="input w-full"
                  />
                </div>
              </div>

              <div>
                <label className="label mb-2 block">Return Data (CSV)</label>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".csv"
                  onChange={handleFileChange}
                  className="hidden"
                />
                <button
                  onClick={() => fileInputRef.current?.click()}
                  className={clsx(
                    'w-full p-4 rounded-lg border-2 border-dashed text-center transition-colors',
                    uploadedFile
                      ? 'border-primary-500 bg-primary-50'
                      : 'border-gray-300 hover:border-gray-400'
                  )}
                >
                  <Upload className={clsx('h-6 w-6 mx-auto mb-2', uploadedFile ? 'text-primary-600' : 'text-gray-400')} />
                  <p className="text-sm font-medium text-gray-700">
                    {uploadedFile ? uploadedFile.name : 'Upload CSV file'}
                  </p>
                  <p className="text-xs text-gray-500 mt-1">
                    Format: ticker, date, return
                  </p>
                </button>
              </div>

              <button
                onClick={() => backtestMutation.mutate()}
                disabled={!selectedFactor || backtestMutation.isPending}
                className="btn-primary w-full flex items-center justify-center gap-2"
              >
                {backtestMutation.isPending ? (
                  <>
                    <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white" />
                    Running...
                  </>
                ) : (
                  <>
                    <Play className="h-4 w-4" />
                    Run Backtest
                  </>
                )}
              </button>
            </div>
          </div>
        </div>

        {/* Results */}
        <div className="lg:col-span-2 space-y-4">
          {result ? (
            <>
              {/* Metrics */}
              <div className="card p-5">
                <h2 className="font-semibold text-gray-900 mb-4">Performance Metrics</h2>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <div className="p-4 bg-gray-50 rounded-lg text-center">
                    <TrendingUp className="h-5 w-5 text-primary-600 mx-auto mb-2" />
                    <div className="text-2xl font-bold text-gray-900">
                      {(result.metrics.ic * 100).toFixed(2)}%
                    </div>
                    <div className="text-sm text-gray-500">IC</div>
                  </div>
                  <div className="p-4 bg-gray-50 rounded-lg text-center">
                    <BarChart className="h-5 w-5 text-primary-600 mx-auto mb-2" />
                    <div className="text-2xl font-bold text-gray-900">
                      {result.metrics.ir.toFixed(2)}
                    </div>
                    <div className="text-sm text-gray-500">IR</div>
                  </div>
                  <div className="p-4 bg-gray-50 rounded-lg text-center">
                    <div className={clsx(
                      'text-2xl font-bold',
                      Math.abs(result.metrics.t_stat) > 2 ? 'text-success-500' : 'text-gray-900'
                    )}>
                      {result.metrics.t_stat.toFixed(2)}
                    </div>
                    <div className="text-sm text-gray-500">T-Stat</div>
                  </div>
                  <div className="p-4 bg-gray-50 rounded-lg text-center">
                    <Target className="h-5 w-5 text-primary-600 mx-auto mb-2" />
                    <div className="text-2xl font-bold text-gray-900">
                      {(result.metrics.hit_rate * 100).toFixed(1)}%
                    </div>
                    <div className="text-sm text-gray-500">Hit Rate</div>
                  </div>
                </div>
              </div>

              {/* Survivorship Bias Warnings */}
              {result.survivorship_bias_warnings && result.survivorship_bias_warnings.length > 0 && (
                <div className="card p-4 bg-warning-50 border-warning-200">
                  <div className="flex items-center gap-2 text-warning-800 mb-2">
                    <AlertTriangle className="h-5 w-5" />
                    <span className="font-semibold">Survivorship Bias Warnings</span>
                  </div>
                  <ul className="list-disc list-inside text-sm text-warning-700">
                    {result.survivorship_bias_warnings.map((warning, idx) => (
                      <li key={idx}>{warning}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Decile Spread */}
              <div className="card p-5">
                <h3 className="font-semibold text-gray-900 mb-4">Decile Spread</h3>
                <div className="h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <RechartsBarChart data={decileData}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                      <XAxis dataKey="decile" tick={{ fontSize: 12 }} />
                      <YAxis tick={{ fontSize: 12 }} tickFormatter={(v) => `${v.toFixed(1)}%`} />
                      <Tooltip formatter={(value) => [`${(value as number).toFixed(2)}%`, 'Return']} />
                      <Bar
                        dataKey="return"
                        fill="#3b82f6"
                        radius={[4, 4, 0, 0]}
                      />
                    </RechartsBarChart>
                  </ResponsiveContainer>
                </div>
              </div>

              {/* Monthly IC */}
              <div className="card p-5">
                <h3 className="font-semibold text-gray-900 mb-4">Monthly IC Time Series</h3>
                <div className="h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={monthlyIcData}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                      <XAxis dataKey="date" tick={{ fontSize: 10 }} />
                      <YAxis tick={{ fontSize: 12 }} tickFormatter={(v) => `${(v * 100).toFixed(1)}%`} />
                      <Tooltip formatter={(value) => [`${((value as number) * 100).toFixed(2)}%`, 'IC']} />
                      <Line type="monotone" dataKey="ic" stroke="#3b82f6" strokeWidth={2} dot={false} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </div>
            </>
          ) : (
            <div className="card p-12 text-center">
              <TrendingUp className="h-12 w-12 text-gray-300 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-gray-900 mb-2">No Results Yet</h3>
              <p className="text-gray-500">Configure your backtest and click Run to see results</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
