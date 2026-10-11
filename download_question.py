
import json
import requests

url = input("Paste the complete questionData URL: ").strip()

response = requests.get(url, timeout=30)
response.raise_for_status()

data = response.json()

with open("questionData.json", "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2)

print(json.dumps(data, indent=2))
print("\nSaved questionData.json")
