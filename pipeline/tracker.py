import uuid
import math
from datetime import datetime
from typing import List, Dict, Tuple, Optional

def calculate_iou(box1: Tuple[float, float, float, float], box2: Tuple[float, float, float, float]) -> float:
    x1_1, y1_1, x2_1, y2_1 = box1
    x1_2, y1_2, x2_2, y2_2 = box2
    
    xi1 = max(x1_1, x1_2)
    yi1 = max(y1_1, y1_2)
    xi2 = min(x2_1, x2_2)
    yi2 = min(y2_1, y2_2)
    
    inter_area = max(0.0, xi2 - xi1) * max(0.0, yi2 - yi1)
    
    box1_area = (x2_1 - x1_1) * (y2_1 - y1_1)
    box2_area = (x2_2 - x1_2) * (y2_2 - y1_2)
    
    union_area = box1_area + box2_area - inter_area
    if union_area == 0:
        return 0.0
    return inter_area / union_area

def calculate_distance(p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
    return math.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)

class CentroidTracker:
    def __init__(self, max_lost_frames: int = 45):
        self.next_track_id = 1
        self.tracks = {}  # track_id -> track_dict
        self.max_lost_frames = max_lost_frames
        
    def update(self, detections: List[Tuple[float, float, float, float, float]]) -> Dict[int, dict]:
        # detections is a list of (x1, y1, x2, y2, confidence)
        for tid in list(self.tracks.keys()):
            self.tracks[tid]["lost_count"] += 1
            
        matched_detections = set()
        matched_tracks = set()
        
        # 1. Match by IoU first
        for tid, track in self.tracks.items():
            best_iou = 0.3
            best_idx = -1
            for idx, det in enumerate(detections):
                if idx in matched_detections:
                    continue
                iou = calculate_iou(track["bbox"], det[:4])
                if iou > best_iou:
                    best_iou = iou
                    best_idx = idx
            if best_idx != -1:
                det = detections[best_idx]
                track["bbox"] = det[:4]
                track["centroid"] = ((det[0] + det[2]) / 2.0, (det[1] + det[3]) / 2.0)
                track["confidence"] = det[4]
                track["lost_count"] = 0
                matched_detections.add(best_idx)
                matched_tracks.add(tid)
                
        # 2. Match remaining by Centroid distance
        for tid, track in self.tracks.items():
            if tid in matched_tracks:
                continue
            best_dist = 0.15
            best_idx = -1
            for idx, det in enumerate(detections):
                if idx in matched_detections:
                    continue
                det_centroid = ((det[0] + det[2]) / 2.0, (det[1] + det[3]) / 2.0)
                dist = calculate_distance(track["centroid"], det_centroid)
                if dist < best_dist:
                    best_dist = dist
                    best_idx = idx
            if best_idx != -1:
                det = detections[best_idx]
                track["bbox"] = det[:4]
                track["centroid"] = ((det[0] + det[2]) / 2.0, (det[1] + det[3]) / 2.0)
                track["confidence"] = det[4]
                track["lost_count"] = 0
                matched_detections.add(best_idx)
                matched_tracks.add(tid)
                
        # Remove expired tracks
        for tid in list(self.tracks.keys()):
            if self.tracks[tid]["lost_count"] > self.max_lost_frames:
                del self.tracks[tid]
                
        # New tracks
        for idx, det in enumerate(detections):
            if idx not in matched_detections:
                centroid = ((det[0] + det[2]) / 2.0, (det[1] + det[3]) / 2.0)
                self.tracks[self.next_track_id] = {
                    "bbox": det[:4],
                    "centroid": centroid,
                    "confidence": det[4],
                    "lost_count": 0
                }
                self.next_track_id += 1
                
        return {tid: track for tid, track in self.tracks.items() if track["lost_count"] == 0}

class SessionResolver:
    def __init__(self, re_entry_window_seconds: float = 120.0):
        self.sessions = {}
        self.exited_sessions = []
        self.re_entry_window = re_entry_window_seconds
        
    def resolve(self, camera_id: str, camera_track_id: int, timestamp_str: str, bbox: Tuple[float, float, float, float]) -> str:
        dt = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        ts = dt.timestamp()
        
        # Clean expired exited sessions
        self.exited_sessions = [s for s in self.exited_sessions if ts - s["exit_time"] <= self.re_entry_window]
        
        # 1. Existing session check
        for sid, sess in self.sessions.items():
            if sess["active_tracks"].get(camera_id) == camera_track_id:
                sess["last_seen_time"] = ts
                return sess["visitor_id"]
                
        # 2. Re-entry on CAM_3
        if camera_id == "CAM_3":
            if self.exited_sessions:
                best_match = self.exited_sessions.pop(0)
                visitor_id = best_match["visitor_id"]
                self.sessions[visitor_id] = {
                    "visitor_id": visitor_id,
                    "last_seen_time": ts,
                    "active_tracks": {camera_id: camera_track_id}
                }
                return visitor_id
                
            visitor_id = f"VIS_{uuid.uuid4().hex[:6].upper()}"
            self.sessions[visitor_id] = {
                "visitor_id": visitor_id,
                "last_seen_time": ts,
                "active_tracks": {camera_id: camera_track_id}
            }
            return visitor_id
            
        # 3. Associate with active sessions across other cameras
        best_sess_id = None
        best_time = 0.0
        for sid, sess in self.sessions.items():
            if ts - sess["last_seen_time"] <= 30.0:
                if camera_id not in sess["active_tracks"]:
                    if sess["last_seen_time"] > best_time:
                        best_time = sess["last_seen_time"]
                        best_sess_id = sid
                        
        if best_sess_id:
            self.sessions[best_sess_id]["active_tracks"][camera_id] = camera_track_id
            self.sessions[best_sess_id]["last_seen_time"] = ts
            return self.sessions[best_sess_id]["visitor_id"]
            
        # Low confidence fallback
        visitor_id = f"VIS_{uuid.uuid4().hex[:6].upper()}"
        self.sessions[visitor_id] = {
            "visitor_id": visitor_id,
            "last_seen_time": ts,
            "active_tracks": {camera_id: camera_track_id}
        }
        return visitor_id
        
    def register_exit(self, visitor_id: str, timestamp_str: str):
        dt = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        ts = dt.timestamp()
        
        if visitor_id in self.sessions:
            del self.sessions[visitor_id]
            
        self.exited_sessions.append({
            "visitor_id": visitor_id,
            "exit_time": ts
        })

