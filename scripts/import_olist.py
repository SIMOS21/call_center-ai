"""Import the genuine Olist historical orders, read-only, NOT Medusa live orders."""
from __future__ import annotations
import csv
import json
from pathlib import Path
from app.storage import conn

def import_orders(path=Path("data/raw/olist/olist_orders_dataset.csv")):
    if not path.exists():
        raise SystemExit("Download the ORIGINAL Olist Kaggle zip and extract csv files to data/raw/olist/")
    count = 0
    inserted = 0
    with conn() as cx, path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not {"order_id", "customer_id", "order_status", "order_purchase_timestamp"}.issubset(reader.fieldnames or []):
            raise ValueError("Olist columns missing")
        for row in reader:
            cursor = cx.execute("INSERT OR IGNORE INTO historical_olist_orders VALUES(?,?,?,?,?)",
                       (row["order_id"], row["customer_id"], row.get("order_status"),
                        row.get("order_purchase_timestamp"), row.get("order_delivered_customer_date")))
            count += 1
            inserted += cursor.rowcount
        persisted = cx.execute("SELECT COUNT(*) FROM historical_olist_orders").fetchone()[0]
    return {"source": "https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce", "role": "read_only_historical",
            "rows_read": count, "rows_inserted": inserted, "rows_persisted": persisted, "columns": reader.fieldnames}


if __name__ == "__main__":
    report = import_orders()
    Path("reports").mkdir(exist_ok=True)
    Path("reports/olist-import.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print("These records are NOT current customer orders; Medusa remains the transactional system.")
