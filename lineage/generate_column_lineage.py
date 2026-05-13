import csv
import json
import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = PROJECT_ROOT / "target" / "manifest.json"
COMPILED_ROOT = PROJECT_ROOT / "target" / "compiled" / "shopstream_dbt_demo"
CSV_OUTPUT = PROJECT_ROOT / "target" / "column_lineage.csv"
JSON_OUTPUT = PROJECT_ROOT / "target" / "column_lineage.json"

SQL_KEYWORDS = {
    "as",
    "cast",
    "coalesce",
    "count",
    "decimal",
    "from",
    "left",
    "min",
    "max",
    "null",
    "on",
    "select",
    "sum",
    "timestamp",
}


def normalize_relation(value: str) -> str:
    value = value.strip().rstrip(",")
    value = value.replace("[", "").replace("]", "")
    value = value.replace("`", "")
    return value


def relation_aliases(sql: str) -> dict[str, str]:
    aliases = {}
    pattern = re.compile(
        r"\b(?:from|join)\s+((?:`[^`]+`|\[[^\]]+\]|[A-Za-z0-9_]+)(?:\.(?:`[^`]+`|\[[^\]]+\]|[A-Za-z0-9_]+)){0,3})\s*(?:as\s+)?([A-Za-z_][A-Za-z0-9_]*)?",
        re.IGNORECASE,
    )

    for match in pattern.finditer(sql):
        relation = normalize_relation(match.group(1))
        alias = match.group(2)
        table_name = relation.split(".")[-1]
        aliases[alias or table_name] = relation

    return aliases


def select_clause(sql: str) -> str:
    match = re.search(r"\bselect\b(.*?)\bfrom\b", sql, re.IGNORECASE | re.DOTALL)
    return match.group(1) if match else ""


def split_select_items(select_sql: str) -> list[str]:
    items = []
    current = []
    depth = 0

    for char in select_sql:
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        elif char == "," and depth == 0:
            item = "".join(current).strip()
            if item:
                items.append(item)
            current = []
            continue

        current.append(char)

    final_item = "".join(current).strip()
    if final_item:
        items.append(final_item)

    return items


def output_column(select_item: str) -> str:
    alias_match = re.search(r"\s+as\s+([A-Za-z_][A-Za-z0-9_]*)\s*$", select_item, re.IGNORECASE)
    if alias_match:
        return alias_match.group(1)

    dotted_match = re.search(r"([A-Za-z_][A-Za-z0-9_]*)\.([A-Za-z_][A-Za-z0-9_]*)\s*$", select_item)
    if dotted_match:
        return dotted_match.group(2)

    bare_match = re.search(r"([A-Za-z_][A-Za-z0-9_]*)\s*$", select_item)
    return bare_match.group(1) if bare_match else select_item


def expression_without_alias(select_item: str) -> str:
    return re.sub(r"\s+as\s+[A-Za-z_][A-Za-z0-9_]*\s*$", "", select_item, flags=re.IGNORECASE).strip()


def source_columns(expression: str, aliases: dict[str, str]) -> list[dict[str, str]]:
    results = []

    for alias, column in re.findall(r"\b([A-Za-z_][A-Za-z0-9_]*)\.([A-Za-z_][A-Za-z0-9_]*)\b", expression):
        if alias in aliases:
            results.append({"relation": aliases[alias], "column": column})

    if results:
        return unique_sources(results)

    if len(aliases) == 1:
        relation = next(iter(aliases.values()))
        tokens = re.findall(r"\b[A-Za-z_][A-Za-z0-9_]*\b", expression)
        for token in tokens:
            if token.lower() not in SQL_KEYWORDS:
                results.append({"relation": relation, "column": token})

    return unique_sources(results)


def unique_sources(sources: list[dict[str, str]]) -> list[dict[str, str]]:
    seen = set()
    unique = []
    for source in sources:
        key = (source["relation"], source["column"])
        if key not in seen:
            seen.add(key)
            unique.append(source)
    return unique


def compiled_sql_path(node: dict) -> Path | None:
    compiled_path = node.get("compiled_path")
    if compiled_path:
        path = PROJECT_ROOT / compiled_path
        if path.exists():
            return path

    original_file_path = node.get("original_file_path")
    if original_file_path:
        path = COMPILED_ROOT / original_file_path
        if path.exists():
            return path

    return None


def target_relation(node: dict) -> str:
    config = node.get("config", {})
    database = config.get("database") or node.get("database")
    schema = config.get("schema") or node.get("schema")
    identifier = node.get("alias") or node.get("name")
    return ".".join(filter(None, [database, schema, identifier]))


def lineage_for_model(node: dict) -> list[dict[str, str]]:
    path = compiled_sql_path(node)
    if not path:
        return []

    sql = path.read_text(encoding="utf-8")
    aliases = relation_aliases(sql)
    rows = []

    for item in split_select_items(select_clause(sql)):
        target_column = output_column(item)
        expression = expression_without_alias(item)
        sources = source_columns(expression, aliases)
        lineage_type = "derived" if any(func in expression.lower() for func in ["cast(", "coalesce(", "sum(", "count(", "min(", "max(", " - "]) else "direct"

        if not sources:
            rows.append(
                {
                    "target_model": node["name"],
                    "target_relation": target_relation(node),
                    "target_column": target_column,
                    "source_relation": "",
                    "source_column": "",
                    "expression": expression,
                    "lineage_type": "constant_or_unknown",
                }
            )
            continue

        for source in sources:
            rows.append(
                {
                    "target_model": node["name"],
                    "target_relation": target_relation(node),
                    "target_column": target_column,
                    "source_relation": source["relation"],
                    "source_column": source["column"],
                    "expression": expression,
                    "lineage_type": lineage_type,
                }
            )

    return rows


def main() -> None:
    with MANIFEST_PATH.open(encoding="utf-8") as f:
        manifest = json.load(f)

    rows = []
    for node in manifest["nodes"].values():
        if node.get("resource_type") == "model":
            rows.extend(lineage_for_model(node))

    CSV_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with CSV_OUTPUT.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "target_model",
                "target_relation",
                "target_column",
                "source_relation",
                "source_column",
                "expression",
                "lineage_type",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    JSON_OUTPUT.write_text(json.dumps(rows, indent=2), encoding="utf-8")

    print(f"Wrote {len(rows)} column lineage rows")
    print(f"CSV: {CSV_OUTPUT}")
    print(f"JSON: {JSON_OUTPUT}")

    for row in rows:
        source = f"{row['source_relation']}.{row['source_column']}" if row["source_relation"] else "UNKNOWN"
        print(f"{source} -> {row['target_relation']}.{row['target_column']} [{row['lineage_type']}]")


if __name__ == "__main__":
    main()
