# Satellite Factors

Factors derived from satellite imagery analysis.

## Overview

Satellite factors capture physical activity patterns through parking lot occupancy (retail foot traffic proxy) and agricultural conditions (NDVI for crop health).

**Data Source**: Sentinel Hub, Planet Labs
**Update Frequency**: Weekly
**Entity Type**: Company (parking), Region (agriculture)

---

## Parking Lot Factors

### parking_lot_occupancy

**Description**: Average occupancy rate (0-1) across tracked locations

**Signal Logic**: Proxy for retail foot traffic and sales

---

### occupancy_vs_historical

**Description**: Current occupancy vs. same period last year

**Signal Logic**: YoY comparison normalizes for seasonality

---

### occupancy_trend

**Description**: 4-week trend in parking lot occupancy

---

### weekend_vs_weekday_ratio

**Description**: Weekend to weekday occupancy ratio

**Signal Logic**: Higher weekend ratio may indicate consumer discretionary strength

---

## Agricultural Factors

### ndvi_score

**Description**: Normalized Difference Vegetation Index

**Signal Logic**:
- 0.6-1.0: Dense vegetation (healthy crops)
- 0.2-0.6: Moderate vegetation
- 0.0-0.2: Sparse/no vegetation

---

### ndvi_vs_historical

**Description**: NDVI compared to historical average for region

**Signal Logic**: Below-average NDVI may signal crop stress

---

### crop_health_score

**Description**: Composite crop health metric

---

### growing_season_progress

**Description**: Progress through typical growing season

---

## Example Usage

### Parking Lot Data

```python
from altdata import AltDataClient

client = AltDataClient(api_key="your-api-key")

# Get parking occupancy
data = client.get_factor(
    "parking_lot_occupancy",
    entity_id="WMT",
    start_date="2024-01-01"
)

df = data.to_dataframe()
print(df.head())

# Get raw parking data
parking = client.get_parking_data(ticker="WMT", start_date="2024-01-01")
park_df = parking.to_dataframe()
print(park_df.head())
```

### Agricultural Data

```python
# Get NDVI data
data = client.get_factor(
    "ndvi_score",
    entity_id="Iowa",
    start_date="2024-01-01"
)

df = data.to_dataframe()
print(df.head())

# Get raw agricultural data
ag = client.get_agricultural_data("Iowa", crop_type="corn")
ag_df = ag.to_dataframe()
print(ag_df.head())
```

---

## Retail Tickers Tracked

| Ticker | Company | Locations |
|--------|---------|-----------|
| WMT | Walmart | 4,700+ |
| TGT | Target | 1,900+ |
| COST | Costco | 590+ |
| HD | Home Depot | 2,300+ |
| LOW | Lowe's | 1,700+ |

---

## Agricultural Regions

| Region | Crops |
|--------|-------|
| Iowa | Corn, Soybeans |
| Illinois | Corn, Soybeans |
| Kansas | Wheat |
| California | Fruits, Vegetables |
| Texas | Cotton, Wheat |

---

## Data Quality Notes

- Cloud cover affects image quality
- Weekly updates may miss daily variations
- Parking detection accuracy ~90%
- Agricultural analysis requires clear imagery
