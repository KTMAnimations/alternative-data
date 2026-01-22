# Environmental Factors

Factors derived from air quality monitoring data.

## Overview

Environmental factors capture air quality conditions, which correlate with industrial activity, weather patterns, and can affect consumer behavior.

**Data Source**: OpenAQ
**Update Frequency**: Hourly
**Entity Type**: City/Region

---

## Factors

### air_quality_index

**Description**: Composite Air Quality Index (AQI)

**Signal Logic**:
- 0-50: Good
- 51-100: Moderate
- 101-150: Unhealthy for sensitive groups
- 151-200: Unhealthy
- \> 200: Very unhealthy

---

### pm25_concentration

**Description**: PM2.5 particulate matter concentration (μg/m³)

**Signal Logic**: Industrial activity often correlates with PM2.5

---

### pm25_anomaly

**Description**: PM2.5 vs. historical average for same period

---

### industrial_pollution_proxy

**Description**: Estimated industrial pollution contribution

---

### air_quality_trend

**Description**: 30-day trend in air quality

---

## Example Usage

```python
from altdata import AltDataClient
from datetime import date

client = AltDataClient(api_key="your-api-key")

# Get air quality data
data = client.get_factor(
    "air_quality_index",
    entity_id="Los Angeles",
    start_date="2024-01-01"
)

df = data.to_dataframe()
print(df.head())

# Get raw air quality readings
aq = client.get_air_quality(date(2024, 1, 15), city="Los Angeles")
aq_df = aq.to_dataframe()
print(aq_df.head())
```

---

## Data Quality Notes

- Sensor coverage varies by city
- Data may have gaps during sensor maintenance
- Weather affects readings significantly
- Seasonal patterns are strong
