import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { MapContainer, TileLayer, Polygon } from 'react-leaflet';
import { Eye, Save } from 'lucide-react';
import { geoApi } from '../../services/api';
import type { EarthquakeEvent } from '../../types';
import clsx from 'clsx';
import 'leaflet/dist/leaflet.css';

const PRESET_REGIONS = [
  { name: 'California', coordinates: [[[-125, 32], [-114, 32], [-114, 42], [-125, 42], [-125, 32]]] },
  { name: 'Pacific Northwest', coordinates: [[[-125, 42], [-116, 42], [-116, 49], [-125, 49], [-125, 42]]] },
  { name: 'Gulf Coast', coordinates: [[[-98, 25], [-80, 25], [-80, 31], [-98, 31], [-98, 25]]] },
  { name: 'New Madrid Zone', coordinates: [[[-92, 34], [-87, 34], [-87, 40], [-92, 40], [-92, 34]]] },
];

export function ThresholdConfigPage() {
  const queryClient = useQueryClient();
  const [regionName, setRegionName] = useState('');
  const [magnitudeThreshold, setMagnitudeThreshold] = useState(5.0);
  const [selectedPreset, setSelectedPreset] = useState<string | null>(null);
  const [previewDays] = useState(30);

  const { data: previewData, isLoading: previewLoading, refetch: refetchPreview } = useQuery({
    queryKey: ['threshold-preview', magnitudeThreshold, previewDays],
    queryFn: () => geoApi.previewThresholdEvents({ magnitude_threshold: magnitudeThreshold, days_back: previewDays }),
    enabled: false,
  });

  const previewEvents: EarthquakeEvent[] = previewData?.data?.events || [];

  const saveMutation = useMutation({
    mutationFn: () => {
      const preset = PRESET_REGIONS.find(p => p.name === selectedPreset);
      if (!preset) throw new Error('Select a region');
      return geoApi.configureRegionalThreshold({
        region_name: regionName || selectedPreset!,
        geometry: { type: 'Polygon', coordinates: preset.coordinates },
        magnitude_threshold: magnitudeThreshold,
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['thresholds'] });
      setRegionName('');
      setSelectedPreset(null);
    },
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Regional Threshold Configuration</h1>
        <p className="text-gray-500">Set different magnitude thresholds by geographic region</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Configuration Form */}
        <div className="space-y-4">
          <div className="card p-5">
            <h2 className="font-semibold text-gray-900 mb-4">New Threshold</h2>

            <div className="space-y-4">
              <div>
                <label className="label mb-2 block">Region Name</label>
                <input
                  type="text"
                  value={regionName}
                  onChange={(e) => setRegionName(e.target.value)}
                  placeholder="e.g., California Coast"
                  className="input w-full"
                />
              </div>

              <div>
                <label className="label mb-2 block">Select Preset Region</label>
                <div className="grid grid-cols-2 gap-2">
                  {PRESET_REGIONS.map((region) => (
                    <button
                      key={region.name}
                      onClick={() => setSelectedPreset(region.name)}
                      className={clsx(
                        'p-2 rounded-lg border text-sm text-left',
                        selectedPreset === region.name
                          ? 'border-primary-500 bg-primary-50'
                          : 'border-gray-200 hover:border-gray-300'
                      )}
                    >
                      {region.name}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label className="label mb-2 block">
                  Magnitude Threshold: {magnitudeThreshold.toFixed(1)}
                </label>
                <input
                  type="range"
                  min="3"
                  max="8"
                  step="0.5"
                  value={magnitudeThreshold}
                  onChange={(e) => setMagnitudeThreshold(parseFloat(e.target.value))}
                  className="w-full"
                />
                <div className="flex justify-between text-xs text-gray-500 mt-1">
                  <span>3.0 (Low)</span>
                  <span>8.0 (High)</span>
                </div>
              </div>

              <div className="flex gap-2">
                <button
                  onClick={() => refetchPreview()}
                  disabled={!selectedPreset || previewLoading}
                  className="btn-outline flex-1 flex items-center justify-center gap-2"
                >
                  <Eye className="h-4 w-4" />
                  Preview
                </button>
                <button
                  onClick={() => saveMutation.mutate()}
                  disabled={!selectedPreset || saveMutation.isPending}
                  className="btn-primary flex-1 flex items-center justify-center gap-2"
                >
                  <Save className="h-4 w-4" />
                  Save
                </button>
              </div>
            </div>
          </div>

          {/* Preview Results */}
          {previewEvents.length > 0 && (
            <div className="card p-5">
              <h3 className="font-semibold text-gray-900 mb-3">
                Preview: {previewEvents.length} events would trigger
              </h3>
              <div className="space-y-2 max-h-64 overflow-y-auto">
                {previewEvents.slice(0, 10).map((event) => (
                  <div key={event.event_id} className="p-2 bg-gray-50 rounded text-sm">
                    <div className="flex items-center justify-between">
                      <span className="font-medium">M {event.magnitude.toFixed(1)}</span>
                      <span className="text-gray-500">
                        {new Date(event.timestamp).toLocaleDateString()}
                      </span>
                    </div>
                    <div className="text-gray-600 text-xs truncate">
                      {event.place_description}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Map */}
        <div className="lg:col-span-2 card overflow-hidden" style={{ height: '500px' }}>
          <MapContainer
            center={[39.8283, -98.5795]}
            zoom={4}
            style={{ height: '100%', width: '100%' }}
          >
            <TileLayer
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            />
            {PRESET_REGIONS.map((region) => (
              <Polygon
                key={region.name}
                positions={region.coordinates[0].map(([lng, lat]) => [lat, lng])}
                pathOptions={{
                  color: selectedPreset === region.name ? '#3b82f6' : '#6b7280',
                  fillColor: selectedPreset === region.name ? '#3b82f6' : '#6b7280',
                  fillOpacity: selectedPreset === region.name ? 0.3 : 0.1,
                  weight: selectedPreset === region.name ? 3 : 1,
                }}
                eventHandlers={{
                  click: () => setSelectedPreset(region.name),
                }}
              />
            ))}
          </MapContainer>
        </div>
      </div>

      {/* Info */}
      <div className="card p-4 bg-blue-50 border-blue-200">
        <p className="text-sm text-blue-700">
          <strong>Note:</strong> Setting different thresholds by region allows you to receive
          alerts for smaller earthquakes near major population centers while filtering out
          minor seismic activity in remote areas.
        </p>
      </div>
    </div>
  );
}
