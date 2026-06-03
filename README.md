# DE-03 · Production Data Mesh with Federated Governance & Cross-Cloud Query

> A simple, fully-runnable backend prototype of a **Data Mesh**: three domain-owned
> data products (Orders, Inventory, Marketing) living in three separate stores,
> queried together through a single federated SQL engine — **with no data movement**.

---

## Project Overview

Large enterprises keep data in silos — Orders on AWS, Inventory on Azure, Marketing
on GCP. Answering one cross-domain question normally means building brittle, slow ETL
pipelines that copy data between clouds. A **Data Mesh** flips this: each team *owns*
its data as a product (with a schema contract, quality contract and an owner), and a
**federation layer** lets anyone query across all of them in one SQL statement without
copying anything.

This project is a college-level **working prototype** of that idea. It keeps the exact
architecture of the enterprise design but runs entirely on your laptop with Python +
SQLite — no cloud accounts required:

| Enterprise design | This prototype |
|---|---|
| AWS S3 / Azure ADLS / GCP BigQuery | 3 separate SQLite databases (`orders.db`, `inventory.db`, `marketing.db`) |
| Trino cross-cloud federation | SQLite `ATTACH DATABASE` (real cross-store JOINs, zero data movement) |
| DataHub catalog + PII governance | `catalog.py` (scans schema contracts, auto-tags PII) |
| Backstage data product portal | `portal.py` (discover products, request access) |
| dbt contracts + Great Expectations | `quality.py` (validates SLA / quality rules) |
| Grafana SLA dashboard | `sla.py` (quality scores + mesh health) |
| Keycloak IAM | `auth.py` (API-key identity check) |

The whole thing is exposed as a **FastAPI** backend (no frontend needed) with interactive
docs at `/docs`.

---

## Table of Contents

