import { useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useQuery, useMutation } from '@tanstack/react-query';
import {
  ArrowLeft,
  Download,
  Clock,
  Calendar,
  TrendingUp,
  Database,
  Copy,
  Check,
  FileSpreadsheet,
  ChevronDown,
  ChevronUp,
  ExternalLink,
} from 'lucide-react';
import { catalogApi } from '../../services/api';
import type { DataSource, DataSourcePreview } from '../../types';
import clsx from 'clsx';
import { format, subDays } from 'date-fns';

export function SourceDetailPage() {
  const { sourceId } = useParams<{ sourceId: string }>();
  const [copied, setCopied] = useState(false);
  const [startDate, setStartDate] = useState(format(subDays(new Date(), 30), 'yyyy-MM-dd'));
  const [endDate, setEndDate] = useState(format(new Date(), 'yyyy-MM-dd'));
  const [ticker, setTicker] = useState('');
  const [previewLimit, setPreviewLimit] = useState(100);
  const [showCode, setShowCode] = useState(false);

  const { data: sourceData, isLoading: sourceLoading } = useQuery({
    queryKey: ['catalog-source', sourceId],
    queryFn: () => catalogApi.getSource(sourceId!),
    enabled: !!sourceId,
  });

  const source: DataSource | undefined = sourceData?.data;

  const { data: previewData, isLoading: previewLoading } = useQuery({
    queryKey: ['catalog-preview', sourceId, startDate, endDate, ticker, previewLimit],
    queryFn: () =>
      catalogApi.getSourcePreview(sourceId!, {
        start_date: startDate,
        end_date: endDate,
        ticker: ticker || undefined,
        limit: previewLimit,
      }),
    enabled: !!sourceId,
  });

  const preview: DataSourcePreview | undefined = previewData?.data;

  const exportMutation = useMutation({
    mutationFn: (format: string) =>
      catalogApi.getSourcePreview(sourceId!, {
        start_date: startDate,
        end_date: endDate,
        ticker: ticker || undefined,
        limit: 10000,
        format,
      }),
    onSuccess: (response, format) => {
      const blob = new Blob([JSON.stringify(response.data, null, 2)], {
        type: format === 'csv' ? 'text/csv' : 'application/json',
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${source?.name || 'data'}.${format}`;
      a.click();
      URL.revokeObjectURL(url);
    },
  });

  const handleCopyCode = () => {
    if (source?.sample_code) {
      navigator.clipboard.writeText(source.sample_code);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  if (sourceLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600" />
      </div>
    );
  }

  if (!source) {
    return (
      <div className="card p-12 text-center">
        <Database className="h-12 w-12 text-gray-300 mx-auto mb-4" />
        <h3 className="text-lg font-medium text-gray-900 mb-2">Source not found</h3>
        <Link to="/catalog" className="text-primary-600 hover:text-primary-700">
          Back to catalog
        </Link>
      </div>
    );
  }

  const columns = preview?.data?.[0] ? Object.keys(preview.data[0]) : [];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <Link
            to="/catalog"
            className="flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700 mb-2"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to Catalog
          </Link>
          <h1 className="text-2xl font-bold text-gray-900">{source.name}</h1>
          <p className="mt-1 text-gray-500">{source.description}</p>
        </div>

        <div className="flex gap-2">
          <button
            onClick={() => exportMutation.mutate('csv')}
            disabled={exportMutation.isPending}
            className="btn-outline flex items-center gap-2"
          >
            <FileSpreadsheet className="h-4 w-4" />
            Export CSV
          </button>
          <button
            onClick={() => exportMutation.mutate('parquet')}
            disabled={exportMutation.isPending}
            className="btn-outline flex items-center gap-2"
          >
            <Database className="h-4 w-4" />
            Export Parquet
          </button>
          <button
            onClick={() => exportMutation.mutate('arrow')}
            disabled={exportMutation.isPending}
            className="btn-primary flex items-center gap-2"
          >
            <Download className="h-4 w-4" />
            Export Arrow
          </button>
        </div>
      </div>

      {/* Metadata Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="card p-4">
          <div className="flex items-center gap-2 text-gray-500 text-sm mb-1">
            <Clock className="h-4 w-4" />
            Update Frequency
          </div>
          <div className="text-lg font-semibold text-gray-900 capitalize">
            {source.update_frequency}
          </div>
        </div>

        <div className="card p-4">
          <div className="flex items-center gap-2 text-gray-500 text-sm mb-1">
            <TrendingUp className="h-4 w-4" />
            Typical Latency
          </div>
          <div className="text-lg font-semibold text-gray-900">
            {source.latency_hours}h
          </div>
        </div>

        <div className="card p-4">
          <div className="flex items-center gap-2 text-gray-500 text-sm mb-1">
            <Calendar className="h-4 w-4" />
            Date Range
          </div>
          <div className="text-lg font-semibold text-gray-900">
            {source.date_range_start} - {source.date_range_end}
          </div>
        </div>

        <div className="card p-4">
          <div className="flex items-center gap-2 text-gray-500 text-sm mb-1">
            <Database className="h-4 w-4" />
            Saturation Level
          </div>
          <div className="text-lg font-semibold text-gray-900">
            {source.saturation_level}%
          </div>
        </div>
      </div>

      {/* Entity Coverage */}
      <div className="card p-5">
        <h3 className="font-semibold text-gray-900 mb-3">Entity Coverage</h3>
        <div className="flex flex-wrap gap-2">
          {source.entity_coverage?.map((entity) => (
            <span
              key={entity}
              className="px-3 py-1 rounded-full bg-primary-50 text-primary-700 text-sm font-medium"
            >
              {entity}
            </span>
          ))}
        </div>
      </div>

      {/* Derived Factors */}
      {source.derived_factors && source.derived_factors.length > 0 && (
        <div className="card p-5">
          <h3 className="font-semibold text-gray-900 mb-3">Derived Factors</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {source.derived_factors.map((factorId) => (
              <Link
                key={factorId}
                to={`/factors/${factorId}`}
                className="flex items-center justify-between p-3 rounded-lg bg-gray-50 hover:bg-gray-100 transition-colors"
              >
                <span className="text-gray-900">{factorId}</span>
                <ExternalLink className="h-4 w-4 text-gray-400" />
              </Link>
            ))}
          </div>
        </div>
      )}

      {/* Sample Code */}
      {source.sample_code && (
        <div className="card overflow-hidden">
          <button
            onClick={() => setShowCode(!showCode)}
            className="w-full flex items-center justify-between p-4 hover:bg-gray-50"
          >
            <h3 className="font-semibold text-gray-900">Sample API Code</h3>
            {showCode ? (
              <ChevronUp className="h-5 w-5 text-gray-500" />
            ) : (
              <ChevronDown className="h-5 w-5 text-gray-500" />
            )}
          </button>

          {showCode && (
            <div className="relative border-t border-gray-200">
              <button
                onClick={handleCopyCode}
                className="absolute top-3 right-3 flex items-center gap-1 px-2 py-1 rounded bg-gray-700 text-white text-xs hover:bg-gray-600"
              >
                {copied ? (
                  <>
                    <Check className="h-3 w-3" />
                    Copied!
                  </>
                ) : (
                  <>
                    <Copy className="h-3 w-3" />
                    Copy
                  </>
                )}
              </button>
              <pre className="p-4 bg-gray-900 text-gray-100 text-sm overflow-x-auto">
                <code>{source.sample_code}</code>
              </pre>
            </div>
          )}
        </div>
      )}

      {/* Data Preview */}
      <div className="card">
        <div className="p-5 border-b border-gray-200">
          <h3 className="font-semibold text-gray-900 mb-4">Data Preview</h3>

          {/* Filters */}
          <div className="flex flex-wrap gap-4">
            <div>
              <label className="label mb-1 block">Start Date</label>
              <input
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                className="input"
              />
            </div>
            <div>
              <label className="label mb-1 block">End Date</label>
              <input
                type="date"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
                className="input"
              />
            </div>
            <div>
              <label className="label mb-1 block">Ticker Filter</label>
              <input
                type="text"
                placeholder="e.g., AAPL"
                value={ticker}
                onChange={(e) => setTicker(e.target.value)}
                className="input"
              />
            </div>
            <div>
              <label className="label mb-1 block">Row Limit</label>
              <select
                value={previewLimit}
                onChange={(e) => setPreviewLimit(Number(e.target.value))}
                className="select"
              >
                <option value={50}>50 rows</option>
                <option value={100}>100 rows</option>
                <option value={500}>500 rows</option>
                <option value={1000}>1000 rows</option>
              </select>
            </div>
          </div>
        </div>

        {/* Quality Indicators */}
        {preview && (
          <div className="p-4 bg-gray-50 border-b border-gray-200 flex gap-6 text-sm">
            <div>
              <span className="text-gray-500">Rows:</span>{' '}
              <span className="font-medium text-gray-900">{preview.row_count}</span>
            </div>
            <div>
              <span className="text-gray-500">Completeness:</span>{' '}
              <span
                className={clsx(
                  'font-medium',
                  preview.completeness_pct >= 95
                    ? 'text-success-500'
                    : preview.completeness_pct >= 80
                    ? 'text-warning-500'
                    : 'text-danger-500'
                )}
              >
                {preview.completeness_pct.toFixed(1)}%
              </span>
            </div>
            <div>
              <span className="text-gray-500">Last Updated:</span>{' '}
              <span className="font-medium text-gray-900">{preview.last_updated}</span>
            </div>
          </div>
        )}

        {/* Data Table */}
        <div className="overflow-x-auto">
          {previewLoading ? (
            <div className="flex items-center justify-center py-12">
              <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-primary-600" />
            </div>
          ) : preview?.data && preview.data.length > 0 ? (
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  {columns.map((col) => (
                    <th
                      key={col}
                      className="px-4 py-3 text-left font-medium text-gray-700"
                    >
                      {col}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {preview.data.map((row, idx) => (
                  <tr key={idx} className="hover:bg-gray-50">
                    {columns.map((col) => (
                      <td key={col} className="px-4 py-3 text-gray-600">
                        {String(row[col] ?? '')}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="py-12 text-center text-gray-500">
              No data available for the selected filters
            </div>
          )}
        </div>

        {/* Statistics */}
        {preview?.statistics && Object.keys(preview.statistics).length > 0 && (
          <div className="p-5 border-t border-gray-200">
            <h4 className="font-medium text-gray-900 mb-3">Statistics</h4>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
              {Object.entries(preview.statistics).map(([field, stats]) => (
                <div key={field} className="p-3 bg-gray-50 rounded-lg">
                  <div className="font-medium text-gray-700 mb-2">{field}</div>
                  {stats.min !== undefined && (
                    <div className="flex justify-between">
                      <span className="text-gray-500">Min:</span>
                      <span className="text-gray-900">{stats.min.toFixed(2)}</span>
                    </div>
                  )}
                  {stats.max !== undefined && (
                    <div className="flex justify-between">
                      <span className="text-gray-500">Max:</span>
                      <span className="text-gray-900">{stats.max.toFixed(2)}</span>
                    </div>
                  )}
                  {stats.mean !== undefined && (
                    <div className="flex justify-between">
                      <span className="text-gray-500">Mean:</span>
                      <span className="text-gray-900">{stats.mean.toFixed(2)}</span>
                    </div>
                  )}
                  {stats.std !== undefined && (
                    <div className="flex justify-between">
                      <span className="text-gray-500">Std:</span>
                      <span className="text-gray-900">{stats.std.toFixed(2)}</span>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
