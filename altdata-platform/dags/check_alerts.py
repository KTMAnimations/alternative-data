"""Airflow DAG for checking alert rules."""

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

default_args = {
    "owner": "altdata",
    "depends_on_past": False,
    "email_on_failure": True,
    "email_on_retry": False,
    "retries": 3,
    "retry_delay": timedelta(minutes=1),
}


def check_alerts():
    """Check all active alert rules and send notifications."""
    import logging
    from src.alerts.engine import AlertEngine

    logger = logging.getLogger(__name__)

    engine = AlertEngine()
    try:
        triggered = engine.check_all_rules()
        logger.info(f"Alert check complete. {len(triggered)} alerts triggered.")

        for notification in triggered:
            logger.info(
                f"Alert triggered: rule_id={notification.rule_id}, "
                f"entity_id={notification.entity_id}, "
                f"value={notification.factor_value}"
            )

        return len(triggered)

    except Exception as e:
        logger.error(f"Error checking alerts: {e}")
        raise

    finally:
        engine.close()


with DAG(
    "check_alerts",
    default_args=default_args,
    description="Check alert rules and send notifications",
    schedule_interval="*/5 * * * *",  # Every 5 minutes
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["alerts", "notifications"],
) as dag:

    check_alerts_task = PythonOperator(
        task_id="check_alerts",
        python_callable=check_alerts,
    )
