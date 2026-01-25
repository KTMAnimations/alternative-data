import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add auth interceptor
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('api_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Add response interceptor for error handling
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('api_token');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

// Catalog API
export const catalogApi = {
  getSources: (params?: {
    category?: string;
    frequency?: string;
    search?: string;
    sort_by?: string;
    sort_order?: string;
  }) => api.get('/catalog/sources', { params }),

  getSource: (sourceId: string) => api.get(`/catalog/sources/${sourceId}`),

  getSourcePreview: (sourceId: string, params?: {
    start_date?: string;
    end_date?: string;
    ticker?: string;
    limit?: number;
    format?: string;
  }) => api.get(`/catalog/sources/${sourceId}/preview`, { params }),

  semanticSearch: (query: string) =>
    api.post('/catalog/search/semantic', { query }),
};

// Factors API
export const factorsApi = {
  getFactors: (params?: { domain?: string; search?: string }) =>
    api.get('/factors', { params }),

  getFactor: (factorId: string) => api.get(`/factors/${factorId}`),

  getFactorGraph: (params?: { relationship_type?: string; domain?: string }) =>
    api.get('/factors/graph', { params }),

  getFactorHistory: (factorId: string, params?: {
    tickers?: string;
    start_date?: string;
    end_date?: string;
    format?: string;
  }) => api.get(`/factors/${factorId}/history`, { params }),

  compareFactors: (factorIds: string[]) =>
    api.post('/factors/compare', { factor_ids: factorIds }),

  blendFactors: (data: {
    factor_ids: string[];
    objective: string;
    constraints?: Record<string, number>;
  }) => api.post('/factors/blend', data),

  generatePineScript: (factorId: string) =>
    api.post(`/factors/${factorId}/pinescript`),
};

// Alerts API
export const alertsApi = {
  getAlerts: () => api.get('/alerts'),

  createAlert: (data: {
    factor_id: string;
    ticker_list: string[];
    threshold_value: number;
    direction: string;
    notification_channel: string;
    name: string;
    description?: string;
    enabled?: boolean;
  }) => api.post('/alerts', data),

  updateAlert: (alertId: string, data: Partial<{
    threshold_value: number;
    direction: string;
    notification_channel: string;
    enabled: boolean;
  }>) => api.patch(`/alerts/${alertId}`, data),

  deleteAlert: (alertId: string) => api.delete(`/alerts/${alertId}`),

  testAlert: (alertId: string) => api.post(`/alerts/${alertId}/test`),

  getAlertHistory: () => api.get('/alerts/history'),
};

// Geo API
export const geoApi = {
  getEarthquakes: (params?: {
    magnitude_min?: number;
    start_date?: string;
    end_date?: string;
    limit?: number;
  }) => api.get('/geo/earthquakes', { params }),

  getEarthquakeDetail: (eventId: string, params?: {
    include_historical?: boolean;
  }) => api.get(`/geo/earthquakes/${eventId}`, { params }),

  configureRegionalThreshold: (data: {
    region_name: string;
    geometry: object;
    magnitude_threshold: number;
  }) => api.post('/geo/thresholds/regional', data),

  previewThresholdEvents: (params: {
    magnitude_threshold: number;
    days_back?: number;
  }) => api.get('/geo/thresholds/preview', { params }),

  getPowerGrid: (params?: {
    iso_region?: string;
    price_percentile_min?: number;
  }) => api.get('/geo/power-grid', { params }),

  getPowerGridHistory: (params: {
    node_id: string;
    start_date: string;
    end_date: string;
  }) => api.get('/geo/power-grid/history', { params }),
};

// Backtest API
export const backtestApi = {
  runBacktest: (data: FormData) =>
    api.post('/backtest/run', data, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }),

  getDecay: (factorId: string) => api.get(`/backtest/decay/${factorId}`),

  getSeasonality: (factorId: string) =>
    api.get(`/backtest/seasonality/${factorId}`),

  exportResearchPack: (data: {
    factor_id: string;
    include_notebook?: boolean;
    include_data?: boolean;
    include_charts?: boolean;
  }) => api.post('/backtest/export', data, { responseType: 'blob' }),

  getExperiments: () => api.get('/backtest/experiments'),

  createExperiment: (data: {
    name: string;
    control_factor_id: string;
    treatment_factor_id: string;
  }) => api.post('/backtest/experiments', data),
};

// Admin API
export const adminApi = {
  getPendingMappings: (params?: { status?: string }) =>
    api.get('/admin/mappings/pending', { params }),

  approveMappings: (mappingIds: string[]) =>
    api.post('/admin/mappings/approve', { mapping_ids: mappingIds }),

  rejectMapping: (mappingId: string, reason: string) =>
    api.post(`/admin/mappings/${mappingId}/reject`, { reason }),

  getMappingCoverage: () => api.get('/admin/mappings/coverage'),

  getSuggestions: (params?: { source?: string }) =>
    api.get('/admin/suggestions/pending', { params }),

  getCollectorHealth: () => api.get('/admin/collectors/health'),

  triggerCollector: (collectorId: string) =>
    api.post(`/admin/collectors/${collectorId}/trigger`),

  // Data Source Requests
  getDataRequests: (params?: { status?: string }) =>
    api.get('/admin/data-requests', { params }),

  createDataRequest: (data: {
    source_name: string;
    source_type: string;
    description: string;
    use_case: string;
    priority: string;
  }) => api.post('/admin/data-requests', data),

  updateDataRequestStatus: (requestId: string, status: string, notes?: string) =>
    api.patch(`/admin/data-requests/${requestId}`, { status, admin_notes: notes }),
};

// User API
export const userApi = {
  getUsage: () => api.get('/user/usage'),

  getTiers: () => api.get('/user/tiers'),

  upgradeTier: (tierId: string, billingCycle?: 'monthly' | 'annual') =>
    api.post('/user/upgrade', { tier_id: tierId, billing_cycle: billingCycle }),

  getApiKeys: () => api.get('/user/api-keys'),

  createApiKey: (data: { name: string; expires_in_days?: number }) =>
    api.post('/user/api-keys', data),

  deleteApiKey: (keyId: string) => api.delete(`/user/api-keys/${keyId}`),

  rotateApiKey: (keyId: string) => api.post(`/user/api-keys/${keyId}/rotate`),
};

// TradingView API
export const tradingViewApi = {
  syncBacktest: (data: {
    factor_id: string;
    tickers: string[];
    start_date: string;
    end_date: string;
    strategy_config?: object;
    sync_direction?: string;
  }) => api.post('/tradingview/backtest/sync', data),

  getSyncStatus: (syncId: string) =>
    api.get(`/tradingview/backtest/sync/${syncId}/status`),

  getSyncHistory: () => api.get('/tradingview/backtest/history'),

  importResults: (data: {
    sync_id: string;
    results: object;
  }) => api.post('/tradingview/backtest/import-results', data),
};
