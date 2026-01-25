// Data Source Types
export interface DataSource {
  id: string;
  name: string;
  description: string;
  category: string;
  update_frequency: string;
  latency_hours: number;
  coverage: string;
  saturation_level: number;
  date_range_start: string;
  date_range_end: string;
  entity_coverage: string[];
  sample_code?: string;
  derived_factors?: string[];
}

export interface DataSourcePreview {
  source_id: string;
  data: Record<string, unknown>[];
  row_count: number;
  completeness_pct: number;
  last_updated: string;
  statistics: {
    [field: string]: {
      min?: number;
      max?: number;
      mean?: number;
      std?: number;
    };
  };
}

// Factor Types
export interface Factor {
  id: string;
  name: string;
  domain: string;
  description: string;
  formula?: string;
  economic_rationale?: string;
  literature_refs?: string[];
  historical_metrics?: FactorMetrics;
  decay_analysis?: DecayAnalysis;
  target_entities: string[];
  signal_interpretation?: string;
  known_limitations?: string[];
  source_id: string;
}

export interface FactorMetrics {
  ic: number;
  ir: number;
  t_stat: number;
  hit_rate: number;
}

export interface DecayAnalysis {
  horizons: number[];
  ic_values: number[];
  half_life_days: number;
}

export interface FactorNode {
  id: string;
  label: string;
  domain: string;
  type: 'factor' | 'source';
}

export interface FactorEdge {
  source: string;
  target: string;
  relationship: 'derived-from' | 'correlated-with' | 'causes' | 'leads' | 'component-of';
}

export interface FactorGraph {
  nodes: FactorNode[];
  edges: FactorEdge[];
}

export interface FactorComparison {
  factor_ids: string[];
  metrics: Record<string, FactorMetrics>;
  correlation_matrix: number[][];
  time_series: {
    dates: string[];
    values: Record<string, number[]>;
  };
}

export interface BlendResult {
  weights: Record<string, number>;
  metrics: FactorMetrics;
  blend_id?: string;
}

// Alert Types
export interface Alert {
  id: string;
  name: string;
  description?: string;
  factor_id: string;
  ticker_list: string[];
  threshold_value: number;
  direction: 'above' | 'below' | 'crosses';
  notification_channel: 'email' | 'webhook';
  webhook_url?: string;
  enabled: boolean;
  created_at: string;
  updated_at: string;
  // Anomaly detection
  alert_type?: 'threshold' | 'anomaly' | 'event';
  sensitivity_std?: number;
  baseline_period_days?: number;
  use_ml?: boolean;
  // Event-based
  event_type?: string;
  event_criteria?: Record<string, unknown>;
  geographic_filter?: {
    region?: string;
    bounding_box?: [number, number, number, number];
  };
  // Fatigue management
  quiet_hours_start?: string;
  quiet_hours_end?: string;
  cooldown_minutes?: number;
  digest_enabled?: boolean;
  digest_time?: string;
}

export interface AlertHistory {
  id: string;
  alert_id: string;
  triggered_at: string;
  factor_value: number;
  threshold_value: number;
  ticker: string;
  read: boolean;
  notification_sent: boolean;
}

// Geographic Types
export interface GeoPoint {
  latitude: number;
  longitude: number;
}

export interface EarthquakeEvent {
  event_id: string;
  timestamp: string;
  magnitude: number;
  magnitude_type: string;
  depth_km: number;
  location: GeoPoint;
  place_description: string;
  felt_reports?: number;
  tsunami_flag: boolean;
  estimated_population_exposure?: number;
  estimated_economic_impact_usd?: number;
}

export interface EarthquakeDetail extends EarthquakeEvent {
  insurance_estimates?: InsuranceEstimate[];
  historical_comparisons?: HistoricalComparison[];
}

export interface InsuranceEstimate {
  ticker: string;
  name: string;
  estimated_loss_mean: number;
  estimated_loss_variance: number;
  confidence_level: number;
  exposure_by_region?: RegionalExposure[];
  reinsurance_percentage?: number;
  net_retained_loss?: number;
}

export interface RegionalExposure {
  region: string;
  exposure_percentage: number;
  exposed_policies_estimate?: number;
  exposure_value_usd?: number;
}

export interface HistoricalComparison {
  event_id: string;
  timestamp: string;
  magnitude: number;
  distance_km: number;
  place_description: string;
  actual_insured_loss_usd?: number;
  similarity_score: number;
}

