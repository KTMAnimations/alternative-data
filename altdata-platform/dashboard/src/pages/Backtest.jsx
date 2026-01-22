import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'
import api from '../api/client'

function Backtest() {
  const queryClient = useQueryClient()
  const [showRunModal, setShowRunModal] = useState(false)
  const [selectedJob, setSelectedJob] = useState(null)

  // Fetch backtest jobs
  const { data: jobsData, isLoading: jobsLoading } = useQuery({
    queryKey: ['backtestJobs'],
    queryFn: () => api.get('/api/v1/backtest/jobs?limit=20').then(res => res.data),
    refetchInterval: 5000, // Poll for updates
  })

  // Fetch selected job result
  const { data: resultData, isLoading: resultLoading } = useQuery({
    queryKey: ['backtestResult', selectedJob],
    queryFn: () => api.get(`/api/v1/backtest/results/${selectedJob}`).then(res => res.data),
    enabled: !!selectedJob,
  })

  // Fetch time series for selected job
  const { data: timeseriesData } = useQuery({
    queryKey: ['backtestTimeseries', selectedJob],
    queryFn: () => api.get(`/api/v1/backtest/results/${selectedJob}/timeseries`).then(res => res.data),
    enabled: !!selectedJob && resultData?.status === 'complete',
  })

  // Delete job mutation
  const deleteMutation = useMutation({
    mutationFn: (jobId) => api.delete(`/api/v1/backtest/jobs/${jobId}`),
    onSuccess: () => {
      queryClient.invalidateQueries(['backtestJobs'])
      if (selectedJob) setSelectedJob(null)
    }
  })

  const statusColors = {
    running: 'bg-yellow-100 text-yellow-800',
    complete: 'bg-green-100 text-green-800',
    failed: 'bg-red-100 text-red-800',
  }

  // Prepare chart data
  const chartData = timeseriesData?.dates?.map((date, i) => ({
    date: date,
    returns: (timeseriesData.cumulative_returns[i] - 1) * 100,
  })) || []

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Backtesting</h1>
          <p className="mt-1 text-sm text-gray-500">
            Evaluate factor performance against historical returns
          </p>
        </div>
        <button
          onClick={() => setShowRunModal(true)}
          className="px-4 py-2 text-sm font-medium text-white bg-indigo-600 rounded-md hover:bg-indigo-700"
        >
          Run Backtest
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Jobs List */}
        <div className="lg:col-span-1">
          <div className="bg-white shadow rounded-lg">
            <div className="px-4 py-5 sm:px-6 border-b">
              <h2 className="text-lg font-medium text-gray-900">Backtest Jobs</h2>
            </div>
            <div className="divide-y divide-gray-200 max-h-96 overflow-y-auto">
              {jobsLoading ? (
                <div className="p-4 text-center text-gray-500">Loading...</div>
              ) : jobsData?.jobs?.length === 0 ? (
                <div className="p-4 text-center text-gray-500">
                  No backtests yet. Run one to get started.
                </div>
              ) : (
                jobsData?.jobs?.map((job) => (
                  <div
                    key={job.job_id}
                    onClick={() => setSelectedJob(job.job_id)}
                    className={`p-4 cursor-pointer hover:bg-gray-50 ${
                      selectedJob === job.job_id ? 'bg-indigo-50' : ''
                    }`}
                  >
                    <div className="flex justify-between items-start">
                      <div>
                        <p className="text-sm font-medium text-gray-900">
                          {job.factor_name || 'Unknown Factor'}
                        </p>
                        <p className="text-xs text-gray-500">
                          {job.submitted_at ? new Date(job.submitted_at).toLocaleString() : ''}
                        </p>
                      </div>
                      <span className={`px-2 py-1 text-xs font-medium rounded ${statusColors[job.status]}`}>
                        {job.status}
                      </span>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

        {/* Results */}
        <div className="lg:col-span-2 space-y-6">
          {selectedJob ? (
            resultLoading ? (
              <div className="bg-white shadow rounded-lg p-8 text-center text-gray-500">
                Loading results...
              </div>
            ) : resultData?.status === 'running' ? (
              <div className="bg-white shadow rounded-lg p-8 text-center">
                <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600 mx-auto"></div>
                <p className="mt-4 text-gray-500">Backtest running...</p>
              </div>
            ) : resultData?.status === 'failed' ? (
              <div className="bg-white shadow rounded-lg p-8 text-center">
                <p className="text-red-600">Backtest failed</p>
                <p className="mt-2 text-sm text-gray-500">{resultData?.error}</p>
              </div>
            ) : (
              <>
                {/* Metrics Grid */}
                <div className="bg-white shadow rounded-lg p-6">
                  <h3 className="text-lg font-medium text-gray-900 mb-4">Performance Metrics</h3>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <MetricCard
                      label="Sharpe Ratio"
                      value={resultData?.sharpe_ratio?.toFixed(2)}
                      good={resultData?.sharpe_ratio > 1}
                    />
                    <MetricCard
                      label="Total Return"
                      value={`${(resultData?.total_return * 100)?.toFixed(1)}%`}
                      good={resultData?.total_return > 0}
                    />
                    <MetricCard
                      label="Max Drawdown"
                      value={`${(resultData?.max_drawdown * 100)?.toFixed(1)}%`}
                      good={resultData?.max_drawdown > -0.2}
                    />
                    <MetricCard
                      label="Volatility"
                      value={`${(resultData?.volatility * 100)?.toFixed(1)}%`}
                    />
                    <MetricCard
                      label="IC Mean"
                      value={resultData?.ic_mean?.toFixed(3)}
                      good={resultData?.ic_mean > 0.03}
                    />
                    <MetricCard
                      label="IC IR"
                      value={resultData?.ic_ir?.toFixed(2)}
                      good={resultData?.ic_ir > 0.5}
                    />
                    <MetricCard
                      label="Win Rate"
                      value={`${(resultData?.win_rate * 100)?.toFixed(0)}%`}
                      good={resultData?.win_rate > 0.5}
                    />
                    <MetricCard
                      label="Turnover"
                      value={resultData?.turnover?.toFixed(2)}
                    />
                  </div>
                </div>

                {/* Returns Chart */}
                {chartData.length > 0 && (
                  <div className="bg-white shadow rounded-lg p-6">
                    <h3 className="text-lg font-medium text-gray-900 mb-4">Cumulative Returns</h3>
                    <div className="h-64">
                      <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={chartData}>
                          <CartesianGrid strokeDasharray="3 3" />
                          <XAxis
                            dataKey="date"
                            tick={{ fontSize: 10 }}
                            tickFormatter={(val) => val.slice(5)}
                          />
                          <YAxis
                            tick={{ fontSize: 10 }}
                            tickFormatter={(val) => `${val.toFixed(0)}%`}
                          />
                          <Tooltip
                            formatter={(val) => [`${val.toFixed(2)}%`, 'Return']}
                            labelFormatter={(label) => `Date: ${label}`}
                          />
                          <Legend />
                          <Line
                            type="monotone"
                            dataKey="returns"
                            stroke="#4F46E5"
                            dot={false}
                            name="Cumulative Return"
                          />
                        </LineChart>
                      </ResponsiveContainer>
                    </div>
                  </div>
                )}

                {/* Job Info */}
                <div className="bg-white shadow rounded-lg p-6">
                  <h3 className="text-lg font-medium text-gray-900 mb-4">Configuration</h3>
                  <dl className="grid grid-cols-2 gap-4 text-sm">
                    <div>
                      <dt className="text-gray-500">Factor</dt>
                      <dd className="font-medium">{resultData?.factor_name}</dd>
                    </div>
                    <div>
                      <dt className="text-gray-500">Universe Size</dt>
                      <dd className="font-medium">{resultData?.universe_size} stocks</dd>
                    </div>
                    <div>
                      <dt className="text-gray-500">Period</dt>
                      <dd className="font-medium">{resultData?.start_date} to {resultData?.end_date}</dd>
                    </div>
                    <div>
                      <dt className="text-gray-500">Rebalance</dt>
                      <dd className="font-medium capitalize">{resultData?.rebalance_freq}</dd>
                    </div>
                    <div>
                      <dt className="text-gray-500">Strategy</dt>
                      <dd className="font-medium">{resultData?.long_short ? 'Long-Short' : 'Long Only'}</dd>
                    </div>
                    <div>
                      <dt className="text-gray-500">Positions</dt>
                      <dd className="font-medium">{resultData?.top_n} per side</dd>
                    </div>
                  </dl>
                  <div className="mt-4 pt-4 border-t">
                    <button
                      onClick={() => deleteMutation.mutate(selectedJob)}
                      className="text-sm text-red-600 hover:text-red-800"
                    >
                      Delete this backtest
                    </button>
                  </div>
                </div>
              </>
            )
          ) : (
            <div className="bg-white shadow rounded-lg p-8 text-center text-gray-500">
              Select a backtest job to view results
            </div>
          )}
        </div>
      </div>

      {/* Run Backtest Modal */}
      {showRunModal && (
        <RunBacktestModal
          onClose={() => setShowRunModal(false)}
          onSuccess={(jobId) => {
            setShowRunModal(false)
            setSelectedJob(jobId)
            queryClient.invalidateQueries(['backtestJobs'])
          }}
        />
      )}
    </div>
  )
}

function MetricCard({ label, value, good }) {
  return (
    <div className="bg-gray-50 rounded-lg p-3">
      <dt className="text-xs text-gray-500">{label}</dt>
      <dd className={`text-lg font-semibold ${
        good === true ? 'text-green-600' : good === false ? 'text-red-600' : 'text-gray-900'
      }`}>
        {value ?? '-'}
      </dd>
    </div>
  )
}

function RunBacktestModal({ onClose, onSuccess }) {
  const [formData, setFormData] = useState({
    factor_name: '',
    universe: '',
    start_date: '',
    end_date: '',
    rebalance_freq: 'weekly',
    long_short: true,
    top_n: 10,
  })

  const runMutation = useMutation({
    mutationFn: (data) => api.post('/api/v1/backtest/run', data),
    onSuccess: (response) => onSuccess(response.data.job_id)
  })

  const handleSubmit = (e) => {
    e.preventDefault()
    const universeList = formData.universe.split(',').map(s => s.trim()).filter(Boolean)
    runMutation.mutate({
      ...formData,
      universe: universeList,
      top_n: parseInt(formData.top_n),
    })
  }

  return (
    <div className="fixed inset-0 bg-gray-500 bg-opacity-75 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl max-w-lg w-full mx-4">
        <div className="px-4 py-5 sm:px-6 border-b">
          <h3 className="text-lg font-medium text-gray-900">Run Backtest</h3>
        </div>
        <form onSubmit={handleSubmit} className="px-4 py-5 sm:p-6 space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700">Factor Name</label>
            <input
              type="text"
              required
              placeholder="e.g., insider_transaction_momentum"
              value={formData.factor_name}
              onChange={(e) => setFormData({ ...formData, factor_name: e.target.value })}
              className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700">Universe (comma-separated tickers)</label>
            <textarea
              required
              placeholder="AAPL, MSFT, GOOGL, AMZN, META, NVDA, TSLA"
              value={formData.universe}
              onChange={(e) => setFormData({ ...formData, universe: e.target.value })}
              rows={3}
              className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700">Start Date</label>
              <input
                type="date"
                required
                value={formData.start_date}
                onChange={(e) => setFormData({ ...formData, start_date: e.target.value })}
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700">End Date</label>
              <input
                type="date"
                required
                value={formData.end_date}
                onChange={(e) => setFormData({ ...formData, end_date: e.target.value })}
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
              />
            </div>
          </div>
          <div className="grid grid-cols-3 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700">Rebalance</label>
              <select
                value={formData.rebalance_freq}
                onChange={(e) => setFormData({ ...formData, rebalance_freq: e.target.value })}
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
              >
                <option value="daily">Daily</option>
                <option value="weekly">Weekly</option>
                <option value="monthly">Monthly</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700">Strategy</label>
              <select
                value={formData.long_short.toString()}
                onChange={(e) => setFormData({ ...formData, long_short: e.target.value === 'true' })}
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
              >
                <option value="true">Long-Short</option>
                <option value="false">Long Only</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700">Top N</label>
              <input
                type="number"
                min="1"
                max="50"
                value={formData.top_n}
                onChange={(e) => setFormData({ ...formData, top_n: e.target.value })}
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
              />
            </div>
          </div>
          <div className="flex justify-end space-x-3 pt-4">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={runMutation.isPending}
              className="px-4 py-2 text-sm font-medium text-white bg-indigo-600 rounded-md hover:bg-indigo-700 disabled:opacity-50"
            >
              {runMutation.isPending ? 'Starting...' : 'Run Backtest'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

export default Backtest
