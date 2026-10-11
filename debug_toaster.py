
import app

question = "How many different customers placed at least one paid order for a Toaster?"

rows = app.filter_orders(question)

print("App data rows:", len(app.ORDERS))
print("Filtered Toaster rows:", len(rows))
print("Paid Toaster rows:", sum(r["status"].lower() == "paid" for r in rows))

paid = [r for r in rows if r["status"].lower() == "paid"]
print("Distinct paid Toaster customers:", len({r["customer"] for r in paid}))

print("\nStatus breakdown:")
from collections import Counter
print(Counter(r["status"] for r in rows))

print("\nProduct breakdown:")
print(Counter(r["product"] for r in app.ORDERS))
