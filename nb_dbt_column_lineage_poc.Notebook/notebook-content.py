# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "synapse_pyspark"
# META   },
# META   "dependencies": {
# META     "warehouse": {
# META       "default_warehouse": "818b8512-4d82-4b2a-b4e8-9f28dcc04d84",
# META       "known_warehouses": [
# META         {
# META           "id": "818b8512-4d82-4b2a-b4e8-9f28dcc04d84",
# META           "type": "Lakewarehouse"
# META         }
# META       ]
# META     }
# META   }
# META }

# MARKDOWN ********************

# # dbt Column-Level Lineage POC for Microsoft Fabric
# 
# This notebook runs **dbt Core inside a Fabric Notebook**, generates dbt artifacts, parses compiled SQL with `sqlglot`, and produces column-level lineage mappings.
# 
# Flow:
# 
# ```text
# dbt project
#   ↓
# dbt compile / dbt docs generate
#   ↓
# target/manifest.json + target/catalog.json + target/compiled SQL
#   ↓
# sqlglot parser
#   ↓
# column-level lineage JSON
#   ↓
# optional Purview / Atlas API publisher
# ```
# 
# > Use this notebook for the POC because the native Fabric dbt Job UI can show compiled SQL, but it may not expose the generated `target/` folder as normal project files.


# MARKDOWN ********************

# ## 0. Parameters
# 
# Update these values before running.
# 
# Important:
# - `FABRIC_SQL_ENDPOINT` should be the SQL endpoint/server for your Fabric Warehouse.
# - `TARGET_DATABASE` should be your Gold Warehouse name.
# - `SILVER_DATABASE` should be where your upstream Silver tables exist. For quick testing, this can be the same as `TARGET_DATABASE`.
# - For service principal auth, use tenant/client/secret values from a secure source if possible.


# CELL ********************

# ============================================================
# USER CONFIGURATION
# ============================================================

from pathlib import Path
import os
import json
import subprocess
import textwrap
import shutil
from datetime import datetime, timezone

# Project names
PROJECT_NAME = "fabric_lineage_poc"
PROFILE_NAME = "fabric_lineage_poc"

# Local notebook filesystem paths
PROJECT_DIR = Path("/tmp/fabric_lineage_poc")
PROFILES_DIR = Path("/tmp/dbt_profiles")

# Fabric Warehouse / SQL endpoint config
# Example server format usually looks like:
# xxxxxxxx.datawarehouse.fabric.microsoft.com
FABRIC_SQL_ENDPOINT = "YOUR_SQL_ENDPOINT_HERE"

# Gold Warehouse target
TARGET_DATABASE = "warehouse_gold"
TARGET_SCHEMA = "dbo"

# Silver source database/lakehouse SQL endpoint name
# For initial testing, you may keep this as warehouse_gold if your stg tables are there.
SILVER_DATABASE = "warehouse_gold"   # Change to lakehouse_silver if needed
SILVER_SCHEMA = "dbo"

# dbt source tables
SILVER_TABLES = [
    "stg_customers",
    "int_orders_with_payments"
]

# Authentication mode.
# Recommended for automation: ActiveDirectoryServicePrincipal
DBT_AUTHENTICATION = "ActiveDirectoryServicePrincipal"

# Service principal credentials.
# Better: read these from Fabric environment variables / Key Vault.
TENANT_ID = os.getenv("AZURE_TENANT_ID", "YOUR_TENANT_ID")
CLIENT_ID = os.getenv("AZURE_CLIENT_ID", "YOUR_CLIENT_ID")
CLIENT_SECRET = os.getenv("AZURE_CLIENT_SECRET", "YOUR_CLIENT_SECRET")

# Optional: save generated lineage JSON into a lakehouse Files path if mounted/available.
# Leave as None if you only want local /tmp output.
LINEAGE_OUTPUT_PATH = PROJECT_DIR / "lineage_output.json"

print("Project directory:", PROJECT_DIR)
print("Profiles directory:", PROFILES_DIR)
print("Target:", TARGET_DATABASE + "." + TARGET_SCHEMA)
print("Silver source:", SILVER_DATABASE + "." + SILVER_SCHEMA)


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## 1. Install packages
# 
# This installs:
# - `dbt-core`
# - `dbt-fabric`
# - `sqlglot`
# - `requests`
# - `azure-identity`
# 
# After installation, restart the Python session if Fabric asks you to.


