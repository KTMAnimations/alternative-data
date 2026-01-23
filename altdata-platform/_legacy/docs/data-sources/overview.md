# Data Sources Overview

The Alternative Data Platform aggregates data from 12+ free and public alternative data sources.

## Source Summary

| Source | Category | Update Freq | Factors | Status |
|--------|----------|-------------|---------|--------|
| SEC EDGAR | Regulatory | Real-time | 15+ | Active |
| FRED | Macro | Daily | 10+ | Active |
| ADS-B Exchange | Aviation | Hourly | 5+ | Active |
| EIA/ISO | Energy | Hourly | 8+ | Active |
| USPTO | Patents | Weekly | 6+ | Active |
| OpenAQ | Environment | Hourly | 5+ | Active |
| Open-Meteo | Weather | Hourly | 8+ | Active |
| Google Trends | Trends | Daily | 5+ | Active |
| Reddit | Sentiment | Hourly | 8+ | Active |
| MarineTraffic | Shipping | Daily | 6+ | Active |
| GitHub | Development | Daily | 7+ | Active |
| Sentinel Hub | Satellite | Weekly | 5+ | Active |

---

## Regulatory Data

### SEC EDGAR

**Description**: SEC filings including Form 4 (insider transactions), 13F (institutional holdings), and other regulatory filings.

**Data Points**:
- Insider buy/sell transactions
- Transaction prices and shares
- Filing dates
- Institutional holdings

**Coverage**: All US public companies

**Lag**: Real-time (filings available within minutes)

---

## Economic Data

### FRED (Federal Reserve Economic Data)

**Description**: Comprehensive database of US economic data maintained by the Federal Reserve Bank of St. Louis.

**Data Points**:
- Treasury yields (2Y, 10Y, 30Y)
- Credit spreads
- Unemployment data
- GDP estimates
- Inflation metrics

**Coverage**: National/regional US data

**Lag**: Varies by series (daily to quarterly)

---

## Transportation Data

### ADS-B Exchange

**Description**: Aircraft tracking data from ADS-B (Automatic Dependent Surveillance-Broadcast) receivers.

**Data Points**:
- Flight paths
- Landing locations
- Aircraft registration
- Timestamp data

**Coverage**: Global (receiver-dependent)

**Lag**: Near real-time (~1 hour)

---

## Energy Data

### EIA / ISO Operators

**Description**: Electricity grid data from Independent System Operators (ISOs).

**Data Points**:
- Grid load (MW)
- Forecasted demand
- Generation by source
- Prices

**Coverage**: US regional grids (CAISO, ERCOT, PJM, MISO)

**Lag**: Hourly

---

## Innovation Data

### USPTO

**Description**: US Patent and Trademark Office patent filing and grant data.

**Data Points**:
- Patent filings
- Grant dates
- Classifications
- Citations

**Coverage**: US patents

**Lag**: Weekly

---

## Environmental Data

### OpenAQ

**Description**: Open air quality data from monitoring stations worldwide.

**Data Points**:
- PM2.5, PM10
- Ozone, NO2, SO2, CO
- AQI calculations

**Coverage**: Global (station-dependent)

**Lag**: Hourly

---

## Weather Data

### Open-Meteo

**Description**: Free weather API providing observations and forecasts.

**Data Points**:
- Temperature
- Precipitation
- Wind
- Humidity
- Forecasts (14-day)

**Coverage**: Global

**Lag**: Hourly

---

## Consumer Behavior Data

### Google Trends

**Description**: Search interest data from Google.

**Data Points**:
- Search interest (0-100 scale)
- Geographic breakdown
- Related queries

**Coverage**: Global

**Lag**: Daily

### Reddit

**Description**: Social media sentiment from investment-related subreddits.

**Data Points**:
- Mention counts
- Sentiment scores
- Post volumes

**Coverage**: US retail investor sentiment

**Lag**: Hourly

---

## Trade & Logistics Data

### MarineTraffic / AIS

**Description**: Vessel tracking and port activity data.

**Data Points**:
- Vessel positions
- Port arrivals/departures
- Waiting times
- Congestion indices

**Coverage**: Major global ports

**Lag**: Daily

---

## Technology Data

### GitHub

**Description**: Open source repository activity metrics.

**Data Points**:
- Commit counts
- Pull requests
- Issues
- Contributors
- Stars/forks

**Coverage**: Public repositories

**Lag**: Daily

---

## Satellite Data

### Sentinel Hub

**Description**: Satellite imagery analysis for parking lots and agriculture.

**Data Points**:
- Parking lot occupancy
- NDVI (vegetation index)
- Land use changes

**Coverage**: US (retail locations, agricultural regions)

**Lag**: Weekly

---

## Data Quality

### Point-in-Time Accuracy

All data is stored with timestamps to ensure point-in-time accuracy:

- `observed_at`: When the data was observed
- `collected_at`: When we collected it
- `effective_date`: The date the data applies to

This prevents look-ahead bias in backtesting.

### Data Validation

Each data source has validation rules:

- Range checks (e.g., temperatures within realistic bounds)
- Completeness checks (missing data flagged)
- Anomaly detection (outliers flagged for review)

### Update Schedule

| Source | Schedule | Time (ET) |
|--------|----------|-----------|
| SEC EDGAR | Continuous | All day |
| FRED | Daily | 8:30 AM |
| Weather | Hourly | :00 |
| Trends | Daily | 2:00 AM |
| Sentiment | Hourly | :15 |
| GitHub | Daily | 3:00 AM |
| Satellite | Weekly | Sunday |

---

## API Access

All sources are accessible through unified API:

```python
from altdata import AltDataClient

client = AltDataClient(api_key="your-api-key")

# Check source status
sources = client.list_sources()
for s in sources.sources:
    print(f"{s.name}: {s.status}")
```
