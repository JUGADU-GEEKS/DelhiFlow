import requests
import json

# Test coordinates from the error
lat = 28.514714
lon = 77.309542

url = "http://127.0.0.1:8000/predict_ward"

payload = {
    "latitude": lat,
    "longitude": lon,
    "aggregation_method": "mean"
}

print(f"Testing ward prediction for: {lat}, {lon}")
print(f"URL: {url}")
print(f"Payload: {json.dumps(payload, indent=2)}")
print("\nMaking request...")

try:
    response = requests.post(url, json=payload)
    print(f"\nStatus Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
except Exception as e:
    print(f"\nError: {e}")
    if hasattr(response, 'text'):
        print(f"Response text: {response.text}")