# CELL ********************

%pip install -q dbt-core dbt-fabric sqlglot requests azure-identity pyodbc

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## 2. Verify dbt installation

# CELL ********************

def run_command(command, cwd=None, env=None, check=False):
    """Run a shell command and print stdout/stderr clearly."""
    print("Running:", " ".join(command))
    result = subprocess.run(
        command,
        cwd=str(cwd) if cwd else None,
        env=env,
        capture_output=True,
        text=True
    )
    print("\n--- STDOUT ---")
    print(result.stdout)
    print("\n--- STDERR ---")
    print(result.stderr)
    print("\nReturn code:", result.returncode)
    if check and result.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(command)}")
    return result

run_command(["dbt", "--version"])


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## 3. Create dbt project files
# 
# This creates a small dbt project dynamically inside `/tmp`.
# 
# For your POC, the model is:
# 
# ```text
# silver.stg_customers
# silver.int_orders_with_payments
#         ↓
# gold.fct_customer_lifetime_value
# ```


# CELL ********************

# Clean and recreate project folders
if PROJECT_DIR.exists():
    shutil.rmtree(PROJECT_DIR)

PROJECT_DIR.mkdir(parents=True, exist_ok=True)
(PROJECT_DIR / "models" / "gold").mkdir(parents=True, exist_ok=True)
(PROJECT_DIR / "models" / "silver").mkdir(parents=True, exist_ok=True)

# dbt_project.yml
dbt_project_yml = f"""
name: '{PROJECT_NAME}'
version: '1.0.0'
config-version: 2

profile: '{PROFILE_NAME}'

model-paths: ["models"]

models:
  {PROJECT_NAME}:
    gold:
      +schema: {TARGET_SCHEMA}
      +materialized: table
""".strip()

(PROJECT_DIR / "dbt_project.yml").write_text(dbt_project_yml)

print((PROJECT_DIR / "dbt_project.yml").read_text())


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# sources.yml
tables_yaml = "\n".join([f"      - name: {table}" for table in SILVER_TABLES])

sources_yml = f"""
version: 2

sources:
  - name: silver
    database: {SILVER_DATABASE}
    schema: {SILVER_SCHEMA}
    tables:
{tables_yaml}
""".strip()

(PROJECT_DIR / "models" / "sources.yml").write_text(sources_yml)

print((PROJECT_DIR / "models" / "sources.yml").read_text())


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Gold model
gold_model_sql = """
select
    c.customer_id,
    c.first_name,
    c.last_name,
    c.email,
    count(o.order_id) as total_orders,
    coalesce(sum(o.order_total), 0) as lifetime_spend,
    coalesce(sum(o.outstanding_balance), 0) as total_outstanding,
    min(o.ordered_at) as first_order_date,
    max(o.ordered_at) as last_order_date
from {{ source('silver', 'stg_customers') }} c
left join {{ source('silver', 'int_orders_with_payments') }} o
    on c.customer_id = o.customer_id
group by
    c.customer_id,
    c.first_name,
    c.last_name,
    c.email
""".strip()

(PROJECT_DIR / "models" / "gold" / "fct_customer_lifetime_value.sql").write_text(gold_model_sql)

print((PROJECT_DIR / "models" / "gold" / "fct_customer_lifetime_value.sql").read_text())


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## 4. Create dbt profile
# 
# This writes `profiles.yml`.
# 
# For a real company POC, do not hardcode secrets in the notebook. Use environment variables, Key Vault, or Fabric workspace-level secret handling.


# CELL ********************

PROFILES_DIR.mkdir(parents=True, exist_ok=True)

profiles_yml = f"""
{PROFILE_NAME}:
  target: dev
  outputs:
    dev:
      type: fabric
      driver: ODBC Driver 18 for SQL Server
      server: {FABRIC_SQL_ENDPOINT}
      port: 1433
      database: {TARGET_DATABASE}
      schema: {TARGET_SCHEMA}
      authentication: {DBT_AUTHENTICATION}
      tenant_id: {TENANT_ID}
      client_id: {CLIENT_ID}
      client_secret: {CLIENT_SECRET}
""".strip()

