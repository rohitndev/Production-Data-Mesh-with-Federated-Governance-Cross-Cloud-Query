"""
Great Expectations-style data quality + SLA validation (simulated).

Reads each domain's quality_contract.yaml and checks the loaded data against it:
completeness (min rows), not-null, uniqueness, allowed values and non-negative
columns. Any failure is the local equivalent of a data-contract breach that
DE-03 would route to Slack.
"""
import os
import sqlite3
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WAREHOUSE = os.path.join(ROOT, "warehouse")

CONTRACTS = {
    "orders": (
        os.path.join(ROOT, "domain-orders", "quality_contract.yaml"),
        os.path.join(WAREHOUSE, "orders.db"), "orders"),
    "inventory": (
        os.path.join(ROOT, "domain-inventory", "quality_contract.yaml"),
        os.path.join(WAREHOUSE, "inventory.db"), "inventory"),
    "marketing": (
        os.path.join(ROOT, "domain-marketing", "quality_contract.yaml"),
        os.path.join(WAREHOUSE, "marketing.db"), "marketing"),
}


def _rows(db, table):
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    data = [dict(r) for r in conn.execute(f"SELECT * FROM {table}").fetchall()]
    conn.close()
    return data


def validate(name):
    """Run all expectations for one data product. Returns a result dict."""
    contract_path, db, table = CONTRACTS[name]
    with open(contract_path, "r", encoding="utf-8") as fh:
        sla = yaml.safe_load(fh)["sla"]

    rows = _rows(db, table)
    checks = []

    def add(check, passed, detail):
        checks.append({"check": check, "passed": passed, "detail": detail})

    # completeness
    add("min_rows", len(rows) >= sla.get("min_rows", 0),
        f"{len(rows)} rows (min {sla.get('min_rows', 0)})")

    # not null
    for col in sla.get("not_null_columns", []):
        nulls = sum(1 for r in rows if r.get(col) in (None, ""))
        add(f"not_null[{col}]", nulls == 0, f"{nulls} null values")

    # uniqueness
    for col in sla.get("unique_columns", []):
        vals = [r.get(col) for r in rows]
        add(f"unique[{col}]", len(vals) == len(set(vals)),
            f"{len(vals) - len(set(vals))} duplicates")

    # allowed values
    for col, allowed in sla.get("allowed_values", {}).items():
        bad = sorted({str(r.get(col)) for r in rows if r.get(col) not in allowed})
        add(f"allowed_values[{col}]", not bad, f"unexpected: {bad or 'none'}")

    # non-negative
    for col in sla.get("non_negative_columns", []):
        bad = sum(1 for r in rows if (r.get(col) or 0) < 0)
        add(f"non_negative[{col}]", bad == 0, f"{bad} negative values")

    passed = sum(1 for c in checks if c["passed"])
    return {
        "data_product": name,
        "checks_total": len(checks),
        "checks_passed": passed,
        "quality_score": round(100 * passed / len(checks), 1) if checks else 100.0,
        "contract_breached": passed != len(checks),
        "checks": checks,
    }


def validate_all():
    return [validate(name) for name in CONTRACTS]


if __name__ == "__main__":
    import json
    print(json.dumps(validate_all(), indent=2))
