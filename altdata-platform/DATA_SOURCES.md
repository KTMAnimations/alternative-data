# Data Sources Reference

Quick reference for all data sources integrated into the platform.

## Tier 1: Highest Priority

### ADS-B Exchange - Aviation Tracking
| Property | Value |
|----------|-------|
| **Category** | Aviation / M&A Signals |
| **API URL** | https://www.adsbexchange.com/data/ |
| **Authentication** | API key (free tier available) |
| **Rate Limit** | 1000 requests/day free, unlimited paid |
| **Update Frequency** | Real-time (1-5 second updates) |
| **Historical Data** | Full history via paid plans |
| **Priority Score** | 8.7/10 |

**Derived Factors:**
| Factor | Description |
|--------|-------------|
| `executive_flight_frequency` | Flights/week for company jets |
| `hq_visit_score` | Jets landing near other company HQs |
| `pe_vc_destination_index` | Flights to PE/VC offices weighted by AUM |
| `unusual_destination_alert` | Binary flag for new destinations |
| `multi_company_colocation` | Multiple company jets at same airport |
| `flight_pattern_change_score` | KL divergence from historical patterns |

**Dependencies:**
- FAA N-Number Registry
- Corporate jet ownership database
- Company HQ geocoding

---

### SEC EDGAR - Regulatory Filings
| Property | Value |
|----------|-------|
| **Category** | Regulatory / Fundamentals |
| **API URL** | https://www.sec.gov/cgi-bin/browse-edgar |
| **Authentication** | None (rate limit by User-Agent) |
| **Rate Limit** | 10 requests/second |
| **Update Frequency** | Real-time (filings available within minutes) |
| **Historical Data** | 1996-present |
| **Priority Score** | 7.3/10 |

**Derived Factors:**
| Factor | Description |
|--------|-------------|
| `risk_factor_sentiment_delta` | Sentiment change in Item 1A vs prior |
| `mda_tone_score` | MD&A section sentiment (Loughran-McDonald) |
| `insider_transaction_momentum` | Net insider buying/selling (30-day) |
| `insider_clustering_score` | Unique insiders trading same direction |
| `8k_event_velocity` | Number of 8-K filings in 30 days |
| `guidance_language_score` | Confident vs hedging language ratio |
| `filing_delay_score` | Days between period end and filing |
| `exhibit_anomaly_flag` | Unusual exhibits (EX-10, EX-99) |

**Dependencies:**
- NLP/LLM for text analysis
- Financial statement parser
- Entity resolution (CIK → ticker)

---

### FRED - Federal Reserve Economic Data
| Property | Value |
|----------|-------|
| **Category** | Macroeconomic |
| **API URL** | https://fred.stlouisfed.org/docs/api/fred/ |
| **Authentication** | Free API key required |
| **Rate Limit** | 120 requests/minute |
| **Update Frequency** | Varies (daily to quarterly) |
| **Historical Data** | Decades for most series |
| **Priority Score** | 5.7/10 |

**Derived Factors:**
| Factor | Description |
|--------|-------------|
| `yield_curve_slope` | 10Y - 2Y Treasury spread |
| `recession_probability` | Smoothed recession probability |
| `credit_spread_index` | BAA corporate spread over 10Y |
| `money_supply_growth` | M2 year-over-year change |
| `initial_claims_momentum` | 4-week MA vs 52-week average |
| `financial_conditions_index` | Chicago Fed NFCI |
| `real_rates` | 10Y nominal - TIPS breakeven |

**Key Series:**
- `GS10`, `GS2` - Treasury yields
- `BAA10Y` - Corporate spread
- `M2SL` - Money supply
- `ICSA`, `IC4WSA` - Jobless claims
- `NFCI` - Financial conditions
- `T10YIE` - Breakeven inflation

---