(PROFILES_DIR / "profiles.yml").write_text(profiles_yml)

# Print a redacted version
redacted = profiles_yml.replace(CLIENT_SECRET, "***REDACTED***") if CLIENT_SECRET else profiles_yml
print(redacted)


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## 5. Run dbt debug
# 
# If this fails, check:
# 1. SQL endpoint/server name
# 2. Warehouse name
# 3. Service principal credentials
# 4. Workspace permissions
# 5. Fabric tenant setting allowing service principals
# 6. ODBC Driver availability in the notebook runtime


# CELL ********************

dbt_env = os.environ.copy()
dbt_env["DBT_PROFILES_DIR"] = str(PROFILES_DIR)

debug_result = run_command(
    ["dbt", "debug"],
    cwd=PROJECT_DIR,
    env=dbt_env,
    check=False
)


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## 6. Run dbt compile
# 
# This is the key step for lineage. It should create:
# 
# ```text
# target/manifest.json
# target/run_results.json
# target/compiled/...
# ```


# CELL ********************

compile_result = run_command(
    ["dbt", "compile"],
    cwd=PROJECT_DIR,
    env=dbt_env,
    check=False
)

print("target exists:", (PROJECT_DIR / "target").exists())
for path in sorted((PROJECT_DIR / "target").rglob("*")) if (PROJECT_DIR / "target").exists() else []:
    print(path)


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## 7. Generate catalog.json
# 
# `catalog.json` contains column names and types after dbt introspects the target database.
# 
# If this fails because the model has not been built yet, run `dbt build` first or comment this cell during early compile-only testing.


# CELL ********************

# Optional: build the model before docs generation.
# Uncomment if docs generate fails because relations don't exist.
# build_result = run_command(
#     ["dbt", "build", "--select", "fct_customer_lifetime_value"],
#     cwd=PROJECT_DIR,
#     env=dbt_env,
#     check=False
# )

docs_result = run_command(
    ["dbt", "docs", "generate"],
    cwd=PROJECT_DIR,
    env=dbt_env,
    check=False
)

print("manifest exists:", (PROJECT_DIR / "target" / "manifest.json").exists())
print("catalog exists:", (PROJECT_DIR / "target" / "catalog.json").exists())


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## 8. Load dbt artifacts
# 
# We load:
# - `manifest.json`
# - `catalog.json`, if available
# - compiled SQL files


# CELL ********************

target_dir = PROJECT_DIR / "target"
manifest_path = target_dir / "manifest.json"
catalog_path = target_dir / "catalog.json"

if not manifest_path.exists():
    raise FileNotFoundError("manifest.json not found. Run dbt compile first.")

manifest = json.loads(manifest_path.read_text())

catalog = None
if catalog_path.exists():
    catalog = json.loads(catalog_path.read_text())

compiled_files = list((target_dir / "compiled").rglob("*.sql"))
print("Compiled SQL files found:", len(compiled_files))

for file in compiled_files:
    print("\nFILE:", file)
    print(file.read_text()[:2000])
    print("=" * 80)


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## 9. Parse compiled SQL with sqlglot
# 
# This first parser extracts:
# - output column name
# - source column references found inside the output expression
# - expression SQL
# - mapping type
# 
# This is enough to prove the POC. We can later make it smarter with alias-to-table resolution, CTE handling, and Atlas/Purview-specific qualified names.


# CELL ********************

import sqlglot
from sqlglot import exp

def classify_mapping(expression_sql: str, source_columns: list[str]) -> str:
    sql_upper = expression_sql.upper()

    if any(fn in sql_upper for fn in ["SUM(", "COUNT(", "MIN(", "MAX(", "AVG("]):
        return "aggregation"
    if "CASE " in sql_upper:
        return "derived_case"
    if "COALESCE(" in sql_upper:
        return "derived_coalesce"
    if "CAST(" in sql_upper or "CONVERT(" in sql_upper:
        return "cast"
    if any(op in expression_sql for op in [" + ", " - ", " * ", " / "]):
        return "calculation"
    if len(source_columns) == 1:
        return "direct_or_rename"
    if len(source_columns) > 1:
        return "derived"
    return "constant_or_unknown"

