import sys
import os
import requests
import argparse

# Allow importing from the root app folder
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from app.pos import load_and_normalize_pos

def upload_pos(api_url: str, csv_path: str):
    if not os.path.exists(csv_path):
        print(f"CSV file not found at: {csv_path}")
        return
        
    print(f"Reading and normalizing transactions from {csv_path}...")
    txns = load_and_normalize_pos(csv_path)
    if not txns:
        print("No transactions found or parsed.")
        return
        
    print(f"Parsed {len(txns)} transactions. Uploading to {api_url}/transactions/ingest...")
    
    try:
        response = requests.post(
            f"{api_url}/transactions/ingest",
            json=txns,
            headers={"Content-Type": "application/json"},
            timeout=15.0
        )
        if response.status_code == 200:
            print(f"Upload successful: {response.json()}")
        else:
            print(f"Upload failed with status code {response.status_code}: {response.text}")
    except Exception as e:
        print(f"Error during upload: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Upload POS transactions to the Store Intelligence API.")
    parser.add_argument("--url", default="http://localhost:8000", help="API base URL")
    parser.add_argument("--csv", default="Brigade_Bangalore_10_April_26.csv", help="POS CSV file path")
    
    args = parser.parse_args()
    
    # Resolve CSV file path
    csv_path = args.csv
    if not os.path.isabs(csv_path):
        csv_path = os.path.join(os.path.dirname(__file__), "..", csv_path)
        
    upload_pos(args.url, csv_path)