### US Power Grid ISOs
| Property | Value |
|----------|-------|
| **Category** | Energy / Industrial Activity |
| **APIs** | CAISO, ERCOT, PJM, MISO |
| **Authentication** | Free registration (some ISOs) |
| **Update Frequency** | Real-time (5-minute intervals) |
| **Historical Data** | 5-10+ years |
| **Priority Score** | 7.7/10 |

**Derived Factors:**
| Factor | Description |
|--------|-------------|
| `industrial_load_index` | Base load (2-5 AM) as production proxy |
| `weather_adjusted_demand` | Actual minus weather-predicted load |
| `peak_demand_ratio` | Daily peak / average load |
| `renewable_generation_share` | Solar + wind / total generation |
| `lmp_volatility` | Price standard deviation (24h) |
| `congestion_stress_index` | 7-day average congestion component |
| `reserve_margin` | Available capacity minus load |
| `yoy_load_growth` | Year-over-year demand change |

**ISO URLs:**
- CAISO: https://oasis.caiso.com
- ERCOT: https://ercot.com/gridmktinfo
- PJM: https://pjm.com/markets-and-operations
- MISO: https://misoenergy.org

---

### USPTO & EPO - Patent Data
| Property | Value |
|----------|-------|
| **Category** | Innovation / R&D |
| **APIs** | USPTO, EPO Open Patent Services |
| **Authentication** | Free registration |
| **Rate Limit** | USPTO: 100/min, EPO: varies |
| **Update Frequency** | Weekly (Thursday for USPTO) |
| **Historical Data** | USPTO: 1790+, EPO: 1978+ |
| **Priority Score** | 7.7/10 |

**Derived Factors:**
| Factor | Description |
|--------|-------------|
| `patent_filing_velocity` | Applications per quarter |
| `patent_grant_rate` | Grants / applications (3-year) |
| `citation_impact_score` | Average forward citations |
| `technology_diversity_index` | CPC code Herfindahl (inverted) |
| `ai_ml_patent_share` | AI/ML patents / total patents |
| `patent_pending_pipeline` | Applications not yet granted |
| `inventor_concentration` | Top 10 inventors share |
| `competitive_overlap_score` | CPC Jaccard with competitors |

**API URLs:**
- USPTO: https://developer.uspto.gov/api-catalog
- EPO: https://ops.epo.org/

---

### OpenAQ - Air Quality
| Property | Value |
|----------|-------|
| **Category** | Environmental / Industrial Proxy |
| **API URL** | https://openaq.org/developers/platform-overview/ |
| **Authentication** | Free API key |
| **Rate Limit** | 100 requests/minute |
| **Update Frequency** | Hourly |
| **Historical Data** | 2015-present |
| **Priority Score** | 8.3/10 |

**Derived Factors:**
| Factor | Description |
|--------|-------------|
| `industrial_activity_index` | PM2.5 + NO2 near industrial zones |
| `china_manufacturing_proxy` | AQI in manufacturing cities |
| `weather_normalized_pollution` | Raw / dispersion factor |
| `week_over_week_change` | WoW pollution change |
| `cross_border_flow_indicator` | Border region differentials |
| `lockdown_detection_score` | Z-score vs 30-day rolling |

**Key Parameters:**
- `pm25` - Fine particulate matter
- `pm10` - Coarse particulate matter
- `no2` - Nitrogen dioxide
- `o3` - Ozone
- `co` - Carbon monoxide

---

### BTS Freight Transportation Services Index
| Property | Value |
|----------|-------|
| **Category** | Transportation / Economic Leading |
| **API URL** | https://www.bts.gov/ |
| **Authentication** | None |
| **Update Frequency** | Monthly (6-week lag) |
| **Historical Data** | 1990-present |
| **Priority Score** | 7.3/10 |

**Derived Factors:**
| Factor | Description |
|--------|-------------|
| `freight_momentum` | 3-month rate of change |
| `trucking_rail_ratio` | Mode shift indicator |
| `intermodal_share` | Rail intermodal / total rail |
| `air_freight_premium` | Air vs surface transport |
| `gdp_lead_indicator` | Weighted TSI components |
| `seasonally_adjusted_trend` | STL decomposition trend |