def extract_column_lineage_from_sql(sql_text: str, dialect: str = "tsql") -> list[dict]:
    parsed = sqlglot.parse_one(sql_text, read=dialect)

    # For this POC, focus on the outer SELECT.
    select_expr = parsed.find(exp.Select)
    if select_expr is None:
        return []

    lineage_rows = []
    for projection in select_expr.expressions:
        output_column = projection.alias_or_name

        # Collect source columns referenced inside this projection.
        source_columns = []
        for col in projection.find_all(exp.Column):
            source_columns.append(col.sql(dialect=dialect))

        expression_sql = projection.sql(dialect=dialect)

        lineage_rows.append({
            "target_column": output_column,
            "source_columns": sorted(set(source_columns)),
            "expression": expression_sql,
            "mapping_type": classify_mapping(expression_sql, source_columns)
        })

    return lineage_rows

all_sql_lineage = {}

for file in compiled_files:
    sql_text = file.read_text()
    lineage_rows = extract_column_lineage_from_sql(sql_text, dialect="tsql")
    all_sql_lineage[str(file)] = lineage_rows

    print("\nCompiled file:", file)
    for row in lineage_rows:
        print(json.dumps(row, indent=2))


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## 10. Resolve model metadata from manifest.json
# 
# This maps dbt model names to:
# - database
# - schema
# - alias / relation name
# - dependencies
# - compiled path
# 
# The goal is to combine dbt's model graph with sqlglot's column extraction.


# CELL ********************

def relation_name_from_node(node: dict) -> str:
    database = node.get("database")
    schema = node.get("schema")
    alias = node.get("alias") or node.get("name")
    parts = [p for p in [database, schema, alias] if p]
    return ".".join(parts)

def get_dbt_nodes(manifest: dict) -> dict:
    nodes = {}
    for unique_id, node in manifest.get("nodes", {}).items():
        if node.get("resource_type") == "model":
            nodes[unique_id] = node
    return nodes

def get_dbt_sources(manifest: dict) -> dict:
    sources = {}
    for unique_id, source in manifest.get("sources", {}).items():
        sources[unique_id] = source
    return sources

nodes = get_dbt_nodes(manifest)
sources = get_dbt_sources(manifest)

print("Models:")
for unique_id, node in nodes.items():
    print(unique_id, "=>", relation_name_from_node(node))
    print("  depends_on:", node.get("depends_on", {}).get("nodes", []))
    print("  compiled_path:", node.get("compiled_path"))

print("\nSources:")
for unique_id, source in sources.items():
    relation = ".".join([
        str(source.get("database")),
        str(source.get("schema")),
        str(source.get("identifier") or source.get("name"))
    ])
    print(unique_id, "=>", relation)


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## 11. Build a column mapping structure
# 
# This produces an in-memory structure similar to what we would later publish to Purview.
# 
# The `column_mappings` are generated from compiled SQL, while model dependency information comes from `manifest.json`.


# CELL ********************

def find_compiled_file_for_node(node: dict) -> Path | None:
    compiled_path = node.get("compiled_path")
    if not compiled_path:
        return None

    candidate = PROJECT_DIR / "target" / compiled_path
    if candidate.exists():
        return candidate

    # Fallback: search by filename.
    node_name = node.get("name")
    matches = list((PROJECT_DIR / "target" / "compiled").rglob(f"{node_name}.sql"))
    if matches:
        return matches[0]
    return None

def source_relation_from_unique_id(unique_id: str, manifest: dict) -> str:
    if unique_id in manifest.get("nodes", {}):
        return relation_name_from_node(manifest["nodes"][unique_id])
    if unique_id in manifest.get("sources", {}):
        s = manifest["sources"][unique_id]
        return ".".join([
            str(s.get("database")),
            str(s.get("schema")),
            str(s.get("identifier") or s.get("name"))
        ])
    return unique_id

lineage_payloads = []

