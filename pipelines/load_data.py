"""
Cross-domain data loader (Dagster-style pipeline, simulated).

Each domain is loaded into its OWN SQLite database file, simulating three
physically separate clouds:

    domain-orders     -> warehouse/orders.db      (AWS S3)
    domain-inventory  -> warehouse/inventory.db   (Azure ADLS Gen2)
    domain-marketing  -> warehouse/marketing.db   (GCP BigQuery)

Keeping them in separate files is the whole point of the prototype: the
federation engine (platform/trino) later queries ACROSS these files without
ever copying data between them ("zero data movement").

Run:  python pipelines/load_data.py
"""
import csv
import os
import sqlite3

# ---- Paths -----------------------------------------------------------------
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WAREHOUSE = os.path.join(ROOT, "warehouse")
os.makedirs(WAREHOUSE, exist_ok=True)

ORDERS_DB = os.path.join(WAREHOUSE, "orders.db")
INVENTORY_DB = os.path.join(WAREHOUSE, "inventory.db")
MARKETING_DB = os.path.join(WAREHOUSE, "marketing.db")

DATA_DIR = {
    "orders": os.path.join(ROOT, "domain-orders", "data", "orders.csv"),
    "inventory": os.path.join(ROOT, "domain-inventory", "data", "inventory.csv"),
    "marketing": os.path.join(ROOT, "domain-marketing", "data", "marketing.csv"),
}

# ---- Seed data (stand-ins for Olist / Instacart / GA4) ---------------------
ORDERS = [
    # order_id, customer_id, order_status, order_value, order_date, product_id
    ("O-1001", "C-01", "delivered", 259.90, "2026-06-01", "P-100"),
    ("O-1002", "C-02", "delivered", 89.00, "2026-06-01", "P-101"),
    ("O-1003", "C-03", "shipped", 410.50, "2026-06-02", "P-102"),
    ("O-1004", "C-01", "delivered", 35.25, "2026-06-02", "P-103"),
    ("O-1005", "C-04", "canceled", 120.00, "2026-06-02", "P-100"),
    ("O-1006", "C-05", "processing", 540.00, "2026-06-03", "P-104"),
    ("O-1007", "C-02", "delivered", 76.40, "2026-06-03", "P-101"),
    ("O-1008", "C-06", "delivered", 199.99, "2026-06-03", "P-105"),
    ("O-1009", "C-03", "shipped", 60.00, "2026-06-03", "P-102"),
    ("O-1010", "C-07", "delivered", 310.10, "2026-06-04", "P-104"),
]

INVENTORY = [
    # product_id, product_name, department, stock_qty, reorder_level
    ("P-100", "Organic Bananas", "produce", 120, 30),
    ("P-101", "Whole Milk 1L", "dairy", 8, 20),       # below reorder level
    ("P-102", "Sourdough Bread", "bakery", 45, 15),
    ("P-103", "Sparkling Water 6pk", "beverages", 200, 50),
    ("P-104", "Free Range Eggs", "dairy", 12, 25),    # below reorder level
    ("P-105", "Dark Chocolate Bar", "snacks", 300, 40),
]

MARKETING = [
    # event_id, customer_id, channel, campaign, spend, event_date
    ("E-9001", "C-01", "email", "winter_sale", 4.50, "2026-05-31"),
    ("E-9002", "C-02", "paid_search", "brand_terms", 12.00, "2026-05-31"),
    ("E-9003", "C-03", "social", "influencer_q2", 7.25, "2026-06-01"),
    ("E-9004", "C-04", "organic", "none", 0.00, "2026-06-01"),
    ("E-9005", "C-05", "paid_search", "competitor_terms", 18.40, "2026-06-02"),
    ("E-9006", "C-06", "email", "winter_sale", 3.10, "2026-06-02"),
    ("E-9007", "C-07", "social", "influencer_q2", 9.80, "2026-06-03"),
    ("E-9008", "C-01", "paid_search", "brand_terms", 11.00, "2026-06-03"),
]


def _write_csv(path, header, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(header)
        writer.writerows(rows)


def _load_table(db_path, ddl, insert_sql, rows):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    table = ddl.split("EXISTS")[1].split("(")[0].strip()
    cur.execute(f"DROP TABLE IF EXISTS {table}")
    cur.execute(ddl)
    cur.executemany(insert_sql, rows)
    conn.commit()
    conn.close()


def main():
    # Orders -> AWS (orders.db)
    _write_csv(DATA_DIR["orders"],
               ["order_id", "customer_id", "order_status", "order_value", "order_date", "product_id"],
               ORDERS)
    _load_table(
        ORDERS_DB,
        """CREATE TABLE IF NOT EXISTS orders (
               order_id TEXT PRIMARY KEY, customer_id TEXT, order_status TEXT,
               order_value REAL, order_date TEXT, product_id TEXT)""",
        "INSERT INTO orders VALUES (?,?,?,?,?,?)",
        ORDERS,
    )

    # Inventory -> Azure (inventory.db)
    _write_csv(DATA_DIR["inventory"],
               ["product_id", "product_name", "department", "stock_qty", "reorder_level"],
               INVENTORY)
    _load_table(
        INVENTORY_DB,
        """CREATE TABLE IF NOT EXISTS inventory (
               product_id TEXT PRIMARY KEY, product_name TEXT, department TEXT,
               stock_qty INTEGER, reorder_level INTEGER)""",
        "INSERT INTO inventory VALUES (?,?,?,?,?)",
        INVENTORY,
    )

    # Marketing -> GCP (marketing.db)
    _write_csv(DATA_DIR["marketing"],
               ["event_id", "customer_id", "channel", "campaign", "spend", "event_date"],
               MARKETING)
    _load_table(
        MARKETING_DB,
        """CREATE TABLE IF NOT EXISTS marketing (
               event_id TEXT PRIMARY KEY, customer_id TEXT, channel TEXT,
               campaign TEXT, spend REAL, event_date TEXT)""",
        "INSERT INTO marketing VALUES (?,?,?,?,?,?)",
        MARKETING,
    )

    print("[pipeline] Loaded 3 domain data products into separate cloud stores:")
    print(f"   AWS   (Orders)    -> {ORDERS_DB}     ({len(ORDERS)} rows)")
    print(f"   Azure (Inventory) -> {INVENTORY_DB}  ({len(INVENTORY)} rows)")
    print(f"   GCP   (Marketing) -> {MARKETING_DB}  ({len(MARKETING)} rows)")


if __name__ == "__main__":
    main()
