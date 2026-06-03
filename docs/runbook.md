# Domain Team Runbook & Trino SQL Guide

## How to add / update a data product

1. Create a folder `domain-<name>/` with:
   - `data/<name>.csv` — the data
   - `schema.yaml` — columns, types, `pii: true/false`, owner
   - `quality_contract.yaml` — the SLA / quality expectations
2. Register it in `pipelines/load_data.py` (add seed rows + a `_load_table` call)
   and in `platform/datahub/catalog.py`, `app/quality.py` and
   `platform/trino/federation.py` (`CATALOGS`).
3. Re-run `python pipelines/load_data.py`.

## Trino (federation) SQL guide

Every domain is a catalog. Reference tables as `catalog.table`:

| Catalog | Table | Cloud |
|---|---|---|
| `orders` | `orders.orders` | AWS |
| `inventory` | `inventory.inventory` | Azure |
| `marketing` | `marketing.marketing` | GCP |

Example — revenue by acquisition channel (AWS × GCP):

```sql
SELECT m.channel,
       ROUND(SUM(o.order_value), 2) AS revenue
FROM marketing.marketing m
JOIN orders.orders o ON o.customer_id = m.customer_id
WHERE o.order_status = 'delivered'
GROUP BY m.channel
ORDER BY revenue DESC;
```

Rules:
- **SELECT only.** Writes/DDL are rejected by the federation layer.
- Joins across catalogs are allowed and never move data between stores.

## What to do on a contract breach

- `GET /monitoring/sla` shows `mesh_health: DEGRADED` and lists the breached product.
- `GET /quality/<product>` shows exactly which check failed.
- In production this fires a Slack alert to the domain's `alert_channel`.
