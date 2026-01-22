# Weather Factors

Factors derived from weather observations and forecasts.

## Overview

Weather factors capture conditions that affect various sectors including retail, agriculture, energy, and transportation.

**Data Source**: Open-Meteo
**Update Frequency**: Hourly
**Entity Type**: City/Region

---

## Factors

### temperature_anomaly

**Description**: Temperature deviation from historical average

**Signal Logic**: Extreme temperatures affect consumer behavior and energy demand

---

### heating_degree_days

**Description**: Heating Degree Days (HDD) - below 65°F

**Signal Logic**: Higher HDD indicates more heating demand

---

### cooling_degree_days

**Description**: Cooling Degree Days (CDD) - above 65°F

**Signal Logic**: Higher CDD indicates more cooling demand

---

### precipitation_anomaly

**Description**: Precipitation vs. historical average

---

### severe_weather_indicator

**Description**: Indicator for severe weather events

**Signal Logic**: Affects retail foot traffic, logistics, and insurance

---

### weather_volatility

**Description**: Variability in weather conditions over period

---

### growing_degree_days

**Description**: Growing Degree Days for agricultural analysis

---

### frost_days_count

**Description**: Number of days with frost conditions

---

## Example Usage

```python
from altdata import AltDataClient
from datetime import date

client = AltDataClient(api_key="your-api-key")

# Get temperature anomaly
data = client.get_factor(
    "temperature_anomaly",
    entity_id="Chicago",
    start_date="2024-01-01"
)

df = data.to_dataframe()
print(df.head())

# Get weather observations
weather = client.get_weather("New York", date(2024, 1, 15))
weather_df = weather.to_dataframe()
print(weather_df.head())

# Get forecast
forecast = client.get_weather_forecast("New York", days=7)
forecast_df = forecast.to_dataframe()
print(forecast_df.head())
```

---

## Sector Applications

| Sector | Weather Impact |
|--------|----------------|
| Retail | Foot traffic, seasonal sales |
| Energy | Heating/cooling demand |
| Agriculture | Crop yields, planting timing |
| Insurance | Storm damage claims |
| Transportation | Flight delays, shipping |

---

## Data Quality Notes

- Historical data may be revised
- Forecasts have decreasing accuracy beyond 3 days
- Urban heat island effects vary by city
- Station coverage varies by region
