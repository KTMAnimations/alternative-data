# Phase 1 Implementation Materials

These materials help you continue building the Alternative Data Platform after the MVP is complete.

## Contents

### 1. PHASE1_IMPLEMENTATION_PROMPT.md
The main implementation prompt for adding Tier 1 data sources. Copy and paste into Claude Code to:
- Add ADS-B Exchange (aviation/M&A signals)
- Add US Power Grid ISOs (CAISO, ERCOT, PJM, MISO)
- Add USPTO Patent data
- Add OpenAQ air quality data
- Implement 30+ new factors
- Extend the API

**Usage:**
```bash
# Copy the prompt contents and paste into Claude Code
# Work through each of the 7 stages
# Verify tests pass at each checkpoint
```

### 2. scripts/backfill.py
Historical data backfill script for populating 6+ months of data for backtesting.

**Usage:**
```bash
# Backfill all sources for 6 months
python scripts/backfill.py --source all --start 2024-01-01 --end 2024-06-30

# Backfill specific source
python scripts/backfill.py --source sec_edgar --start 2024-01-01 --end 2024-06-30

# Only compute factors (data already exists)
python scripts/backfill.py --factors-only --start 2024-01-01 --end 2024-06-30

# Dry run to see what would happen
python scripts/backfill.py --source all --start 2024-01-01 --end 2024-06-30 --dry-run
```

**Supported Sources:**
- `sec_edgar` - SEC filings and Form 4
- `fred` - Federal Reserve economic data
- `power_grid` - All 4 ISOs
- `patents` - USPTO patent data
- `air_quality` - OpenAQ readings
- `all` - Everything

### 3. dags/altdata_dags.py
Airflow DAGs for production scheduling.

**DAGs Included:**
| DAG | Schedule | Description |
|-----|----------|-------------|
| `altdata_sec_edgar` | Every 5 min | SEC EDGAR filings |
| `altdata_fred` | Daily 8 AM | FRED economic data |
| `altdata_aviation` | Hourly | ADS-B flight data |
| `altdata_power_grid` | Hourly | Power grid (4 ISOs) |
| `altdata_air_quality` | Hourly | OpenAQ readings |
| `altdata_patents` | Weekly (Tue) | USPTO patents |
| `altdata_data_quality` | Daily 9 AM | Quality checks |
| `altdata_backfill` | Manual | Historical backfill |

**Setup:**
```bash
# Install Airflow
pip install apache-airflow

# Copy DAGs to Airflow
cp dags/altdata_dags.py $AIRFLOW_HOME/dags/

# Configure Airflow Variables (UI or CLI)
airflow variables set ALTDATA_HOME /path/to/altdata-platform
airflow variables set DATABASE_URL postgresql://user:pass@host/db
airflow variables set REDIS_URL redis://localhost:6379/0
airflow variables set SEC_EDGAR_USER_AGENT "YourName email@example.com"
airflow variables set FRED_API_KEY your-fred-key
# ... etc for other API keys

# Start Airflow
airflow standalone  # Development
# OR
airflow webserver & airflow scheduler  # Production
```

## Recommended Order of Operations

### Week 1-2: Backfill Historical Data
```bash
# 1. Start with FRED (fastest, most reliable)
python scripts/backfill.py --source fred --start 2024-01-01 --end 2024-06-30

# 2. Then SEC EDGAR
python scripts/backfill.py --source sec_edgar --start 2024-01-01 --end 2024-06-30

# 3. Compute factors
python scripts/backfill.py --factors-only --start 2024-01-01 --end 2024-06-30
```

### Week 3-4: Implement Phase 1 Sources
1. Copy PHASE1_IMPLEMENTATION_PROMPT.md into Claude Code
2. Work through stages 1-7
3. Verify all tests pass

### Week 5: Deploy Production Scheduling
1. Set up Airflow
2. Deploy DAGs
3. Configure monitoring/alerting
4. Run parallel with backfill to catch up

### Week 6+: Monitor and Iterate
1. Watch data quality metrics
2. Tune factor computations
3. Add new factors based on research
4. Scale infrastructure as needed

## API Keys Required

| Service | Required For | How to Get |
|---------|--------------|------------|
| FRED | Economic data | https://fred.stlouisfed.org/docs/api/api_key.html |
| ADS-B Exchange | Flight data | https://rapidapi.com/adsbexchange |
| OpenAQ | Air quality | https://openaq.org/developers/ |
| USPTO | Patents | https://developer.uspto.gov/ |

## Infrastructure Requirements

For production with all Tier 1 sources:
- PostgreSQL 15+ with TimescaleDB (100GB+ storage)
- Redis 7+ (4GB RAM)
- 4+ CPU cores for collectors
- 16GB+ RAM for factor computation

## Support

If you encounter issues:
1. Check logs in `logs/` directory
2. Verify API keys are valid
3. Check rate limits haven't been exceeded
4. Review test output for specific failures
