# Alternative Data Platform - Product Requirements Document

## Overview
Comprehensive platform for collecting, processing, and delivering alternative data signals for investment decision-making. Aggregates 49+ sources across travel, real estate, gaming, energy, government, and infrastructure domains, transforming raw data into actionable investment factors mapped to a global ticker universe.

**Key Differentiators:**
- Full probabilistic output (mean + variance)
- Global coverage including emerging markets with ETF aggregation
- Research-grade analytics with academic documentation
- Graph-based factor taxonomy with relationship visualization
- Real-time + batch hybrid latency model
- Full TradingView bidirectional integration

**MVP Scope:** Phase 1 data sources (8 free APIs) + full platform UI. Quality-focused, no fixed deadline.

---

## User Stories

### Epic 1: Data Catalog Discovery

#### US-001: Browse Available Data Sources
**As a** fundamental analyst
**I want to** browse all available data sources in a searchable catalog
**So that** I can discover new alternative data relevant to my coverage universe

**Acceptance Criteria:**
- [ ] Catalog displays all sources with name, description, frequency
- [ ] Filter by category (travel, real estate, energy, gaming, government, infrastructure)
- [ ] Filter by update frequency (continuous, hourly, daily, weekly, monthly)
- [ ] Search by keyword in name and description
- [ ] Sort by saturation level, freshness, coverage
- [ ] Show data availability date range

#### US-002: AI-Powered Data Discovery
**As a** data scientist
**I want to** ask natural language questions like "show me consumer spending signals"
**So that** I can quickly find relevant data without knowing exact source names

**Acceptance Criteria:**
- [ ] Natural language search input field in catalog header
- [ ] LLM interprets query and returns ranked relevant sources
- [ ] Show explanation of why each source matches the query
- [ ] Suggest related sources based on query intent
- [ ] Remember recent searches for quick access

#### US-003: Preview Sample Data
**As a** quant PM
**I want to** preview sample data for any source with interactive date selection
**So that** I can evaluate data quality before integrating

**Acceptance Criteria:**
- [ ] Interactive date range picker (any historical date range)
- [ ] Display sample data in sortable, filterable table format
- [ ] Show data quality indicators (completeness, freshness)
- [ ] Export preview data in CSV, Parquet, or Arrow format
- [ ] Filter preview by entity/ticker
- [ ] Show row count and basic statistics

#### US-004: View Source Metadata
**As a** analyst
**I want to** see comprehensive metadata for each data source
**So that** I understand data characteristics before use

**Acceptance Criteria:**
- [ ] Display source name and description
- [ ] Show collection frequency and typical latency
- [ ] Display geographic and entity coverage
- [ ] Show date range of available history
- [ ] List saturation level (novel, low, medium, high)
- [ ] Show sample API code snippets
- [ ] List derived factors from this source

---

### Epic 2: Factor Analysis

#### US-005: Explore Factor Taxonomy Graph
**As a** data scientist
**I want to** visualize relationships between factors in a graph view
**So that** I can understand factor derivation and correlation structure

**Acceptance Criteria:**
- [ ] Interactive graph visualization of all factors
- [ ] Click node to expand factor details panel
- [ ] Edge types: derived-from, correlated-with, causes, leads, component-of
- [ ] Filter by relationship type
- [ ] Filter by factor domain (travel, real estate, etc.)
- [ ] Search for specific factors by name
- [ ] Zoom, pan, and cluster controls

#### US-006: View Factor Documentation
**As a** quant PM
**I want to** see academic-quality documentation for each factor
**So that** I understand economic rationale and expected performance

**Acceptance Criteria:**
- [ ] Display factor formula with mathematical notation
- [ ] Show economic rationale (2-3 paragraphs)
- [ ] Include literature references with links
- [ ] Display historical metrics table (IC, IR, t-stat, hit rate)
- [ ] Show decay analysis chart (IC at 1d, 5d, 10d, 21d, 63d horizons)
- [ ] List target entities (primary and secondary)
- [ ] Document signal interpretation (positive/negative meaning)
- [ ] Note known limitations

#### US-007: Compare Factors Side-by-Side
**As a** data scientist
**I want to** compare multiple factors side-by-side
**So that** I can evaluate which factors to include in my model

**Acceptance Criteria:**
- [ ] Select up to 4 factors for comparison
- [ ] Side-by-side performance metrics table
- [ ] Correlation matrix between selected factors
- [ ] Overlaid time-series charts with date sync
- [ ] Highlight statistically significant differences
- [ ] Export comparison as research pack

