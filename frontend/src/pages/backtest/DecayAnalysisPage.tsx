import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { TrendingDown, Clock, Info } from 'lucide-react';
import { XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, BarChart, Bar } from 'recharts';
import { factorsApi, backtestApi } from '../../services/api';
import type { Factor, DecayAnalysis } from '../../types';

const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444'];

export function DecayAnalysisPage() {
  const [selectedFactors, setSelectedFactors] = useState<string[]>([]);
  const [searchQuery, setSearchQuery] = useState('');

  const { data: factorsData } = useQuery({
    queryKey: ['factors-list'],
    queryFn: () => factorsApi.getFactors(),
  });

  const factors: Factor[] = factorsData?.data?.factors || [];

  const { data: decayData, isLoading } = useQuery({
    queryKey: ['decay-analysis', selectedFactors[0]],
    queryFn: () => backtestApi.getDecay(selectedFactors[0]),
    enabled: selectedFactors.length > 0,
  });

  const decay: DecayAnalysis | undefined = decayData?.data;

  const filteredFactors = factors.filter(
    (f) =>
      !selectedFactors.includes(f.id) &&
      f.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const addFactor = (factorId: string) => {
    if (selectedFactors.length < 4) {
      setSelectedFactors([...selectedFactors, factorId]);
    }
    setSearchQuery('');
  };

  const removeFactor = (factorId: string) => {
    setSelectedFactors(selectedFactors.filter((f) => f !== factorId));
  };

  const chartData = decay
    ? decay.horizons.map((horizon, idx) => ({
        horizon: `${horizon}d`,
        ic: decay.ic_values[idx] * 100,
      }))
    : [];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Signal Decay Analysis</h1>
        <p className="text-gray-500">Analyze how factor signals decay over time</p>
      </div>

      {/* Factor Selection */}
      <div className="card p-5">
        <h2 className="font-semibold text-gray-900 mb-4">Select Factors (max 4)</h2>

        <div className="flex flex-wrap gap-2 mb-4">
          {selectedFactors.map((factorId, idx) => {
            const factor = factors.find((f) => f.id === factorId);
            return (
              <div
                key={factorId}
                className="flex items-center gap-2 px-3 py-2 rounded-lg border"
                style={{ borderColor: COLORS[idx] }}
              >
                <div className="w-3 h-3 rounded-full" style={{ backgroundColor: COLORS[idx] }} />
                <span className="font-medium">{factor?.name || factorId}</span>
                <button onClick={() => removeFactor(factorId)} className="text-gray-400 hover:text-gray-600">×</button>
              </div>
            );
          })}
        </div>

        <div className="relative">
          <input
            type="text"
            placeholder="Search factors..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="input w-full"
          />
          {searchQuery && (
            <div className="absolute top-full left-0 right-0 mt-1 bg-white border rounded-lg shadow-lg max-h-48 overflow-y-auto z-10">
              {filteredFactors.slice(0, 10).map((factor) => (
                <button
                  key={factor.id}
                  onClick={() => addFactor(factor.id)}
                  className="w-full px-4 py-2 text-left hover:bg-gray-50"
                >
                  {factor.name}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Results */}
      {isLoading ? (
        <div className="flex items-center justify-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600" />
        </div>
      ) : decay ? (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Half-life Card */}
          <div className="card p-5">
            <div className="flex items-center gap-2 text-gray-500 mb-2">
              <Clock className="h-5 w-5" />
              <span className="text-sm">Signal Half-Life</span>
            </div>
            <div className="text-4xl font-bold text-primary-600">
              {decay.half_life_days} days
            </div>
            <p className="text-sm text-gray-500 mt-2">
              Time for signal to decay to 50% of initial strength
            </p>
          </div>

          {/* Info Card */}
          <div className="lg:col-span-2 card p-5 bg-blue-50 border-blue-200">
            <div className="flex items-start gap-3">
              <Info className="h-5 w-5 text-blue-500 mt-0.5" />
              <div>
                <h4 className="font-semibold text-blue-900">Interpretation</h4>
                <p className="text-sm text-blue-700 mt-1">
                  A shorter half-life suggests the factor captures information that gets priced in quickly.
                  Consider shorter holding periods. A longer half-life indicates more persistent signals
                  suitable for longer-term strategies.
                </p>
              </div>
            </div>
          </div>

          {/* Decay Curve */}
          <div className="lg:col-span-3 card p-5">
            <h3 className="font-semibold text-gray-900 mb-4">IC Decay Curve</h3>
            <div className="h-80">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                  <XAxis dataKey="horizon" tick={{ fontSize: 12 }} />
                  <YAxis tick={{ fontSize: 12 }} tickFormatter={(v) => `${v.toFixed(1)}%`} />
                  <Tooltip formatter={(value) => [`${(value as number).toFixed(2)}%`, 'IC']} />
                  <Bar dataKey="ic" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      ) : (
        <div className="card p-12 text-center">
          <TrendingDown className="h-12 w-12 text-gray-300 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-900 mb-2">Select a Factor</h3>
          <p className="text-gray-500">Choose a factor to analyze its signal decay</p>
        </div>
      )}
    </div>
  );
}