- [Project Overview](#project-overview)
1. [**Prerequisites**](#1-prerequisites)
2. [**Steps to Run This Project**](#2-steps-to-run-this-project)
   - [2.1 Install dependencies](#21-install-dependencies)
   - [2.2 Build the warehouse (load the 3 data products)](#22-build-the-warehouse-load-the-3-data-products)
   - [2.3 Start the backend API](#23-start-the-backend-api)
   - [2.4 Try it out](#24-try-it-out)
3. [**Architecture**](#3-architecture)
   - [3.1 Architecture Diagram](#31-architecture-diagram)
   - [3.2 Data Flow](#32-data-flow)
   - [3.3 Project Structure](#33-project-structure)
4. [**The Data Mesh, Layer by Layer**](#4-the-data-mesh-layer-by-layer)
   - [4.1 Domain Data Products (the 3 "clouds")](#41-domain-data-products-the-3-clouds)
   - [4.2 Trino Federation (cross-cloud query)](#42-trino-federation-cross-cloud-query)
   - [4.3 DataHub Catalog & Governance](#43-datahub-catalog--governance)
   - [4.4 Backstage Data Product Portal](#44-backstage-data-product-portal)
   - [4.5 Quality & SLA Contracts](#45-quality--sla-contracts)
   - [4.6 Monitoring (Grafana-style)](#46-monitoring-grafana-style)
   - [4.7 Identity (Keycloak-style)](#47-identity-keycloak-style)
5. [**API Reference**](#5-api-reference)
6. [**Kaggle Notebook**](#6-kaggle-notebook)

---

## 1. Prerequisites

- **Python 3.10+** (tested on 3.12)
- **pip** (comes with Python)
- That's it — SQLite ships with Python, and no cloud accounts are needed.

Python packages (installed in the next step): `fastapi`, `uvicorn`, `pydantic`, `PyYAML`.

---

## 2. Steps to Run This Project

All commands are run from the `de03-data-mesh/` folder.

### 2.1 Install dependencies

```bash
pip install -r requirements.txt
```

### 2.2 Build the warehouse (load the 3 data products)

This loads each domain into its **own** database file, simulating three separate clouds:

```bash
python pipelines/load_data.py
```

```text
[pipeline] Loaded 3 domain data products into separate cloud stores:
   AWS   (Orders)    -> warehouse/orders.db      (10 rows)
   Azure (Inventory) -> warehouse/inventory.db   (6 rows)
   GCP   (Marketing) -> warehouse/marketing.db   (8 rows)
```

### 2.3 Start the backend API

```bash
uvicorn app.main:app --reload
```

```text
INFO:     Will watch for changes in these directories: ['/de03-data-mesh']
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Started reloader process [12480] using StatReload
INFO:     Started server process [9032]
INFO:     Application startup complete.
```

Then open the interactive API docs in your browser:

```text
http://127.0.0.1:8000/docs
```

A quick health check confirms the control plane is up:

```bash
curl http://127.0.0.1:8000/
```

```json
{
  "service": "DE-03 Data Mesh",
  "status": "up",
  "domains": ["orders (AWS)", "inventory (Azure)", "marketing (GCP)"],
  "docs": "/docs"
}
```

### 2.4 Try it out

Run a **single federated query that joins all three clouds** at once:

```bash
curl -X POST http://127.0.0.1:8000/federation/query \
  -H "Content-Type: application/json" \
  -d '{"sql":"SELECT o.customer_id, COUNT(o.order_id) AS orders, m.channel FROM orders.orders o JOIN marketing.marketing m ON m.customer_id=o.customer_id GROUP BY o.customer_id"}'
```

```json
{
  "columns": ["customer_id", "orders", "channel"],
  "rows": [
    {"customer_id": "C-01", "orders": 2, "channel": "email"},
    {"customer_id": "C-02", "orders": 2, "channel": "paid_search"},
    {"customer_id": "C-03", "orders": 2, "channel": "social"}
  ],
  "row_count": 3
}
```

---

## 3. Architecture

### 3.1 Architecture Diagram

```text
 ┌─────────────────────────────────────────────────────────────────────┐
 │                        DE-03 DATA MESH                                │
 └─────────────────────────────────────────────────────────────────────┘

   ┌────────────┐        ┌────────────┐        ┌────────────┐
   │  DOMAIN 1  │        │  DOMAIN 2  │        │  DOMAIN 3  │
   │   Orders   │        │ Inventory  │        │ Marketing  │
   │  AWS  S3   │        │ Azure ADLS │        │ GCP BigQry │
   │ orders.db  │        │inventory.db│        │marketing.db│
   └─────┬──────┘        └─────┬──────┘        └─────┬──────┘
         │                     │                     │
         └─────────────────────┼─────────────────────┘
                               │   (no data movement)
                       ┌───────▼────────┐
                       │     TRINO      │   federation.py
                       │  Cross-Cloud   │   (SQLite ATTACH)
                       │   Federation   │
                       └───────┬────────┘
                               │
        ┌──────────────────────┼──────────────────────┐
        │                      │                       │
 ┌──────▼──────┐       ┌───────▼───────┐       ┌───────▼───────┐
 │   DataHub   │       │   Backstage   │       │    Grafana    │
 │  Catalog +  │       │ Data Product  │       │  SLA / Health │
 │ PII + Lineage│      │    Portal     │       │   Dashboard   │
 └─────────────┘       └───────────────┘       └───────────────┘
        catalog.py          portal.py               sla.py
                               │
                       ┌───────▼────────┐
                       │  FastAPI app   │  app/main.py  (single control plane)
                       │   REST + /docs │  + Keycloak auth.py
                       └────────────────┘
```

### 3.2 Data Flow

1. Each domain team publishes a **data product**: data + `schema.yaml` (contract) + `quality_contract.yaml` (SLA).
2. The pipeline loads each product into its **own** store — Orders→AWS, Inventory→Azure, Marketing→GCP.
3. **Trino** attaches all three stores and runs federated SQL JOINs — the data never leaves its store.
4. **DataHub** scans the schemas to build one catalog, auto-discovers PII columns, and exposes lineage.
5. **Backstage** lets an analyst browse products and request access (auto-approved in seconds).
6. **Great Expectations + dbt** validate each product against its quality/SLA contract.
7. **Grafana** rolls the quality results into a mesh-health dashboard; **Keycloak** gates access requests.

### 3.3 Project Structure

```text
de03-data-mesh/
├── domain-orders/         # Data product 1 — Orders (AWS)
│   ├── data/orders.csv
│   ├── schema.yaml            # data contract (columns, PII flags, owner)
│   └── quality_contract.yaml  # SLA: freshness, not-null, allowed values
├── domain-inventory/      # Data product 2 — Inventory (Azure)
│   ├── data/inventory.csv
│   ├── schema.yaml
│   └── quality_contract.yaml
├── domain-marketing/      # Data product 3 — Marketing (GCP)
│   ├── data/marketing.csv
│   ├── schema.yaml
│   └── quality_contract.yaml
├── platform/
│   ├── trino/federation.py    # cross-cloud query engine (ATTACH)
│   ├── datahub/catalog.py     # catalog, PII discovery, lineage
│   ├── backstage/portal.py    # self-service data product portal
│   └── keycloak/auth.py       # API-key identity
├── pipelines/load_data.py     # builds the 3 separate "cloud" databases
├── monitoring/sla.py          # Grafana-style SLA dashboard feed
├── app/
│   ├── main.py                # FastAPI backend (all endpoints)
│   └── quality.py             # Great Expectations-style validation
├── warehouse/                 # generated SQLite DBs (the 3 clouds)
├── docs/runbook.md            # domain-team runbook + Trino SQL guide
├── requirements.txt
└── README.md
```

---

## 4. The Data Mesh, Layer by Layer

A brief, point-by-point explanation of each section above:

### 4.1 Domain Data Products (the 3 "clouds")
- Three independent domains, each **owning** its own data, schema and SLA.
- Stored in **separate** databases so they behave like physically separate clouds.
- `GET /catalog` lists every product with its owner, cloud and description.

```json
[
  {"data_product": "orders",    "domain": "Orders",    "cloud": "AWS",   "owner": "orders-team@company.com"},
  {"data_product": "inventory", "domain": "Inventory", "cloud": "Azure", "owner": "inventory-team@company.com"},
  {"data_product": "marketing", "domain": "Marketing", "cloud": "GCP",   "owner": "marketing-team@company.com"}
]
```

### 4.2 Trino Federation (cross-cloud query)
- A single SQL `SELECT` can JOIN `orders`, `inventory` and `marketing` together.
- Implemented with SQLite `ATTACH DATABASE`, so **no data is copied** between stores.
- Read-only by design — write/DDL statements are rejected.
- `POST /federation/query` runs any SELECT; `GET /federation/samples` returns ready-made queries.

Revenue vs. marketing spend per channel, joining Orders (AWS) with Marketing (GCP) in one query:

```json
{
  "columns": ["channel", "marketing_spend", "order_revenue"],
  "rows": [
    {"channel": "email",       "marketing_spend": 12.1, "order_revenue": 495.14},
    {"channel": "paid_search", "marketing_spend": 46.0, "order_revenue": 460.55},
    {"channel": "social",      "marketing_spend": 9.8,  "order_revenue": 310.1}
  ],
  "row_count": 3
}
```

### 4.3 DataHub Catalog & Governance
- Auto-scans all three `schema.yaml` contracts into one control plane.
- **Auto-discovers PII** columns for GDPR mapping (`GET /governance/pii`).
- Publishes a lineage graph showing how the products link (`GET /lineage`).

```json
{
  "pii_columns": [
    {"data_product": "orders",    "cloud": "AWS", "column": "customer_id", "classification": "PII"},
    {"data_product": "marketing", "cloud": "GCP", "column": "customer_id", "classification": "PII"}
  ]
}
```

The lineage graph shows how the three products link across clouds (`GET /lineage`):

```json
{
  "nodes": [
    {"id": "orders.orders",       "cloud": "AWS"},
    {"id": "inventory.inventory", "cloud": "Azure"},
    {"id": "marketing.marketing", "cloud": "GCP"}
  ],
  "edges": [
    {"from": "orders.orders", "to": "inventory.inventory", "on": "product_id",  "type": "foreign_key"},
    {"from": "orders.orders", "to": "marketing.marketing", "on": "customer_id", "type": "foreign_key"}
  ]
}
```

### 4.4 Backstage Data Product Portal
- A "storefront" where analysts discover products and one-click sample queries.
- **Self-service access**: `POST /portal/access` returns an auto-approved ticket in seconds — the prototype version of the "6 weeks → 5 minutes" goal.

The storefront an analyst sees (`GET /portal`):

```json
{
  "storefront": [
    {"data_product": "orders",    "domain": "Orders",    "cloud": "AWS",   "owner": "orders-team@company.com",    "access": "request-required"},
    {"data_product": "inventory", "domain": "Inventory", "cloud": "Azure", "owner": "inventory-team@company.com", "access": "request-required"},
    {"data_product": "marketing", "domain": "Marketing", "cloud": "GCP",   "owner": "marketing-team@company.com", "access": "request-required"}
  ]
}
```

Requesting access returns an auto-approved ticket (`POST /portal/access`):

```json
{"ticket_id": "REQ-0001", "analyst": "ana.analyst@company.com",
 "data_product": "orders", "status": "approved", "approval": "auto"}
```

### 4.5 Quality & SLA Contracts
- Each product is validated against its `quality_contract.yaml`: completeness, not-null,
  uniqueness, allowed values, non-negative checks.
- A failing check is a **contract breach** (the trigger for a Slack alert in the real system).
- `GET /quality` validates all products; `GET /quality/{product}` validates one.

A full validation report for the Orders product, with every expectation broken out (`GET /quality/orders`):

```json
{
  "data_product": "orders",
  "checks_total": 6,
  "checks_passed": 6,
  "quality_score": 100.0,
  "contract_breached": false,
  "checks": [
    {"check": "min_rows",                    "passed": true, "detail": "10 rows (min 5)"},
    {"check": "not_null[order_id]",          "passed": true, "detail": "0 null values"},
    {"check": "not_null[customer_id]",       "passed": true, "detail": "0 null values"},
    {"check": "not_null[order_status]",      "passed": true, "detail": "0 null values"},
    {"check": "unique[order_id]",            "passed": true, "detail": "0 duplicates"},
    {"check": "allowed_values[order_status]","passed": true, "detail": "unexpected: none"}
  ]
}
```

### 4.6 Monitoring (Grafana-style)
- Rolls all quality results into a single **mesh health** view.
- `GET /monitoring/sla` returns per-domain scores and overall status.

```json
{
  "mesh_health": "HEALTHY",
  "average_quality_score": 100.0,
  "contract_breaches": [],
  "domains": [
    {"data_product": "orders",    "quality_score": 100.0, "checks_passed": "6/6", "status": "OK"},
    {"data_product": "inventory", "quality_score": 100.0, "checks_passed": "7/7", "status": "OK"},
    {"data_product": "marketing", "quality_score": 100.0, "checks_passed": "6/6", "status": "OK"}
  ]
}
```

### 4.7 Identity (Keycloak-style)
- Access requests require an `X-API-Key` header (demo keys: `analyst-key`, `admin-key`).
- Stands in for cross-cloud SSO + Trino ACLs — the governance/IAM layer of the mesh.

---

## 5. API Reference

| Method | Endpoint | Layer | Purpose |
|---|---|---|---|
| `GET`  | `/` , `/health` | — | Service status |
| `GET`  | `/catalog` | DataHub | List all data products |
| `GET`  | `/catalog/{product}` | DataHub | Full schema of one product |
| `GET`  | `/governance/pii` | DataHub | Auto-discovered PII columns |
| `GET`  | `/lineage` | DataHub | Cross-cloud lineage graph |
| `GET`  | `/federation/samples` | Trino | Ready-made federated queries |
| `POST` | `/federation/query` | Trino | Run a federated SELECT |
| `GET`  | `/portal` | Backstage | Data product storefront |
| `POST` | `/portal/access` | Backstage | Request access (needs `X-API-Key`) |
| `GET`  | `/portal/access` | Backstage | Access request log |
| `GET`  | `/quality` | Great Expectations | Validate all products |
| `GET`  | `/quality/{product}` | Great Expectations | Validate one product |
| `GET`  | `/monitoring/sla` | Grafana | Mesh health dashboard |

Example — the full schema contract returned by `GET /catalog/orders`:

```json
{
  "data_product": "orders",
  "domain": "Orders",
  "cloud": "AWS",
  "storage": "s3://de03-orders/olist/  (simulated -> warehouse/orders.db)",
  "owner": "orders-team@company.com",
  "version": "1.0.0",
  "table": "orders",
  "columns": [
    {"name": "order_id",     "type": "TEXT", "pii": false, "description": "Unique order identifier (primary key)."},
    {"name": "customer_id",  "type": "TEXT", "pii": true,  "description": "Customer identifier."},
    {"name": "order_status", "type": "TEXT", "pii": false, "description": "delivered / shipped / canceled / processing."},
    {"name": "order_value",  "type": "REAL", "pii": false, "description": "Total order amount in BRL."},
    {"name": "order_date",   "type": "TEXT", "pii": false, "description": "Order purchase timestamp (ISO date)."},
    {"name": "product_id",   "type": "TEXT", "pii": false, "description": "Foreign key to inventory.product_id."}
  ]
}
```

---

## 6. Kaggle Notebook

A polished, presentation-ready notebook lives in `../kaggle/`:

```text
kaggle/data_mesh_in_practice.ipynb
```

**"Data Mesh in Practice: Cross-Cloud Analytics Without ETL"** walks through the same
three domains (Olist Orders, Instacart Inventory, GA4 Marketing), builds the federated
warehouse, runs cross-cloud queries, and visualizes the quality/SLA scorecard — a
standalone, professional companion to this backend.

---

### Tech Stack
`Python` · `FastAPI` · `SQLite (ATTACH federation)` · `Pydantic` · `PyYAML` · `Uvicorn`

### Topics
`data-mesh` · `trino` · `datahub` · `backstage` · `multi-cloud` · `data-governance` · `federated-query`
