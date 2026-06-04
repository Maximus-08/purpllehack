import cv2
import os
import json
from datetime import datetime, timedelta, timezone
from ultralytics import YOLO
from pipeline.tracker import CentroidTracker, SessionResolver
from pipeline.zones import is_in_polygon
from pipeline.emit import emit_event
from app.database import get_db_connection

def load_layout(store_id: str) -> dict:
    pipeline_dir = os.path.dirname(__file__)
    layout_path = os.path.join(pipeline_dir, "../app/layouts", f"{store_id}.json")
    if not os.path.exists(layout_path):
        layout_path = os.path.join(pipeline_dir, "../app/store_layout.json")
        
    if not os.path.exists(layout_path):
        return {}
    with open(layout_path, "r") as f:
        return json.load(f)

def run_detection(max_seconds: float = None, store_id: str = None):
    if not store_id:
        store_id = os.getenv("STORE_ID", "STORE_BLR_002")
        
    # Initialize layout
    layout = load_layout(store_id)
    if not layout:
        print(f"Layout file for store {store_id} not found. Aborting.")
        return
        
    store_id = layout["store_id"]
    cameras = layout["cameras"]
    zones_config = layout["zones"]
    
    # Initialize trackers
    trackers = {cam_id: CentroidTracker(max_lost_frames=45) for cam_id in cameras.keys()}
    resolver = SessionResolver()
    
    # Initialize YOLO Model
    print("Loading YOLOv8n model...")
    model = YOLO("yolov8n.pt")
    
    # Track visitor session durations to apply staff heuristics
    # visitor_id -> { 'first_seen', 'last_seen', 'has_billing_counter' }
    visitor_durations = {}
    
    # Track visitor active zones to emit ZONE_ENTER / ZONE_EXIT / ZONE_DWELL
    # visitor_id -> { 'zone_id', 'entered_at', 'last_dwell_at' }
    visitor_zones = {}
    
    # Filepath for generated events
    output_filepath = os.path.join(os.path.dirname(__file__), "../data/generated_events.jsonl")
    if os.path.exists(output_filepath):
        try:
            os.remove(output_filepath)
        except Exception:
            pass
            
    # Process camera clips one by one
    for cam_id, cam_meta in cameras.items():
        video_path = os.path.join(os.path.dirname(__file__), "..", cam_meta["file_path"])
        if not os.path.exists(video_path):
            print(f"Video file not found for {cam_id} at {video_path}. Skipping.")
            continue
            
        print(f"Processing camera {cam_id}: {video_path}...")
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            print(f"Failed to open video {video_path}. Skipping.")
            continue
            
        fps = cap.get(cv2.CAP_PROP_FPS) or cam_meta.get("fps", 25.0)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width = cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 1920
        height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 1080
        
        start_utc_str = cam_meta["clip_start_at_utc"]
        start_dt = datetime.fromisoformat(start_utc_str.replace("Z", "+00:00"))
        
        frame_idx = 0
        frame_skip = 5 # process every 5th frame
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
                
            current_seconds = frame_idx / fps
            if max_seconds and current_seconds > max_seconds:
                break
                
            if frame_idx % frame_skip != 0:
                frame_idx += 1
                continue
                
            # Compute current timestamp
            current_dt = start_dt + timedelta(seconds=current_seconds)
            ts_str = current_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
            
            # YOLO Person detection (class 0 is person)
            results = model(frame, classes=[0], verbose=False)
            detections = []
            
            if len(results) > 0:
                boxes = results[0].boxes
                for box in boxes:
                    xyxy = box.xyxy[0].tolist()
                    conf = float(box.conf[0])
                    # Store as (x1, y1, x2, y2, confidence)
                    detections.append((xyxy[0], xyxy[1], xyxy[2], xyxy[3], conf))
                    
            # Normalize detections coordinates (0.0 to 1.0)
            norm_detections = []
            for det in detections:
                norm_detections.append((
                    det[0] / width,
                    det[1] / height,
                    det[2] / width,
                    det[3] / height,
                    det[4]
                ))
                
            # Update camera tracker
            active_tracks = trackers[cam_id].update(norm_detections)
            
            # Update tracking states and emit zone events
            for track_id, track in active_tracks.items():
                bbox = track["bbox"]
                centroid = track["centroid"]
                conf = track["confidence"]
                
                # Resolve global visitor_id
                visitor_id = resolver.resolve(cam_id, track_id, ts_str, bbox)
                
                # Track session duration for staff heuristic
                if visitor_id not in visitor_durations:
                    visitor_durations[visitor_id] = {
                        "first_seen": current_dt,
                        "last_seen": current_dt,
                        "has_billing_counter": False
                    }
                    # Emit Entry event if on CAM_3 (or first camera they appear on)
                    if cam_id == "CAM_3":
                        emit_event(
                            event_type="ENTRY",
                            visitor_id=visitor_id,
                            store_id=store_id,
                            camera_id=cam_id,
                            timestamp=ts_str,
                            confidence=conf,
                            metadata={"session_seq": 1},
                            filepath=output_filepath
                        )
                else:
                    visitor_durations[visitor_id]["last_seen"] = current_dt
                    
                # Determine which zone the visitor is in
                current_zone = None
                for zid, zmeta in zones_config.items():
                    if cam_id in zmeta.get("camera_ids", []):
                        poly = zmeta.get("camera_polygons", {}).get(cam_id)
                        if poly and is_in_polygon(centroid, poly):
                            current_zone = zid
                            break
                            
                # Manage zone changes
                prev_state = visitor_zones.get(visitor_id)
                
                if current_zone == "BILLING_COUNTER":
                    visitor_durations[visitor_id]["has_billing_counter"] = True
                    
                if prev_state is None:
                    # Brand new zone enter
                    if current_zone is not None:
                        visitor_zones[visitor_id] = {
                            "zone_id": current_zone,
                            "entered_at": current_dt,
                            "last_dwell_at": current_dt
                        }
                        emit_event(
                            event_type="ZONE_ENTER",
                            visitor_id=visitor_id,
                            store_id=store_id,
                            camera_id=cam_id,
                            timestamp=ts_str,
                            zone_id=current_zone,
                            confidence=conf,
                            metadata={"session_seq": 2},
                            filepath=output_filepath
                        )
                        # If billing counter, also emit queue join
                        if current_zone == "BILLING_COUNTER":
                            emit_event(
                                event_type="BILLING_QUEUE_JOIN",
                                visitor_id=visitor_id,
                                store_id=store_id,
                                camera_id=cam_id,
                                timestamp=ts_str,
                                zone_id="BILLING_COUNTER",
                                confidence=conf,
                                metadata={"queue_depth": 1, "session_seq": 3},
                                filepath=output_filepath
                            )
                else:
                    prev_zone = prev_state["zone_id"]
                    if current_zone != prev_zone:
                        # Exited previous zone
                        dwell_ms = int((current_dt - prev_state["entered_at"]).total_seconds() * 1000)
                        emit_event(
                            event_type="ZONE_EXIT",
                            visitor_id=visitor_id,
                            store_id=store_id,
                            camera_id=cam_id,
                            timestamp=ts_str,
                            zone_id=prev_zone,
                            dwell_ms=dwell_ms,
                            confidence=conf,
                            metadata={"session_seq": 4},
                            filepath=output_filepath
                        )
                        
                        if current_zone is not None:
                            visitor_zones[visitor_id] = {
                                "zone_id": current_zone,
                                "entered_at": current_dt,
                                "last_dwell_at": current_dt
                            }
                            emit_event(
                                event_type="ZONE_ENTER",
                                visitor_id=visitor_id,
                                store_id=store_id,
                                camera_id=cam_id,
                                timestamp=ts_str,
                                zone_id=current_zone,
                                confidence=conf,
                                metadata={"session_seq": 5},
                                filepath=output_filepath
                            )
                            if current_zone == "BILLING_COUNTER":
                                emit_event(
                                    event_type="BILLING_QUEUE_JOIN",
                                    visitor_id=visitor_id,
                                    store_id=store_id,
                                    camera_id=cam_id,
                                    timestamp=ts_str,
                                    zone_id="BILLING_COUNTER",
                                    confidence=conf,
                                    metadata={"queue_depth": 1, "session_seq": 6},
                                    filepath=output_filepath
                                )
                        else:
                            del visitor_zones[visitor_id]
                    else:
                        # Continuous dwell check
                        time_since_last_dwell = (current_dt - prev_state["last_dwell_at"]).total_seconds()
                        if time_since_last_dwell >= 5.0: # 5 seconds lower threshold for demo/test mode
                            dwell_ms = int((current_dt - prev_state["entered_at"]).total_seconds() * 1000)
                            emit_event(
                                event_type="ZONE_DWELL",
                                visitor_id=visitor_id,
                                store_id=store_id,
                                camera_id=cam_id,
                                timestamp=ts_str,
                                zone_id=prev_zone,
                                dwell_ms=dwell_ms,
                                confidence=conf,
                                metadata={"session_seq": 7},
                                filepath=output_filepath
                            )
                            prev_state["last_dwell_at"] = current_dt
                            
            frame_idx += 1
            
        cap.release()
        
        # After completing a camera, check tracks that went missing and emit final exit / zone exits
        # Let's say if they were last seen on CAM_3, we emit exit
        for visitor_id, state in list(visitor_zones.items()):
            prev_zone = state["zone_id"]
            last_ts_str = visitor_durations[visitor_id]["last_seen"].strftime("%Y-%m-%dT%H:%M:%SZ")
            dwell_ms = int((visitor_durations[visitor_id]["last_seen"] - state["entered_at"]).total_seconds() * 1000)
            
            emit_event(
                event_type="ZONE_EXIT",
                visitor_id=visitor_id,
                store_id=store_id,
                camera_id=cam_id,
                timestamp=last_ts_str,
                zone_id=prev_zone,
                dwell_ms=dwell_ms,
                confidence=1.0,
                metadata={"session_seq": 8},
                filepath=output_filepath
            )
            del visitor_zones[visitor_id]
            
        if cam_id == "CAM_3":
            # For visitors seen on CAM_3, register their exits
            for visitor_id, duration in visitor_durations.items():
                last_ts_str = duration["last_seen"].strftime("%Y-%m-%dT%H:%M:%SZ")
                emit_event(
                    event_type="EXIT",
                    visitor_id=visitor_id,
                    store_id=store_id,
                    camera_id="CAM_3",
                    timestamp=last_ts_str,
                    confidence=1.0,
                    metadata={"session_seq": 9},
                    filepath=output_filepath
                )
                resolver.register_exit(visitor_id, last_ts_str)
                
    # Staff Post-Processing Heuristic:
    # If a visitor was present for > 90 seconds (since clips are ~2 minutes), flag them as staff.
    # Also if they are present in billing counter area repeatedly but never purchase.
    staff_ids = []
    for visitor_id, info in visitor_durations.items():
        duration_sec = (info["last_seen"] - info["first_seen"]).total_seconds()
        # If active for > 85 seconds, heuristically mark as staff
        if duration_sec > 85.0:
            staff_ids.append(visitor_id)
            
    if staff_ids:
        print(f"Heuristically flagged {len(staff_ids)} sessions as staff: {staff_ids}")
        # Update is_staff flag in output file
        temp_filepath = output_filepath + ".tmp"
        with open(output_filepath, "r") as f_in, open(temp_filepath, "w") as f_out:
            for line in f_in:
                if line.strip():
                    evt = json.loads(line)
                    if evt["visitor_id"] in staff_ids:
                        evt["is_staff"] = True
                    f_out.write(json.dumps(evt) + "\n")
        os.replace(temp_filepath, output_filepath)
        
    print(f"Pipeline executed successfully. Output saved to {output_filepath}")

