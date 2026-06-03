import pandas as pd
import os
import json
from datetime import datetime, timezone, timedelta

def load_and_normalize_pos(csv_path: str) -> list[dict]:
    if not os.path.exists(csv_path):
        return []
        
    df = pd.read_csv(csv_path)
    
    # 1. Filter only sales and ignore returned rows
    df["invoice_type"] = df["invoice_type"].astype(str).str.strip().str.lower()
    df_sales = df[df["invoice_type"] == "sales"].copy()
    
    # Ignore rows with populated return_id
    if "return_id" in df_sales.columns:
        df_sales = df_sales[df_sales["return_id"].isna() | (df_sales["return_id"].astype(str).str.strip() == "")]
        
    if df_sales.empty:
        return []
        
    # Group by order_id and invoice_number
    # Since invoice_number and order_id are aligned, we can group by both
    grouped = df_sales.groupby(["order_id", "invoice_number"], dropna=False)
    
    normalized_txns = []
    tz_kolkata = timezone(timedelta(hours=5, minutes=30))
    
    for (order_id, invoice_number), group in grouped:
        # Build transaction_id
        txn_id = str(invoice_number) if pd.notna(invoice_number) and str(invoice_number).strip() != "" else str(order_id)
        
        # Map store ID (source ST1008 -> target STORE_BLR_002)
        source_store = str(group["store_id"].iloc[0])
        store_id = "STORE_BLR_002" if source_store == "ST1008" else source_store
        
        # Parse timestamp
        # order_date format: DD-MM-YYYY, order_time format: HH:MM:SS
        date_str = str(group["order_date"].iloc[0]).strip()
        time_str = str(group["order_time"].iloc[0]).strip()
        
        try:
            # Try DD-MM-YYYY HH:MM:SS
            dt_local = datetime.strptime(f"{date_str} {time_str}", "%d-%m-%Y %H:%M:%S")
        except ValueError:
            try:
                # Fallback to YYYY-MM-DD HH:MM:SS
                dt_local = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M:%S")
            except ValueError:
                # Default fallback
                dt_local = datetime.now()
                
        # Localize to Asia/Kolkata and convert to UTC
        dt_utc = dt_local.replace(tzinfo=tz_kolkata).astimezone(timezone.utc)
        ts_utc_str = dt_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
        
        # Calculate basket value
        basket_value = 0.0
        for _, row in group.iterrows():
            val = 0.0
            # Check NMV, fallback to total_amount, then GMV, then 0.0
            for col in ["NMV", "total_amount", "GMV"]:
                if col in row and pd.notna(row[col]):
                    try:
                        val = float(row[col])
                        break
                    except ValueError:
                        continue
            basket_value += val
            
        # Calculate item count
        item_count = 0
        if "qty" in group.columns:
            item_count = int(group["qty"].sum())
            
        line_count = len(group)
        
        metadata = {
            "source_store_id": source_store,
            "order_id": str(order_id),
            "invoice_number": str(invoice_number),
            "line_count": line_count,
            "customer_name": str(group["customer_name"].iloc[0]) if "customer_name" in group.columns else "Guest"
        }
        
        normalized_txns.append({
            "transaction_id": txn_id,
            "store_id": store_id,
            "timestamp": ts_utc_str,
            "basket_value_inr": round(basket_value, 2),
            "item_count": item_count,
            "metadata_json": json.dumps(metadata)
        })
        
    return normalized_txns
