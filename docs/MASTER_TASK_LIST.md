# Alternative Data Platform - Master Task List

> **Source of Truth** for all implementation tasks across the platform build-out.
> Generated from comprehensive planning document.

---

## Table of Contents

1. [Phase 1: Quick Wins (Free Public APIs)](#phase-1-quick-wins-free-public-apis)
2. [Phase 2: Government & Regulatory Data](#phase-2-government--regulatory-data)
3. [Phase 3: Gaming & Entertainment](#phase-3-gaming--entertainment)
4. [Phase 4: Energy & Commodities](#phase-4-energy--commodities)
5. [Phase 5: Satellite & Trade Data](#phase-5-satellite--trade-data)
6. [Phase 6: Infrastructure & VC](#phase-6-infrastructure--vc)
7. [Phase 7: Entity Mapping & Factor Computation](#phase-7-entity-mapping--factor-computation)
8. [Phase 8: Platform Integration](#phase-8-platform-integration)
9. [Phase 9: Commercial Data Expansion](#phase-9-commercial-data-expansion)
10. [Validation & Testing Framework](#validation--testing-framework)

---

## Phase Overview Matrix

| Phase | Focus Area | Tasks | Dependencies | Priority |
|-------|------------|-------|--------------|----------|
| **1** | Quick Wins (Free APIs) | 8 data sources | None | Highest |
| **2** | Government Data | 4 data sources | Phase 1 patterns | High |
| **3** | Gaming & Entertainment | 4 data sources | Phase 1 patterns | High |
| **4** | Energy & Commodities | 5 data sources | Phase 1 patterns | High |
| **5** | Satellite & Trade | 4 data sources | Phase 2-4 patterns | Medium |
| **6** | Infrastructure & VC | 3 data sources | Phase 1-5 patterns | Medium |
| **7** | Entity Mapping & Factors | 4 mapping systems | All Phase 1-6 data | High |
| **8** | Platform Integration | 4 UI components | All prior phases | Medium |
| **9** | Commercial Expansion | 6+ data sources | Platform complete | Low |

---

## Phase 1: Quick Wins (Free Public APIs)

**Goal**: Establish data collection patterns with free, publicly available APIs.
**Estimated Tasks**: 8 data sources, ~40 subtasks
**Dependencies**: None
**Validation**: Unit tests, data quality checks

---

### Task 1.1: TSA Checkpoint Data

**Priority**: 1 | **Effort**: Small | **Saturation**: LOW

#### 1.1.1 Data Acquisition
- [ ] Research TSA.gov page structure at `https://www.tsa.gov/travel/passenger-volumes`
- [ ] Determine scraping vs API approach (currently webpage scrape)
- [ ] Test rate limits and access patterns
- [ ] Document data format (daily throughput, YoY comparison)

#### 1.1.2 Collector Implementation
- [ ] Create `src/collectors/tsa_checkpoint.py`
- [ ] Inherit from `BaseCollector`
- [ ] Implement `fetch()` method with requests/BeautifulSoup
- [ ] Implement `parse()` method to extract daily figures
- [ ] Add error handling for missing days
- [ ] Implement historical backfill (2019-present)
- [ ] Register collector in scheduler (daily at 10:00 AM ET)

#### 1.1.3 Data Model
- [ ] Create SQLAlchemy model `TSACheckpoint`
  - `id`: Integer, primary key
  - `date`: Date, indexed
  - `current_year_throughput`: Integer
  - `prior_year_throughput`: Integer
  - `yoy_change_pct`: Float
  - `day_of_week`: Integer (0=Monday, 6=Sunday)
  - `is_holiday_period`: Boolean
  - `raw_data_id`: ForeignKey to raw_data_catalog
  - `created_at`: DateTime
- [ ] Create composite index on (date, day_of_week)
- [ ] Generate Alembic migration
- [ ] Run migration and verify schema

#### 1.1.4 Factor Implementation
- [ ] Implement `TSAThroughputMomentum` factor
  - 7-day rolling average vs same period prior year
  - Register with `@FactorRegistry.register`
  - Target entities: DAL, UAL, AAL, LUV, JBLU, JETS
- [ ] Implement `TSAWeekdayWeekendRatio` factor
  - Weekday avg / weekend avg (14-day lookback)
  - Signal for business vs leisure travel mix
  - Target entities: DAL, UAL (business heavy)
- [ ] Implement `TSAAirlineEnplanementNowcast` factor
  - Monthly TSA total × 0.97 correlation coefficient
  - Estimate monthly enplanements before BTS release

#### 1.1.5 Entity Mapping
- [ ] Create direct ticker mapping for airlines
  - High correlation: DAL, UAL, AAL, LUV, JBLU
  - Sector ETF: JETS
  - Secondary (travel-related): MAR, HLT

#### 1.1.6 Testing & Validation
- [ ] Write unit tests for collector
- [ ] Write unit tests for each factor
- [ ] Validate daily throughput in range 1M-4M
- [ ] Verify no data gaps > 1 day
- [ ] Backtest factor correlation with airline returns (target > 0.3)
- [ ] Verify data arrives by 10am ET daily

---

### Task 1.2: OpenTable Reservations

**Priority**: 1 | **Effort**: Medium | **Saturation**: LOW

#### 1.2.1 Data Acquisition
- [ ] Research OpenTable State of Industry page at `https://www.opentable.com/c/state-of-industry/`
- [ ] Identify JavaScript-rendered content requiring Playwright
- [ ] Map available metrics (YoY seated diners by region)
- [ ] Document weekly update schedule (Mondays)

#### 1.2.2 Collector Implementation
- [ ] Create `src/collectors/opentable.py`
- [ ] Install/configure Playwright dependencies
- [ ] Implement headless browser scraping
- [ ] Parse regional breakdown (US, UK, Germany, Australia, Canada)
- [ ] Parse city-level data if available
- [ ] Handle anti-bot measures appropriately
- [ ] Register collector in scheduler (weekly on Tuesday)
- [ ] Implement historical backfill (2020-present)

#### 1.2.3 Data Model
- [ ] Create SQLAlchemy model `OpenTableMetrics`
  - `id`: Integer, primary key
  - `week_ending`: Date, indexed
  - `region`: String (US, UK, Germany, etc.)
  - `city`: String (nullable for national level)
  - `yoy_seated_diners_pct`: Float
  - `raw_data_id`: ForeignKey
  - `created_at`: DateTime
- [ ] Create composite index on (week_ending, region)
- [ ] Create unique constraint on (week_ending, region, city)
- [ ] Generate and run Alembic migration

#### 1.2.4 Factor Implementation
- [ ] Implement `SeatedDinersMomentum` factor
  - Week-over-week change in YoY seated diners percentage
  - Signal: accelerating/decelerating dining demand
- [ ] Implement `RegionalDiningSpread` factor
  - Max - min YoY percentage across major regions
  - Signal: uneven economic recovery
- [ ] Implement `RestaurantSectorHealth` factor
  - 4-week rolling average, normalized 0-100 scale
  - Composite sector health indicator

#### 1.2.5 Entity Mapping
- [ ] Map US seated diners to restaurant tickers
  - DRI, MCD, SBUX, CMG, YUM (high strength)
- [ ] Map experiential dining growth to fine dining segment
- [ ] Map regional spread to regional restaurant REITs

#### 1.2.6 Testing & Validation
- [ ] Write unit tests for Playwright scraper
- [ ] Write unit tests for each factor
- [ ] Validate YoY percentage in range -100% to +200%
- [ ] Verify all major regions captured weekly
- [ ] Backtest factor correlation with DRI earnings (target > 0.4)
- [ ] Verify data arrives by Tuesday each week

---

### Task 1.3: USGS Earthquake API

**Priority**: 2 | **Effort**: Small | **Saturation**: NOVEL

#### 1.3.1 Data Acquisition
- [ ] Review USGS API documentation at `https://earthquake.usgs.gov/fdsnws/event/1/`
- [ ] Test API endpoints (GeoJSON format)
- [ ] Document query parameters (magnitude, location, time range)
- [ ] Verify no authentication required

#### 1.3.2 Collector Implementation
- [ ] Create `src/collectors/usgs_earthquake.py`
- [ ] Implement REST API client
- [ ] Query parameters: minmagnitude=4.0, format=geojson
- [ ] Parse event data (magnitude, location, depth, timestamp)
- [ ] Handle pagination for historical bulk loads
- [ ] Register collector (continuous polling, 15-minute intervals)
- [ ] Implement historical backfill (configurable depth)

#### 1.3.3 Data Model
- [ ] Create SQLAlchemy model `EarthquakeEvent`
  - `id`: Integer, primary key
  - `event_id`: String, unique (USGS ID)
  - `timestamp`: DateTime, indexed
  - `latitude`: Float
  - `longitude`: Float
  - `depth_km`: Float
  - `magnitude`: Float
  - `magnitude_type`: String (ml, mb, mw)
  - `place_description`: String
  - `felt_reports`: Integer
  - `tsunami_flag`: Boolean
  - `raw_data_id`: ForeignKey
- [ ] Generate and run Alembic migration

#### 1.3.4 Factor Implementation
- [ ] Implement `SeismicRiskExposure` factor
  - Company asset proximity to seismic events
  - Requires asset location database (future enhancement)
- [ ] Implement `DisasterImpactEstimate` factor
  - Modeled economic damage from magnitude + population
  - Insurance claims predictor

#### 1.3.5 Entity Mapping
- [ ] Map seismic events to insurance stocks: ALL, TRV, CB, PGR
- [ ] Map to regional REITs by event location
- [ ] Map to semiconductor fabs (TSMC Taiwan exposure)

#### 1.3.6 Testing & Validation
- [ ] Write unit tests for API client
- [ ] Write unit tests for factors
- [ ] Verify data arrives within 15 minutes of event
- [ ] Validate magnitude values are reasonable (0-10 scale)
- [ ] Test historical backfill accuracy

---

### Task 1.4: UK Carbon Intensity API

**Priority**: 2 | **Effort**: Small | **Saturation**: NOVEL

#### 1.4.1 Data Acquisition
- [ ] Review API documentation at `https://carbonintensity.org.uk/`
- [ ] Test endpoints: `/intensity`, `/generation`, `/regional`
- [ ] Verify no authentication required
- [ ] Document 30-minute interval data format

#### 1.4.2 Collector Implementation
- [ ] Create `src/collectors/carbon_intensity.py`
- [ ] Implement REST API client
- [ ] Fetch national and regional intensity data
- [ ] Fetch generation mix breakdown (biomass, coal, gas, nuclear, solar, wind)
- [ ] Register collector (30-minute intervals)
- [ ] Implement historical backfill (2018-present)

#### 1.4.3 Data Model
- [ ] Create SQLAlchemy model `CarbonIntensityReading`
  - `id`: Integer, primary key
  - `timestamp`: DateTime, indexed
  - `region`: String (UK national or regional code)
  - `intensity_forecast`: Integer (gCO2/kWh)
  - `intensity_actual`: Integer
  - `intensity_index`: String (very low, low, moderate, high, very high)
  - `generation_mix`: JSON ({"biomass": %, "coal": %, ...})
  - `raw_data_id`: ForeignKey
- [ ] Generate and run Alembic migration

#### 1.4.4 Factor Implementation
- [ ] Implement `CarbonIntensityTrend` factor
  - Month-over-month carbon intensity change
  - Signal: grid decarbonization progress
- [ ] Implement `RenewableShareGrowth` factor
  - % renewable in generation mix trend
  - Signal: energy transition momentum

#### 1.4.5 Entity Mapping
- [ ] Map to UK utilities: NG.L, SSE.L
- [ ] Map to ESG-focused ETFs
- [ ] Map to carbon credit markets (future)

#### 1.4.6 Testing & Validation
- [ ] Write unit tests for API client
- [ ] Write unit tests for factors
- [ ] Verify 30-minute data intervals
- [ ] Validate intensity values reasonable (0-500 gCO2/kWh range)

---

### Task 1.5: FRED Building Permits

**Priority**: 1 | **Effort**: Small | **Saturation**: LOW

#### 1.5.1 Data Acquisition
- [ ] Review FRED API for PERMIT series
- [ ] Identify related series: PERMITNSA, regional permits
- [ ] Verify FRED API key configuration
- [ ] Document monthly release schedule (~3 weeks after month end)

#### 1.5.2 Collector Implementation
- [ ] Extend existing `src/collectors/fred_collector.py`
- [ ] Add PERMIT series to collection list
- [ ] Add PERMITNSA (non-seasonally adjusted)
- [ ] Add regional permit series (PERMIT1, PERMIT2, etc.)
- [ ] Verify historical backfill (1960-present available)

#### 1.5.3 Data Model
- [ ] Create SQLAlchemy model `BuildingPermitData`
  - `id`: Integer, primary key
  - `period`: Date, indexed
  - `geography_level`: String (national, state, county, place)
  - `geography_code`: String
  - `geography_name`: String
  - `permit_type`: String (total, single_family, multi_family)
  - `units_authorized`: Integer
  - `valuation`: Numeric(15,2)
  - `raw_data_id`: ForeignKey
- [ ] Generate and run Alembic migration

#### 1.5.4 Factor Implementation
- [ ] Implement `PermitMomentum` factor
  - Month-over-month change in permit volume
  - Signal: construction pipeline strength
- [ ] Implement `PermitToStartRatio` factor
  - Permits issued / housing starts begun
  - Signal: builder confidence/execution gap
- [ ] Implement `RenovationShareIndex` factor
  - Renovation permits / new construction permits
  - Signal: market maturity indicator

#### 1.5.5 Entity Mapping
- [ ] Map national permits to homebuilders: DHI, LEN, PHM, TOL, NVR
- [ ] Map regional permits to regional homebuilders
- [ ] Map renovation share to home improvement: HD, LOW

#### 1.5.6 Testing & Validation
- [ ] Write unit tests for extended FRED collector
- [ ] Write unit tests for factors
- [ ] Verify monthly data freshness
- [ ] Validate permit values against Census BPS

---

### Task 1.6: Movie Box Office (TheNumbers)

**Priority**: 2 | **Effort**: Medium | **Saturation**: LOW

#### 1.6.1 Data Acquisition
- [ ] Research TheNumbers page structure at `https://www.the-numbers.com/box-office-chart/daily`
- [ ] Map available data: daily gross, theater count, per-screen average
- [ ] Identify weekend vs daily chart differences
- [ ] Document update schedule (daily)

#### 1.6.2 Collector Implementation
- [ ] Create `src/collectors/boxoffice.py`
- [ ] Implement web scraper for daily charts
- [ ] Implement web scraper for weekend charts
- [ ] Parse movie title, distributor, gross, theaters
- [ ] Handle cumulative gross tracking
- [ ] Register collector (daily)
- [ ] Implement historical backfill (1995-present)

#### 1.6.3 Data Model
- [ ] Create SQLAlchemy model `BoxOfficeDaily`
  - `id`: Integer, primary key
  - `date`: Date, indexed
  - `movie_title`: String
  - `distributor`: String
  - `distributor_ticker`: String, indexed
  - `daily_gross`: Numeric(15,2)
  - `cumulative_gross`: Numeric(15,2)
  - `theater_count`: Integer
  - `per_theater_avg`: Numeric(10,2)
  - `days_in_release`: Integer
  - `raw_data_id`: ForeignKey
- [ ] Generate and run Alembic migration

#### 1.6.4 Factor Implementation
- [ ] Implement `OpeningWeekendSurprise` factor
  - Actual gross vs tracking estimates (requires estimate source)
  - Signal: earnings surprise proxy
- [ ] Implement `StudioMarketShare` factor
  - Studio gross / total market gross
  - Signal: competitive position

#### 1.6.5 Entity Mapping (Task 7.3 dependency)
- [ ] Create studio-to-ticker mapping table
  - Disney → DIS
  - Warner Bros → WBD
  - Paramount → PARA
  - Universal → CMCSA
  - Sony Pictures → SONY
  - Lionsgate → LGF.A

#### 1.6.6 Testing & Validation
- [ ] Write unit tests for scraper
- [ ] Write unit tests for factors
- [ ] Verify daily data freshness
- [ ] Validate gross values are reasonable
- [ ] Cross-reference with public announcements

---

### Task 1.7: Cloudflare Radar API

**Priority**: 2 | **Effort**: Small | **Saturation**: NOVEL

#### 1.7.1 Data Acquisition
- [ ] Review Cloudflare Radar API documentation
- [ ] Register for free API token
- [ ] Test endpoints: `/traffic`, `/attacks`, `/outages`
- [ ] Document rate limits

#### 1.7.2 Collector Implementation
- [ ] Create `src/collectors/cloudflare_radar.py`
- [ ] Implement REST API client with authentication
- [ ] Fetch global traffic volumes
- [ ] Fetch attack/DDoS trends
- [ ] Fetch outage data
- [ ] Register collector (hourly)

#### 1.7.3 Data Model
- [ ] Create SQLAlchemy model `CloudflareRadarMetrics`
  - `id`: Integer, primary key
  - `timestamp`: DateTime, indexed
  - `metric_type`: String (traffic, attacks, outages)
  - `region`: String (global or country code)
  - `value`: Float
  - `metadata`: JSON
  - `raw_data_id`: ForeignKey
- [ ] Generate and run Alembic migration

#### 1.7.4 Factor Implementation
- [ ] Implement `TrafficAnomalyIndex` factor
  - Deviation from baseline traffic
  - Signal: internet outage/disruption detection
- [ ] Implement `SecurityThreatLevel` factor
  - DDoS attack volume trends
  - Signal: cybersecurity spend driver

#### 1.7.5 Testing & Validation
- [ ] Write unit tests for API client
- [ ] Write unit tests for factors
- [ ] Verify hourly data collection
- [ ] Validate anomaly detection accuracy

---

### Task 1.8: Zillow Rental Data

**Priority**: 2 | **Effort**: Small | **Saturation**: LOW

#### 1.8.1 Data Acquisition
- [ ] Review Zillow Research data downloads at `https://www.zillow.com/research/data/`
- [ ] Identify ZORI (Zillow Observed Rent Index) CSV files
- [ ] Map available geographic levels (national, metro, zip)
- [ ] Document monthly release schedule

#### 1.8.2 Collector Implementation
- [ ] Create `src/collectors/zillow_rental.py`
- [ ] Implement CSV download and parsing
- [ ] Handle multiple geographic granularities
- [ ] Register collector (monthly)
- [ ] Implement historical backfill (2015-present)

#### 1.8.3 Data Model
- [ ] Create SQLAlchemy model `ZillowRentalIndex`
  - `id`: Integer, primary key
  - `period`: Date, indexed
  - `geography_level`: String (national, metro, zip)
  - `geography_id`: String
  - `geography_name`: String
  - `zori_value`: Float (rent index)
  - `mom_change_pct`: Float
  - `yoy_change_pct`: Float
  - `raw_data_id`: ForeignKey
- [ ] Generate and run Alembic migration

#### 1.8.4 Factor Implementation
- [ ] Implement `RentInflationIndex` factor
  - ZORI YoY change
  - Signal: CPI housing component leading indicator
- [ ] Implement `SFRMultifamilySpread` factor
  - Single-family rent vs apartment rent differential
  - Signal: housing type preference

#### 1.8.5 Entity Mapping
- [ ] Map to apartment REITs: EQR, AVB, MAA
- [ ] Map to SFR REITs: INVH, AMH
- [ ] Map to homebuilders with SFR exposure

#### 1.8.6 Testing & Validation
- [ ] Write unit tests for CSV parser
- [ ] Write unit tests for factors
- [ ] Verify monthly data freshness
- [ ] Validate index values reasonable

---

## Phase 2: Government & Regulatory Data

**Goal**: Implement government procurement and regulatory data sources.
**Estimated Tasks**: 4 data sources, ~25 subtasks
**Dependencies**: Phase 1 patterns established
**Validation**: Entity mapping validation, contract value checks

---

### Task 2.1: FPDS Federal Contracts

**Priority**: 1 | **Effort**: Large | **Saturation**: LOW

#### 2.1.1 Data Acquisition
- [ ] Register for FPDS.gov account
- [ ] Review ATOM feed documentation
- [ ] Test bulk download endpoints
- [ ] Document data dictionary (contract fields)
- [ ] Understand 24-48 hour posting delay

#### 2.1.2 Collector Implementation
- [ ] Create `src/collectors/fpds.py`
- [ ] Implement ATOM feed parser for incremental updates
- [ ] Implement bulk download handler for historical data
- [ ] Parse all contract fields (vendor, agency, value, dates, PSC, NAICS)
- [ ] Handle contract modifications (deduplication)
- [ ] Register collector (daily incremental)
- [ ] Implement historical backfill strategy (50M+ contracts)

#### 2.1.3 Data Model
- [ ] Create SQLAlchemy model `GovernmentContract`
  - `contract_id`: String, unique
  - `vendor_duns`: String, indexed
  - `vendor_uei`: String, indexed
  - `vendor_name`: String
  - `vendor_address_state`: String(2)
  - `awarding_agency_code`: String
  - `awarding_agency_name`: String
  - `contract_value`: Numeric(15,2)
  - `base_value`: Numeric(15,2)
  - `options_value`: Numeric(15,2)
  - `award_date`: Date, indexed
  - `performance_start`: Date
  - `performance_end`: Date
  - `product_service_code`: String
  - `naics_code`: String
  - `contract_type`: String
  - `ticker`: String, indexed (mapped)
  - `sector`: String
- [ ] Create composite indexes for common queries
- [ ] Generate and run Alembic migration

#### 2.1.4 Factor Implementation
- [ ] Implement `ContractWinMomentum` factor
  - YoY change in contract value won (TTM)
  - Signal: revenue predictor for gov contractors
- [ ] Implement `NewMegaContractAlert` factor
  - Contract value > 2σ from company historical mean
  - Signal: lumpy revenue event
- [ ] Implement `GovernmentRevenueExposure` factor
  - TTM contract value (proxy for gov revenue)
- [ ] Implement `AgencyConcentrationRisk` factor
  - Herfindahl index by awarding agency
  - Signal: customer concentration risk

#### 2.1.5 Testing & Validation
- [ ] Write unit tests for ATOM parser
- [ ] Write unit tests for factors
- [ ] Validate 95% of top 25 contractors mapped
- [ ] Verify contract values in reasonable ranges
- [ ] Ensure no future-dated awards
- [ ] Backtest factor IC > 0.02 for LMT, RTX

---

### Task 2.2: USAspending.gov

**Priority**: 2 | **Effort**: Medium | **Saturation**: LOW

#### 2.2.1 Data Acquisition
- [ ] Review USAspending API documentation
- [ ] Test download/API endpoints
- [ ] Understand relationship to FPDS (aggregation)
- [ ] Document available data beyond FPDS

#### 2.2.2 Collector Implementation
- [ ] Create `src/collectors/usaspending.py`
- [ ] Implement API client
- [ ] Focus on data not in FPDS (grants, loans)
- [ ] Register collector (weekly)

#### 2.2.3 Data Model
- [ ] Create or extend government spending models
- [ ] Generate Alembic migration

#### 2.2.4 Testing & Validation
- [ ] Write unit tests
- [ ] Validate data completeness

---

### Task 2.3: Congressional Trading

**Priority**: 2 | **Effort**: Medium | **Saturation**: MEDIUM

#### 2.3.1 Data Acquisition
- [ ] Research Capitol Trades, Quiver Quant, or SEC filings
- [ ] Identify data sources for congressional trades
- [ ] Document disclosure timing (45 days)

#### 2.3.2 Collector Implementation
- [ ] Create `src/collectors/congressional_trades.py`
- [ ] Implement data collection (scraping or API)
- [ ] Parse trade details (member, ticker, date, amount, type)
- [ ] Register collector (daily)

#### 2.3.3 Data Model
- [ ] Create SQLAlchemy model `CongressionalTrade`
- [ ] Generate Alembic migration

#### 2.3.4 Factor Implementation
- [ ] Implement `CongressTradeAlert` factor
  - Flag significant congressional trades
  - Signal: political information edge

#### 2.3.5 Testing & Validation
- [ ] Write unit tests
- [ ] Validate trade data accuracy

---

### Task 2.4: FCC Cell Tower Data

**Priority**: 3 | **Effort**: Medium | **Saturation**: NOVEL

#### 2.4.1 Data Acquisition
- [ ] Review FCC Universal Licensing System
- [ ] Research OpenCelliD database
- [ ] Document tower permit/registration process

#### 2.4.2 Collector Implementation
- [ ] Create `src/collectors/fcc_towers.py`
- [ ] Implement data collection from FCC ULS
- [ ] Parse tower registrations and permits
- [ ] Register collector (weekly)

#### 2.4.3 Data Model
- [ ] Create SQLAlchemy model for cell tower data
- [ ] Generate Alembic migration

#### 2.4.4 Factor Implementation
- [ ] Implement `TowerPermitVelocity` factor
  - New permits filed per month
  - Signal: telecom capex deployment
- [ ] Implement `5GCoverageExpansion` factor
  - New 5G sites / total sites ratio

#### 2.4.5 Entity Mapping
- [ ] Map to carriers: T, VZ, TMUS
- [ ] Map to tower REITs: AMT, CCI, SBAC

#### 2.4.6 Testing & Validation
- [ ] Write unit tests
- [ ] Validate permit counts

---

## Phase 3: Gaming & Entertainment

**Goal**: Capture gaming engagement metrics for publisher revenue signals.
**Estimated Tasks**: 4 data sources, ~20 subtasks
**Dependencies**: Phase 1 patterns
**Validation**: Publisher revenue correlation

---

### Task 3.1: Twitch API

**Priority**: 1 | **Effort**: Small | **Saturation**: LOW

#### 3.1.1 Data Acquisition
- [ ] Register Twitch Developer application
- [ ] Obtain OAuth Client Credentials
- [ ] Review API endpoints: `/games/top`, `/streams`
- [ ] Document 800 requests/minute rate limit

#### 3.1.2 Collector Implementation
- [ ] Create `src/collectors/twitch.py`
- [ ] Implement OAuth authentication
- [ ] Fetch top 100 games by viewership
- [ ] Fetch viewer counts, channel counts
- [ ] Register collector (hourly)
- [ ] Implement historical aggregation

#### 3.1.3 Data Model
- [ ] Create SQLAlchemy model `TwitchMetrics`
  - `timestamp`: DateTime, indexed
  - `game_name`: String
  - `publisher_ticker`: String, indexed
  - `avg_viewers`: Integer
  - `peak_viewers`: Integer
  - `channels_broadcasting`: Integer
- [ ] Generate Alembic migration

#### 3.1.4 Factor Implementation
- [ ] Implement `TwitchViewerGrowth` factor
  - Game's avg viewers month-over-month
  - Signal: game popularity trend
- [ ] Implement `StreamerMigration` factor
  - Top streamers switching games
  - Signal: platform/game shifts

#### 3.1.5 Entity Mapping (Task 7.2 dependency)
- [ ] Create game-to-publisher mapping
- [ ] Map publishers to tickers: EA, ATVI, TTWO, UBSFY, RBLX

#### 3.1.6 Testing & Validation
- [ ] Write unit tests for OAuth flow
- [ ] Write unit tests for factors
- [ ] Validate viewer counts reasonable
- [ ] Backtest correlation with publisher earnings

---

### Task 3.2: Steam Charts

**Priority**: 1 | **Effort**: Small | **Saturation**: LOW

#### 3.2.1 Data Acquisition
- [ ] Review SteamCharts.com or Steam Web API
- [ ] Identify concurrent player data availability
- [ ] Document data format and update frequency

#### 3.2.2 Collector Implementation
- [ ] Create `src/collectors/steam.py`
- [ ] Implement data collection (API or scrape)
- [ ] Fetch concurrent player counts by game
- [ ] Register collector (daily)

#### 3.2.3 Data Model
- [ ] Create SQLAlchemy model `SteamMetrics`
  - `timestamp`: DateTime, indexed
  - `app_id`: Integer
  - `game_name`: String
  - `publisher_ticker`: String, indexed
  - `concurrent_players`: Integer
  - `peak_24h`: Integer
- [ ] Generate Alembic migration

#### 3.2.4 Factor Implementation
- [ ] Implement `SteamConcurrentPeak` factor
  - Peak players vs all-time high
  - Signal: game retention/engagement

#### 3.2.5 Testing & Validation
- [ ] Write unit tests
- [ ] Validate player counts

---

### Task 3.3: Discord API

**Priority**: 2 | **Effort**: Medium | **Saturation**: LOW

#### 3.3.1 Data Acquisition
- [ ] Review Discord API capabilities
- [ ] Identify public server discovery limitations
- [ ] Document available metrics

#### 3.3.2 Collector Implementation
- [ ] Create `src/collectors/discord.py`
- [ ] Implement server member tracking (if available)
- [ ] Register collector (daily)

#### 3.3.3 Data Model
- [ ] Create SQLAlchemy model for Discord metrics
- [ ] Generate Alembic migration

#### 3.3.4 Factor Implementation
- [ ] Implement `DiscordServerGrowth` factor
  - New members per week
  - Signal: community engagement

#### 3.3.5 Testing & Validation
- [ ] Write unit tests
- [ ] Validate data accuracy

---

### Task 3.4: Kickstarter API

**Priority**: 2 | **Effort**: Medium | **Saturation**: NOVEL

#### 3.4.1 Data Acquisition
- [ ] Research Kickstarter data access (scraping likely required)
- [ ] Identify campaign data fields
- [ ] Document category structure

#### 3.4.2 Collector Implementation
- [ ] Create `src/collectors/kickstarter.py`
- [ ] Implement web scraper or API client
- [ ] Track funding amounts, backer counts, success rates
- [ ] Register collector (daily)

#### 3.4.3 Data Model
- [ ] Create SQLAlchemy model `KickstarterCampaign`
- [ ] Generate Alembic migration

#### 3.4.4 Factor Implementation
- [ ] Implement `CategoryFundingVelocity` factor
  - Category $ raised per week
  - Signal: consumer category interest
- [ ] Implement `OverfundingRatio` factor
  - Amount raised / goal
  - Signal: demand strength

#### 3.4.5 Testing & Validation
- [ ] Write unit tests
- [ ] Validate campaign data

---

## Phase 4: Energy & Commodities

**Goal**: Capture energy markets and commodity price signals.
**Estimated Tasks**: 5 data sources, ~25 subtasks
**Dependencies**: Phase 1 patterns
**Validation**: Price signal backtesting

---

### Task 4.1: Lumber Futures

**Priority**: 2 | **Effort**: Small | **Saturation**: LOW

#### 4.1.1 Data Acquisition
- [ ] Research CME lumber futures data access
- [ ] Review FRED lumber price series
- [ ] Document available price points

#### 4.1.2 Collector Implementation
- [ ] Create `src/collectors/lumber_futures.py`
- [ ] Implement data collection from FRED or CME
- [ ] Register collector (daily)

#### 4.1.3 Data Model
- [ ] Create SQLAlchemy model for lumber prices
- [ ] Generate Alembic migration

#### 4.1.4 Factor Implementation
- [ ] Implement `LumberFuturesMomentum` factor
  - 30-day price change
  - Signal: building material cost trend
- [ ] Implement `BuilderMarginProxy` factor
  - Home price / lumber cost ratio

#### 4.1.5 Entity Mapping
- [ ] Map to homebuilders: DHI, LEN, PHM
- [ ] Map to timberlands: WY, RYN

#### 4.1.6 Testing & Validation
- [ ] Write unit tests
- [ ] Backtest correlation with homebuilder margins

---

### Task 4.2: Manheim Index (Used Cars)

**Priority**: 2 | **Effort**: Small | **Saturation**: LOW

#### 4.2.1 Data Acquisition
- [ ] Research Manheim MUVVI release schedule
- [ ] Identify scraping approach for index values
- [ ] Document mid-month and end-of-month releases

#### 4.2.2 Collector Implementation
- [ ] Create `src/collectors/manheim.py`
- [ ] Implement web scraper for index values
- [ ] Capture main index, EV index, non-EV index
- [ ] Register collector (bi-weekly)

#### 4.2.3 Data Model
- [ ] Create SQLAlchemy model `ManheimIndex`
  - `date`: Date, indexed
  - `muvvi_value`: Float
  - `ev_index`: Float
  - `non_ev_index`: Float
  - `yoy_change_pct`: Float
  - `mom_change_pct`: Float
- [ ] Generate Alembic migration

#### 4.2.4 Factor Implementation
- [ ] Implement `ManheimMomentum` factor
  - MoM index change
- [ ] Implement `EVvsICESpread` factor
  - EV index / non-EV index
  - Signal: EV demand relative to ICE

#### 4.2.5 Entity Mapping
- [ ] Map to auto dealers: KMX, AN, LAD
- [ ] Map to rental: CAR, HTZ
- [ ] Map to OEMs: F, GM

#### 4.2.6 Testing & Validation
- [ ] Write unit tests
- [ ] Validate index values

---

### Task 4.3: ISO Power Grid Data

**Priority**: 1 | **Effort**: Medium | **Saturation**: LOW

#### 4.3.1 Data Acquisition
- [ ] Research PJM Dataminer API
- [ ] Research ERCOT data products
- [ ] Research CAISO OASIS
- [ ] Research ISO-NE Express
- [ ] Document data formats and access requirements

#### 4.3.2 Collector Implementation
- [ ] Create `src/collectors/power_lmp.py`
- [ ] Implement PJM collector
- [ ] Implement ERCOT collector
- [ ] Implement CAISO collector
- [ ] Implement ISO-NE collector
- [ ] Register collectors (hourly day-ahead, 5-minute real-time)

#### 4.3.3 Data Model
- [ ] Create SQLAlchemy model `LMPPrice`
  - `timestamp`: DateTime, indexed
  - `iso`: String (PJM, ERCOT, CAISO, ISONE)
  - `node_id`: String
  - `market_type`: String (DAY_AHEAD, REAL_TIME)
  - `lmp`: Float
  - `energy_component`: Float
  - `congestion_component`: Float
  - `loss_component`: Float
- [ ] Generate Alembic migration

#### 4.3.4 Factor Implementation
- [ ] Implement `LMPVolatility` factor
  - Standard deviation of hourly prices
- [ ] Implement `LoadSurprise` factor
  - Actual vs forecasted load
  - Signal: economic activity proxy
- [ ] Implement `RenewableShare` factor
  - % wind/solar in generation mix

#### 4.3.5 Entity Mapping
- [ ] Map to utilities by ISO region
- [ ] Map to data center demand (future)

#### 4.3.6 Testing & Validation
- [ ] Write unit tests for each ISO collector
- [ ] Validate price data ranges
- [ ] Verify real-time data freshness

---

### Task 4.4: EIA Natural Gas Storage

**Priority**: 2 | **Effort**: Small | **Saturation**: MEDIUM

#### 4.4.1 Data Acquisition
- [ ] Review EIA Weekly Natural Gas Storage Report
- [ ] Document Thursday 10:30 AM ET release schedule
- [ ] Identify API or download endpoint

#### 4.4.2 Collector Implementation
- [ ] Create `src/collectors/eia_natgas.py`
- [ ] Implement weekly data collection
- [ ] Capture working gas, injection/withdrawal, regional data
- [ ] Register collector (weekly on Thursday)

#### 4.4.3 Data Model
- [ ] Create SQLAlchemy model for natural gas storage
- [ ] Generate Alembic migration

#### 4.4.4 Factor Implementation
- [ ] Implement `StorageSurprise` factor
  - Actual change vs estimate
- [ ] Implement `StorageVs5YrAvg` factor
  - Current storage / 5-year average

#### 4.4.5 Entity Mapping
- [ ] Map to natural gas producers: EQT, AR, CHK
- [ ] Map to UNG ETF

#### 4.4.6 Testing & Validation
- [ ] Write unit tests
- [ ] Validate storage values

---

### Task 4.5: Container Port TEU

**Priority**: 2 | **Effort**: Medium | **Saturation**: MEDIUM

#### 4.5.1 Data Acquisition
- [ ] Research Port of LA/Long Beach data
- [ ] Review World Bank port data
- [ ] Document release schedules

#### 4.5.2 Collector Implementation
- [ ] Create `src/collectors/container_ports.py`
- [ ] Implement data collection for major ports
- [ ] Track TEU volumes (imports, exports)
- [ ] Register collector (monthly)

#### 4.5.3 Data Model
- [ ] Create SQLAlchemy model for port throughput
- [ ] Generate Alembic migration

#### 4.5.4 Factor Implementation
- [ ] Implement `PortThroughputGrowth` factor
  - YoY TEU change
- [ ] Implement `ImportExportImbalance` factor
  - Inbound / outbound TEUs

#### 4.5.5 Entity Mapping
- [ ] Map to logistics: FDX, UPS
- [ ] Map to import-dependent retailers: AMZN

#### 4.5.6 Testing & Validation
- [ ] Write unit tests
- [ ] Validate TEU values

---

## Phase 5: Satellite & Trade Data

**Goal**: Implement novel satellite and trade flow data sources.
**Estimated Tasks**: 4 data sources, ~20 subtasks
**Dependencies**: Phase 2-4 patterns
**Validation**: Cross-source validation

---

### Task 5.1: VIIRS Nightlights

**Priority**: 2 | **Effort**: Medium | **Saturation**: NOVEL

#### 5.1.1 Data Acquisition
- [ ] Review NASA Earth Observations (earthdata.nasa.gov)
- [ ] Review World Bank Night Lights data
- [ ] Document VIIRS monthly data format
- [ ] Understand data access (registration required)

#### 5.1.2 Collector Implementation
- [ ] Create `src/collectors/viirs_nightlights.py`
- [ ] Implement NASA data download
- [ ] Process satellite imagery (may need specialized libraries)
- [ ] Aggregate by geography (country, region)
- [ ] Register collector (monthly)

#### 5.1.3 Data Model
- [ ] Create SQLAlchemy model for nightlight intensity
- [ ] Generate Alembic migration

#### 5.1.4 Factor Implementation
- [ ] Implement `NightLightGrowth` factor
  - YoY light intensity change
  - Signal: GDP growth proxy for emerging markets

#### 5.1.5 Testing & Validation
- [ ] Write unit tests
- [ ] Validate correlation with official GDP

---

### Task 5.2: Tax Lien/Foreclosure Data

**Priority**: 3 | **Effort**: Large | **Saturation**: NOVEL

#### 5.2.1 Data Acquisition
- [ ] Research county tax collector data sources
- [ ] Evaluate GovEase, Tax Sale Resources
- [ ] Document available data fields

#### 5.2.2 Collector Implementation
- [ ] Create `src/collectors/tax_liens.py`
- [ ] Implement data collection from available sources
- [ ] Track liens sold, foreclosures, auction results
- [ ] Register collector (monthly)

#### 5.2.3 Data Model
- [ ] Create SQLAlchemy model for real estate distress
- [ ] Generate Alembic migration

#### 5.2.4 Factor Implementation
- [ ] Implement `TaxLienVolumeGrowth` factor
  - YoY change in liens sold
  - Signal: real estate distress

#### 5.2.5 Entity Mapping
- [ ] Map to REITs, homebuilders, mortgage servicers

#### 5.2.6 Testing & Validation
- [ ] Write unit tests
- [ ] Validate data coverage

---

### Task 5.3: OpenCelliD 5G Coverage

**Priority**: 3 | **Effort**: Medium | **Saturation**: NOVEL

#### 5.3.1 Data Acquisition
- [ ] Review OpenCelliD database access
- [ ] Document cell tower data format
- [ ] Identify 5G vs 4G differentiation

#### 5.3.2 Collector Implementation
- [ ] Create `src/collectors/opencellid.py`
- [ ] Implement data collection
- [ ] Track cell tower locations and types
- [ ] Register collector (weekly)

#### 5.3.3 Data Model
- [ ] Create SQLAlchemy model for cell coverage
- [ ] Generate Alembic migration

#### 5.3.4 Factor Implementation
- [ ] Implement `5GDeploymentRate` factor
  - 5G towers / total towers over time

#### 5.3.5 Testing & Validation
- [ ] Write unit tests
- [ ] Validate coverage data

---

### Task 5.4: USGS Critical Minerals

**Priority**: 3 | **Effort**: Small | **Saturation**: LOW

#### 5.4.1 Data Acquisition
- [ ] Review USGS Mineral Commodity Summaries
- [ ] Review IEA Critical Minerals Explorer
- [ ] Document annual/quarterly release schedules

#### 5.4.2 Collector Implementation
- [ ] Create `src/collectors/critical_minerals.py`
- [ ] Implement data collection from USGS
- [ ] Track production by mineral and country
- [ ] Register collector (quarterly)

#### 5.4.3 Data Model
- [ ] Create SQLAlchemy model for mineral production
- [ ] Generate Alembic migration

#### 5.4.4 Factor Implementation
- [ ] Implement `ProductionConcentrationRisk` factor
  - Top 3 country share
  - Signal: supply chain risk

#### 5.4.5 Entity Mapping
- [ ] Map to lithium: ALB, LTHM
- [ ] Map to rare earths: MP
- [ ] Map to copper: FCX, SCCO

#### 5.4.6 Testing & Validation
- [ ] Write unit tests
- [ ] Validate production values

---

## Phase 6: Infrastructure & VC

**Goal**: Capture AI infrastructure and startup ecosystem signals.
**Estimated Tasks**: 3 data sources, ~15 subtasks
**Dependencies**: Phase 1-5 patterns
**Validation**: Data freshness monitoring

---

### Task 6.1: Data Center Pipeline

**Priority**: 2 | **Effort**: Medium | **Saturation**: LOW

#### 6.1.1 Data Acquisition
- [ ] Research CBRE Data Center Reports
- [ ] Review Synergy Research data
- [ ] Review Data Center Frontier news
- [ ] Document available metrics (MW capacity, vacancy)

#### 6.1.2 Collector Implementation
- [ ] Create `src/collectors/datacenter.py`
- [ ] Implement data collection (may be manual/quarterly)
- [ ] Track capacity additions, construction pipeline
- [ ] Register collector (monthly/quarterly)

#### 6.1.3 Data Model
- [ ] Create SQLAlchemy model for data center capacity
- [ ] Generate Alembic migration

#### 6.1.4 Factor Implementation
- [ ] Implement `CapacityGrowthRate` factor
  - New MW added / existing MW
  - Signal: AI infrastructure demand

#### 6.1.5 Entity Mapping
- [ ] Map to DC REITs: EQIX, DLR
- [ ] Map to AI chips: NVDA, AMD

#### 6.1.6 Testing & Validation
- [ ] Write unit tests
- [ ] Validate capacity values

---

### Task 6.2: Crunchbase VC Data

**Priority**: 2 | **Effort**: Medium | **Saturation**: MEDIUM

#### 6.2.1 Data Acquisition
- [ ] Review Crunchbase free tier capabilities
- [ ] Document API rate limits
- [ ] Identify available fields (funding rounds, amounts)

#### 6.2.2 Collector Implementation
- [ ] Create `src/collectors/crunchbase.py`
- [ ] Implement API client (within free tier limits)
- [ ] Track funding rounds by sector
- [ ] Register collector (daily/weekly)

#### 6.2.3 Data Model
- [ ] Create SQLAlchemy model for VC funding
- [ ] Generate Alembic migration

#### 6.2.4 Factor Implementation
- [ ] Implement `SectorFundingVelocity` factor
  - Category $ raised month-over-month
- [ ] Implement `MegaRoundCount` factor
  - Deals > $100M / total deals

#### 6.2.5 Testing & Validation
- [ ] Write unit tests
- [ ] Validate funding amounts

---

### Task 6.3: Office Lease Data

**Priority**: 3 | **Effort**: Medium | **Saturation**: MEDIUM

#### 6.3.1 Data Acquisition
- [ ] Research CBRE, JLL, CoStar data access
- [ ] Identify free vs paid data sources
- [ ] Document available metrics (vacancy, lease rates)

#### 6.3.2 Collector Implementation
- [ ] Create `src/collectors/office_lease.py`
- [ ] Implement data collection from available sources
- [ ] Track vacancy rates, lease rates, absorption
- [ ] Register collector (quarterly)

#### 6.3.3 Data Model
- [ ] Create SQLAlchemy model for office market data
- [ ] Generate Alembic migration

#### 6.3.4 Factor Implementation
- [ ] Implement `VacancyTrend` factor
  - QoQ vacancy rate change
- [ ] Implement `NetAbsorptionIndex` factor
  - Absorption / total inventory

#### 6.3.5 Entity Mapping
- [ ] Map to office REITs: BXP, SLG, VNO

#### 6.3.6 Testing & Validation
- [ ] Write unit tests
- [ ] Validate market data

---

## Phase 7: Entity Mapping & Factor Computation

**Goal**: Build robust entity mapping and implement all Phase 1-6 factors.
**Estimated Tasks**: 4 mapping systems, comprehensive factor validation
**Dependencies**: All Phase 1-6 data
**Validation**: Factor IC/IR validation

---

### Task 7.1: DUNS→Ticker Mapping

**Priority**: 1 | **Effort**: Large | **Saturation**: N/A

#### 7.1.1 Mapping Table Design
- [ ] Create SQLAlchemy model `GovernmentContractorMapping`
  - `duns`: String, indexed
  - `uei`: String, indexed
  - `vendor_name_pattern`: String (regex)
  - `ticker`: String, indexed
  - `company_name`: String
  - `confidence_score`: Float (1.0=manual, 0.7=algorithm)
  - `updated_at`: DateTime
- [ ] Generate Alembic migration

#### 7.1.2 Seed Data
- [ ] Manually verify and seed top 25 defense contractors
  - LMT, RTX, BA, GD, NOC, LHX, HII, LDOS, SAIC, BAH
  - CACI, MRCY, KTOS, PLTR, NET...
- [ ] Extend to top 100 contractors by value
- [ ] Document DUNS numbers for each

#### 7.1.3 Fuzzy Matching Algorithm
- [ ] Implement `normalize_company_name()` function
  - Remove Inc, Corp, LLC, etc.
  - Standardize abbreviations
- [ ] Implement fuzzy name matching
  - Use fuzzywuzzy or rapidfuzz
  - Threshold tuning
- [ ] Implement subsidiary→parent lookup
  - Build parent company database

#### 7.1.4 Mapping Validation
- [ ] Create mapping coverage report
- [ ] Validate 95%+ of top 25 contractors mapped
- [ ] Review and correct low-confidence mappings

#### 7.1.5 Testing
- [ ] Write unit tests for mapping functions
- [ ] Test edge cases (name variations, subsidiaries)

---

### Task 7.2: Game→Publisher→Ticker Mapping

**Priority**: 2 | **Effort**: Medium | **Saturation**: N/A

#### 7.2.1 Mapping Table Design
- [ ] Create SQLAlchemy model `GamePublisherMapping`
  - `game_name`: String
  - `game_id`: String (Steam App ID, Twitch ID)
  - `publisher_name`: String
  - `ticker`: String, indexed
  - `confidence_score`: Float
- [ ] Generate Alembic migration

#### 7.2.2 Seed Data
- [ ] Map top 100 games on Twitch/Steam
- [ ] Map publishers to tickers:
  - EA → EA
  - Activision Blizzard → ATVI
  - Take-Two → TTWO
  - Ubisoft → UBSFY
  - Roblox → RBLX
  - Microsoft (Minecraft, etc.) → MSFT

#### 7.2.3 Testing & Validation
- [ ] Write unit tests
- [ ] Validate coverage of top games

---

### Task 7.3: Studio→Ticker Mapping

**Priority**: 2 | **Effort**: Small | **Saturation**: N/A

#### 7.3.1 Mapping Table Design
- [ ] Create SQLAlchemy model `MovieStudioMapping`
  - `distributor_name`: String (as appears in box office data)
  - `studio_name`: String
  - `ticker`: String, indexed
- [ ] Generate Alembic migration

#### 7.3.2 Seed Data
- [ ] Map all major studios:
  - Disney (Walt Disney Studios, Marvel, Pixar, Lucasfilm, 20th Century) → DIS
  - Warner Bros → WBD
  - Paramount → PARA
  - Universal → CMCSA
  - Sony Pictures → SONY
  - Lionsgate → LGF.A
  - A24 → Private
  - Focus Features → CMCSA

#### 7.3.3 Testing & Validation
- [ ] Write unit tests
- [ ] Validate distributor name variations

---

### Task 7.4: Phase 1 Factor Implementation Review

**Priority**: 1 | **Effort**: Medium | **Saturation**: N/A

#### 7.4.1 Factor Audit
- [ ] List all factors from Phase 1 tasks
- [ ] Verify each factor is implemented and registered
- [ ] Check factor computation logic

#### 7.4.2 Factor Quality Metrics
- [ ] Compute Information Coefficient (IC) for each factor
  - Target: IC > 0.02
- [ ] Compute Information Ratio (IR) for each factor
  - Target: IR > 0.5
- [ ] Generate factor correlation matrix
- [ ] Identify redundant factors

#### 7.4.3 Factor Decay Analysis
- [ ] Analyze IC at horizons: 1d, 5d, 10d, 21d, 63d
- [ ] Estimate half-life for each factor
- [ ] Document optimal holding periods

#### 7.4.4 Factor Documentation
- [ ] Document each factor's computation logic
- [ ] Document target entities
- [ ] Document expected signal interpretation

---

## Phase 8: Platform Integration

**Goal**: Build platform UI and user-facing features.
**Estimated Tasks**: 4 UI components
**Dependencies**: All prior phases
**Validation**: E2E user flow testing

---

### Task 8.1: Data Catalog UI

**Priority**: 1 | **Effort**: Medium | **Saturation**: N/A

#### 8.1.1 Design
- [ ] Define data catalog schema/metadata
  - Source name, description
  - Frequency, latency
  - Coverage, saturation level
  - Sample data preview
- [ ] Design UI wireframes

#### 8.1.2 Backend
- [ ] Create FastAPI endpoints for catalog
- [ ] Create Pydantic response models
- [ ] Implement catalog search/filter

#### 8.1.3 Frontend
- [ ] Build React components for catalog listing
- [ ] Build detail view for each data source
- [ ] Implement search and filter UI

#### 8.1.4 Testing
- [ ] Write API tests
- [ ] Write frontend component tests
- [ ] E2E testing for catalog flow

---

### Task 8.2: Visualization Components

**Priority**: 2 | **Effort**: Medium | **Saturation**: N/A

#### 8.2.1 Design
- [ ] Define chart types needed
  - Time-series line charts
  - Factor heatmaps
  - Correlation matrices
- [ ] Design visualization wireframes

#### 8.2.2 Implementation
- [ ] Select charting library (Recharts, D3, Plotly)
- [ ] Build time-series chart component
- [ ] Build heatmap component
- [ ] Build correlation matrix component

#### 8.2.3 Integration
- [ ] Connect charts to factor data endpoints
- [ ] Implement date range selection
- [ ] Implement entity selection

#### 8.2.4 Testing
- [ ] Test chart rendering
- [ ] Test data binding
- [ ] Performance testing

---

### Task 8.3: Factor Comparison Tools

**Priority**: 2 | **Effort**: Medium | **Saturation**: N/A

#### 8.3.1 Design
- [ ] Define factor comparison features
  - Multi-factor overlay
  - IC/IR display
  - Decay curves
- [ ] Design comparison UI

#### 8.3.2 Implementation
- [ ] Build factor selector component
- [ ] Build comparison chart component
- [ ] Build metrics display component

#### 8.3.3 Testing
- [ ] Test factor comparison logic
- [ ] Test UI interactions

---

### Task 8.4: Authentication & Access Control

**Priority**: 2 | **Effort**: Medium | **Saturation**: N/A

#### 8.4.1 Design
- [ ] Define user roles and permissions
- [ ] Define authentication flow (OAuth, JWT)
- [ ] Design tiered access model

#### 8.4.2 Implementation
- [ ] Implement user authentication
- [ ] Implement role-based access control
- [ ] Implement API key management

#### 8.4.3 Testing
- [ ] Test authentication flows
- [ ] Test authorization rules
- [ ] Security testing

---

## Phase 9: Commercial Data Expansion

**Goal**: Integrate commercial/paid data sources.
**Estimated Tasks**: 6+ data sources (as budget allows)
**Dependencies**: Platform complete
**Validation**: ROI analysis

---

### Task 9.1: Satellite Imagery (Orbital Insight)

**Priority**: 3 | **Effort**: High | **Saturation**: MEDIUM

- [ ] Evaluate Orbital Insight pricing and API
- [ ] Design integration architecture
- [ ] Implement if budget approved

---

### Task 9.2: Foot Traffic (Placer.ai)

**Priority**: 3 | **Effort**: High | **Saturation**: MEDIUM

- [ ] Evaluate Placer.ai pricing and API
- [ ] Design integration architecture
- [ ] Implement if budget approved

---

### Task 9.3: Credit Card Data

**Priority**: 4 | **Effort**: High | **Saturation**: HIGH

- [ ] Evaluate Bloomberg Second Measure, Earnest
- [ ] Design integration architecture
- [ ] Implement if budget approved

---

### Task 9.4: Job Posting Data (Revelio Labs)

**Priority**: 3 | **Effort**: Medium | **Saturation**: MEDIUM

- [ ] Evaluate Revelio Labs or LinkUp
- [ ] Design integration architecture
- [ ] Implement if budget approved

---

### Task 9.5: Maritime AIS (Kpler)

**Priority**: 3 | **Effort**: Medium | **Saturation**: MEDIUM

- [ ] Evaluate Kpler/MarineTraffic pricing
- [ ] Design integration architecture
- [ ] Implement if budget approved

---

### Task 9.6: Retail Scanner Data (NielsenIQ)

**Priority**: 4 | **Effort**: High | **Saturation**: HIGH

- [ ] Evaluate NielsenIQ/Circana pricing
- [ ] Design integration architecture
- [ ] Implement if budget approved

---

## Validation & Testing Framework

### Data Quality Framework

#### Freshness Validation
| Data Source | Expected Latency | Check Frequency |
|-------------|------------------|-----------------|
| TSA Checkpoint | 12 hours | Daily |
| OpenTable | 2 days | Weekly |
| Government Contracts | 48 hours | Daily |
| Twitch Metrics | 1 hour | Hourly |
| Steam Metrics | 24 hours | Daily |
| Earthquake Events | 15 minutes | Continuous |
| Power Grid Load | 5 minutes | Continuous |

#### Coverage Validation
| Data Source | Expected Coverage | Threshold |
|-------------|-------------------|-----------|
| Gov Contracts (Top 25) | 95% | 90% |
| Gaming (Top 100 Games) | 90% | 85% |
| Major Publishers | 10 | 8 |

#### Point-in-Time (PIT) Accuracy
- [ ] Implement PIT validator class
- [ ] Verify no look-ahead bias in factor computation
- [ ] Audit all factors for PIT compliance

### Factor Quality Metrics

| Metric | Target | Critical Threshold |
|--------|--------|-------------------|
| Mean IC | > 0.02 | > 0.01 |
| IR | > 0.5 | > 0.3 |
| T-stat | > 2.0 | > 1.5 |
| Hit Rate | > 52% | > 50% |

### Platform Performance Benchmarks

| Metric | Target | Critical |
|--------|--------|----------|
| API P50 Latency | < 100ms | < 500ms |
| API P99 Latency | < 500ms | < 2000ms |
| Factor Compute Batch | < 1 hour | < 4 hours |
| UI Time to Interactive | < 3 sec | < 10 sec |
| Concurrent Users | 100 | 50 |

### Automated Quality Monitoring
- [ ] Implement `DataFreshnessChecker` class
- [ ] Implement `CoverageValidator` class
- [ ] Implement `PITValidator` class
- [ ] Implement `QualityMonitor` daily checks
- [ ] Set up alerting for quality degradation

---

## Research Queue (Future Exploration)

### Tier A: High Novel Potential
- Tax Lien/Foreclosure Data
- Crowdfunding Campaigns (Kickstarter)
- Video Game Sales (Circana/NPD)
- 5G Cell Tower Permits
- EV Charging Utilization

### Tier B: Medium Novel Potential
- Domain Registrations
- Podcast Downloads
- Music Streaming Charts
- Sports Betting Lines
- Academic Citations
- Trade Show Attendance

### Tier C: Requires Commercial Access
- Supply Chain Visibility (FourKites)
- Earnings Call Transcripts NLP
- Influencer Marketing Data

---

## Quick Reference: File Paths

### Collectors
```
src/collectors/
├── tsa_checkpoint.py
├── opentable.py
├── usgs_earthquake.py
├── carbon_intensity.py
├── building_permits.py (extend fred_collector.py)
├── boxoffice.py
├── cloudflare_radar.py
├── zillow_rental.py
├── fpds.py
├── usaspending.py
├── congressional_trades.py
├── fcc_towers.py
├── twitch.py
├── steam.py
├── discord.py
├── kickstarter.py
├── lumber_futures.py
├── manheim.py
├── power_lmp.py
├── eia_natgas.py
├── container_ports.py
├── viirs_nightlights.py
├── tax_liens.py
├── opencellid.py
├── critical_minerals.py
├── datacenter.py
├── crunchbase.py
└── office_lease.py
```

### Entity Mappings
```
src/entity_mapping/
├── government_contractor_mapping.py
├── game_publisher_mapping.py
└── studio_ticker_mapping.py
```

### Factors
```
src/transformations/factors/
├── tsa_factors.py
├── restaurant_factors.py
├── earthquake_factors.py
├── carbon_factors.py
├── building_permit_factors.py
├── boxoffice_factors.py
├── internet_factors.py
├── rental_factors.py
├── government_contract_factors.py
├── gaming_factors.py
├── energy_factors.py
├── commodity_factors.py
└── infrastructure_factors.py
```

---

## Summary Statistics

| Category | Count |
|----------|-------|
| Total Data Sources | 49 |
| Phase 1 Sources | 8 |
| Phase 2 Sources | 4 |
| Phase 3 Sources | 4 |
| Phase 4 Sources | 5 |
| Phase 5 Sources | 4 |
| Phase 6 Sources | 3 |
| Entity Mapping Systems | 3 |
| Platform Components | 4 |
| Total Derived Factors | 150+ |

---

*Last Updated: Generated from steady-tickling-squid.md planning document*
