import os
import cv2
import time
import math
import base64
import asyncio
import threading
from typing import List, Dict
from fastapi import FastAPI, Depends, WebSocket, WebSocketDisconnect, UploadFile, File, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from backend.database import init_db, get_db, Violation
from backend.video_processor import VideoProcessor

app = FastAPI(title="Smart Traffic Management System API")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Directories setup
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VIOLATIONS_DIR = os.path.join(BASE_DIR, "violations")
VIDEOS_DIR = os.path.join(BASE_DIR, "videos")
MODELS_DIR = os.path.join(BASE_DIR, "models")

os.makedirs(VIOLATIONS_DIR, exist_ok=True)
os.makedirs(VIDEOS_DIR, exist_ok=True)
os.makedirs(MODELS_DIR, exist_ok=True)

# Mount static folders to serve screenshots and videos
app.mount("/violations", StaticFiles(directory=VIOLATIONS_DIR), name="violations")

# Initialize database
@app.on_event("startup")
def startup_event():
    init_db()

# Global state
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        print(f"WebSocket client connected. Total connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            print(f"WebSocket client disconnected. Total connections: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        # Create a copy of list to prevent concurrent modifications
        connections = list(self.active_connections)
        for connection in connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                print(f"Error sending message to client: {e}")
                # Clean up stale connections
                if connection in self.active_connections:
                    self.active_connections.remove(connection)

manager = ConnectionManager()
video_processor = None
processing_thread = None
is_processing = False

def get_processor():
    global video_processor
    if video_processor is None:
        video_processor = VideoProcessor(
            main_model_path="yolov8s.pt",
            helmet_model_path=os.path.join(MODELS_DIR, "helmet_yolov8n.pt"),
            accident_model_path=os.path.join(MODELS_DIR, "accident_yolov8s.pt")
        )
    return video_processor

# Video processing runner running in a background thread
def run_video_processing(video_path: str):
    global is_processing
    is_processing = True
    
    processor = get_processor()
    cap = cv2.VideoCapture(video_path)
    
    if not cap.isOpened():
        print(f"Failed to open video: {video_path}")
        is_processing = False
        return
        
    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps <= 0 or math.isnan(fps):
        fps = 30.0
        
    frame_delay = 1.0 / fps
    frame_count = 0
    
    # Event loop to handle websocket broadcasts from the background thread
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    db = next(get_db())
    
    try:
        while is_processing:
            start_time = time.time()
            ret, frame = cap.read()
            if not ret:
                print("End of video stream reached or loop terminated.")
                break
                
            frame_count += 1
            
            # Process frame for unique count, speed estimation, helmets, accidents
            annotated_frame, new_violations = processor.process_frame(frame, frame_count, fps, db)
            
            # Encode frame to base64 jpeg
            _, buffer = cv2.imencode('.jpg', annotated_frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
            frame_base64 = base64.b64encode(buffer).decode('utf-8')
            
            # Prepare broadcast payload
            payload = {
                "type": "frame",
                "frame": f"data:image/jpeg;base64,{frame_base64}",
                "stats": processor.get_stats(),
                "violations": new_violations  # Empty list if no new violations
            }
            
            # Broadcast to UI clients synchronously
            loop.run_until_complete(manager.broadcast(payload))
            
            # Frame rate pacing
            elapsed = time.time() - start_time
            sleep_time = max(0, frame_delay - elapsed)
            time.sleep(sleep_time)
            
    except Exception as e:
        print(f"Exception during background video processing: {e}")
    finally:
        cap.release()
        db.close()
        is_processing = False
        print("Video processing stopped.")
        # Broadcast termination message
        loop.run_until_complete(manager.broadcast({"type": "status", "status": "stopped"}))
        loop.close()

# REST Endpoints
@app.get("/api/violations", response_model=list)
def read_violations(skip: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    return db.query(Violation).order_by(Violation.id.desc()).offset(skip).limit(limit).all()

@app.get("/api/stats")
def read_stats():
    if video_processor is not None:
        return video_processor.get_stats()
    return {"cars": 0, "bikes": 0, "buses": 0, "trucks": 0, "total": 0}

@app.post("/api/start")
def start_processing(video_name: str, background_tasks: BackgroundTasks):
    global processing_thread, is_processing
    if is_processing:
        raise HTTPException(status_code=400, detail="Processing is already active")
        
    video_path = os.path.join(VIDEOS_DIR, video_name)
    if not os.path.exists(video_path):
        raise HTTPException(status_code=404, detail="Video file not found")
        
    processing_thread = threading.Thread(target=run_video_processing, args=(video_path,))
    processing_thread.daemon = True
    processing_thread.start()
    
    return {"status": "started", "video": video_name}

@app.post("/api/stop")
def stop_processing():
    global is_processing
    if not is_processing:
        return {"status": "inactive"}
    is_processing = False
    return {"status": "stopping"}

@app.post("/api/upload")
async def upload_video(file: UploadFile = File(...)):
    # Save uploaded video
    video_path = os.path.join(VIDEOS_DIR, file.filename)
    with open(video_path, "wb") as buffer:
        content = await file.read()
        buffer.write(content)
    return {"filename": file.filename, "size": len(content)}

@app.get("/api/videos")
def list_videos():
    # List available videos in the videos directory
    files = [f for f in os.listdir(VIDEOS_DIR) if f.endswith(('.mp4', '.avi', '.mov', '.mkv'))]
    return {"videos": files}

# WebSocket Endpoint
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive, listen for any commands
            data = await websocket.receive_text()
            # If clients send control signals through WS (e.g. 'pause', 'stop')
            if data == "stop":
                global is_processing
                is_processing = False
    except WebSocketDisconnect:
        manager.disconnect(websocket)