#### US-008: Blend Factors with Optimization
**As a** quant PM
**I want to** blend multiple factors with optimized weights
**So that** I can create composite signals

**Acceptance Criteria:**
- [ ] Select multiple factors for blending
- [ ] Choose optimization objective (max IC, max Sharpe, min correlation, multi-objective)
- [ ] Set constraints (max weight, turnover limits)
- [ ] Run optimization and display optimal weights
- [ ] Show blended factor performance metrics
- [ ] Save blend as custom factor

---

### Epic 3: Real-Time Monitoring

#### US-009: Configure Threshold Alerts
**As a** fundamental analyst
**I want to** set alerts when factors cross specific thresholds
**So that** I'm notified of significant market signals

**Acceptance Criteria:**
- [ ] Select factor from dropdown
- [ ] Select ticker or ticker list
- [ ] Configure threshold value
- [ ] Choose direction (above, below, crosses)
- [ ] Choose notification channel (email, webhook)
- [ ] Set alert name and optional description
- [ ] Enable/disable toggle without deletion
- [ ] Test alert with sample notification

#### US-010: Configure Anomaly Detection Alerts
**As a** quant PM
**I want to** receive alerts when factors show unusual movements
**So that** I can react to significant market events

**Acceptance Criteria:**
- [ ] Select factor and ticker scope
- [ ] Configure sensitivity (standard deviations from baseline)
- [ ] Choose baseline period (7d, 30d, 90d rolling)
- [ ] ML-based anomaly detection option
- [ ] Show recent anomalies detected
- [ ] Configure notification channels

#### US-011: Configure Event-Based Alerts
**As a** insurance analyst
**I want to** receive alerts for specific events like earthquakes above magnitude 6.0
**So that** I can assess portfolio exposure

**Acceptance Criteria:**
- [ ] Select event type (earthquake, contract award, etc.)
- [ ] Configure event criteria (magnitude > 6.0)
- [ ] Set geographic filters (region, distance from location)
- [ ] Include estimated impact in alert
- [ ] Immediate notification for critical events

#### US-012: Subscribe to WebSocket Streams
**As a** quant PM
**I want to** subscribe to real-time factor updates via WebSocket
**So that** I can incorporate signals into my intraday trading system

**Acceptance Criteria:**
- [ ] WebSocket endpoint with API key authentication
- [ ] Subscribe to specific factors and tickers
- [ ] Choose verbosity level (simple value, delta, full context with mean/variance)
- [ ] Automatic reconnection on disconnect
- [ ] Heartbeat for connection health
- [ ] Python SDK wrapper for easy integration

#### US-013: Manage Alert Fatigue
**As a** analyst
**I want to** configure smart suppression for my alerts
**So that** I don't get overwhelmed with notifications

**Acceptance Criteria:**
- [ ] Set quiet hours (no alerts during specified times)
- [ ] Configure cooldown period between repeated alerts
- [ ] Option for daily digest instead of real-time
- [ ] ML-based alert prioritization and bundling
- [ ] View alert history with read/unread status

---

### Epic 4: Geographic Visualization

#### US-014: View Earthquake Event Map
**As a** insurance analyst
**I want to** see earthquake events on a geographic map
**So that** I can assess exposure for insurance companies

**Acceptance Criteria:**
- [ ] Map displaying earthquake locations with magnitude-sized markers
- [ ] Filter by magnitude threshold
- [ ] Filter by date range
- [ ] Click event marker for details (magnitude, depth, location, timestamp)
- [ ] Show population within radius
- [ ] Show estimated economic impact
- [ ] Show insurance loss estimates by insurer

#### US-015: Configure Regional Earthquake Thresholds
**As a** data admin
**I want to** set different magnitude thresholds by region
**So that** alerts are appropriate for population/asset exposure

**Acceptance Criteria:**
- [ ] Define geographic regions (draw on map or select)
- [ ] Set magnitude threshold per region
- [ ] Lower default thresholds near population centers
- [ ] Higher thresholds in remote/ocean areas
- [ ] Preview which recent events would trigger

#### US-016: View Power Grid Node Map
**As a** energy analyst
**I want to** see LMP prices visualized on a geographic map
**So that** I can identify price spikes and congestion

