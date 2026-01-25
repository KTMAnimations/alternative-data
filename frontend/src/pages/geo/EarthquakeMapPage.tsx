import { useState, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { MapContainer, TileLayer, CircleMarker, Popup } from 'react-leaflet';
import { Sliders, X, Users, DollarSign, Building } from 'lucide-react';
import { geoApi } from '../../services/api';
import type { EarthquakeEvent, EarthquakeDetail } from '../../types';
import { format, subDays } from 'date-fns';
import 'leaflet/dist/leaflet.css';

export function EarthquakeMapPage() {
  const [magnitudeMin, setMagnitudeMin] = useState(4.0);
  const [startDate, setStartDate] = useState(format(subDays(new Date(), 30), 'yyyy-MM-dd'));
  const [endDate, setEndDate] = useState(format(new Date(), 'yyyy-MM-dd'));
  const [selectedEvent, setSelectedEvent] = useState<string | null>(null);
  const [showFilters, setShowFilters] = useState(true);

  const { data: earthquakesData, isLoading } = useQuery({
    queryKey: ['earthquakes', magnitudeMin, startDate, endDate],
    queryFn: () =>
      geoApi.getEarthquakes({
        magnitude_min: magnitudeMin,
        start_date: startDate,
        end_date: endDate,
        limit: 500,
      }),
  });

  const earthquakes: EarthquakeEvent[] = earthquakesData?.data?.features?.map((f: any) => ({
    event_id: f.properties.event_id,
    timestamp: f.properties.timestamp,
    magnitude: f.properties.magnitude,
    magnitude_type: f.properties.magnitude_type,
    depth_km: f.properties.depth_km,
    location: {
      latitude: f.geometry.coordinates[1],
      longitude: f.geometry.coordinates[0],
    },
    place_description: f.properties.place_description,
    felt_reports: f.properties.felt_reports,
    tsunami_flag: f.properties.tsunami_flag,
    estimated_population_exposure: f.properties.estimated_population_exposure,
    estimated_economic_impact_usd: f.properties.estimated_economic_impact_usd,
  })) || [];

  const { data: detailData } = useQuery({
    queryKey: ['earthquake-detail', selectedEvent],
    queryFn: () => geoApi.getEarthquakeDetail(selectedEvent!, { include_historical: true }),
    enabled: !!selectedEvent,
  });

  const eventDetail: EarthquakeDetail | undefined = detailData?.data;

  const getMagnitudeColor = (mag: number) => {
    if (mag >= 7) return '#ef4444';
    if (mag >= 6) return '#f97316';
    if (mag >= 5) return '#eab308';
    return '#22c55e';
  };

  const getMagnitudeRadius = (mag: number) => {
    return Math.max(5, (mag - 3) * 8);
  };

  const mapCenter: [number, number] = useMemo(() => {
    if (earthquakes.length === 0) return [37.7749, -122.4194];
    const avgLat = earthquakes.reduce((sum, e) => sum + e.location.latitude, 0) / earthquakes.length;
    const avgLng = earthquakes.reduce((sum, e) => sum + e.location.longitude, 0) / earthquakes.length;
    return [avgLat, avgLng];
  }, [earthquakes]);

  return (
    <div className="h-[calc(100vh-10rem)] flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Earthquake Map</h1>
          <p className="text-gray-500">View seismic events and insurance exposure</p>
        </div>
        <button
          onClick={() => setShowFilters(!showFilters)}
          className="btn-outline flex items-center gap-2"
        >
          <Sliders className="h-4 w-4" />
          {showFilters ? 'Hide Filters' : 'Show Filters'}
        </button>
      </div>

      <div className="flex-1 flex gap-4">
        {/* Filters Sidebar */}
        {showFilters && (
          <aside className="w-72 flex-shrink-0 space-y-4">
            <div className="card p-4">
              <h3 className="font-semibold text-gray-900 mb-4">Filters</h3>

              {/* Magnitude Slider */}
              <div className="mb-4">
                <label className="label mb-2 block">
                  Minimum Magnitude: {magnitudeMin.toFixed(1)}
                </label>
                <input
                  type="range"
                  min="2"
                  max="8"
                  step="0.5"
                  value={magnitudeMin}
                  onChange={(e) => setMagnitudeMin(parseFloat(e.target.value))}
                  className="w-full"
                />
                <div className="flex justify-between text-xs text-gray-500 mt-1">
                  <span>2.0</span>
                  <span>8.0</span>
                </div>
              </div>

              {/* Date Range */}
              <div className="space-y-3">
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
            </div>

            {/* Legend */}
            <div className="card p-4">
              <h3 className="font-semibold text-gray-900 mb-3">Magnitude Scale</h3>
              <div className="space-y-2 text-sm">
                {[
                  { min: 7, color: '#ef4444', label: '7.0+ (Major)' },
                  { min: 6, color: '#f97316', label: '6.0-6.9 (Strong)' },
                  { min: 5, color: '#eab308', label: '5.0-5.9 (Moderate)' },
                  { min: 4, color: '#22c55e', label: '4.0-4.9 (Light)' },
                ].map((item) => (
                  <div key={item.min} className="flex items-center gap-2">
                    <div
                      className="w-4 h-4 rounded-full"
                      style={{ backgroundColor: item.color }}
                    />
                    <span className="text-gray-600">{item.label}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Stats */}
            <div className="card p-4">
              <h3 className="font-semibold text-gray-900 mb-3">Summary</h3>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-gray-500">Total Events</span>
                  <span className="font-medium text-gray-900">{earthquakes.length}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Max Magnitude</span>
                  <span className="font-medium text-gray-900">
                    {earthquakes.length > 0 ? Math.max(...earthquakes.map((e) => e.magnitude)).toFixed(1) : '-'}
                  </span>
                </div>
              </div>
            </div>
          </aside>
        )}

        {/* Map */}
        <div className="flex-1 card overflow-hidden relative">
          {isLoading && (
            <div className="absolute inset-0 bg-white/80 z-[1000] flex items-center justify-center">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600" />
            </div>
          )}

          <MapContainer
            center={mapCenter}
            zoom={4}
            style={{ height: '100%', width: '100%' }}
            scrollWheelZoom={true}
          >
            <TileLayer
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            />

            {earthquakes.map((eq) => (
              <CircleMarker
                key={eq.event_id}
                center={[eq.location.latitude, eq.location.longitude]}
                radius={getMagnitudeRadius(eq.magnitude)}
                pathOptions={{
                  fillColor: getMagnitudeColor(eq.magnitude),
                  fillOpacity: 0.7,
                  color: getMagnitudeColor(eq.magnitude),
                  weight: 1,
                }}
                eventHandlers={{
                  click: () => setSelectedEvent(eq.event_id),
                }}
              >
                <Popup>
                  <div className="min-w-[200px]">
                    <div className="font-semibold text-gray-900">M {eq.magnitude.toFixed(1)}</div>
                    <div className="text-sm text-gray-600">{eq.place_description}</div>
                    <div className="text-xs text-gray-500 mt-1">
                      {format(new Date(eq.timestamp), 'MMM d, yyyy h:mm a')}
                    </div>
                    <button
                      onClick={() => setSelectedEvent(eq.event_id)}
                      className="text-primary-600 text-sm mt-2 hover:underline"
                    >
                      View Details
                    </button>
                  </div>
                </Popup>
              </CircleMarker>
            ))}
          </MapContainer>
        </div>

        {/* Detail Panel */}
        {selectedEvent && eventDetail && (
          <aside className="w-80 flex-shrink-0">
            <div className="card p-4 space-y-4">
              <div className="flex items-start justify-between">
                <div>
                  <h3 className="font-semibold text-gray-900">
                    M {eventDetail.magnitude.toFixed(1)} Earthquake
                  </h3>
                  <p className="text-sm text-gray-500">{eventDetail.place_description}</p>
                </div>
                <button
                  onClick={() => setSelectedEvent(null)}
                  className="text-gray-400 hover:text-gray-600"
                >
                  <X className="h-5 w-5" />
                </button>
              </div>

              <div className="grid grid-cols-2 gap-3 text-sm">
                <div className="p-3 bg-gray-50 rounded-lg">
                  <div className="text-gray-500">Depth</div>
                  <div className="font-semibold text-gray-900">{eventDetail.depth_km} km</div>
                </div>
                <div className="p-3 bg-gray-50 rounded-lg">
                  <div className="text-gray-500">Felt Reports</div>
                  <div className="font-semibold text-gray-900">{eventDetail.felt_reports || 0}</div>
                </div>
              </div>

              {eventDetail.estimated_population_exposure && (
                <div className="p-3 bg-blue-50 rounded-lg flex items-center gap-3">
                  <Users className="h-5 w-5 text-blue-500" />
                  <div>
                    <div className="text-sm text-blue-700">Population Exposure</div>
                    <div className="font-semibold text-blue-900">
                      {(eventDetail.estimated_population_exposure / 1000000).toFixed(2)}M people
                    </div>
                  </div>
                </div>
              )}

              {eventDetail.estimated_economic_impact_usd && (
                <div className="p-3 bg-orange-50 rounded-lg flex items-center gap-3">
                  <DollarSign className="h-5 w-5 text-orange-500" />
                  <div>
                    <div className="text-sm text-orange-700">Economic Impact</div>
                    <div className="font-semibold text-orange-900">
                      ${(eventDetail.estimated_economic_impact_usd / 1000000000).toFixed(2)}B
                    </div>
                  </div>
                </div>
              )}

              {/* Insurance Estimates */}
              {eventDetail.insurance_estimates && eventDetail.insurance_estimates.length > 0 && (
                <div>
                  <h4 className="font-semibold text-gray-900 mb-2 flex items-center gap-2">
                    <Building className="h-4 w-4" />
                    Insurance Loss Estimates
                  </h4>
                  <div className="space-y-2">
                    {eventDetail.insurance_estimates.map((est) => (
                      <div key={est.ticker} className="p-3 bg-gray-50 rounded-lg">
                        <div className="flex items-center justify-between mb-1">
                          <span className="font-medium text-gray-900">{est.ticker}</span>
                          <span className="text-sm text-gray-500">{est.name}</span>
                        </div>
                        <div className="text-sm">
                          <span className="text-gray-600">Est. Loss: </span>
                          <span className="font-semibold text-danger-600">
                            ${(est.estimated_loss_mean / 1000000).toFixed(1)}M
                          </span>
                          {est.reinsurance_percentage && (
                            <span className="text-gray-500 ml-2">
                              ({est.reinsurance_percentage}% reinsured)
                            </span>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Historical Comparisons */}
              {eventDetail.historical_comparisons && eventDetail.historical_comparisons.length > 0 && (
                <div>
                  <h4 className="font-semibold text-gray-900 mb-2">Similar Historical Events</h4>
                  <div className="space-y-2">
                    {eventDetail.historical_comparisons.slice(0, 3).map((comp) => (
                      <div key={comp.event_id} className="p-2 bg-gray-50 rounded text-sm">
                        <div className="flex items-center justify-between">
                          <span className="font-medium">M {comp.magnitude.toFixed(1)}</span>
                          <span className="text-gray-500">
                            {(comp.similarity_score * 100).toFixed(0)}% similar
                          </span>
                        </div>
                        <div className="text-gray-600 text-xs mt-1">
                          {comp.place_description} • {format(new Date(comp.timestamp), 'MMM yyyy')}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </aside>
        )}
      </div>
    </div>
  );
}
