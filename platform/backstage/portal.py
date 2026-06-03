"""
Backstage-style Data Product Portal (simulated).

The self-service layer: analysts discover data products, view their SLA / owner,
grab a ready-made federated sample query, and request access. Access requests
are auto-approved (as in the PDF's "automated approval") and kept in memory.
"""
import sys
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "platform", "datahub"))
sys.path.insert(0, os.path.join(ROOT, "platform", "trino"))

import catalog          # noqa: E402
import federation       # noqa: E402

# In-memory access request log (resets on restart).
_ACCESS_REQUESTS = []


def storefront():
    """Catalog cards an analyst sees when opening the portal."""
    cards = []
    for p in catalog.list_products():
        cards.append({
            "data_product": p["data_product"],
            "domain": p["domain"],
            "cloud": p["cloud"],
            "owner": p["owner"],
            "description": p["description"],
            "access": "request-required",
        })
    return cards


def sample_queries():
    """Curated cross-cloud queries an analyst can run with one click."""
    return [
        {"id": key, "description": desc, "sql": sql.strip()}
        for key, (desc, sql) in federation.SAMPLE_QUERIES.items()
    ]


def request_access(analyst, data_product, reason="self-service analytics"):
    """Auto-approved access request (time-to-data: seconds, not weeks)."""
    if data_product not in [p["data_product"] for p in catalog.list_products()]:
        return {"status": "rejected", "reason": f"unknown data product '{data_product}'"}
    ticket = {
        "ticket_id": f"REQ-{len(_ACCESS_REQUESTS) + 1:04d}",
        "analyst": analyst,
        "data_product": data_product,
        "reason": reason,
        "status": "approved",
        "approval": "auto",
    }
    _ACCESS_REQUESTS.append(ticket)
    return ticket


def access_requests():
    return _ACCESS_REQUESTS
