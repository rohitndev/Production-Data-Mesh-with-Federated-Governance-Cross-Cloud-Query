"""
Trino-style cross-cloud query federation (simulated with SQLite ATTACH).

Real DE-03 uses Trino connectors to query AWS S3, Azure ADLS and GCP BigQuery
in a single SQL statement WITHOUT moving data between clouds. We reproduce that
behaviour locally: each domain lives in its own SQLite file, and we ATTACH all
three into one in-memory connection so a single SELECT can JOIN across them.

The data never leaves its own file ("cloud") — exactly the zero-data-movement
guarantee Trino provides.
"""
import os
import sqlite3

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
WAREHOUSE = os.path.join(ROOT, "warehouse")

# catalog name -> (cloud, db file)  — mirrors a Trino catalog/connector
CATALOGS = {
    "orders": ("AWS",   os.path.join(WAREHOUSE, "orders.db")),
    "inventory": ("Azure", os.path.join(WAREHOUSE, "inventory.db")),
    "marketing": ("GCP",   os.path.join(WAREHOUSE, "marketing.db")),
}

# Only SELECT queries are allowed through the federation layer (read-only).
_FORBIDDEN = ("insert", "update", "delete", "drop", "alter", "create", "attach", "pragma")


def _federated_connection():
    """Return a connection with all three 'cloud' databases attached."""
    missing = [db for _, db in CATALOGS.values() if not os.path.exists(db)]
    if missing:
        raise FileNotFoundError(
            "Warehouse not built. Run: python pipelines/load_data.py first."
        )
    conn = sqlite3.connect(":memory:")
    for catalog, (_cloud, db) in CATALOGS.items():
        conn.execute("ATTACH DATABASE ? AS " + catalog, (db,))
    conn.row_factory = sqlite3.Row
    return conn


def run_query(sql: str):
    """Execute a read-only federated SQL query across the 3 clouds."""
    lowered = sql.strip().lower()
    if not lowered.startswith("select") and not lowered.startswith("with"):
        raise ValueError("Only SELECT queries are allowed (read-only federation).")
    if any(word in lowered.split() for word in _FORBIDDEN):
        raise ValueError("Write/DDL statements are not permitted.")

    conn = _federated_connection()
    try:
        cur = conn.execute(sql)
        rows = [dict(r) for r in cur.fetchall()]
        columns = [d[0] for d in cur.description] if cur.description else []
        return {"columns": columns, "rows": rows, "row_count": len(rows)}
    finally:
        conn.close()


# A few ready-made federated queries used by the portal "sample query" feature.
SAMPLE_QUERIES = {
    "revenue_by_channel": (
        "Marketing spend vs. order revenue per channel (AWS x GCP)",
        """
        SELECT m.channel,
               ROUND(SUM(m.spend), 2)        AS marketing_spend,
               ROUND(SUM(o.order_value), 2)  AS order_revenue
        FROM marketing.marketing m
        JOIN orders.orders o ON o.customer_id = m.customer_id
        WHERE o.order_status = 'delivered'
        GROUP BY m.channel
        ORDER BY order_revenue DESC
        """,
    ),
    "low_stock_orders": (
        "Delivered orders for products that are below reorder level (AWS x Azure)",
        """
        SELECT o.order_id, i.product_name, i.stock_qty, i.reorder_level
        FROM orders.orders o
        JOIN inventory.inventory i ON i.product_id = o.product_id
        WHERE o.order_status = 'delivered'
          AND i.stock_qty < i.reorder_level
        ORDER BY i.stock_qty ASC
        """,
    ),
    "customer_360": (
        "Cross-cloud customer 360: orders + acquisition channel (AWS x Azure x GCP)",
        """
        SELECT o.customer_id,
               COUNT(DISTINCT o.order_id)    AS orders,
               ROUND(SUM(o.order_value), 2)  AS lifetime_value,
               GROUP_CONCAT(DISTINCT i.department) AS departments,
               GROUP_CONCAT(DISTINCT m.channel)    AS channels
        FROM orders.orders o
        JOIN inventory.inventory i ON i.product_id = o.product_id
        LEFT JOIN marketing.marketing m ON m.customer_id = o.customer_id
        GROUP BY o.customer_id
        ORDER BY lifetime_value DESC
        """,
    ),
}


if __name__ == "__main__":
    for key, (desc, sql) in SAMPLE_QUERIES.items():
        print(f"\n=== {key}: {desc} ===")
        out = run_query(sql)
        print(" | ".join(out["columns"]))
        for row in out["rows"]:
            print(" | ".join(str(row[c]) for c in out["columns"]))
