# Macro Factors

Macroeconomic factors derived from Federal Reserve Economic Data (FRED) and other sources.

## Overview

Macro factors capture broad economic conditions that affect all securities. These are market-wide factors rather than company-specific.

**Data Source**: FRED (Federal Reserve Economic Data)
**Update Frequency**: Daily
**Entity Type**: Market (applies to all securities)

---

## Factors

### yield_curve_slope

**Description**: 10Y Treasury minus 2Y Treasury yield

**Signal Logic**:
- Positive = Normal yield curve (economic expansion)
- Negative = Inverted yield curve (recession warning)
- Historically, inversions precede recessions by 6-18 months

**Calculation**:
```
Slope = GS10 - GS2
```

**Use Case**: Classic recession indicator

```python
data = client.get_factor("yield_curve_slope", entity_id="MARKET")
```

---

### credit_spread

**Description**: BAA corporate bond spread over 10Y Treasury

**Signal Logic**:
- Higher spreads = Increased credit risk/stress
- Lower spreads = Risk-on environment

**Calculation**:
```
Spread = BAA Yield - 10Y Treasury Yield
```

---

### ted_spread

**Description**: 3-Month LIBOR minus 3-Month T-Bill rate

**Signal Logic**: Measures banking sector stress

---

### unemployment_change

**Description**: Month-over-month change in unemployment rate

**Signal Logic**:
- Rising unemployment = Economic weakness
- Falling unemployment = Economic strength

---

### initial_claims_momentum

**Description**: 4-week moving average change in initial jobless claims

**Signal Logic**: Leading indicator of labor market conditions

---

### consumer_confidence_change

**Description**: Change in University of Michigan Consumer Sentiment

**Signal Logic**: Consumer spending drives ~70% of GDP

---

### pce_inflation_rate

**Description**: PCE price index year-over-year change

**Signal Logic**: Fed's preferred inflation measure

---

### real_gdp_growth

**Description**: Real GDP growth rate (quarterly, annualized)

---

### ism_manufacturing_pmi

**Description**: ISM Manufacturing PMI

**Signal Logic**:
- \> 50 = Expansion
- < 50 = Contraction

---

### housing_starts_momentum

**Description**: Month-over-month change in housing starts

**Signal Logic**: Leading indicator of construction and economic activity

---

## Example Usage

### Get Yield Curve Data

```python
from altdata import AltDataClient

client = AltDataClient(api_key="your-api-key")

# Get yield curve slope
data = client.get_factor(
    "yield_curve_slope",
    entity_id="MARKET",
    start_date="2020-01-01"
)

df = data.to_dataframe()
print(df.tail())

# Check for inversion
is_inverted = df["value"].iloc[-1] < 0
print(f"Yield Curve Inverted: {is_inverted}")
```

### Monitor Multiple Macro Factors

```python
macro_factors = [
    "yield_curve_slope",
    "credit_spread",
    "unemployment_change",
    "ism_manufacturing_pmi"
]

macro_snapshot = {}
for factor in macro_factors:
    data = client.get_factor(factor, entity_id="MARKET")
    if data.values:
        macro_snapshot[factor] = data.values[0].value

print("Macro Snapshot:")
for factor, value in macro_snapshot.items():
    print(f"  {factor}: {value:.2f}")
```

### Create Macro Risk Index

```python
import pandas as pd

# Get multiple macro factors
factors_data = {}
for factor in ["yield_curve_slope", "credit_spread", "unemployment_change"]:
    data = client.get_factor(factor, entity_id="MARKET", start_date="2020-01-01")
    factors_data[factor] = data.to_dataframe()["value"]

# Combine into DataFrame
macro_df = pd.DataFrame(factors_data)

# Normalize each factor
normalized = (macro_df - macro_df.mean()) / macro_df.std()

# Create composite risk index
# Invert yield curve (negative = bad), keep credit spread (high = bad)
normalized["yield_curve_slope"] = -normalized["yield_curve_slope"]
macro_df["risk_index"] = normalized.mean(axis=1)

print(macro_df.tail())
```

---

## Historical Context

### Yield Curve Inversions

Historical inversions and subsequent recessions:

| Inversion Start | Recession Start | Lead Time |
|-----------------|-----------------|-----------|
| Dec 1988 | Jul 1990 | 19 months |
| Feb 2000 | Mar 2001 | 13 months |
| Feb 2006 | Dec 2007 | 22 months |
| Aug 2019 | Feb 2020 | 6 months |

### Credit Spread Thresholds

Historical context for credit spreads:

| Level | Interpretation |
|-------|----------------|
| < 2% | Very tight (risk-on) |
| 2-3% | Normal |
| 3-5% | Elevated stress |
| \> 5% | Crisis conditions |

---

## Data Quality Notes

- FRED data is typically available by 8:30 AM ET
- Some series have revisions (GDP, employment)
- Treasury yields are daily averages, not real-time
- Holiday schedules affect data availability
