from datetime import datetime, timedelta
import os

from airflow import DAG
from airflow.operators.bash import BashOperator


DBT_PROJECT_DIR = "/mnt/c/Users/TusharGwal/Documents/shopstream_dbt_demo"


default_args = {
    "owner": "tushar",
    "depends_on_past": False,
    "start_date": datetime(2024, 1, 1),
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
    "email_on_failure": False,
    "email_on_retry": False,
}


with DAG(
    "shopstream_dbt_pipeline",
    default_args=default_args,
    description="dbt Bronze->Silver->Gold pipeline for Shopstream demo",
    schedule_interval="@daily",
    catchup=False,
    tags=["dbt", "shopstream", "medallion"],
) as dag:
    PYTHON = "/usr/bin/python3"

    dbt_bronze_to_silver = BashOperator(
        task_id="dbt_bronze_to_silver",
        bash_command=(
            f"cd {DBT_PROJECT_DIR} && "
            f"{PYTHON} run_dbt.py build --profiles-dir . --target bronze_lakehouse "
            "--select stg_customers stg_orders stg_payments --no-partial-parse"
        ),
        env={
            **os.environ,
            "DBT_PROFILES_DIR": DBT_PROJECT_DIR,
        },
    )

    dbt_silver_intermediate = BashOperator(
        task_id="dbt_silver_intermediate",
        bash_command=(
            f"cd {DBT_PROJECT_DIR} && "
            f"{PYTHON} run_dbt.py build --profiles-dir . --target silver_lakehouse "
            "--select int_orders_with_payments --no-partial-parse"
        ),
        env={
            **os.environ,
            "DBT_PROFILES_DIR": DBT_PROJECT_DIR,
        },
    )

    dbt_silver_to_gold = BashOperator(
        task_id="dbt_silver_to_gold",
        bash_command=(
            f"cd {DBT_PROJECT_DIR} && "
            f"{PYTHON} run_dbt.py build --profiles-dir . --target gold_warehouse "
            "--select gold --no-partial-parse"
        ),
        env={
            **os.environ,
            "DBT_PROFILES_DIR": DBT_PROJECT_DIR,
        },
    )

    dbt_bronze_to_silver >> dbt_silver_intermediate >> dbt_silver_to_gold
