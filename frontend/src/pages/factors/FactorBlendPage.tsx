import { useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { Plus, X, Sliders, Save, Loader2, CheckCircle } from 'lucide-react';
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend } from 'recharts';
import { factorsApi } from '../../services/api';
import type { Factor, BlendResult } from '../../types';
import clsx from 'clsx';

const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4'];

const OBJECTIVES = [
  { id: 'max_ic', label: 'Maximize IC', description: 'Optimize for highest information coefficient' },
  { id: 'max_sharpe', label: 'Maximize Sharpe', description: 'Optimize for best risk-adjusted returns' },
  { id: 'min_correlation', label: 'Minimize Correlation', description: 'Reduce factor overlap' },
  { id: 'multi_objective', label: 'Multi-Objective', description: 'Balance IC, Sharpe, and correlation' },
];

export function FactorBlendPage() {
  const [selectedFactors, setSelectedFactors] = useState<string[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [objective, setObjective] = useState('max_ic');
  const [maxWeight, setMaxWeight] = useState(0.5);
  const [turnoverLimit, setTurnoverLimit] = useState(0.2);
  const [blendName, setBlendName] = useState('');
  const [saved, setSaved] = useState(false);

  // Fetch all factors
  const { data: factorsData } = useQuery({
    queryKey: ['factors-list'],
    queryFn: () => factorsApi.getFactors(),
  });

  const allFactors: Factor[] = factorsData?.data?.factors || [];

  // Blend mutation
  const blendMutation = useMutation({
    mutationFn: () =>
      factorsApi.blendFactors({
        factor_ids: selectedFactors,
        objective,
        constraints: {
          max_weight: maxWeight,
          turnover_limit: turnoverLimit,
        },
      }),
  });

  const blendResult: BlendResult | undefined = blendMutation.data?.data;

  // Save blend mutation
  const saveMutation = useMutation({
    mutationFn: () =>
      factorsApi.blendFactors({
        factor_ids: selectedFactors,
        objective,
        constraints: { max_weight: maxWeight, turnover_limit: turnoverLimit },
      }),
    onSuccess: () => {
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    },
  });

  const addFactor = (factorId: string) => {
    if (!selectedFactors.includes(factorId)) {
      setSelectedFactors([...selectedFactors, factorId]);
    }
    setSearchQuery('');
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

  const pieData = blendResult
    ? Object.entries(blendResult.weights).map(([factorId, weight], idx) => {
        const factor = allFactors.find((f) => f.id === factorId);
        return {
          name: factor?.name || factorId,
          value: weight,
          color: COLORS[idx % COLORS.length],
        };
      })
    : [];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Blend Factors</h1>
        <p className="text-gray-500">
          Create optimized composite signals by blending multiple factors
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Factor Selection */}
        <div className="lg:col-span-2 space-y-6">
          <div className="card p-5">
            <h2 className="font-semibold text-gray-900 mb-4">Select Factors</h2>

            {/* Selected Factors */}
            <div className="flex flex-wrap gap-2 mb-4">
              {selectedFactors.map((factorId, idx) => {
                const factor = allFactors.find((f) => f.id === factorId);
                return (
                  <div
                    key={factorId}
                    className="flex items-center gap-2 px-3 py-2 rounded-lg bg-gray-100"
                  >
                    <div
                      className="w-3 h-3 rounded-full"
                      style={{ backgroundColor: COLORS[idx % COLORS.length] }}
                    />
                    <span className="text-sm font-medium text-gray-900">
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
            </div>

            {/* Factor Search */}
            <div className="relative">
              <input
                type="text"
                placeholder="Search and add factors..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="input w-full"
              />
              <Plus className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />

              {searchQuery && (
                <div className="absolute top-full left-0 right-0 mt-1 bg-white border border-gray-200 rounded-lg shadow-lg max-h-48 overflow-y-auto z-10">
                  {filteredFactors.slice(0, 10).map((factor) => (
                    <button
                      key={factor.id}
                      onClick={() => addFactor(factor.id)}
                      className="w-full px-4 py-2 text-left hover:bg-gray-50 flex items-center justify-between"
                    >
                      <span className="font-medium text-gray-900">{factor.name}</span>
                      <span className="text-xs text-gray-500 capitalize">
                        {factor.domain.replace('_', ' ')}
                      </span>
                    </button>
                  ))}
                  {filteredFactors.length === 0 && (
                    <div className="px-4 py-2 text-gray-500 text-sm">No factors found</div>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* Optimization Settings */}
          <div className="card p-5">
            <h2 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
              <Sliders className="h-5 w-5" />
              Optimization Settings
            </h2>

            {/* Objective Selection */}
            <div className="mb-6">
              <label className="label mb-2 block">Optimization Objective</label>
              <div className="grid grid-cols-2 gap-3">
                {OBJECTIVES.map((obj) => (
                  <button
                    key={obj.id}
                    onClick={() => setObjective(obj.id)}
                    className={clsx(
                      'p-3 rounded-lg border text-left transition-colors',
                      objective === obj.id
                        ? 'border-primary-500 bg-primary-50'
                        : 'border-gray-200 hover:border-gray-300'
                    )}
                  >
                    <div className="font-medium text-gray-900">{obj.label}</div>
                    <div className="text-xs text-gray-500 mt-1">{obj.description}</div>
                  </button>
                ))}
              </div>
            </div>

            {/* Constraints */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="label mb-2 block">
                  Max Weight per Factor: {(maxWeight * 100).toFixed(0)}%
                </label>
                <input
                  type="range"
                  min="0.1"
                  max="1"
                  step="0.05"
                  value={maxWeight}
                  onChange={(e) => setMaxWeight(parseFloat(e.target.value))}
                  className="w-full"
                />
              </div>
              <div>
                <label className="label mb-2 block">
                  Turnover Limit: {(turnoverLimit * 100).toFixed(0)}%
                </label>
                <input
                  type="range"
                  min="0.05"
                  max="0.5"
                  step="0.05"
                  value={turnoverLimit}
                  onChange={(e) => setTurnoverLimit(parseFloat(e.target.value))}
                  className="w-full"
                />
              </div>
            </div>
          </div>

          {/* Run Optimization */}
          <button
            onClick={() => blendMutation.mutate()}
            disabled={selectedFactors.length < 2 || blendMutation.isPending}
            className="btn-primary w-full flex items-center justify-center gap-2"
          >
            {blendMutation.isPending ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Optimizing...
              </>
            ) : (
              'Run Optimization'
            )}
          </button>
        </div>

        {/* Results Panel */}
        <div className="space-y-6">
          {blendResult ? (
            <>
              {/* Weights Chart */}
              <div className="card p-5">
                <h3 className="font-semibold text-gray-900 mb-4">Optimal Weights</h3>
                <div className="h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={pieData}
                        cx="50%"
                        cy="50%"
                        innerRadius={60}
                        outerRadius={80}
                        paddingAngle={2}
                        dataKey="value"
                      >
                        {pieData.map((entry, index) => (
                          <Cell key={index} fill={entry.color} />
                        ))}
                      </Pie>
                      <Tooltip
                        formatter={(value) => `${((value as number) * 100).toFixed(1)}%`}
                      />
                      <Legend />
                    </PieChart>
                  </ResponsiveContainer>
                </div>

                {/* Weight List */}
                <div className="mt-4 space-y-2">
                  {pieData.map((item, idx) => (
                    <div key={idx} className="flex items-center justify-between text-sm">
                      <div className="flex items-center gap-2">
                        <div
                          className="w-3 h-3 rounded-full"
                          style={{ backgroundColor: item.color }}
                        />
                        <span className="text-gray-700">{item.name}</span>
                      </div>
                      <span className="font-medium text-gray-900">
                        {(item.value * 100).toFixed(1)}%
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Blended Metrics */}
              <div className="card p-5">
                <h3 className="font-semibold text-gray-900 mb-4">
                  Blended Factor Metrics
                </h3>
                <div className="space-y-3">
                  <div className="flex justify-between items-center">
                    <span className="text-gray-600">Information Coefficient</span>
                    <span className="font-semibold text-gray-900">
                      {(blendResult.metrics.ic * 100).toFixed(2)}%
                    </span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-gray-600">Information Ratio</span>
                    <span className="font-semibold text-gray-900">
                      {blendResult.metrics.ir.toFixed(2)}
                    </span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-gray-600">T-Statistic</span>
                    <span
                      className={clsx(
                        'font-semibold',
                        Math.abs(blendResult.metrics.t_stat) > 2
                          ? 'text-success-500'
                          : 'text-gray-900'
                      )}
                    >
                      {blendResult.metrics.t_stat.toFixed(2)}
                    </span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-gray-600">Hit Rate</span>
                    <span className="font-semibold text-gray-900">
                      {(blendResult.metrics.hit_rate * 100).toFixed(1)}%
                    </span>
                  </div>
                </div>
              </div>

              {/* Save as Custom Factor */}
              <div className="card p-5">
                <h3 className="font-semibold text-gray-900 mb-4">
                  Save as Custom Factor
                </h3>
                <div className="space-y-3">
                  <input
                    type="text"
                    placeholder="Custom factor name..."
                    value={blendName}
                    onChange={(e) => setBlendName(e.target.value)}
                    className="input w-full"
                  />
                  <button
                    onClick={() => saveMutation.mutate()}
                    disabled={!blendName || saveMutation.isPending}
                    className="btn-primary w-full flex items-center justify-center gap-2"
                  >
                    {saved ? (
                      <>
                        <CheckCircle className="h-4 w-4" />
                        Saved!
                      </>
                    ) : saveMutation.isPending ? (
                      <>
                        <Loader2 className="h-4 w-4 animate-spin" />
                        Saving...
                      </>
                    ) : (
                      <>
                        <Save className="h-4 w-4" />
                        Save Custom Factor
                      </>
                    )}
                  </button>
                </div>
              </div>
            </>
          ) : (
            <div className="card p-8 text-center">
              <Sliders className="h-12 w-12 text-gray-300 mx-auto mb-4" />
              <h3 className="font-medium text-gray-900 mb-2">No Results Yet</h3>
              <p className="text-sm text-gray-500">
                Select factors and run optimization to see results
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