**Acceptance Criteria:**
- [ ] Map showing ISO regions (PJM, ERCOT, CAISO, ISO-NE, MISO, SPP, NYISO)
- [ ] Heat map overlay of current LMP prices
- [ ] Historical playback slider
- [ ] Click node for price history chart
- [ ] Filter by price percentile
- [ ] Show renewable generation share overlay option

---

### Epic 5: Backtesting & Research

#### US-017: Run Factor Backtest
**As a** quant PM
**I want to** backtest a factor against my return data
**So that** I can validate signal quality before deployment

**Acceptance Criteria:**
- [ ] Upload return data (CSV with ticker, date, return columns)
- [ ] Select factor to backtest
- [ ] Select date range
- [ ] Compute IC, IR, t-stat, hit rate
- [ ] Display decile spread chart (long-short returns)
- [ ] Show monthly IC time series
- [ ] Flag survivorship bias warnings

#### US-018: Analyze Factor Decay
**As a** data scientist
**I want to** analyze how factor signal decays over time
**So that** I can determine optimal holding period

**Acceptance Criteria:**
- [ ] Select factor
- [ ] Compute IC at horizons: 1d, 2d, 5d, 10d, 21d, 63d, 126d, 252d
- [ ] Display decay curve chart
- [ ] Estimate signal half-life
- [ ] Compare decay across multiple factors

#### US-019: Analyze Factor Seasonality
**As a** quant PM
**I want to** understand seasonal patterns in factor performance
**So that** I can adjust my strategy timing

**Acceptance Criteria:**
- [ ] Select factor
- [ ] Show day-of-week IC breakdown
- [ ] Show monthly IC breakdown
- [ ] Identify holiday effects (global developed market calendar)
- [ ] Show event-based seasonality (earnings season, etc.)
- [ ] Seasonal adjustment toggle for factor values

#### US-020: Export Research Pack
**As a** data scientist
**I want to** export a complete research pack for a factor
**So that** I can share analysis with my team

**Acceptance Criteria:**
- [ ] Generate Jupyter notebook with analysis code
- [ ] Include raw factor data export (CSV, Parquet, Arrow)
- [ ] Include computed statistics (JSON)
- [ ] Include charts as PNG/SVG images
- [ ] Include methodology documentation (PDF/Markdown)
- [ ] Package as downloadable ZIP

#### US-021: Run Factor A/B Experiment
**As a** data scientist
**I want to** run A/B tests on different factor formulations
**So that** I can identify the best performing variant

**Acceptance Criteria:**
- [ ] Create experiment with name and description
- [ ] Define control factor (existing)
- [ ] Define treatment factor (variant)
- [ ] Set experiment duration or sample size
- [ ] Track performance metrics for each variant in parallel
- [ ] Statistical significance testing with p-value
- [ ] Promote winning variant to production

---

### Epic 6: API Integration

#### US-022: Authenticate with API Key
**As a** developer
**I want to** authenticate API requests with an API key
**So that** I can access factor data programmatically

**Acceptance Criteria:**
- [ ] Generate API key in user settings UI
- [ ] Display key once (cannot be retrieved again)
- [ ] Include key in Authorization header (Bearer token)
- [ ] Key tied to account tier with rate limits
- [ ] Key rotation support (create new, deprecate old)
- [ ] View usage statistics per key (requests, data volume)

#### US-023: Query Factor History via REST
**As a** quant PM
**I want to** query historical factor values via REST API
**So that** I can integrate data into my backtesting system

**Acceptance Criteria:**
- [ ] GET /api/v1/factors/{factor_id}/history endpoint
- [ ] Query params: tickers (comma-separated), start_date, end_date
- [ ] Pagination with cursor (for large result sets)
- [ ] Response format negotiation (JSON, CSV, Parquet, Arrow)
- [ ] Include mean and variance in response
- [ ] Include as_of_date and computation_timestamp
- [ ] Rate limit headers in response

#### US-024: Query Entity Factors via REST
**As a** analyst
**I want to** get all factors for a specific ticker
**So that** I can see the full signal picture

**Acceptance Criteria:**
- [ ] GET /api/v1/entities/{ticker}/factors endpoint
- [ ] Optional factor_ids filter
- [ ] Optional date range filter
- [ ] Return latest values by default
- [ ] Include factor metadata in response
- [ ] Support ETF ticker aggregation

#### US-025: Generate Pine Script Indicator
**As a** retail trader
**I want to** generate a Pine Script indicator from a platform factor
**So that** I can use it in TradingView

