# Trends Factors

Factors derived from Google Trends search interest data.

## Overview

Trends factors capture consumer and investor interest through search behavior, providing early signals of demand shifts and sentiment changes.

**Data Source**: Google Trends
**Update Frequency**: Daily
**Entity Type**: Keyword/Topic

---

## Factors

### search_interest_momentum

**Description**: Change in search interest over past 7 days

**Signal Logic**: Rising interest may precede price movements

---

### search_interest_zscore

**Description**: Current interest vs. historical standard deviations

**Signal Logic**: Extreme z-scores indicate unusual attention

---

### relative_search_interest

**Description**: Interest relative to category benchmark

---

### breakout_indicator

**Description**: Indicator for sudden interest spikes

**Signal Logic**: Breakouts often precede news/price moves

---

### interest_volatility

**Description**: Variability in search interest

---

## Example Usage

```python
from altdata import AltDataClient

client = AltDataClient(api_key="your-api-key")

# Get search interest for a keyword
data = client.get_factor(
    "search_interest_momentum",
    entity_id="bitcoin",
    start_date="2024-01-01"
)

df = data.to_dataframe()
print(df.head())

# Get raw trends data
trends = client.get_trends(
    keyword="bitcoin",
    geo="US",
    start_date="2024-01-01"
)
trends_df = trends.to_dataframe()
print(trends_df.head())
```

---

## Popular Keywords

### Crypto
- bitcoin, ethereum, crypto

### Tech
- ChatGPT, AI, iPhone

### Finance
- stock market, recession, inflation

### Consumer
- Black Friday, Prime Day, back to school

---

## Data Quality Notes

- Interest values are relative (0-100 scale)
- Daily data may differ from weekly/monthly
- Geographic filtering affects results
- Some keywords may be censored