**Index Components:**
- `tsi_freight` - Total freight index
- `trucking_index` - For-hire trucking
- `rail_carloads_index` - Rail carloads
- `rail_intermodal_index` - Rail containers
- `waterborne_index` - Inland waterways
- `air_freight_index` - Air cargo
- `pipeline_index` - Oil/gas pipelines

---

## Tier 2: High Priority

### NOAA/NWS Weather Data
| Property | Value |
|----------|-------|
| **Category** | Weather / Agriculture / Energy |
| **API URL** | https://www.weather.gov/documentation/services-web-api |
| **Rate Limit** | Reasonable use |
| **Update Frequency** | Hourly forecasts |

**Key Factors:** HDD, CDD, GDD, precipitation anomaly, drought index, frost days, temperature volatility

---

### Sentinel-2 Satellite Imagery
| Property | Value |
|----------|-------|
| **Category** | Satellite / Agriculture / Real Estate |
| **API URL** | https://scihub.copernicus.eu/dhus/ |
| **Rate Limit** | 2 concurrent, 2TB/month |
| **Revisit Time** | 5 days |

**Key Factors:** NDVI, crop yield estimate, parking lot occupancy, construction progress, water body area

---

### Google Trends
| Property | Value |
|----------|-------|
| **Category** | Search Interest |
| **Access** | pytrends (unofficial) |
| **Rate Limit** | ~10-20/minute |

**Key Factors:** Brand momentum, product launch interest, recession fear index, category demand

---

### Reddit API
| Property | Value |
|----------|-------|
| **Category** | Social Sentiment |
| **API URL** | https://www.reddit.com/dev/api/ |
| **Rate Limit** | 60/minute (OAuth) |

**Key Factors:** WSB mention velocity, sentiment score, engagement ratio, YOLO index, bull/bear ratio

---

### MarineTraffic / AIS Data
| Property | Value |
|----------|-------|
| **Category** | Shipping / Trade |
| **Rate Limit** | 500/day free tier |

**Key Factors:** Port congestion, container traffic, tanker volume, route activity, dark shipping

---

### GitHub API
| Property | Value |
|----------|-------|
| **Category** | Technology / Developer Activity |
| **API URL** | https://docs.github.com/en/rest |
| **Rate Limit** | 5000/hour authenticated |

**Key Factors:** Repo activity, developer growth, OSS investment, dependency adoption, resolution speed

---

## API Key Requirements Summary

| Source | Key Required | Free Tier |
|--------|-------------|-----------|
| ADS-B Exchange | Yes | 1000 req/day |
| SEC EDGAR | No (User-Agent) | Unlimited |
| FRED | Yes | Unlimited |
| Power Grid ISOs | Varies | Yes |
| USPTO | Yes | Yes |
| EPO | Yes | Yes |
| OpenAQ | Yes | Yes |
| BTS | No | Yes |
| NOAA | No | Yes |
| Sentinel-2 | Yes | 2TB/month |
| Google Trends | No | Rate limited |
| Reddit | Yes (OAuth) | 60 req/min |
| MarineTraffic | Yes | 500 req/day |
| GitHub | Yes | 5000 req/hr |

---

## Data Quality Notes

### Known Limitations
- **ADS-B**: FAA LADD blocking can hide aircraft identity
- **SEC EDGAR**: NLP accuracy ~85% for complex filings
- **Power Grid**: Holiday schedules affect patterns
- **OpenAQ**: Sensor quality varies by region
- **Google Trends**: Normalized scores, not absolute volumes
- **Reddit**: Historical data limited via official API

### Entity Resolution Challenges
- Ticker changes and M&A require monthly mapping updates
- Multi-class shares complicate company identification
- International companies may have multiple identifiers
- Private companies have no ticker mapping
