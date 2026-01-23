"""
Airflow DAGs for Alternative Data Platform

This module defines production DAGs for:
1. Data collection from all sources
2. Factor computation
3. Data quality monitoring
4. Alerting

Setup:
    1. Install Airflow: pip install apache-airflow
    2. Copy this file to your Airflow dags folder
    3. Configure connections in Airflow UI:
       - postgres_default: PostgreSQL connection
       - redis_default: Redis connection
    4. Set environment variables or Airflow Variables for API keys
"""

from datetime import datetime, timedelta
from typing import Dict, Any

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
from airflow.sensors.external_task import ExternalTaskSensor
from airflow.utils.task_group import TaskGroup
from airflow.models import Variable

# ===========================================
# DEFAULT ARGS
# ===========================================

default_args = {
    "owner": "altdata",
    "depends_on_past": False,
    "email": ["alerts@yourcompany.com"],
    "email_on_failure": True,
    "email_on_retry": False,
    "retries": 3,
    "retry_delay": timedelta(minutes=5),
    "execution_timeout": timedelta(hours=1),
}


# ===========================================
# HELPER FUNCTIONS
# ===========================================

def get_db_session():
    """Get database session for Airflow tasks."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    
    db_url = Variable.get("DATABASE_URL", default_var="postgresql://localhost/altdata")
    engine = create_engine(db_url)
    Session = sessionmaker(bind=engine)
    return Session()


def run_collector(source: str, **context):
    """Run a data collector."""
    import asyncio
    import sys
    sys.path.insert(0, Variable.get("ALTDATA_HOME", "/opt/altdata"))
    
    from src.collectors.base import BaseCollector
    
    # Import the specific collector
    if source == "sec_edgar":
        from src.collectors.sec_edgar import SECEdgarCollector
        collector = SECEdgarCollector(
            user_agent=Variable.get("SEC_EDGAR_USER_AGENT")
        )
    elif source == "fred":
        from src.collectors.fred import FREDCollector
        collector = FREDCollector(
            api_key=Variable.get("FRED_API_KEY")
        )
    elif source == "adsb":
        from src.collectors.adsb_exchange import ADSBExchangeCollector
        collector = ADSBExchangeCollector(
            api_key=Variable.get("ADSB_API_KEY"),
            rapidapi_key=Variable.get("ADSB_RAPIDAPI_KEY")
        )
    elif source == "openaq":
        from src.collectors.openaq import OpenAQCollector
        collector = OpenAQCollector(
            api_key=Variable.get("OPENAQ_API_KEY")
        )
    elif source == "weather":
        from src.collectors.weather import WeatherCollector
        collector = WeatherCollector(
            api_key=Variable.get("OPENWEATHERMAP_API_KEY")
        )
    elif source == "trends":
        from src.collectors.google_trends import GoogleTrendsCollector
        collector = GoogleTrendsCollector()
    elif source == "reddit":
        from src.collectors.reddit_sentiment import RedditSentimentCollector
        collector = RedditSentimentCollector(
            client_id=Variable.get("REDDIT_CLIENT_ID"),
            client_secret=Variable.get("REDDIT_CLIENT_SECRET")
        )
    elif source == "shipping":
        from src.collectors.marine_traffic import MarineTrafficCollector
        collector = MarineTrafficCollector(
            api_key=Variable.get("MARINETRAFFIC_API_KEY")
        )
    elif source == "github":
        from src.collectors.github_activity import GitHubActivityCollector
        collector = GitHubActivityCollector(
            token=Variable.get("GITHUB_TOKEN")
        )
    elif source == "satellite":
        from src.collectors.sentinel import SentinelCollector
        collector = SentinelCollector(
            client_id=Variable.get("SENTINEL_HUB_CLIENT_ID"),
            client_secret=Variable.get("SENTINEL_HUB_CLIENT_SECRET")
        )
    elif source == "patents":
        from src.collectors.uspto import USPTOCollector
        collector = USPTOCollector(
            api_key=Variable.get("USPTO_API_KEY", "")
        )
    else:
        raise ValueError(f"Unknown source: {source}")
    
    # Run collector
    result = asyncio.run(collector.run())
    
    # Push metrics to XCom
    context["ti"].xcom_push(key="record_count", value=len(result) if result else 0)
    
    return result


def compute_factors(factor_category: str, **context):
    """Compute factors for a category."""
    import sys
    sys.path.insert(0, Variable.get("ALTDATA_HOME", "/opt/altdata"))
    
    from src.transformations.factor_registry import FACTOR_REGISTRY, compute_factor
    from src.models.schemas import Factor, Entity
    from datetime import date
    
    execution_date = context["execution_date"].date()
    session = get_db_session()
    
    # Get factors for this category
    factors = [f for f in FACTOR_REGISTRY.values() if f.category == factor_category]
    
    # Get entities
    entities = session.query(Entity).filter(Entity.is_active == True).all()
    
    computed = 0
    for entity in entities:
        for factor_spec in factors:
            if factor_spec.entity_type != entity.entity_type:
                continue
            
            try:
                value = compute_factor(factor_spec.id, entity.id, execution_date, session)
                
                if value is not None:
                    factor = Factor(
                        factor_name=factor_spec.id,
                        entity_id=entity.id,
                        entity_type=entity.entity_type,
                        value=value,
                        effective_date=execution_date,
                        computed_at=datetime.utcnow(),
                        version=1
                    )
                    session.merge(factor)
                    computed += 1
            except Exception as e:
                print(f"Error computing {factor_spec.id} for {entity.id}: {e}")
    
    session.commit()
    session.close()
    
    context["ti"].xcom_push(key="factors_computed", value=computed)
    return computed


def check_data_quality(**context):
    """Run data quality checks."""
    import sys
    sys.path.insert(0, Variable.get("ALTDATA_HOME", "/opt/altdata"))
    
    from sqlalchemy import func
    from src.models.schemas import Factor, RawDataCatalog
    
    session = get_db_session()
    execution_date = context["execution_date"].date()
    
    issues = []
    
    # Check 1: Raw data received today
    raw_count = session.query(func.count(RawDataCatalog.id)).filter(
        func.date(RawDataCatalog.fetch_timestamp) == execution_date
    ).scalar()
    
    if raw_count == 0:
        issues.append("No raw data received today")
    
    # Check 2: Factors computed today
    factor_count = session.query(func.count(Factor.id)).filter(
        Factor.effective_date == execution_date
    ).scalar()
    
    if factor_count < 10:  # Threshold
        issues.append(f"Low factor count: {factor_count}")
    
    # Check 3: Missing critical factors
    critical_factors = ["insider_transaction_momentum", "yield_curve_slope"]
    for factor_name in critical_factors:
        count = session.query(func.count(Factor.id)).filter(
            Factor.factor_name == factor_name,
            Factor.effective_date == execution_date
        ).scalar()
        
        if count == 0:
            issues.append(f"Missing critical factor: {factor_name}")
    
    session.close()
    
    # Push results
    context["ti"].xcom_push(key="quality_issues", value=issues)
    context["ti"].xcom_push(key="quality_passed", value=len(issues) == 0)
    
    if issues:
        raise ValueError(f"Data quality issues: {issues}")
    
    return True


def send_alert(alert_type: str, **context):
    """Send alert notification."""
    # This could integrate with Slack, PagerDuty, email, etc.
    issues = context["ti"].xcom_pull(key="quality_issues", task_ids="data_quality_check")
    
    message = f"""
    🚨 ALTDATA ALERT: {alert_type}
    
    Date: {context["execution_date"]}
    Issues: {issues}
    
    Please investigate.
    """
    
    print(message)
    # slack_webhook.post(message)
    # pagerduty.trigger(message)


def invalidate_cache(**context):
    """Invalidate Redis cache after new data."""
    import redis
    
    redis_url = Variable.get("REDIS_URL", "redis://localhost:6379/0")
    r = redis.from_url(redis_url)
    
    execution_date = context["execution_date"].strftime("%Y-%m-%d")
    
    # Invalidate factor cache for this date
    pattern = f"factor:*:{execution_date}"
    keys = r.keys(pattern)
    
    if keys:
        r.delete(*keys)
        print(f"Invalidated {len(keys)} cache keys")
    
    return len(keys)


# ===========================================
# DAG 1: SEC EDGAR COLLECTION
# ===========================================

dag_sec = DAG(
    "altdata_sec_edgar",
    default_args=default_args,
    description="Collect SEC EDGAR filings",
    schedule_interval="*/5 * * * *",  # Every 5 minutes
    start_date=datetime(2024, 1, 1),
    catchup=False,
    max_active_runs=1,
    tags=["altdata", "collection", "sec"],
)

with dag_sec:
    collect_sec = PythonOperator(
        task_id="collect_sec_edgar",
        python_callable=run_collector,
        op_kwargs={"source": "sec_edgar"},
    )
    
    compute_sec_factors = PythonOperator(
        task_id="compute_sec_factors",
        python_callable=compute_factors,
        op_kwargs={"factor_category": "sec"},
    )
    
    invalidate = PythonOperator(
        task_id="invalidate_cache",
        python_callable=invalidate_cache,
    )
    
    collect_sec >> compute_sec_factors >> invalidate


# ===========================================
# DAG 2: FRED COLLECTION (Daily)
# ===========================================

dag_fred = DAG(
    "altdata_fred",
    default_args=default_args,
    description="Collect FRED economic data",
    schedule_interval="0 8 * * *",  # 8 AM daily
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["altdata", "collection", "macro"],
)

with dag_fred:
    collect_fred = PythonOperator(
        task_id="collect_fred",
        python_callable=run_collector,
        op_kwargs={"source": "fred"},
    )
    
    compute_macro_factors = PythonOperator(
        task_id="compute_macro_factors",
        python_callable=compute_factors,
        op_kwargs={"factor_category": "macro"},
    )
    
    collect_fred >> compute_macro_factors


# ===========================================
# DAG 3: AVIATION DATA (Hourly)
# ===========================================

dag_adsb = DAG(
    "altdata_aviation",
    default_args=default_args,
    description="Collect ADS-B flight data",
    schedule_interval="0 * * * *",  # Every hour
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["altdata", "collection", "aviation"],
)

with dag_adsb:
    collect_adsb = PythonOperator(
        task_id="collect_adsb",
        python_callable=run_collector,
        op_kwargs={"source": "adsb"},
    )
    
    compute_aviation_factors = PythonOperator(
        task_id="compute_aviation_factors",
        python_callable=compute_factors,
        op_kwargs={"factor_category": "aviation"},
    )
    
    collect_adsb >> compute_aviation_factors


# ===========================================
# DAG 4: POWER GRID (Hourly)
# ===========================================

dag_power = DAG(
    "altdata_power_grid",
    default_args=default_args,
    description="Collect power grid data from ISOs",
    schedule_interval="0 * * * *",  # Every hour
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["altdata", "collection", "energy"],
)

with dag_power:
    with TaskGroup(group_id="collect_isos") as collect_group:
        for iso in ["caiso", "ercot", "pjm", "miso"]:
            PythonOperator(
                task_id=f"collect_{iso}",
                python_callable=run_collector,
                op_kwargs={"source": iso},
            )
    
    compute_energy_factors = PythonOperator(
        task_id="compute_energy_factors",
        python_callable=compute_factors,
        op_kwargs={"factor_category": "energy"},
    )
    
    collect_group >> compute_energy_factors


# ===========================================
# DAG 5: AIR QUALITY (Hourly)
# ===========================================

dag_air = DAG(
    "altdata_air_quality",
    default_args=default_args,
    description="Collect OpenAQ air quality data",
    schedule_interval="0 * * * *",  # Every hour
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["altdata", "collection", "environment"],
)

with dag_air:
    collect_air = PythonOperator(
        task_id="collect_openaq",
        python_callable=run_collector,
        op_kwargs={"source": "openaq"},
    )
    
    compute_env_factors = PythonOperator(
        task_id="compute_env_factors",
        python_callable=compute_factors,
        op_kwargs={"factor_category": "environment"},
    )
    
    collect_air >> compute_env_factors


# ===========================================
# DAG 6: PATENTS (Weekly)
# ===========================================

dag_patents = DAG(
    "altdata_patents",
    default_args=default_args,
    description="Collect USPTO patent data",
    schedule_interval="0 6 * * TUE",  # Tuesday 6 AM (after USPTO release)
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["altdata", "collection", "patents"],
)

with dag_patents:
    collect_patents = PythonOperator(
        task_id="collect_patents",
        python_callable=run_collector,
        op_kwargs={"source": "patents"},
    )
    
    compute_patent_factors = PythonOperator(
        task_id="compute_patent_factors",
        python_callable=compute_factors,
        op_kwargs={"factor_category": "patents"},
    )
    
    collect_patents >> compute_patent_factors


# ===========================================
# DAG 7: DATA QUALITY (Daily)
# ===========================================

dag_quality = DAG(
    "altdata_data_quality",
    default_args=default_args,
    description="Daily data quality checks",
    schedule_interval="0 9 * * *",  # 9 AM daily (after morning collections)
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["altdata", "monitoring"],
)

with dag_quality:
    # Wait for key DAGs to complete
    wait_for_sec = ExternalTaskSensor(
        task_id="wait_for_sec",
        external_dag_id="altdata_sec_edgar",
        external_task_id="compute_sec_factors",
        mode="reschedule",
        timeout=3600,
    )
    
    wait_for_fred = ExternalTaskSensor(
        task_id="wait_for_fred",
        external_dag_id="altdata_fred",
        external_task_id="compute_macro_factors",
        mode="reschedule",
        timeout=3600,
    )
    
    quality_check = PythonOperator(
        task_id="data_quality_check",
        python_callable=check_data_quality,
    )
    
    alert_on_failure = PythonOperator(
        task_id="send_alert",
        python_callable=send_alert,
        op_kwargs={"alert_type": "DATA_QUALITY_FAILURE"},
        trigger_rule="one_failed",  # Only run if quality check fails
    )
    
    [wait_for_sec, wait_for_fred] >> quality_check >> alert_on_failure


# ===========================================
# DAG 8: FULL BACKFILL (Manual Trigger)
# ===========================================

dag_backfill = DAG(
    "altdata_backfill",
    default_args={
        **default_args,
        "retries": 1,
        "execution_timeout": timedelta(hours=24),
    },
    description="Manual backfill for historical data",
    schedule_interval=None,  # Manual trigger only
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["altdata", "backfill"],
    params={
        "source": "all",
        "start_date": "2024-01-01",
        "end_date": "2024-06-30",
    },
)

with dag_backfill:
    backfill_task = BashOperator(
        task_id="run_backfill",
        bash_command="""
            cd {{ var.value.ALTDATA_HOME }}
            source venv/bin/activate
            python scripts/backfill.py \
                --source {{ params.source }} \
                --start {{ params.start_date }} \
                --end {{ params.end_date }}
        """,
    )


# ===========================================
# DAG 9: WEATHER DATA (Hourly)
# ===========================================

dag_weather = DAG(
    "altdata_weather",
    default_args=default_args,
    description="Collect OpenWeatherMap weather data",
    schedule_interval="0 * * * *",  # Every hour
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["altdata", "collection", "weather"],
)

with dag_weather:
    collect_weather = PythonOperator(
        task_id="collect_weather",
        python_callable=run_collector,
        op_kwargs={"source": "weather"},
    )

    compute_weather_factors = PythonOperator(
        task_id="compute_weather_factors",
        python_callable=compute_factors,
        op_kwargs={"factor_category": "weather"},
    )

    collect_weather >> compute_weather_factors


# ===========================================
# DAG 10: GOOGLE TRENDS (Daily)
# ===========================================

dag_trends = DAG(
    "altdata_trends",
    default_args=default_args,
    description="Collect Google Trends search data",
    schedule_interval="0 6 * * *",  # Daily at 6 AM
    start_date=datetime(2024, 1, 1),
    catchup=False,
    max_active_runs=1,  # Rate limiting is aggressive
    tags=["altdata", "collection", "trends"],
)

with dag_trends:
    collect_trends = PythonOperator(
        task_id="collect_trends",
        python_callable=run_collector,
        op_kwargs={"source": "trends"},
    )

    compute_trends_factors = PythonOperator(
        task_id="compute_trends_factors",
        python_callable=compute_factors,
        op_kwargs={"factor_category": "trends"},
    )

    collect_trends >> compute_trends_factors


# ===========================================
# DAG 11: REDDIT SENTIMENT (Hourly)
# ===========================================

dag_reddit = DAG(
    "altdata_reddit",
    default_args=default_args,
    description="Collect Reddit sentiment data with FinBERT",
    schedule_interval="0 * * * *",  # Every hour
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["altdata", "collection", "sentiment"],
)

with dag_reddit:
    collect_reddit = PythonOperator(
        task_id="collect_reddit",
        python_callable=run_collector,
        op_kwargs={"source": "reddit"},
    )

    compute_sentiment_factors = PythonOperator(
        task_id="compute_sentiment_factors",
        python_callable=compute_factors,
        op_kwargs={"factor_category": "sentiment"},
    )

    collect_reddit >> compute_sentiment_factors


# ===========================================
# DAG 12: SHIPPING DATA (Hourly)
# ===========================================

dag_shipping = DAG(
    "altdata_shipping",
    default_args=default_args,
    description="Collect MarineTraffic/AIS shipping data",
    schedule_interval="0 * * * *",  # Every hour
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["altdata", "collection", "shipping"],
)

with dag_shipping:
    collect_shipping = PythonOperator(
        task_id="collect_shipping",
        python_callable=run_collector,
        op_kwargs={"source": "shipping"},
    )

    compute_shipping_factors = PythonOperator(
        task_id="compute_shipping_factors",
        python_callable=compute_factors,
        op_kwargs={"factor_category": "shipping"},
    )

    collect_shipping >> compute_shipping_factors


# ===========================================
# DAG 13: GITHUB ACTIVITY (Daily)
# ===========================================

dag_github = DAG(
    "altdata_github",
    default_args=default_args,
    description="Collect GitHub developer activity data",
    schedule_interval="0 6 * * *",  # Daily at 6 AM
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["altdata", "collection", "github"],
)

with dag_github:
    collect_github = PythonOperator(
        task_id="collect_github",
        python_callable=run_collector,
        op_kwargs={"source": "github"},
    )

    compute_github_factors = PythonOperator(
        task_id="compute_github_factors",
        python_callable=compute_factors,
        op_kwargs={"factor_category": "github"},
    )

    collect_github >> compute_github_factors


# ===========================================
# DAG 14: SATELLITE IMAGERY (Weekly)
# ===========================================

dag_satellite = DAG(
    "altdata_satellite",
    default_args={
        **default_args,
        "execution_timeout": timedelta(hours=4),  # Satellite processing takes longer
    },
    description="Collect Sentinel-2 satellite imagery analysis",
    schedule_interval="0 6 * * MON",  # Weekly on Monday at 6 AM
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["altdata", "collection", "satellite"],
)

with dag_satellite:
    collect_satellite = PythonOperator(
        task_id="collect_satellite",
        python_callable=run_collector,
        op_kwargs={"source": "satellite"},
    )

    compute_satellite_factors = PythonOperator(
        task_id="compute_satellite_factors",
        python_callable=compute_factors,
        op_kwargs={"factor_category": "satellite"},
    )

    collect_satellite >> compute_satellite_factors