export interface RegionalThreshold {
  id: string;
  region_name: string;
  geometry: GeoJSON.Polygon;
  magnitude_threshold: number;
}

export interface PowerGridNode {
  node_id: string;
  iso_region: string;
  location: GeoPoint;
  current_lmp: number;
  lmp_percentile: number;
  renewable_share: number;
}

export interface PowerGridHistory {
  node_id: string;
  timestamps: string[];
  lmp_values: number[];
  renewable_shares: number[];
}

// Backtest Types
export interface BacktestResult {
  factor_id: string;
  date_range: [string, string];
  metrics: FactorMetrics;
  decile_returns: number[];
  monthly_ic: {
    dates: string[];
    values: number[];
  };
  survivorship_bias_warnings?: string[];
}

export interface SeasonalityAnalysis {
  factor_id: string;
  day_of_week_ic: Record<string, number>;
  monthly_ic: Record<string, number>;
  holiday_effects: {
    holiday: string;
    ic_impact: number;
  }[];
  event_patterns: {
    event: string;
    ic_impact: number;
  }[];
}

export interface Experiment {
  id: string;
  name: string;
  control_factor_id: string;
  treatment_factor_id: string;
  start_date: string;
  status: 'running' | 'completed' | 'stopped';
  control_metrics?: FactorMetrics;
  treatment_metrics?: FactorMetrics;
  p_value?: number;
  winner?: 'control' | 'treatment' | 'inconclusive';
}

// Entity Mapping Types
export interface EntityMapping {
  id: string;
  source_entity: string;
  source_type: string;
  suggested_ticker: string;
  confidence_score: number;
  status: 'pending' | 'approved' | 'rejected' | 'needs_review';
  alternatives?: {
    ticker: string;
    score: number;
  }[];
  reviewed_by?: string;
  reviewed_at?: string;
}

export interface MappingSuggestion {
  id: string;
  source_entity: string;
  suggested_ticker: string;
  rationale: string;
  status: 'submitted' | 'evaluating' | 'approved' | 'rejected' | 'implemented';
  submitted_by: string;
  submitted_at: string;
}

export interface MappingCoverage {
  source_id: string;
  source_name: string;
  total_entities: number;
  mapped_entities: number;
  coverage_pct: number;
  unmapped_value_usd?: number;
  priority_unmapped: string[];
}

export interface CorporateAction {
  id: string;
  action_type: 'ticker_change' | 'merger' | 'spinoff' | 'acquisition';
  old_ticker?: string;
  new_ticker?: string;
  effective_date: string;
  affected_mappings: string[];
  adjustment_preview?: string;
  status: 'pending' | 'approved' | 'rejected';
}

// User Types
export interface UserUsage {
  user_id: string;
  tier_id: string;
  tier_name: string;
  api_calls_used: number;
  api_calls_limit: number;
  data_downloaded_mb: number;
  data_limit_mb: number;
  billing_period_start: string;
  billing_period_end: string;
  warning_threshold_pct: number;
  at_warning: boolean;
  at_critical: boolean;
  historical_usage: {
    date: string;
    requests: number;
    data_volume_mb: number;
  }[];
}

export interface Tier {
  id: string;
  name: string;
  rate_limit: number;
  api_calls_limit: number;
  data_limit_mb: number;
  data_access: string[];
  features: string[];
  price_monthly: number;
}

export interface ApiKey {
  id: string;
  name: string;
  key_prefix: string;
  created_at: string;
  last_used_at?: string;
  expires_at?: string;
  is_active: boolean;
  requests_count: number;
}

// Data Source Request Types
export interface DataSourceRequest {
  id: string;
  source_name: string;
  source_type: string;
  description: string;
  use_case: string;
  priority: 'low' | 'medium' | 'high' | 'critical';
  status: 'pending' | 'in_review' | 'approved' | 'rejected' | 'in_progress' | 'completed';
  created_at: string;
  updated_at: string;
  requested_by: string;
  admin_notes?: string;
}

// Collector Health Types
export interface CollectorHealth {
  collector_id: string;
  name: string;
  status: 'healthy' | 'degraded' | 'down';
  last_success: string;
  last_error?: string;
  error_count_24h: number;
  freshness_sla_hours: number;
  current_freshness_hours: number;
  sla_breach: boolean;
}
