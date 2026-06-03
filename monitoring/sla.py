"""
Grafana-style SLA dashboard feed (simulated).

Aggregates the per-domain quality results into the numbers a Grafana SLA
dashboard would show: quality score per domain, contract-breach count, and an
overall mesh health status.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "app"))

import quality  # noqa: E402


def dashboard():
    results = quality.validate_all()
    breaches = [r["data_product"] for r in results if r["contract_breached"]]
    avg_score = round(sum(r["quality_score"] for r in results) / len(results), 1)
    return {
        "mesh_health": "DEGRADED" if breaches else "HEALTHY",
        "average_quality_score": avg_score,
        "contract_breaches": breaches,
        "domains": [
            {
                "data_product": r["data_product"],
                "quality_score": r["quality_score"],
                "checks_passed": f'{r["checks_passed"]}/{r["checks_total"]}',
                "status": "BREACH" if r["contract_breached"] else "OK",
            }
            for r in results
        ],
    }


if __name__ == "__main__":
    import json
    print(json.dumps(dashboard(), indent=2))
