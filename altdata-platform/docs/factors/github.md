# GitHub Factors

Factors derived from GitHub repository activity for tech companies.

## Overview

GitHub factors capture developer activity, which can signal product development progress, organizational health, and innovation velocity.

**Data Source**: GitHub API
**Update Frequency**: Daily
**Entity Type**: Company (via associated repos)

---

## Factors

### developer_activity_score

**Description**: Composite score of commits, PRs, and issues

---

### commit_momentum

**Description**: Change in commit frequency vs. historical average

**Signal Logic**: Accelerating commits may indicate product push

---

### pr_merge_rate

**Description**: Ratio of merged to opened PRs

**Signal Logic**: Higher rates indicate efficient development

---

### issue_velocity

**Description**: Net issue creation (opened - closed)

**Signal Logic**: Rising issues may indicate quality problems

---

### contributor_count_change

**Description**: Change in unique contributors

---

### star_momentum

**Description**: Change in GitHub stars

**Signal Logic**: Star growth indicates community interest

---

### fork_activity

**Description**: Fork creation rate

---

## Example Usage

```python
from altdata import AltDataClient

client = AltDataClient(api_key="your-api-key")

# Get developer activity
data = client.get_factor(
    "developer_activity_score",
    entity_id="MSFT",
    start_date="2024-01-01"
)

df = data.to_dataframe()
print(df.head())

# List tracked repos
repos = client.list_github_repos(ticker="MSFT")
for repo in repos.repos:
    print(f"{repo.full_name}: {repo.stars} stars")

# Get activity for specific repo
activity = client.get_github_activity(
    repo="microsoft/vscode",
    start_date="2024-01-01"
)
act_df = activity.to_dataframe()
print(act_df.head())
```

---

## Tracked Companies

Major tech companies with significant open source presence:

| Ticker | Company | Notable Repos |
|--------|---------|---------------|
| MSFT | Microsoft | vscode, TypeScript, azure-sdk |
| GOOGL | Alphabet | kubernetes, TensorFlow, Angular |
| META | Meta | React, PyTorch, llama |
| AAPL | Apple | swift, webkit |
| AMZN | Amazon | aws-sdk, boto3 |

---

## Data Quality Notes

- Not all companies have significant GitHub presence
- Internal repos are not visible
- Bot commits are filtered
- Acquisition/org changes affect history
