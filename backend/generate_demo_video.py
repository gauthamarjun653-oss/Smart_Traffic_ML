import cv2
import numpy as np
import os

def create_demo_video(output_path="backend/videos/demo_traffic.mp4", duration_seconds=15, fps=30):
    width, height = 1280, 720
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
    
    total_frames = duration_seconds * fps
    
    # Initialize object trajectories (y position, x position, type)
    # We want to simulate:
    # 1. Car 1: Lane 1, Normal Speed
    # 2. Car 2 (Overspeeding): Lane 2, High Speed
    # 3. Motorcycle: Lane 3, Normal Speed
    # 4. Car 3 & 4 (Accident): Lane 1, collides at frame 150
    
    objects = {
        "car_1": {"x": 300, "y": -100, "speed": 6, "type": "car", "color": (255, 100, 100)},
        "car_fast": {"x": 550, "y": -100, "speed": 18, "type": "car", "color": (100, 100, 255)}, # Overspeeding
        "bike_1": {"x": 800, "y": -100, "speed": 8, "type": "motorcycle", "color": (100, 255, 100)}, # Rider
        "car_collide_1": {"x": 300, "y": -200, "speed": 5, "type": "car", "color": (200, 200, 200)},
        "car_collide_2": {"x": 300, "y": -400, "speed": 9, "type": "car", "color": (150, 150, 250)}
    }
    
    print(f"Generating simulated traffic video at: {output_path}...")
    
    for frame_idx in range(total_frames):
        # Create road background
        frame = np.ones((height, width, 3), dtype=np.uint8) * 30  # Dark grey road
        
        # Draw road boundaries
        cv2.line(frame, (150, 0), (150, height), (100, 100, 100), 5)
        cv2.line(frame, (1130, 0), (1130, height), (100, 100, 100), 5)
        
        # Draw lane separators (dashed yellow lines)
        for y in range(0, height, 40):
            if (y // 40) % 2 == 0:
                cv2.line(frame, (450, y), (450, y + 20), (0, 255, 255), 2)
                cv2.line(frame, (750, y), (750, y + 20), (0, 255, 255), 2)
                
        # Update and draw simulated vehicles
        for obj_name, data in list(objects.items()):
            # Handle special accident logic
            if obj_name == "car_collide_1" or obj_name == "car_collide_2":
                # They collide around frame 150 (y position ~ 450)
                if frame_idx >= 150:
                    # After collision, they stop and stay overlapping
                    data["y"] = 450
                    if obj_name == "car_collide_2":
                        data["y"] = 475 # Overlap
                else:
                    data["y"] += data["speed"]
            else:
                data["y"] += data["speed"]
                
            y = int(data["y"])
            x = data["x"]
            
            # Draw shape on frame
            if data["type"] == "car":
                # Draw car body
                cv2.rectangle(frame, (x - 45, y - 60), (x + 45, y + 60), data["color"], -1)
                # Wheels
                cv2.rectangle(frame, (x - 50, y - 50), (x - 45, y - 20), (0,0,0), -1)
                cv2.rectangle(frame, (x + 45, y - 50), (x + 50, y - 20), (0,0,0), -1)
                cv2.rectangle(frame, (x - 50, y + 20), (x - 45, y + 50), (0,0,0), -1)
                cv2.rectangle(frame, (x + 45, y + 20), (x + 50, y + 50), (0,0,0), -1)
                # Windshield
                cv2.rectangle(frame, (x - 35, y - 30), (x + 35, y - 10), (255,255,255), -1)
                cv2.rectangle(frame, (x - 35, y + 20), (x + 35, y + 40), (255,255,255), -1)
                
            elif data["type"] == "motorcycle":
                # Draw bike body (thin ellipse)
                cv2.ellipse(frame, (x, y), (15, 50), 0, 0, 360, data["color"], -1)
                # Wheels
                cv2.circle(frame, (x, y - 45), 10, (0,0,0), -1)
                cv2.circle(frame, (x, y + 45), 10, (0,0,0), -1)
                # Rider (draw small circle)
                cv2.circle(frame, (x, y), 12, (200, 150, 100), -1) # Skin tone
                
        out.write(frame)
        
    out.release()
    print(f"Success! Saved demo video to {output_path}")

if __name__ == "__main__":
    create_demo_video()
