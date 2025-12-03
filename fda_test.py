import requests
import json

# Replace with your API key if you have one
api_key = None  # Or 'your_key_here'

base_url = "https://api.fda.gov/drug/ndc.json"
params = {
    "search": 'openfda.indications_and_usage:"BRAF V600E" AND "NSCLC"',
    "limit": 10
}
if api_key:
    params["api_key"] = api_key

response = requests.get(base_url, params=params)
data = response.json()

if "results" in data:
    for drug in data["results"]:
        brand = drug["openfda"]["brand_name"][0] if "brand_name" in drug["openfda"] else "N/A"
        generic = drug["openfda"]["generic_name"][0] if "generic_name" in drug["openfda"] else "N/A"
        indications = drug["openfda"]["indications_and_usage"][0] if "indications_and_usage" in drug["openfda"] else "N/A"
        print(f"Brand: {brand}\nGeneric: {generic}\nIndications: {indications[:200]}...\n---")
else:
    print("No results found or error:", data.get("error", "Unknown"))