**Acceptance Criteria:**
- [ ] Select factor in UI
- [ ] Click "Generate Pine Script" button
- [ ] Display generated code in modal
- [ ] Copy to clipboard button
- [ ] Include real-time data feed integration code
- [ ] Provide TradingView setup instructions

#### US-026: Full TradingView Sync
**As a** quant developer
**I want to** bidirectionally sync between platform and TradingView
**So that** I can use both tools seamlessly

**Acceptance Criteria:**
- [ ] Push factor values to TradingView in real-time
- [ ] Import TradingView annotations back to platform
- [ ] Synchronized backtesting capabilities
- [ ] Pine Script SDK documentation
- [ ] OAuth connection to TradingView account

---

### Epic 7: Entity Mapping

#### US-027: Review Pending Entity Mappings
**As a** data admin
**I want to** review algorithmically-generated entity mappings
**So that** I can ensure data quality

**Acceptance Criteria:**
- [ ] List of pending mappings (confidence < 0.9)
- [ ] Show source entity name and suggested ticker
- [ ] Show confidence score
- [ ] Show AI-suggested alternatives with scores
- [ ] Approve, reject, or correct each mapping
- [ ] Bulk approve high-confidence matches
- [ ] Audit trail for all decisions

#### US-028: Suggest Missing Entity Mapping
**As a** analyst
**I want to** suggest a ticker mapping for an unmapped entity
**So that** the data becomes actionable for me

**Acceptance Criteria:**
- [ ] View list of unmapped entities
- [ ] Filter by data source
- [ ] Submit mapping suggestion (entity → ticker)
- [ ] Include confidence and rationale text
- [ ] Receive notification when suggestion is reviewed
- [ ] View status of submitted suggestions

#### US-029: View Entity Mapping Coverage
**As a** data admin
**I want to** see entity mapping coverage statistics
**So that** I can prioritize mapping efforts

**Acceptance Criteria:**
- [ ] Dashboard showing % mapped by data source
- [ ] Show $ value or volume of unmapped entities
- [ ] Prioritized list of high-value unmapped entities
- [ ] Trend chart of mapping coverage over time
- [ ] Export unmapped entity list

#### US-030: Handle Corporate Actions
**As a** data admin
**I want to** be notified of corporate actions affecting mappings
**So that** historical data is properly adjusted

**Acceptance Criteria:**
- [ ] Alert on detected ticker changes, mergers, spinoffs
- [ ] Show affected entity mappings
- [ ] Preview historical adjustment impact
- [ ] Approve/reject adjustment
- [ ] Audit trail of adjustments

---

### Epic 8: Disaster & Event Signals

#### US-031: View Insurance Loss Estimates
**As a** insurance analyst
**I want to** see modeled loss estimates by insurer after disasters
**So that** I can assess sector impact

**Acceptance Criteria:**
- [ ] After earthquake above threshold, display loss estimate panel
- [ ] Break down by major insurers (ALL, TRV, CB, PGR, etc.)
- [ ] Show confidence interval (mean + variance)
- [ ] Consider insurer geographic book exposure
- [ ] Factor in reinsurance arrangements
- [ ] Compare to historical similar events

#### US-032: View Box Office Predictions
**As a** entertainment analyst
**I want to** see opening weekend forecasts from Thursday previews
**So that** I can anticipate studio performance

**Acceptance Criteria:**
- [ ] After Thursday preview numbers, show weekend forecast
- [ ] Ensemble model with multiple predictions
- [ ] Confidence intervals on forecast
- [ ] Compare to studio guidance/tracking
- [ ] Historical accuracy metrics for model
- [ ] Map to studio tickers (DIS, WBD, PARA, etc.)

---

### Epic 9: Data Catalog Management

#### US-033: Request New Data Source
**As a** analyst
**I want to** request that a new data source be added
**So that** I can get signals I need

**Acceptance Criteria:**
- [ ] Submit request form (source name, URL, description)
- [ ] Indicate priority and use case
- [ ] Track request status (submitted, evaluating, approved, rejected, implemented)
- [ ] Receive notification on status changes
- [ ] View all user requests with status

#### US-034: View Source Health Dashboard
**As a** data admin
**I want to** see health status of all data collectors
**So that** I can identify and fix issues

**Acceptance Criteria:**
- [ ] List all collectors with up/down status
- [ ] Show last successful collection timestamp
- [ ] Show data freshness vs SLA
- [ ] Alert on SLA breaches
- [ ] Show error logs for failed collections
- [ ] Manual trigger collection button

