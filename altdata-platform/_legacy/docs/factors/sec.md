# SEC Factors

Factors derived from SEC EDGAR filings, including insider transactions and institutional holdings.

## Overview

SEC factors capture trading activity by corporate insiders and institutional investors. These are classic alternative data signals used by quantitative investors.

**Data Source**: SEC EDGAR
**Update Frequency**: Real-time (as filings are published)
**Entity Type**: Company (ticker)

---

## Factors

### insider_transaction_momentum

**Description**: Net insider buying/selling from Form 4 filings over 30 days

**Signal Logic**:
- Positive values indicate net insider buying (bullish)
- Negative values indicate net insider selling (bearish)
- Insiders include executives, directors, and 10%+ shareholders

**Calculation**:
```
Net Value = Σ(Buy Value) - Σ(Sell Value)
Buy Value = Shares Purchased × Price
Sell Value = Shares Sold × Price
```

**Use Case**: Insider buying often precedes positive stock performance

```python
data = client.get_factor("insider_transaction_momentum", entity_id="AAPL")
```

---

### form4_net_shares

**Description**: Net shares acquired/disposed by insiders over 30 days

**Signal Logic**:
- Positive = Net accumulation
- Negative = Net distribution

**Calculation**:
```
Net Shares = Σ(Shares Acquired) - Σ(Shares Disposed)
```

---

### insider_buy_ratio

**Description**: Ratio of buy to sell transactions by insiders

**Signal Logic**:
- \> 1.0 = More buys than sells (bullish)
- < 1.0 = More sells than buys (bearish)

**Calculation**:
```
Ratio = Number of Buy Transactions / Number of Sell Transactions
```

---

### insider_transaction_count

**Description**: Total number of insider transactions in period

**Signal Logic**: High activity may signal important corporate events

---

### form4_dollar_volume

**Description**: Total dollar volume of insider transactions

**Calculation**:
```
Dollar Volume = Σ(|Transaction Value|)
```

---

### unique_insider_count

**Description**: Number of unique insiders transacting

**Signal Logic**: Multiple insiders buying is stronger signal than one

---

### ceo_transaction_signal

**Description**: CEO-specific buying/selling activity

**Signal Logic**: CEO transactions carry more weight due to information asymmetry

---

### director_transaction_signal

**Description**: Board director transaction activity

---

### form4_filing_delay

**Description**: Average delay between transaction and Form 4 filing

**Signal Logic**: Longer delays may indicate less urgency/importance

---

### institutional_holdings_change

**Description**: Change in 13F institutional holdings

**Data Source**: 13F filings (quarterly)

**Signal Logic**:
- Increase = Institutional accumulation
- Decrease = Institutional distribution

---

### top10_institutional_concentration

**Description**: Concentration of shares among top 10 institutional holders

**Signal Logic**: High concentration may indicate conviction or liquidity risk

---

### hedge_fund_ownership_change

**Description**: Change in hedge fund ownership

---

### mutual_fund_ownership_change

**Description**: Change in mutual fund ownership

---

### new_institutional_positions

**Description**: Number of new institutional positions initiated

**Signal Logic**: New positions indicate fresh interest from sophisticated investors

---

### closed_institutional_positions

**Description**: Number of institutional positions fully closed

**Signal Logic**: Full exits may indicate loss of confidence

---

## Example Usage

### Get Insider Activity for AAPL

```python
from altdata import AltDataClient

client = AltDataClient(api_key="your-api-key")

# Get insider momentum
data = client.get_factor(
    "insider_transaction_momentum",
    entity_id="AAPL",
    start_date="2024-01-01"
)

df = data.to_dataframe()
print(df.head())
```

### Screen for Insider Buying

```python
tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "META"]

insider_signals = {}
for ticker in tickers:
    data = client.get_factor(
        "insider_transaction_momentum",
        entity_id=ticker
    )
    if data.values:
        latest = data.values[0]
        insider_signals[ticker] = latest.value

# Find tickers with positive insider buying
buyers = {t: v for t, v in insider_signals.items() if v > 0}
print("Insider Buying:", buyers)
```

### Combine with Price Data

```python
import yfinance as yf

# Get insider factor
insider_data = client.get_factor(
    "insider_transaction_momentum",
    entity_id="AAPL",
    start_date="2023-01-01"
)
insider_df = insider_data.to_dataframe()

# Get price data
prices = yf.download("AAPL", start="2023-01-01")["Adj Close"]

# Merge and analyze
combined = insider_df.join(prices.rename("price"), how="inner")
combined["forward_return"] = combined["price"].pct_change(20).shift(-20)

# Correlation between insider activity and forward returns
correlation = combined["value"].corr(combined["forward_return"])
print(f"Insider → 20-day Forward Return Correlation: {correlation:.3f}")
```

---

## Data Quality Notes

- Form 4 filings must be filed within 2 business days of transaction
- Some transactions are reported late (captured in `form4_filing_delay`)
- Stock option exercises are excluded from momentum calculations
- Gift transactions are excluded
