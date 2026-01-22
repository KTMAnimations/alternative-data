# Sentiment Factors

Factors derived from social media sentiment analysis.

## Overview

Sentiment factors capture retail investor and consumer sentiment from Reddit and other social platforms, providing early signals of crowd psychology.

**Data Source**: Reddit (WallStreetBets, investing, stocks)
**Update Frequency**: Hourly
**Entity Type**: Company (ticker)

---

## Factors

### sentiment_score

**Description**: Average sentiment score (-1 to +1) from social mentions

**Signal Logic**:
- \> 0: Positive sentiment (bullish)
- < 0: Negative sentiment (bearish)

---

### mention_count

**Description**: Number of times ticker mentioned in period

**Signal Logic**: High mentions indicate attention, may precede volatility

---

### sentiment_momentum

**Description**: Change in sentiment vs. previous period

---

### mention_momentum

**Description**: Change in mention count vs. previous period

---

### sentiment_dispersion

**Description**: Disagreement in sentiment (variance)

**Signal Logic**: High dispersion indicates controversy/uncertainty

---

### positive_ratio

**Description**: Ratio of positive to total mentions

---

### wallstreetbets_attention

**Description**: WSB-specific attention score

**Signal Logic**: WSB attention can precede retail-driven moves

---

### sentiment_vs_price

**Description**: Divergence between sentiment and recent price action

**Signal Logic**: Divergences may indicate potential reversals

---

## Example Usage

```python
from altdata import AltDataClient

client = AltDataClient(api_key="your-api-key")

# Get sentiment score
data = client.get_factor(
    "sentiment_score",
    entity_id="AAPL",
    start_date="2024-01-01"
)

df = data.to_dataframe()
print(df.head())

# Get raw sentiment data
sentiment = client.get_sentiment(
    ticker="AAPL",
    start_date="2024-01-01"
)
sent_df = sentiment.to_dataframe()
print(sent_df.head())
```

---

## Subreddit Coverage

| Subreddit | Focus |
|-----------|-------|
| r/wallstreetbets | High-risk retail trading |
| r/investing | Long-term investing |
| r/stocks | General stock discussion |
| r/options | Options trading |
| r/pennystocks | Small cap speculation |

---

## Data Quality Notes

- Sentiment analysis has ~80% accuracy
- Bot activity is filtered but not eliminated
- Weekend activity is lower
- Meme stock attention is episodic