for unique_id, node in nodes.items():
    compiled_file = find_compiled_file_for_node(node)
    if not compiled_file:
        print("No compiled file found for:", unique_id)
        continue

    sql_text = compiled_file.read_text()
    column_lineage = extract_column_lineage_from_sql(sql_text, dialect="tsql")

    input_relations = [
        source_relation_from_unique_id(dep, manifest)
        for dep in node.get("depends_on", {}).get("nodes", [])
    ]

    payload = {
        "process": f"dbt.{node.get('name')}",
        "dbt_unique_id": unique_id,
        "compiled_sql_path": str(compiled_file),
        "inputs": input_relations,
        "outputs": [relation_name_from_node(node)],
        "column_mappings": []
    }

    target_table = relation_name_from_node(node)

    for mapping in column_lineage:
        # This POC stores source column references as sqlglot sees them, e.g. c.customer_id.
        # Later we can resolve aliases c/o to exact input tables using FROM/JOIN parsing.
        if mapping["source_columns"]:
            for source_column in mapping["source_columns"]:
                payload["column_mappings"].append({
                    "source_column_reference": source_column,
                    "target_table": target_table,
                    "target_column": mapping["target_column"],
                    "type": mapping["mapping_type"],
                    "expression": mapping["expression"]
                })
        else:
            payload["column_mappings"].append({
                "source_column_reference": None,
                "target_table": target_table,
                "target_column": mapping["target_column"],
                "type": mapping["mapping_type"],
                "expression": mapping["expression"]
            })

    lineage_payloads.append(payload)

print(json.dumps(lineage_payloads, indent=2))


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## 12. Resolve table aliases from the SQL
# 
# This improves mappings like:
# 
# ```text
# c.customer_id
# ```
# 
# into:
# 
# ```text
# warehouse_gold.dbo.stg_customers.customer_id
# ```
# 
# For this first POC, the alias resolver handles direct `FROM table alias` and `JOIN table alias` patterns in the compiled SQL.


# CELL ********************

def extract_alias_map(sql_text: str, dialect: str = "tsql") -> dict:
    parsed = sqlglot.parse_one(sql_text, read=dialect)
    alias_map = {}

    # Find all table references.
    for table in parsed.find_all(exp.Table):
        alias = table.alias
        table_name = table.sql(dialect=dialect)

        # Remove quotes for easier display.
        clean_table = table_name.replace('"', '').replace('[', '').replace(']', '')

        if alias:
            alias_map[alias] = clean_table
        else:
            alias_map[table.name] = clean_table

    return alias_map

def resolve_source_column_ref(source_ref: str, alias_map: dict) -> dict:
    if source_ref is None:
        return {
            "source_table": None,
            "source_column": None
        }

    clean = source_ref.replace('"', '').replace('[', '').replace(']', '')
    parts = clean.split(".")

    if len(parts) == 2:
        alias, column = parts
        source_table = alias_map.get(alias, alias)
        return {
            "source_table": source_table,
            "source_column": column
        }

    if len(parts) >= 3:
        return {
            "source_table": ".".join(parts[:-1]),
            "source_column": parts[-1]
        }

    return {
        "source_table": None,
        "source_column": clean
    }

enhanced_payloads = []

for payload in lineage_payloads:
    sql_text = Path(payload["compiled_sql_path"]).read_text()
    alias_map = extract_alias_map(sql_text, dialect="tsql")

    enhanced = dict(payload)
    enhanced["alias_map"] = alias_map
    enhanced["column_mappings"] = []

    for mapping in payload["column_mappings"]:
        resolved = resolve_source_column_ref(mapping["source_column_reference"], alias_map)
        enhanced_mapping = {
            "source_table": resolved["source_table"],
            "source_column": resolved["source_column"],
            "target_table": mapping["target_table"],
            "target_column": mapping["target_column"],
            "type": mapping["type"],
            "expression": mapping["expression"]
        }
        enhanced["column_mappings"].append(enhanced_mapping)

    enhanced_payloads.append(enhanced)

print(json.dumps(enhanced_payloads, indent=2))


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## 13. Save lineage JSON
# 
# This saves the generated lineage payload locally in the notebook filesystem.
# 
# You can later copy this to OneLake / Lakehouse Files / ADLS if needed.


# CELL ********************

final_output = {
    "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    "project_name": PROJECT_NAME,
    "target_database": TARGET_DATABASE,
    "target_schema": TARGET_SCHEMA,
    "lineage": enhanced_payloads
}

LINEAGE_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
LINEAGE_OUTPUT_PATH.write_text(json.dumps(final_output, indent=2))

