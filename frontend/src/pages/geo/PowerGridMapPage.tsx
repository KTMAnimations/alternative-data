import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { MapContainer, TileLayer, CircleMarker, Popup } from 'react-leaflet';
import { Play, Pause, Leaf } from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { geoApi } from '../../services/api';
import type { PowerGridNode, PowerGridHistory } from '../../types';
import { format, subDays } from 'date-fns';
import 'leaflet/dist/leaflet.css';

const ISO_REGIONS = ['ERCOT', 'PJM', 'CAISO', 'ISO-NE', 'MISO', 'SPP', 'NYISO'];

export function PowerGridMapPage() {
  const [selectedIso, setSelectedIso] = useState<string>('');
  const [pricePercentileMin, setPricePercentileMin] = useState(0);
  const [showRenewables, setShowRenewables] = useState(false);
  const [selectedNode, setSelectedNode] = useState<string | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);

  const { data: gridData, isLoading } = useQuery({
    queryKey: ['power-grid', selectedIso, pricePercentileMin],
    queryFn: () =>
      geoApi.getPowerGrid({
        iso_region: selectedIso || undefined,
        price_percentile_min: pricePercentileMin > 0 ? pricePercentileMin : undefined,
      }),
  });

  const nodes: PowerGridNode[] = gridData?.data?.nodes || [];

  const { data: historyData } = useQuery({
    queryKey: ['power-grid-history', selectedNode],
    queryFn: () =>
      geoApi.getPowerGridHistory({
        node_id: selectedNode!,
        start_date: format(subDays(new Date(), 7), 'yyyy-MM-dd'),
        end_date: format(new Date(), 'yyyy-MM-dd'),
      }),
    enabled: !!selectedNode,
  });

  const history: PowerGridHistory | undefined = historyData?.data;

  const getPriceColor = (percentile: number) => {
    if (percentile >= 95) return '#ef4444';
    if (percentile >= 80) return '#f97316';
    if (percentile >= 60) return '#eab308';
    if (percentile >= 40) return '#22c55e';
    return '#3b82f6';
  };

  const getRenewableColor = (share: number) => {
    if (share >= 0.8) return '#22c55e';
    if (share >= 0.5) return '#84cc16';
    if (share >= 0.3) return '#eab308';
    return '#f97316';
  };

  const historyChartData = history
    ? history.timestamps.map((ts, idx) => ({
        time: format(new Date(ts), 'HH:mm'),
        lmp: history.lmp_values[idx],
        renewable: history.renewable_shares[idx] * 100,
      }))
    : [];

  return (
    <div className="h-[calc(100vh-10rem)] flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Power Grid Map</h1>
          <p className="text-gray-500">View LMP prices and renewable generation by ISO region</p>
        </div>
      </div>

      <div className="flex-1 flex gap-4">
        {/* Filters Sidebar */}
        <aside className="w-72 flex-shrink-0 space-y-4">
          <div className="card p-4">
            <h3 className="font-semibold text-gray-900 mb-4">Filters</h3>

            {/* ISO Region */}
            <div className="mb-4">
              <label className="label mb-2 block">ISO Region</label>
              <select
                value={selectedIso}
                onChange={(e) => setSelectedIso(e.target.value)}
                className="select w-full"
              >
                <option value="">All Regions</option>
                {ISO_REGIONS.map((iso) => (
                  <option key={iso} value={iso}>{iso}</option>
                ))}
              </select>
            </div>

            {/* Price Percentile */}
            <div className="mb-4">
              <label className="label mb-2 block">
                Min Price Percentile: {pricePercentileMin}%
              </label>
              <input
                type="range"
                min="0"
                max="95"
                step="5"
                value={pricePercentileMin}
                onChange={(e) => setPricePercentileMin(parseInt(e.target.value))}
                className="w-full"
              />
            </div>

            {/* Renewable Overlay */}
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={showRenewables}
                onChange={(e) => setShowRenewables(e.target.checked)}
                className="rounded border-gray-300"
              />
              <Leaf className="h-4 w-4 text-green-500" />
              <span className="text-sm text-gray-700">Show Renewable Share</span>
            </label>
          </div>

          {/* Legend */}
          <div className="card p-4">
            <h3 className="font-semibold text-gray-900 mb-3">
              {showRenewables ? 'Renewable Share' : 'Price Percentile'}
            </h3>
            <div className="space-y-2 text-sm">
              {showRenewables ? (
                <>
                  {[
                    { min: 80, color: '#22c55e', label: '80%+ (Excellent)' },
                    { min: 50, color: '#84cc16', label: '50-79% (Good)' },
                    { min: 30, color: '#eab308', label: '30-49% (Moderate)' },
                    { min: 0, color: '#f97316', label: '<30% (Low)' },
                  ].map((item) => (
                    <div key={item.min} className="flex items-center gap-2">
                      <div className="w-4 h-4 rounded-full" style={{ backgroundColor: item.color }} />
                      <span className="text-gray-600">{item.label}</span>
                    </div>
                  ))}
                </>
              ) : (
                <>
                  {[
                    { min: 95, color: '#ef4444', label: '95%+ (Extreme)' },
                    { min: 80, color: '#f97316', label: '80-94% (High)' },
                    { min: 60, color: '#eab308', label: '60-79% (Elevated)' },
                    { min: 40, color: '#22c55e', label: '40-59% (Normal)' },
                    { min: 0, color: '#3b82f6', label: '<40% (Low)' },
                  ].map((item) => (
                    <div key={item.min} className="flex items-center gap-2">
                      <div className="w-4 h-4 rounded-full" style={{ backgroundColor: item.color }} />
                      <span className="text-gray-600">{item.label}</span>
                    </div>
                  ))}
                </>
              )}
            </div>
          </div>

          {/* Playback Controls */}
          <div className="card p-4">
            <h3 className="font-semibold text-gray-900 mb-3">Historical Playback</h3>
            <div className="flex items-center gap-3">
              <button
                onClick={() => setIsPlaying(!isPlaying)}
                className="btn-outline p-2"
              >
                {isPlaying ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
              </button>
              <input type="range" min="0" max="24" step="1" className="flex-1" />
              <span className="text-sm text-gray-500">00:00</span>
            </div>
          </div>
        </aside>

        {/* Map */}
        <div className="flex-1 card overflow-hidden relative">
          {isLoading && (
            <div className="absolute inset-0 bg-white/80 z-[1000] flex items-center justify-center">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600" />
            </div>
          )}

          <MapContainer
            center={[39.8283, -98.5795]}
            zoom={4}
            style={{ height: '100%', width: '100%' }}
            scrollWheelZoom={true}
          >
            <TileLayer
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            />

            {nodes.map((node) => (
              <CircleMarker
                key={node.node_id}
                center={[node.location.latitude, node.location.longitude]}
                radius={8}
                pathOptions={{
                  fillColor: showRenewables
                    ? getRenewableColor(node.renewable_share)
                    : getPriceColor(node.lmp_percentile),
                  fillOpacity: 0.8,
                  color: '#fff',
                  weight: 1,
                }}
                eventHandlers={{
                  click: () => setSelectedNode(node.node_id),
                }}
              >
                <Popup>
                  <div className="min-w-[180px]">
                    <div className="font-semibold text-gray-900">{node.node_id}</div>
                    <div className="text-sm text-gray-600">{node.iso_region}</div>
                    <div className="mt-2 space-y-1 text-sm">
                      <div className="flex justify-between">
                        <span className="text-gray-500">LMP:</span>
                        <span className="font-medium">${node.current_lmp.toFixed(2)}/MWh</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-500">Percentile:</span>
                        <span className="font-medium">{node.lmp_percentile.toFixed(0)}%</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-500">Renewable:</span>
                        <span className="font-medium">{(node.renewable_share * 100).toFixed(1)}%</span>
                      </div>
                    </div>
                  </div>
                </Popup>
              </CircleMarker>
            ))}
          </MapContainer>
        </div>

        {/* History Panel */}
        {selectedNode && history && (
          <aside className="w-80 flex-shrink-0">
            <div className="card p-4 space-y-4">
              <div className="flex items-start justify-between">
                <div>
                  <h3 className="font-semibold text-gray-900">{selectedNode}</h3>
                  <p className="text-sm text-gray-500">Price History (7 days)</p>
                </div>
                <button
                  onClick={() => setSelectedNode(null)}
                  className="text-gray-400 hover:text-gray-600"
                >
                  ×
                </button>
              </div>

              {/* Price Chart */}
              <div className="h-48">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={historyChartData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                    <XAxis dataKey="time" tick={{ fontSize: 10 }} />
                    <YAxis tick={{ fontSize: 10 }} />
                    <Tooltip />
                    <Line
                      type="monotone"
                      dataKey="lmp"
                      stroke="#3b82f6"
                      strokeWidth={2}
                      dot={false}
                      name="LMP ($/MWh)"
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>

              {/* Renewable Chart */}
              <div className="h-48">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={historyChartData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                    <XAxis dataKey="time" tick={{ fontSize: 10 }} />
                    <YAxis tick={{ fontSize: 10 }} domain={[0, 100]} />
                    <Tooltip />
                    <Line
                      type="monotone"
                      dataKey="renewable"
                      stroke="#22c55e"
                      strokeWidth={2}
                      dot={false}
                      name="Renewable %"
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
          </aside>
        )}
      </div>
    </div>
  );
}
