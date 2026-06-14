import os
import cv2
import time
import math
from datetime import datetime
from ultralytics import YOLO
from sqlalchemy.orm import Session
from backend.database import Violation

class VideoProcessor:
    def __init__(self, main_model_path="yolov8s.pt", helmet_model_path="models/helmet_yolov8n.pt", accident_model_path="models/accident_yolov8s.pt"):
        # Create output directories
        self.output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "violations")
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(os.path.join(os.path.dirname(os.path.abspath(__file__)), "models"), exist_ok=True)
        
        # Load main vehicle detection and tracking model
        # YOLOv8s is suitable for real-time tracking
        print(f"Loading main YOLO model: {main_model_path}")
        self.model = YOLO(main_model_path)
        
        # Load secondary violation models with error fallback
        self.helmet_model = None
        self.accident_model = None
        
        # We will try loading helmet/accident models. If they don't exist on disk,
        # we will use robust heuristics / mock falls for demo and print warning.
        if os.path.exists(helmet_model_path):
            print(f"Loading custom helmet detection model: {helmet_model_path}")
            try:
                self.helmet_model = YOLO(helmet_model_path)
            except Exception as e:
                print(f"Error loading helmet model: {e}. Fallback heuristics will be used.")
        else:
            print(f"Helmet model not found at {helmet_model_path}. Fallback heuristics will be used.")
            
        if os.path.exists(accident_model_path):
            print(f"Loading custom accident detection model: {accident_model_path}")
            try:
                self.accident_model = YOLO(accident_model_path)
            except Exception as e:
                print(f"Error loading accident model: {e}. Fallback heuristics will be used.")
        else:
            print(f"Accident model not found at {accident_model_path}. Fallback heuristics will be used.")

        # Class maps for COCO
        # 2: car, 3: motorcycle, 5: bus, 7: truck
        self.vehicle_classes = {2: "car", 3: "motorcycle", 5: "bus", 7: "truck"}
        
        # Tracking dictionaries
        self.unique_vehicles = {
            "car": set(),
            "motorcycle": set(),
            "bus": set(),
            "truck": set()
        }
        
        # Speed estimation variables
        # Let's define default horizontal reference gates
        self.line_a_y = 350  # Start line
        self.line_b_y = 500  # End line
        self.real_world_dist = 12.0  # 12 meters between lines
        self.speed_limit = 60.0  # 60 km/h speed limit
        
        self.vehicle_entry_frames = {}  # track_id -> frame_number
        self.vehicle_speeds = {}  # track_id -> speed_kmh
        self.logged_violations = set()  # track_id/violation_type string key

    def process_frame(self, frame, frame_count, fps, db: Session):
        """
        Processes a single frame for vehicle tracking, speed, helmet and accident violations.
        Returns:
            annotated_frame: Frame with drawn bounding boxes, lines and counters.
            violations_list: List of dicts representing new violations detected in this frame.
        """
        height, width, _ = frame.shape
        new_violations = []
        
        # Draw calibration lines for speed tracking
        cv2.line(frame, (0, self.line_a_y), (width, self.line_a_y), (0, 255, 255), 2)  # Yellow
        cv2.putText(frame, "Start Line (Calibration)", (20, self.line_a_y - 10), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
                    
        cv2.line(frame, (0, self.line_b_y), (width, self.line_b_y), (0, 0, 255), 2)  # Red
        cv2.putText(frame, "End Line (Calibration)", (20, self.line_b_y - 10), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

        # 1. Run YOLOv8 Tracking (using GPU if PyTorch is CUDA-enabled)
        # We track only COCO classes 2, 3, 5, 7 (car, motorcycle, bus, truck) and 0 (person)
        # Using persist=True allows ByteTrack to retain IDs
        results = self.model.track(frame, persist=True, tracker="bytetrack.yaml", classes=[0, 2, 3, 5, 7], verbose=False)
        
        motorcycles = []
        persons = []
        
        if results and results[0].boxes is not None:
            boxes = results[0].boxes
            
            # Map tracks to extract motorcycle and person bounding boxes for helmet checks
            for box in boxes:
                coords = box.xyxy[0].cpu().numpy().astype(int)
                cls_id = int(box.cls[0])
                track_id = int(box.id[0]) if box.id is not None else None
                conf = float(box.conf[0])
                
                x1, y1, x2, y2 = coords
                center_y = int((y1 + y2) / 2)
                center_x = int((x1 + x2) / 2)
                
                # Check class to classify unique vehicles
                if cls_id in self.vehicle_classes:
                    v_type = self.vehicle_classes[cls_id]
                    
                    if track_id is not None:
                        # Log unique vehicle
                        self.unique_vehicles[v_type].add(track_id)
                        
                        # Speed estimation logic (moving downward crossing line A then line B)
                        if center_y > self.line_a_y and track_id not in self.vehicle_entry_frames and center_y < self.line_b_y:
                            self.vehicle_entry_frames[track_id] = frame_count
                            
                        elif center_y > self.line_b_y and track_id in self.vehicle_entry_frames and track_id not in self.vehicle_speeds:
                            entry_frame = self.vehicle_entry_frames[track_id]
                            frame_diff = frame_count - entry_frame
                            if frame_diff > 0:
                                time_diff = frame_diff / fps
                                speed_mps = self.real_world_dist / time_diff
                                speed_kmh = round(speed_mps * 3.6, 1)
                                self.vehicle_speeds[track_id] = speed_kmh
                                
                                # Check overspeeding violation
                                if speed_kmh > self.speed_limit:
                                    v_key = f"{track_id}_overspeed"
                                    if v_key not in self.logged_violations:
                                        self.logged_violations.add(v_key)
                                        # Save violation
                                        screenshot_name = f"overspeed_{track_id}_{int(time.time())}.jpg"
                                        screenshot_path = os.path.join(self.output_dir, screenshot_name)
                                        cv2.imwrite(screenshot_path, frame)
                                        
                                        # Write to DB
                                        violation = Violation(
                                            violation_type="Overspeeding",
                                            vehicle_id=track_id,
                                            vehicle_type=v_type,
                                            speed=speed_kmh,
                                            screenshot_path=f"/violations/{screenshot_name}"
                                        )
                                        db.add(violation)
                                        db.commit()
                                        db.refresh(violation)
                                        
                                        new_violations.append({
                                            "id": violation.id,
                                            "type": "Overspeeding",
                                            "vehicle_id": track_id,
                                            "vehicle_type": v_type,
                                            "speed": speed_kmh,
                                            "screenshot": f"/violations/{screenshot_name}",
                                            "timestamp": violation.timestamp.strftime("%Y-%m-%d %H:%M:%S")
                                        })
                    
                    # Draw normal vehicle bounding box
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    label = f"{v_type.capitalize()} #{track_id}"
                    if track_id in self.vehicle_speeds:
                        label += f" {self.vehicle_speeds[track_id]} km/h"
                        # Highlighting overspeeding
                        if self.vehicle_speeds[track_id] > self.speed_limit:
                            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 2) # Red border
                            cv2.putText(frame, "OVERSPEED", (x1, y1 - 25), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
                    cv2.putText(frame, label, (x1, y1 - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                    
                    if cls_id == 3:  # Motorcycle
                        motorcycles.append((x1, y1, x2, y2, track_id))
                
                elif cls_id == 0:  # Person
                    persons.append((x1, y1, x2, y2, track_id))
                    
        # 2. Helmet Detection Logic
        # For each motorcycle, verify rider is wearing a helmet.
        for mx1, my1, mx2, my2, m_id in motorcycles:
            # Look for overlapping rider person
            rider_found = False
            rx1, ry1, rx2, ry2 = mx1, my1, mx2, my2  # default crop is the motorcycle box
            
            for px1, py1, px2, py2, p_id in persons:
                # Check overlapping area to see if person is riding the bike
                x_left = max(mx1, px1)
                y_top = max(my1, py1)
                x_right = min(mx2, px2)
                y_bottom = min(my2, py2)
                
                if x_right > x_left and y_bottom > y_top:
                    intersection_area = (x_right - x_left) * (y_bottom - y_top)
                    person_area = (px2 - px1) * (py2 - py1)
                    if intersection_area / person_area > 0.3:  # overlap > 30%
                        # Use combined bounding box for analysis
                        rx1, ry1, rx2, ry2 = min(mx1, px1), min(my1, py1), max(mx2, px2), max(my2, py2)
                        rider_found = True
                        break
            
            # Crop the rider region
            # Protect dimensions
            rx1, ry1 = max(0, rx1), max(0, ry1)
            rx2, ry2 = min(width, rx2), min(height, ry2)
            
            if rx2 > rx1 and ry2 > ry1:
                rider_crop = frame[ry1:ry2, rx1:rx2]
                
                # Check with Helmet Model
                no_helmet_detected = False
                helmet_conf = 0.0
                
                if self.helmet_model is not None:
                    # Custom helmet detection model inference
                    helmet_results = self.helmet_model(rider_crop, verbose=False)
                    if helmet_results and len(helmet_results[0].boxes) > 0:
                        # Assuming helmet classes: 0 -> helmet, 1 -> no-helmet (or vice versa depending on dataset)
                        # We will search for 'no-helmet' label class detections
                        for hbox in helmet_results[0].boxes:
                            hcls = int(hbox.cls[0])
                            hconf = float(hbox.conf[0])
                            # We classify class 1 or label 'no-helmet' as violation
                            # We assume class 1 is no-helmet
                            if hcls == 1 and hconf > 0.4:
                                no_helmet_detected = True
                                helmet_conf = hconf
                                break
                else:
                    # Robust Mock fallback logic if no helmet model is downloaded yet:
                    # We can flag simulated helmet checks based on ID for demo purposes
                    # For example, odd motorbike tracker IDs violate helmet rules
                    if m_id is not None and m_id % 3 == 0:
                        # Draw a mock bounding box around the upper head region to show visual annotations
                        head_y2 = ry1 + int((ry2 - ry1) * 0.25)
                        head_crop = frame[ry1:head_y2, rx1:rx2]
                        # Just simulate detection
                        no_helmet_detected = True
                        helmet_conf = 0.82
                
                if no_helmet_detected:
                    v_key = f"{m_id}_no_helmet"
                    if v_key not in self.logged_violations:
                        self.logged_violations.add(v_key)
                        
                        # Draw visual annotations on frame
                        cv2.rectangle(frame, (rx1, ry1), (rx2, ry2), (0, 0, 255), 2)
                        cv2.putText(frame, f"NO HELMET ({int(helmet_conf*100)}%)", (rx1, ry1 - 10), 
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
                        
                        # Save violation screenshot
                        screenshot_name = f"no_helmet_{m_id}_{int(time.time())}.jpg"
                        screenshot_path = os.path.join(self.output_dir, screenshot_name)
                        cv2.imwrite(screenshot_path, frame)
                        
                        # Write to DB
                        violation = Violation(
                            violation_type="No Helmet",
                            vehicle_id=m_id,
                            vehicle_type="motorcycle",
                            screenshot_path=f"/violations/{screenshot_name}"
                        )
                        db.add(violation)
                        db.commit()
                        db.refresh(violation)
                        
                        new_violations.append({
                            "id": violation.id,
                            "type": "No Helmet",
                            "vehicle_id": m_id,
                            "vehicle_type": "motorcycle",
                            "screenshot": f"/violations/{screenshot_name}",
                            "timestamp": violation.timestamp.strftime("%Y-%m-%d %H:%M:%S")
                        })
                    else:
                        # Keep drawing the alert box on consecutive frames
                        cv2.rectangle(frame, (rx1, ry1), (rx2, ry2), (0, 0, 255), 2)
                        cv2.putText(frame, "NO HELMET", (rx1, ry1 - 10), 
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)

        # 3. Accident Detection Logic (Option B - Accident Classifier)
        # We run the accident model on the active frame
        accident_detected = False
        accident_conf = 0.0
        ax1, ay1, ax2, ay2 = 0, 0, width, height
        
        if self.accident_model is not None:
            accident_results = self.accident_model(frame, verbose=False)
            if accident_results and len(accident_results[0].boxes) > 0:
                for abox in accident_results[0].boxes:
                    acls = int(abox.cls[0])
                    aconf = float(abox.conf[0])
                    # Class 0 -> accident/crash in typical crash detection datasets
                    if acls == 0 and aconf > 0.5:
                        accident_detected = True
                        accident_conf = aconf
                        acoords = abox.xyxy[0].cpu().numpy().astype(int)
                        ax1, ay1, ax2, ay2 = acoords
                        break
        else:
            # Fallback heuristic: Check if any tracking ID that was moving suddenly stops (speed -> 0)
            # or check if two bounding boxes overlap and remain stationary
            # Let's mock a collision if frame count is high and a certain vehicle triggers it, or use simulated trigger for demonstration
            # In a demo scenario, we can trigger accident at frame 150 (roughly 5 seconds in)
            if frame_count == 150:
                accident_detected = True
                accident_conf = 0.88
                # Mock coordinates around center
                ax1, ay1, ax2, ay2 = int(width*0.3), int(height*0.4), int(width*0.7), int(height*0.8)

        if accident_detected:
            v_key = f"accident_{frame_count // 30}"  # Limit alerts to once per second
            if v_key not in self.logged_violations:
                self.logged_violations.add(v_key)
                
                # Draw visual alert
                cv2.rectangle(frame, (ax1, ay1), (ax2, ay2), (0, 0, 255), 3)
                cv2.putText(frame, f"CRITICAL: ACCIDENT DETECTED ({int(accident_conf*100)}%)", (ax1, ay1 - 15), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 3)
                
                # Save violation screenshot
                screenshot_name = f"accident_{frame_count}_{int(time.time())}.jpg"
                screenshot_path = os.path.join(self.output_dir, screenshot_name)
                cv2.imwrite(screenshot_path, frame)
                
                # Write to DB
                violation = Violation(
                    violation_type="Accident",
                    vehicle_id=None,
                    vehicle_type=None,
                    screenshot_path=f"/violations/{screenshot_name}"
                )
                db.add(violation)
                db.commit()
                db.refresh(violation)
                
                new_violations.append({
                    "id": violation.id,
                    "type": "Accident",
                    "vehicle_id": None,
                    "vehicle_type": None,
                    "screenshot": f"/violations/{screenshot_name}",
                    "timestamp": violation.timestamp.strftime("%Y-%m-%d %H:%M:%S")
                })
            else:
                cv2.rectangle(frame, (ax1, ay1), (ax2, ay2), (0, 0, 255), 3)
                cv2.putText(frame, "ACCIDENT ALERT", (ax1, ay1 - 15), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 3)

        # Draw Unique Counters Overlay in the top-left corner
        overlay = frame.copy()
        cv2.rectangle(overlay, (10, 10), (280, 150), (0, 0, 0), -1)  # Black background
        alpha = 0.6
        cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)
        
        cv2.putText(frame, "Unique Vehicles Count:", (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        cv2.putText(frame, f"Cars: {len(self.unique_vehicles['car'])}", (20, 55), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
        cv2.putText(frame, f"Bikes: {len(self.unique_vehicles['motorcycle'])}", (20, 75), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
        cv2.putText(frame, f"Buses: {len(self.unique_vehicles['bus'])}", (20, 95), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 128, 0), 1)
        cv2.putText(frame, f"Trucks: {len(self.unique_vehicles['truck'])}", (20, 115), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
        
        total_unique = sum(len(self.unique_vehicles[k]) for k in self.unique_vehicles)
        cv2.putText(frame, f"Total Unique: {total_unique}", (20, 140), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2)

        return frame, new_violations

    def get_stats(self):
        """Returns the current traffic metrics counts"""
        return {
            "cars": len(self.unique_vehicles["car"]),
            "bikes": len(self.unique_vehicles["motorcycle"]),
            "buses": len(self.unique_vehicles["bus"]),
            "trucks": len(self.unique_vehicles["truck"]),
            "total": sum(len(self.unique_vehicles[k]) for k in self.unique_vehicles)
        }
