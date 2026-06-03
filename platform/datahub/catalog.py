"""
DataHub-style federated catalog & governance (simulated).

Scans every domain's schema.yaml and builds a single control-plane view of all
data products across the 3 clouds: schemas, owners, lineage hints and
auto-discovered PII columns. This is the local stand-in for DataHub's federated
schema discovery + PII classification.
"""
import os
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DOMAINS = {
    "orders": os.path.join(ROOT, "domain-orders", "schema.yaml"),
    "inventory": os.path.join(ROOT, "domain-inventory", "schema.yaml"),
    "marketing": os.path.join(ROOT, "domain-marketing", "schema.yaml"),
}


def _load(path):
    with open(path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def list_products():
    """High-level catalog entry for every registered data product."""
    products = []
    for name, path in DOMAINS.items():
        meta = _load(path)
        products.append({
            "data_product": meta["data_product"],
            "domain": meta["domain"],
            "cloud": meta["cloud"],
            "owner": meta["owner"],
            "version": meta["version"],
            "description": meta["description"],
            "storage": meta["storage"],
            "columns": len(meta["columns"]),
        })
    return products


def get_product(name):
    """Full schema + column-level metadata for one data product."""
    if name not in DOMAINS:
        return None
    return _load(DOMAINS[name])


def pii_report():
    """Auto-discovered PII columns across all clouds (GDPR mapping)."""
    findings = []
    for name, path in DOMAINS.items():
        meta = _load(path)
        for col in meta["columns"]:
            if col.get("pii"):
                findings.append({
                    "data_product": meta["data_product"],
                    "cloud": meta["cloud"],
                    "column": col["name"],
                    "classification": "PII",
                    "description": col["description"],
                })
    return findings


def lineage():
    """Simple lineage graph: how the 3 products link together."""
    return {
        "nodes": [
            {"id": "orders.orders", "cloud": "AWS"},
            {"id": "inventory.inventory", "cloud": "Azure"},
            {"id": "marketing.marketing", "cloud": "GCP"},
        ],
        "edges": [
            {"from": "orders.orders", "to": "inventory.inventory",
             "on": "product_id", "type": "foreign_key"},
            {"from": "orders.orders", "to": "marketing.marketing",
             "on": "customer_id", "type": "foreign_key"},
        ],
    }


if __name__ == "__main__":
    import json
    print(json.dumps({"products": list_products(), "pii": pii_report()}, indent=2))
