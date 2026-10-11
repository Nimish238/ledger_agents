
import json
from pathlib import Path

import requests

with open("questionData.json", encoding="utf-8") as f:
    data = json.load(f)

url = data["links"]["orders"]
all_orders = []
seen_pages = set()
page = 1

with requests.Session() as session:
    while url:
        if url in seen_pages:
            print("Repeated pagination URL detected. Stopping to avoid an infinite loop.")
            break

        seen_pages.add(url)
        print(f"\nDownloading page {page}...")

        response = session.get(url, timeout=30)
        response.raise_for_status()
        page_data = response.json()

        orders = page_data.get("orders", [])
        all_orders.extend(orders)

        next_url = page_data.get("next")

        print(f"Records received: {len(orders)}")
        print(f"Total records so far: {len(all_orders)}")
        print(f"Next page available: {bool(next_url)}")

        url = next_url
        page += 1

Path("all_orders.json").write_text(
    json.dumps(all_orders, ensure_ascii=False),
    encoding="utf-8",
)

print(f"\nTotal downloaded records: {len(all_orders)}")
print(f"Unique order IDs: {len({r['id'] for r in all_orders})}")
print("Saved all_orders.json")