#### US-035: View Archived Sources
**As a** analyst
**I want to** access historical data from deprecated sources
**So that** I can maintain continuity in my research

**Acceptance Criteria:**
- [ ] Archived sources clearly labeled in catalog
- [ ] Historical data fully accessible via API
- [ ] Show deprecation reason and date
- [ ] Suggest alternative sources if available
- [ ] Factors from archived sources still computable

---

### Epic 10: User Management & Tiers

#### US-036: View Tier Usage
**As a** user
**I want to** see my API usage relative to tier limits
**So that** I know if I need to upgrade

**Acceptance Criteria:**
- [ ] Dashboard showing requests used / limit
- [ ] Show data volume consumed
- [ ] Show features available in current tier
- [ ] Warning at 80% and 95% usage
- [ ] Historical usage chart

#### US-037: Upgrade Tier
**As a** user
**I want to** upgrade my subscription tier
**So that** I can access more data and features

**Acceptance Criteria:**
- [ ] Compare tiers side-by-side
- [ ] Clear pricing for each tier
- [ ] One-click upgrade
- [ ] Immediate access to new tier features
- [ ] Prorated billing for mid-cycle upgrades

---

## Technical Specifications

### Data Sources (Phase 1 MVP)

| Source | Frequency | Latency | Real-Time | Primary Entities |
|--------|-----------|---------|-----------|------------------|
| TSA Checkpoint | Daily | 12h | Yes | DAL, UAL, AAL, LUV, JBLU, JETS |
| OpenTable | Weekly | 2d | No | DRI, MCD, SBUX, CMG, YUM |
| USGS Earthquake | Continuous | 15min | Yes | ALL, TRV, CB, PGR |
| UK Carbon Intensity | 30min | 30min | No | NG.L, SSE.L |
| FRED Building Permits | Monthly | 3wk | No | DHI, LEN, PHM, HD, LOW |
| Box Office | Daily | 1d | No | DIS, WBD, PARA, CMCSA, SONY |
| Cloudflare Radar | Hourly | 1h | Yes | NET, CRWD, PANW, ZS |
| Zillow Rental | Monthly | 1mo | No | EQR, AVB, MAA, INVH, AMH |

### Phase 1 Factors

| Source | Factor | Signal |
|--------|--------|--------|
| TSA | TSAThroughputMomentum | Air travel demand (7d rolling vs prior year) |
| TSA | TSAWeekdayWeekendRatio | Business vs leisure travel mix |
| TSA | TSAAirlineEnplanementNowcast | Monthly enplanement estimate |
| OpenTable | SeatedDinersMomentum | Dining demand acceleration |
| OpenTable | RegionalDiningSpread | Regional economic recovery disparity |
| OpenTable | RestaurantSectorHealth | Composite sector health (0-100) |
| USGS | SeismicRiskExposure | Asset proximity to events |
| USGS | DisasterImpactEstimate | Economic damage + insurer loss model |
| Carbon | CarbonIntensityTrend | Grid decarbonization progress |
| Carbon | RenewableShareGrowth | Energy transition momentum |
| Permits | PermitMomentum | Construction pipeline strength |
| Permits | PermitToStartRatio | Builder confidence gap |
| Permits | RenovationShareIndex | Market maturity indicator |
| BoxOffice | OpeningWeekendSurprise | Actual vs forecast (ensemble model) |
| BoxOffice | StudioMarketShare | Competitive position |
| Cloudflare | TrafficAnomalyIndex | Internet disruption detection |
| Cloudflare | SecurityThreatLevel | Cybersecurity spend driver |
| Zillow | RentInflationIndex | CPI housing leading indicator |
| Zillow | SFRMultifamilySpread | Housing type preference |

### Architecture

| Component | Technology |
|-----------|------------|
| Database | PostgreSQL (PIT-enabled) |
| Task Queue | Celery + Redis |
| API | FastAPI |
| Frontend | Professional fintech SaaS (light mode) |
| File Storage | S3-compatible |

### API Design

- **Versioning**: URL path (/api/v1/)
- **Formats**: JSON, CSV, Parquet, Arrow
- **Auth**: Bearer token (API key)
- **Rate Limiting**: Adaptive (load-based)
- **Pagination**: Cursor-based for large results

### Factor Output Format

