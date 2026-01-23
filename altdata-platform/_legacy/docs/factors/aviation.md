# Aviation Factors

Factors derived from corporate jet tracking data via ADS-B Exchange.

## Overview

Aviation factors track corporate jet movements, which can signal M&A activity, executive travel patterns, and business development activity.

**Data Source**: ADS-B Exchange
**Update Frequency**: Hourly
**Entity Type**: Company

---

## Factors

### corporate_jet_activity

**Description**: Number of corporate jet flights in past 30 days

**Signal Logic**: Increased executive travel may signal deal activity

---

### hq_destination_flights

**Description**: Flights landing near other company headquarters

**Signal Logic**: Visits to other companies' HQs may signal M&A discussions

---

### unusual_destination_score

**Description**: Flights to unusual destinations (relative to history)

**Signal Logic**: New destinations may indicate business expansion or deals

---

### flight_frequency_change

**Description**: Change in flight frequency vs. historical average

---

### multi_company_meeting_indicator

**Description**: Flights that land near multiple company HQs on same trip

**Signal Logic**: Multi-stop trips may indicate complex deal negotiations

---

## Example Usage

```python
from altdata import AltDataClient

client = AltDataClient(api_key="your-api-key")

# Get corporate jet activity
data = client.get_factor(
    "corporate_jet_activity",
    entity_id="AAPL",
    start_date="2024-01-01"
)

df = data.to_dataframe()
print(df.head())

# Get flight records directly
flights = client.get_flights(
    company_id="AAPL",
    start_date="2024-01-01"
)

flight_df = flights.to_dataframe()
print(f"Total flights: {flights.total}")
```

---

## Data Quality Notes

- ADS-B coverage varies by region
- Not all corporate jets are tracked
- Aircraft ownership changes may affect data
- Some executives use commercial flights
