"""
DE-03 Data Mesh — FastAPI backend (the single control plane).

Exposes every layer of the mesh over a REST API:

    Catalog / Governance (DataHub)  -> /catalog, /catalog/{p}, /governance/pii, /lineage
    Federation (Trino)              -> /federation/query, /federation/samples
    Data Product Portal (Backstage) -> /portal, /portal/samples, /portal/access
    Quality / SLA (GE + dbt)        -> /quality, /quality/{p}
    Monitoring (Grafana)            -> /monitoring/sla
    Identity (Keycloak)             -> X-API-Key header on /portal/access

Run:  uvicorn app.main:app --reload   (from the de03-data-mesh/ folder)
Docs: http://127.0.0.1:8000/docs
"""
import os
import sys

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

# --- wire up the platform modules (each lives in its own folder) ------------
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for sub in ["platform/datahub", "platform/trino", "platform/backstage",
            "platform/keycloak", "monitoring", "app"]:
    sys.path.insert(0, os.path.join(ROOT, sub))

import catalog        # noqa: E402  DataHub
import federation     # noqa: E402  Trino
import portal         # noqa: E402  Backstage
import quality        # noqa: E402  Great Expectations
import sla            # noqa: E402  Grafana
import auth           # noqa: E402  Keycloak

app = FastAPI(
    title="DE-03 · Production Data Mesh",
    description="Federated governance & cross-cloud query — local working prototype.",
    version="1.0.0",
)


# ---- request models --------------------------------------------------------
class QueryRequest(BaseModel):
    sql: str


class AccessRequest(BaseModel):
    data_product: str
    reason: str = "self-service analytics"


# ---- root ------------------------------------------------------------------
@app.get("/")
def root():
    return {
        "service": "DE-03 Data Mesh",
        "status": "up",
        "domains": ["orders (AWS)", "inventory (Azure)", "marketing (GCP)"],
        "docs": "/docs",
    }


@app.get("/health")
def health():
    return {"status": "healthy"}


# ---- Catalog & Governance (DataHub) ----------------------------------------
@app.get("/catalog")
def get_catalog():
    return {"data_products": catalog.list_products()}


@app.get("/catalog/{product}")
def get_catalog_product(product: str):
    meta = catalog.get_product(product)
    if not meta:
        raise HTTPException(404, f"data product '{product}' not found")
    return meta


@app.get("/governance/pii")
def get_pii():
    return {"pii_columns": catalog.pii_report()}


@app.get("/lineage")
def get_lineage():
    return catalog.lineage()


# ---- Federation (Trino) ----------------------------------------------------
@app.get("/federation/samples")
def federation_samples():
    return {"samples": portal.sample_queries()}


@app.post("/federation/query")
def federation_query(req: QueryRequest):
    try:
        return federation.run_query(req.sql)
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(400, str(exc))


# ---- Data Product Portal (Backstage) ---------------------------------------
@app.get("/portal")
def get_portal():
    return {"storefront": portal.storefront()}


@app.get("/portal/samples")
def portal_samples():
    return {"samples": portal.sample_queries()}


@app.post("/portal/access")
def portal_access(req: AccessRequest, x_api_key: str = Header(default="")):
    identity = auth.authenticate(x_api_key)
    if not identity:
        raise HTTPException(401, "Invalid or missing X-API-Key (try 'analyst-key').")
    return portal.request_access(identity["user"], req.data_product, req.reason)


@app.get("/portal/access")
def portal_access_log():
    return {"access_requests": portal.access_requests()}


# ---- Quality / SLA (Great Expectations + dbt) ------------------------------
@app.get("/quality")
def get_quality():
    return {"results": quality.validate_all()}


@app.get("/quality/{product}")
def get_quality_product(product: str):
    if product not in quality.CONTRACTS:
        raise HTTPException(404, f"data product '{product}' not found")
    return quality.validate(product)


# ---- Monitoring (Grafana) --------------------------------------------------
@app.get("/monitoring/sla")
def get_sla():
    return sla.dashboard()
