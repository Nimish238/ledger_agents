
import json
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")

with open("all_orders.json", encoding="utf-8") as f:
    raw = json.load(f)

def parse_time(value):
    return datetime.fromisoformat(
        value.replace("Z", "+00:00")
    ).astimezone(IST)

# Keep the latest version of each order.
latest = {}

for order in raw:
    order_id = order["id"]

    if (
        order_id not in latest
        or parse_time(order["updated_at"])
        > parse_time(latest[order_id]["updated_at"])
    ):
        latest[order_id] = order

orders = list(latest.values())

# Inspect the actual customer field in your data.
print("Order fields:", list(orders[0].keys()))

toaster_paid = [
    order for order in orders
    if str(order.get("product", "")).strip().lower() == "toaster"
    and str(order.get("status", "")).strip().lower() == "paid"
]

print("Latest unique orders:", len(orders))
print("Paid Toaster orders:", len(toaster_paid))

# Identify the customer field from the actual schema.
customer_field = next(
    (
        field for field in ("customer_id", "customer", "customerId")
        if field in orders[0]
    ),
    None,
)

if customer_field is None:
    print("Customer field not found. Inspect the order fields above.")
else:
    customers = {
        order[customer_field]
        for order in toaster_paid
        if order.get(customer_field) is not None
    }

    print("Customer field:", customer_field)
    print("Distinct customers:", len(customers))