print("Saved lineage output to:", LINEAGE_OUTPUT_PATH)
print(LINEAGE_OUTPUT_PATH.read_text())


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## 14. Build Purview / Atlas columnMapping JSON
# 
# Purview's Atlas-compatible API can represent lineage by creating:
# - dataset entities for inputs/outputs
# - a process entity for the transformation
# - process-level column mapping metadata
# 
# This cell only builds the payload shape. Do **not** run publishing until credentials and Purview endpoint are confirmed.


# CELL ********************

def build_column_mapping_attribute(column_mappings: list[dict]) -> str:
    """
    Build a JSON string suitable for storing on a process entity's columnMapping-like attribute.
    The exact custom type/attribute names may need to match your Purview/Atlas type definitions.
    """
    purview_mappings = []

    for m in column_mappings:
        purview_mappings.append({
            "SourceTable": m.get("source_table"),
            "SourceColumn": m.get("source_column"),
            "SinkTable": m.get("target_table"),
            "SinkColumn": m.get("target_column"),
            "Expression": m.get("expression"),
            "MappingType": m.get("type")
        })

    return json.dumps(purview_mappings)

def build_atlas_process_entity(payload: dict) -> dict:
    process_name = payload["process"]
    output_name = payload["outputs"][0] if payload["outputs"] else process_name

    process_entity = {
        "typeName": "Process",
        "attributes": {
            "qualifiedName": process_name,
            "name": process_name,
            "description": f"dbt column-level lineage for {process_name}",
            "inputs": payload.get("inputs", []),
            "outputs": payload.get("outputs", []),
            # This is the key idea from the workaround:
            # store serialized column mappings as metadata on the process.
            "columnMapping": build_column_mapping_attribute(payload.get("column_mappings", []))
        }
    }
    return process_entity

atlas_process_entities = [
    build_atlas_process_entity(payload)
    for payload in enhanced_payloads
]

print(json.dumps(atlas_process_entities, indent=2))


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## 15. Optional Purview publisher skeleton
# 
# This is intentionally disabled by default.
# 
# Before enabling:
# 1. Confirm your Purview account endpoint.
# 2. Confirm whether you are using Microsoft Purview Data Map Atlas API.
# 3. Confirm the entity type names and attributes accepted in your tenant.
# 4. Confirm credentials and permissions.
# 
# Then set `ENABLE_PURVIEW_PUBLISH = True`.


# CELL ********************

import requests
from azure.identity import ClientSecretCredential

ENABLE_PURVIEW_PUBLISH = False

PURVIEW_ACCOUNT_NAME = "YOUR_PURVIEW_ACCOUNT_NAME"
PURVIEW_ENDPOINT = f"https://{PURVIEW_ACCOUNT_NAME}.purview.azure.com"

def get_purview_token():
    credential = ClientSecretCredential(
        tenant_id=TENANT_ID,
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET
    )
    token = credential.get_token("https://purview.azure.net/.default")
    return token.token

def publish_entities_to_purview(entities: list[dict]):
    token = get_purview_token()
    url = f"{PURVIEW_ENDPOINT}/catalog/api/atlas/v2/entity/bulk"

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    body = {
        "entities": entities
    }

    response = requests.post(url, headers=headers, json=body, timeout=60)
    print("Status:", response.status_code)
    print(response.text)
    response.raise_for_status()
    return response.json()

if ENABLE_PURVIEW_PUBLISH:
    result = publish_entities_to_purview(atlas_process_entities)
    print(json.dumps(result, indent=2))
else:
    print("Purview publishing is disabled. Set ENABLE_PURVIEW_PUBLISH = True after validating endpoint, auth, and entity schema.")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## 16. Summary
# 
# What this notebook proves:
# 
# ```text
# dbt Core runs inside Fabric Notebook
#         ↓
# dbt artifacts are accessible in target/
#         ↓
# compiled SQL is parsed by sqlglot
#         ↓
# column-level mappings are generated automatically
#         ↓
# payload is ready for Purview/Atlas publishing
# ```
# 
# Next improvements:
# 1. Support more complex CTEs and nested queries.
# 2. Add stronger alias resolution using dbt manifest dependencies.
# 3. Add macro-generated SQL test cases.
# 4. Publish validated entities/processes to Purview.
# 5. Add a small Power BI / Fabric visual over the generated JSON for demo.

