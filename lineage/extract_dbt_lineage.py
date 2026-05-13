"""
Extract table-level and column-level lineage from dbt artifacts.

This script reads:
- target/manifest.json
- target/compiled/shopstream_dbt_demo/**/*.sql

And writes:
- target/lineage_output.json

Purview publishing is intentionally left for a future step.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import sqlglot
from sqlglot import exp


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = PROJECT_ROOT / "target" / "manifest.json"
COMPILED_ROOT = PROJECT_ROOT / "target" / "compiled" / "shopstream_dbt_demo"
OUTPUT_PATH = PROJECT_ROOT / "target" / "lineage_output.json"


class DbtLineageExtractor:
    def __init__(self, manifest_path: Path, compiled_sql_root: Path):
        self.manifest_path = manifest_path
        self.compiled_sql_root = compiled_sql_root
        self.manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    def get_model_fqn(self, node: dict[str, Any]) -> str:
        config = node.get("config", {})
        database = config.get("database") or node.get("database")
        schema = config.get("schema") or node.get("schema")
        name = node.get("alias") or node.get("name")
        return ".".join(part for part in [database, schema, name] if part)

    def get_source_fqn(self, source: dict[str, Any]) -> str:
        database = source.get("database") or source.get("source_name")
        schema = source.get("schema")
        name = source.get("identifier") or source.get("name")
        return ".".join(part for part in [database, schema, name] if part)

    def get_compiled_sql(self, node: dict[str, Any]) -> str | None:
        if node.get("compiled_code"):
            return node["compiled_code"]

        compiled_path = node.get("compiled_path")
        if compiled_path:
            path = PROJECT_ROOT / compiled_path
            if path.exists():
                return path.read_text(encoding="utf-8")

        original_file_path = node.get("original_file_path")
        if original_file_path:
            path = self.compiled_sql_root / original_file_path
            if path.exists():
                return path.read_text(encoding="utf-8")

        return None

    def extract_table_lineage(self) -> list[dict[str, Any]]:
        table_lineage = []

        for node_id, node in self.manifest["nodes"].items():
            if node.get("resource_type") != "model":
                continue

            sources = []
            for dep_id in node.get("depends_on", {}).get("nodes", []):
                if dep_id.startswith("source."):
                    source = self.manifest["sources"].get(dep_id)
                    if source:
                        sources.append(self.get_source_fqn(source))
                elif dep_id.startswith("model."):
                    dep_node = self.manifest["nodes"].get(dep_id)
                    if dep_node:
                        sources.append(self.get_model_fqn(dep_node))

            table_lineage.append(
                {
                    "target": self.get_model_fqn(node),
                    "sources": sources,
                    "node_id": node_id,
                    "model_name": node.get("name"),
                }
            )

        return table_lineage

    def parse_relation_name(self, table_expr: exp.Expression) -> str:
        catalog = table_expr.args.get("catalog")
        db = table_expr.args.get("db")
        name = table_expr.this
        parts = [catalog, db, name]
        return ".".join(str(part).strip("`[]\"") for part in parts if part)

    def extract_table_aliases(self, parsed: exp.Expression) -> dict[str, str]:
        aliases = {}

        for table in parsed.find_all(exp.Table):
            relation_name = self.parse_relation_name(table)
            alias = table.alias_or_name
            table_name = table.name

            if alias:
                aliases[alias] = relation_name
            if table_name:
                aliases[table_name] = relation_name

        return aliases

    def target_column_name(self, projection: exp.Expression) -> str | None:
        if isinstance(projection, exp.Alias):
            return projection.alias
        if isinstance(projection, exp.Column):
            return projection.name
        return projection.output_name or None

    def transformation_type(self, expression: exp.Expression) -> str:
        if isinstance(expression, exp.Column):
            return "DIRECT"
        if expression.find(exp.Cast):
            return "CAST"
        if expression.find(exp.Sum) or expression.find(exp.Count) or expression.find(exp.Avg):
            return "AGGREGATE"
        if expression.find(exp.Min) or expression.find(exp.Max):
            return "AGGREGATE"
        return "EXPRESSION"

    def parse_column_lineage_from_sql(
        self,
        model_name: str,
        sql: str,
        target_table: str,
        table_lineage: dict[str, list[str]],
    ) -> list[dict[str, Any]]:
        column_lineage = []

        try:
            dialect = "tsql" if "[" in sql and "]" in sql else "spark"
            parsed = sqlglot.parse_one(sql, read=dialect)
        except Exception as exc:
            print(f"WARNING: Error parsing SQL for {model_name}: {exc}")
            return column_lineage

        select = parsed.find(exp.Select)
        if not select:
            return column_lineage

        aliases = self.extract_table_aliases(parsed)
        source_tables = table_lineage.get(model_name, [])
        single_source = source_tables[0] if len(source_tables) == 1 else None

        for projection in select.expressions:
            target_col = self.target_column_name(projection)
            if not target_col:
                continue

            expression = projection.this if isinstance(projection, exp.Alias) else projection
            transformation = self.transformation_type(expression)

            for column in expression.find_all(exp.Column):
                source_alias = column.table
                source_table = aliases.get(source_alias) if source_alias else single_source

                if not source_table and source_alias:
                    source_table = f"UNRESOLVED_{source_alias}"
                elif not source_table:
                    source_table = "UNRESOLVED"

                column_lineage.append(
                    {
                        "target_table": target_table,
                        "target_column": target_col,
                        "source_table": source_table,
                        "source_column": column.name,
                        "transformation": transformation,
                        "model_name": model_name,
                        "expression": expression.sql(dialect="spark"),
                    }
                )

        return column_lineage

    def extract_column_lineage(self, table_lineage_entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
        all_column_lineage = []
        table_lineage_by_model = {
            entry["model_name"]: entry["sources"] for entry in table_lineage_entries
        }

        for node in self.manifest["nodes"].values():
            if node.get("resource_type") != "model":
                continue

            model_name = node.get("name")
            target_table = self.get_model_fqn(node)
            sql = self.get_compiled_sql(node)

            if not sql:
                print(f"WARNING: Compiled SQL not found for {model_name}")
                continue

            mappings = self.parse_column_lineage_from_sql(
                model_name=model_name,
                sql=sql,
                target_table=target_table,
                table_lineage=table_lineage_by_model,
            )
            all_column_lineage.extend(mappings)
            print(f"Extracted {len(mappings)} column mappings from {model_name}")

        return all_column_lineage

    def export_lineage(self, output_path: Path) -> dict[str, Any]:
        table_lineage = self.extract_table_lineage()
        column_lineage = self.extract_column_lineage(table_lineage)

        output = {
            "table_lineage": table_lineage,
            "column_lineage": column_lineage,
            "metadata": {
                "total_models": len(
                    [
                        node
                        for node in self.manifest["nodes"].values()
                        if node.get("resource_type") == "model"
                    ]
                ),
                "total_sources": len(self.manifest.get("sources", {})),
                "dbt_project": self.manifest.get("metadata", {}).get("project_name"),
            },
        }

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(output, indent=2), encoding="utf-8")

        print(f"\nLineage exported to: {output_path}")
        print(f"Table lineage entries: {len(table_lineage)}")
        print(f"Column lineage entries: {len(column_lineage)}")

        return output


def main() -> None:
    extractor = DbtLineageExtractor(MANIFEST_PATH, COMPILED_ROOT)
    lineage = extractor.export_lineage(OUTPUT_PATH)

    print("\nSample Column Lineage:")
    for entry in lineage["column_lineage"][:8]:
        print(
            f"  {entry['target_table']}.{entry['target_column']}\n"
            f"    <- {entry['source_table']}.{entry['source_column']} "
            f"[{entry['transformation']}]"
        )


if __name__ == "__main__":
    main()
