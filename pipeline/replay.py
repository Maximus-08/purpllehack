import sys
import json
import time
import requests
import argparse
import os
from datetime import datetime

def replay_events(api_url: str, filepath: str, batch_size: int = 25, mode: str = "fast"):
    if not os.path.exists(filepath):
        print(f"File not found: {filepath}")
        return
        
    print(f"Replaying events from {filepath} to {api_url}/events/ingest...")
    
    events = []
    with open(filepath, "r") as f:
        for line in f:
            if line.strip():
                try:
                    events.append(json.loads(line))
                except Exception as e:
                    print(f"Error parsing line: {line}. Error: {e}")
                    
    if not events:
        print("No events to replay.")
        return
        
    # Sort events chronologically
    events.sort(key=lambda x: x.get("timestamp", ""))
    
    total_sent = 0
    total_accepted = 0
    total_rejected = 0
    total_duplicates = 0
    
    # Send events in batches
    for i in range(0, len(events), batch_size):
        batch = events[i:i+batch_size]
        try:
            response = requests.post(
                f"{api_url}/events/ingest", 
                json=batch, 
                headers={"Content-Type": "application/json"},
                timeout=10.0
            )
            if response.status_code == 200:
                res_data = response.json()
                accepted = res_data.get("accepted", 0)
                rejected = res_data.get("rejected", 0)
                duplicates = res_data.get("duplicates", 0)
                
                total_accepted += accepted
                total_rejected += rejected
                total_duplicates += duplicates
                total_sent += len(batch)
                
                print(f"Batch {i//batch_size + 1}: Sent {len(batch)} -> Accepted: {accepted}, Duplicates: {duplicates}, Rejected: {rejected}")
                if res_data.get("errors"):
                    for err in res_data["errors"]:
                        print(f"  Error at index {err['index']}: {err['message']}")
            else:
                print(f"Batch {i//batch_size + 1}: Failed with status code {response.status_code}")
                total_rejected += len(batch)
        except Exception as e:
            print(f"Batch {i//batch_size + 1}: Exception occurred: {e}")
            total_rejected += len(batch)
            
        if mode == "demo":
            time.sleep(1.0)
        elif mode == "realtime" and i + batch_size < len(events):
            try:
                t1 = datetime.fromisoformat(batch[-1]["timestamp"].replace("Z", "+00:00")).timestamp()
                t2 = datetime.fromisoformat(events[i+batch_size]["timestamp"].replace("Z", "+00:00")).timestamp()
                diff = t2 - t1
                if 0 < diff < 10:
                    time.sleep(diff)
            except Exception:
                time.sleep(0.5)
                
    print(f"\nReplay Summary:")
    print(f"Total processed: {total_sent}")
    print(f"Total accepted:  {total_accepted}")
    print(f"Total duplicates: {total_duplicates}")
    print(f"Total rejected:  {total_rejected}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Replay Purplle Store Intelligence events to the API.")
    parser.add_argument("--url", default="http://localhost:8000", help="API base URL")
    parser.add_argument("--file", default="data/generated_events.jsonl", help="JSONL file of events")
    parser.add_argument("--batch", type=int, default=25, help="Batch size for ingest")
    parser.add_argument("--mode", choices=["fast", "demo", "realtime"], default="fast", help="Replay speed mode")
    
    args = parser.parse_args()
    
    # Resolve file path
    filepath = args.file
    if not os.path.isabs(filepath):
        filepath = os.path.join(os.path.dirname(__file__), "..", filepath)
        
    replay_events(args.url, filepath, args.batch, args.mode)

