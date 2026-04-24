#!/usr/bin/env python3
"""
Get Started with Snowflake-Managed Iceberg Tables
DuckDB Interoperability Demo

Connects DuckDB to Snowflake-managed Iceberg tables via Horizon Catalog
and runs analytical queries — no data movement, no Snowflake compute.

Prerequisites:
  pip install duckdb python-dotenv

Usage:
  python duckdb_interop.py
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load configuration
SCRIPT_DIR = Path(__file__).parent.resolve()
CONFIG_PATH = SCRIPT_DIR / 'config.env'
if CONFIG_PATH.exists():
    load_dotenv(CONFIG_PATH)
else:
    load_dotenv('config.env')

try:
    import duckdb
except ImportError:
    print("ERROR: duckdb is not installed. Run: pip install duckdb")
    raise SystemExit(1)

SNOWFLAKE_ACCOUNT_URL = os.getenv('SNOWFLAKE_ACCOUNT', '').replace('.', '-')
SNOWFLAKE_PAT = os.getenv('SNOWFLAKE_PAT', '')
SNOWFLAKE_DATABASE = os.getenv('SNOWFLAKE_DATABASE', 'FLEET_DB')

if not SNOWFLAKE_PAT:
    print("ERROR: SNOWFLAKE_PAT is not set in config.env.")
    print("Create a Programmatic Access Token in Snowsight:")
    print("  User Menu → My Profile → Programmatic Access Tokens")
    raise SystemExit(1)

print("=" * 60)
print("DuckDB ↔ Snowflake Horizon Catalog Interoperability")
print("=" * 60)
print(f"Account:  {SNOWFLAKE_ACCOUNT_URL}")
print(f"Database: {SNOWFLAKE_DATABASE}")
print()

# Connect
conn = duckdb.connect()
conn.execute("INSTALL iceberg; LOAD iceberg;")
conn.execute(f"""
    CREATE OR REPLACE SECRET horizon_secret (
        TYPE BEARER,
        TOKEN '{SNOWFLAKE_PAT}'
    );
""")
conn.execute(f"""
    ATTACH '{SNOWFLAKE_DATABASE}' AS horizon (
        TYPE ICEBERG,
        ENDPOINT '{SNOWFLAKE_ACCOUNT_URL}.snowflakecomputing.com/polaris/api/catalog',
        SECRET horizon_secret
    );
""")
print("Connected to Horizon Catalog!\n")

# List tables
print("--- Tables in RAW schema ---")
conn.execute("SHOW TABLES IN horizon.RAW").show()
print()

# Query vehicle registry
print("--- Vehicle Registry (top 10) ---")
conn.execute("""
    SELECT VEHICLE_ID, MAKE, MODEL, YEAR, FLEET_REGION
    FROM horizon.RAW.VEHICLE_REGISTRY
    LIMIT 10
""").show()
print()

# Aggregate sensor readings
print("--- Top 10 Vehicles by Fuel Consumption ---")
conn.execute("""
    SELECT
        VEHICLE_ID,
        COUNT(*) AS reading_count,
        ROUND(AVG(ENGINE_TEMP_F), 1) AS avg_engine_temp,
        ROUND(AVG(FUEL_CONSUMPTION_GPH), 2) AS avg_fuel_gph
    FROM horizon.RAW.SENSOR_READINGS
    GROUP BY VEHICLE_ID
    ORDER BY avg_fuel_gph DESC
    LIMIT 10
""").show()

print("\nDone! DuckDB read Snowflake-managed Iceberg tables with zero data movement.")
