# Databricks notebook source
# MAGIC %md
# MAGIC # Bootstrap environment
# MAGIC Idempotently creates the Unity Catalog objects used by the retail ETL pipeline
# MAGIC and seeds a small raw feed so the job can run end-to-end on Databricks Free Edition.
# MAGIC
# MAGIC Run once per environment (`qa`, `prod`).

# COMMAND ----------

dbutils.widgets.text("catalog", "qa", "Target catalog")
catalog = dbutils.widgets.get("catalog").strip()

if catalog not in ("qa", "prod"):
    raise ValueError(f"Unsupported catalog '{catalog}'. Expected 'qa' or 'prod'.")

print(f"Bootstrapping catalog: {catalog}")

# COMMAND ----------

spark.sql(f"CREATE CATALOG IF NOT EXISTS `{catalog}`")

for schema in ("landing", "bronze", "silver", "gold"):
    spark.sql(f"CREATE SCHEMA IF NOT EXISTS `{catalog}`.`{schema}`")

spark.sql(f"CREATE VOLUME IF NOT EXISTS `{catalog}`.`landing`.`raw`")

# COMMAND ----------

import csv
import os
import random
from datetime import datetime, timedelta

target_dir = f"/Volumes/{catalog}/landing/raw/orders"
os.makedirs(target_dir, exist_ok=True)
target_file = f"{target_dir}/orders_seed.csv"

random.seed(42)
countries = ["IN", "US", "UK", "DE", "AU"]
start = datetime(2026, 1, 1)

rows = []
for i in range(1, 501):
    rows.append(
        {
            "order_id": f"ORD-{i:05d}",
            "customer_id": f"CUST-{random.randint(1, 120):04d}",
            "product_id": f"SKU-{random.randint(1, 60):03d}",
            "country": random.choice(countries),
            "quantity": random.randint(1, 8),
            "unit_price": round(random.uniform(4.5, 250.0), 2),
            "order_ts": (start + timedelta(hours=i)).isoformat(sep=" "),
        }
    )

# Deliberate dirty records so the data quality gate has something to catch.
rows.append({**rows[0]})  # duplicate business key
rows.append({**rows[1], "order_id": "ORD-BAD-1", "customer_id": "", "quantity": 0, "unit_price": 0.0})

with open(target_file, "w", newline="", encoding="utf-8") as handle:
    writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)

print(f"Seeded {len(rows)} rows -> {target_file}")

# COMMAND ----------

display(spark.sql(f"SHOW SCHEMAS IN `{catalog}`"))
