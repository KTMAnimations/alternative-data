# Patent Factors

Factors derived from USPTO patent filings and grants.

## Overview

Patent factors capture innovation activity, R&D productivity, and competitive positioning. Patent activity often leads commercial success by several years.

**Data Source**: USPTO
**Update Frequency**: Weekly
**Entity Type**: Company

---

## Factors

### patent_filing_momentum

**Description**: Change in patent filings over rolling 90 days

**Signal Logic**: Accelerating filings may indicate R&D breakthroughs

---

### patent_grant_rate

**Description**: Ratio of granted patents to total applications

**Signal Logic**: Higher grant rates indicate quality R&D output

---

### patent_citation_score

**Description**: Average citations received by company's patents

**Signal Logic**: Highly cited patents indicate influential innovations

---

### technology_breadth

**Description**: Number of distinct patent classes filed in

**Signal Logic**: Broader tech coverage may indicate diversification

---

### patent_portfolio_growth

**Description**: Year-over-year growth in total patent portfolio

---

### competitor_citation_ratio

**Description**: Ratio of citations from competitors vs. others

**Signal Logic**: High competitor citations indicate strategic importance

---

## Example Usage

```python
from altdata import AltDataClient

client = AltDataClient(api_key="your-api-key")

# Get patent momentum
data = client.get_factor(
    "patent_filing_momentum",
    entity_id="AAPL",
    start_date="2024-01-01"
)

df = data.to_dataframe()
print(df.head())

# Get raw patent data
patents = client.get_patents(company_id="AAPL", start_date="2024-01-01")
patent_df = patents.to_dataframe()
print(f"Total patents: {patents.total}")
```

---

## Data Quality Notes

- Patent publications lag filings by ~18 months
- Grant dates lag filing by 2-5 years
- Company name matching is approximate
- International patents not included
