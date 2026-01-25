import { useParams, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { ArrowLeft, ExternalLink, TrendingUp, Target, AlertTriangle, BookOpen } from 'lucide-react';
import {
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
} from 'recharts';
import { factorsApi } from '../../services/api';
import type { Factor } from '../../types';

// Simple KaTeX-like rendering (in production, use actual KaTeX)
function MathFormula({ formula }: { formula: string }) {
  return (
    <div className="bg-gray-50 rounded-lg p-4 overflow-x-auto">
      <code className="text-lg font-mono text-gray-800">{formula}</code>
    </div>
  );
}

export function FactorDetailPage() {
  const { factorId } = useParams<{ factorId: string }>();

  const { data: factorData, isLoading, error } = useQuery({
    queryKey: ['factor', factorId],
    queryFn: () => factorsApi.getFactor(factorId!),
    enabled: !!factorId,
  });

  const factor: Factor | undefined = factorData?.data;

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600" />
      </div>
    );
  }

  if (error || !factor) {
    return (
      <div className="card p-12 text-center">
        <TrendingUp className="h-12 w-12 text-gray-300 mx-auto mb-4" />
        <h3 className="text-lg font-medium text-gray-900 mb-2">Factor not found</h3>
        <Link to="/factors/graph" className="text-primary-600 hover:text-primary-700">
          Back to Factor Graph
        </Link>
      </div>
    );
  }

  const decayData = factor.decay_analysis
    ? factor.decay_analysis.horizons.map((horizon, idx) => ({
        horizon: `${horizon}d`,
        ic: factor.decay_analysis!.ic_values[idx],
      }))
    : [];

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      {/* Header */}
      <div>
        <Link
          to="/factors/graph"
          className="flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700 mb-2"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to Factor Graph
        </Link>
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">{factor.name}</h1>
            <p className="mt-1 text-gray-500 capitalize">
              {factor.domain.replace('_', ' ')} Domain
            </p>
          </div>
          <Link
            to={`/factors/compare?factors=${factor.id}`}
            className="btn-outline"
          >
            Compare
          </Link>
        </div>
      </div>

      {/* Description */}
      <div className="card p-5">
        <p className="text-gray-700 leading-relaxed">{factor.description}</p>
      </div>

      {/* Formula */}
      {factor.formula && (
        <div className="card p-5">
          <h2 className="text-lg font-semibold text-gray-900 mb-3">Formula</h2>
          <MathFormula formula={factor.formula} />
        </div>
      )}

      {/* Historical Metrics */}
      {factor.historical_metrics && (
        <div className="card p-5">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">
            Historical Performance Metrics
          </h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="p-4 bg-gray-50 rounded-lg text-center">
              <div className="text-2xl font-bold text-primary-600">
                {(factor.historical_metrics.ic * 100).toFixed(2)}%
              </div>
              <div className="text-sm text-gray-500">Information Coefficient</div>
            </div>
            <div className="p-4 bg-gray-50 rounded-lg text-center">
              <div className="text-2xl font-bold text-primary-600">
                {factor.historical_metrics.ir.toFixed(2)}
              </div>
              <div className="text-sm text-gray-500">Information Ratio</div>
            </div>
            <div className="p-4 bg-gray-50 rounded-lg text-center">
              <div className="text-2xl font-bold text-primary-600">
                {factor.historical_metrics.t_stat.toFixed(2)}
              </div>
              <div className="text-sm text-gray-500">T-Statistic</div>
            </div>
            <div className="p-4 bg-gray-50 rounded-lg text-center">
              <div className="text-2xl font-bold text-primary-600">
                {(factor.historical_metrics.hit_rate * 100).toFixed(1)}%
              </div>
              <div className="text-sm text-gray-500">Hit Rate</div>
            </div>
          </div>
        </div>
      )}

      {/* Decay Analysis */}
      {factor.decay_analysis && decayData.length > 0 && (
        <div className="card p-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-gray-900">Signal Decay Analysis</h2>
            <div className="text-sm text-gray-500">
              Half-life: <span className="font-medium text-gray-900">
                {factor.decay_analysis.half_life_days} days
              </span>
            </div>
          </div>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={decayData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis dataKey="horizon" tick={{ fontSize: 12 }} />
                <YAxis
                  tick={{ fontSize: 12 }}
                  tickFormatter={(v) => `${(v * 100).toFixed(1)}%`}
                />
                <Tooltip
                  formatter={(value) => [`${((value as number) * 100).toFixed(2)}%`, 'IC']}
                />
                <Bar dataKey="ic" fill="#3b82f6" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Economic Rationale */}
      {factor.economic_rationale && (
        <div className="card p-5">
          <h2 className="text-lg font-semibold text-gray-900 mb-3 flex items-center gap-2">
            <BookOpen className="h-5 w-5" />
            Economic Rationale
          </h2>
          <p className="text-gray-700 leading-relaxed whitespace-pre-line">
            {factor.economic_rationale}
          </p>
        </div>
      )}

      {/* Literature References */}
      {factor.literature_refs && factor.literature_refs.length > 0 && (
        <div className="card p-5">
          <h2 className="text-lg font-semibold text-gray-900 mb-3">
            Literature References
          </h2>
          <ul className="space-y-2">
            {factor.literature_refs.map((ref, idx) => (
              <li key={idx} className="flex items-start gap-2">
                <ExternalLink className="h-4 w-4 text-gray-400 mt-1 flex-shrink-0" />
                <a
                  href={ref.startsWith('http') ? ref : `https://scholar.google.com/scholar?q=${encodeURIComponent(ref)}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-primary-600 hover:text-primary-700 hover:underline"
                >
                  {ref}
                </a>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Target Entities */}
      {factor.target_entities && factor.target_entities.length > 0 && (
        <div className="card p-5">
          <h2 className="text-lg font-semibold text-gray-900 mb-3 flex items-center gap-2">
            <Target className="h-5 w-5" />
            Target Entities
          </h2>
          <div className="flex flex-wrap gap-2">
            {factor.target_entities.map((entity) => (
              <span
                key={entity}
                className="px-3 py-1 rounded-full bg-primary-50 text-primary-700 text-sm font-medium"
              >
                {entity}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Signal Interpretation */}
      {factor.signal_interpretation && (
        <div className="card p-5">
          <h2 className="text-lg font-semibold text-gray-900 mb-3">
            Signal Interpretation
          </h2>
          <p className="text-gray-700 leading-relaxed">
            {factor.signal_interpretation}
          </p>
        </div>
      )}

      {/* Known Limitations */}
      {factor.known_limitations && factor.known_limitations.length > 0 && (
        <div className="card p-5 border-warning-200 bg-warning-50">
          <h2 className="text-lg font-semibold text-warning-800 mb-3 flex items-center gap-2">
            <AlertTriangle className="h-5 w-5" />
            Known Limitations
          </h2>
          <ul className="space-y-2">
            {factor.known_limitations.map((limitation, idx) => (
              <li key={idx} className="flex items-start gap-2 text-warning-700">
                <span className="text-warning-500 mt-1">•</span>
                {limitation}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Actions */}
      <div className="flex gap-3">
        <Link to={`/factors/compare?factors=${factor.id}`} className="btn-outline flex-1">
          Compare with Other Factors
        </Link>
        <Link to={`/backtest?factor=${factor.id}`} className="btn-primary flex-1">
          Run Backtest
        </Link>
      </div>
    </div>
  );
}