```json
{
  "ticker": "DAL",
  "factor_id": "tsa_momentum",
  "as_of_date": "2026-01-22",
  "mean": 0.045,
  "variance": 0.0001,
  "data_quality": 0.95,
  "revision_status": "original"
}
```

### SLAs

| Metric | Target |
|--------|--------|
| Uptime | 99.99% (measured daily) |
| API P50 Latency | < 100ms |
| API P99 Latency | < 500ms |
| Factor Compute | < 1 hour batch |

---

## Entity Mapping

### Mapping Types

| Type | Example | Confidence Source |
|------|---------|-------------------|
| Government Contractors | DUNS → Ticker | Manual for top 25, ML for rest |
| Game Publishers | Game name → Ticker | Manual seed, pattern matching |
| Movie Studios | Distributor → Ticker | Manual (small set) |

### Confidence Thresholds

| Score | Action |
|-------|--------|
| 1.0 | Manual - auto-approved |
| 0.9+ | Algorithmic - auto-approved |
| 0.7-0.9 | Flagged for review |
| < 0.7 | Requires manual mapping |

### Unmapped Entity Handling

- Show AI-suggested mappings with confidence
- Allow user submissions
- Track for market context even without ticker

### Corporate Actions

- Full retroactive adjustment on mergers/spinoffs
- Version history maintained
- Audit trail for all changes

---

## Ticker Universe

| Market | Approximate Count |
|--------|-------------------|
| US (NYSE/NASDAQ) | 8,000 |
| ADRs | 2,000 |
| Europe | 5,000 |
| Japan | 3,500 |
| Emerging Markets | 10,000 |
| **Total** | ~28,500 |

### ETF Support

- Full weighted factor aggregation for any ETF
- Dynamic weights from latest holdings
- Custom basket definition

---

## Alerting

### Alert Types

| Type | Description |
|------|-------------|
| Threshold | Factor crosses value |
| Anomaly | ML-detected unusual movement |
| Event | Specific occurrence (earthquake, contract) |
| Compound | Multiple conditions combined |

### Channels

- Email (per-alert or digest)
- Webhook (generic POST)

### Fatigue Prevention

- ML-based smart suppression
- Cooldown periods
- Quiet hours
- Prioritization and bundling

---

## Backtesting

### Capabilities

- IC/IR calculation
- T-statistics
- Hit rate
- Decile spreads
- Turnover analysis
- Decay analysis (full spectrum: 1d to 252d)
- Seasonal decomposition (day-of-week, monthly, holiday, event)

### Return Data

User provides return data; platform provides factors.

### Survivorship Bias

Warning labels on affected periods; user responsible for delisted handling.

---

## Data Quality

### Revision Handling

Store both original and revised values with timestamps; flag revision status in API responses.

### Failure Handling

Silent gaps (missing data doesn't appear); operators alerted; backfill on recovery.

### Timezone

- Storage: UTC
- Metadata: Source timezone preserved
- Display: User-configurable
- API: Timezone-aware queries

---

## Pricing Tiers

| Tier | Rate Limit | Data Access | Features |
|------|------------|-------------|----------|
| Free | 100/day | Phase 1, 30d history | Basic API |
| Pro | 10K/day | All free, full history | Alerts, backtesting, SDK |
| Enterprise | Unlimited | All sources | Full features, SLA, support |
| Custom | Negotiated | Custom factors | White-glove |

---

## SDKs

### Python

```python
from altdata import Client

client = Client(api_key="...")
factors = client.factors.get("tsa_momentum", tickers=["DAL", "UAL"])

async for update in client.stream.subscribe(["tsa_momentum"]):
    print(f"{update.ticker}: {update.mean}")
```

### Pine Script

Full bidirectional TradingView integration:
- Generate indicators from factors
- Real-time data feed
- Sync annotations

---

## Commercial Vendor Comparison (Phase 9)

### Recommendations (Free-First)

| Category | Free Option | Commercial Alternative |
|----------|-------------|------------------------|
| Satellite | NASA VIIRS | Orbital Insight (real-time) |
| Foot Traffic | SafeGraph free tier | Advan Research |
| Job Postings | Indeed/Glassdoor scrape | Revelio Labs |
| Maritime AIS | MarineTraffic free tier | Kpler (commodities) |
| Credit Card | Deprioritize | High cost, high saturation |
| Retail Scanner | Deprioritize | Extreme cost (NielsenIQ) |
