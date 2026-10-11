
import json
from pathlib import Path

import requests

with open("questionData.json", encoding="utf-8") as f:
    data = json.load(f)

print("Service:", data.get("service"))
print("\nBusiness rules:")
for note in data.get("notes", []):
    print("-", note)

links = data["links"]

for name in ("orders", "rates", "export"):
    if name not in links:
        print(f"Skipping missing link: {name}")
        continue

    print(f"\nDownloading {name}...")
    response = requests.get(links[name], timeout=60)
    response.raise_for_status()

    Path(f"{name}.json").write_text(
        response.text, encoding="utf-8"
    )

    print("HTTP:", response.status_code)
    print("Bytes:", len(response.content))
    print("Saved:", f"{name}.json")
