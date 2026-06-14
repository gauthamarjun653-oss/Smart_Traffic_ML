# 🚥 Smart AI Traffic Management & Monitoring System

An advanced, GPU-accelerated computer vision and real-time dashboard system designed to process live traffic feeds. The system tracks vehicles, logs traffic counts, detects violations (no-helmet, overspeeding), and fires critical accident warnings in real-time.

---

## 📸 System Dashboard Preview & Architecture

```mermaid
graph TD
    VideoFeed[Traffic Video Feed] --> OpenCV[OpenCV Frame Reader]
    OpenCV --> YOLO[YOLOv8 & Tracking Engine (GPU-Accelerated)]
    YOLO --> SpeedTracker[Speed Estimation Module]
    YOLO --> HelmetClassifier[Helmet Detection Model (YOLOv8)]
    YOLO --> AccidentDetector[Accident Detection Module (Option B)]
    
    SpeedTracker --> Violations[Violation & Event Manager]
    HelmetClassifier --> Violations
    AccidentDetector --> Violations
    
    Violations --> Screenshot[Screenshot Taker & Saver]
    Violations --> FastAPI[FastAPI Backend Server]
    
    FastAPI --> DB[(SQLite Database)]
    FastAPI --> WS[WebSocket Server]
    
    WS --> React[React Dashboard]
    React --> Display[Charts, Logs, Live Feed & Violation Screenshots]
```

---

## ✨ Core Features

1. **🚗 Unique Vehicle Tracking & Counting**: Uses YOLOv8 object detection coupled with the **ByteTrack** tracking algorithm to identify vehicles (cars, motorcycles, buses, trucks) and assign persistent IDs, preventing double-counting.
2. **⛑️ Real-Time Helmet Detection**: Isolates motorcycle riders, crops their head bounds, and runs an inference pass. Riders without helmets are annotated with **red visual bounding boxes**, and screenshots of the infraction are logged.
3. **⚡ Speed Calibration & Estimation**: Tracks pixel movement across two virtual lines (calibration gates). Computes velocity in km/h based on frames elapsed. Flags overspeeding and captures evidence.
4. **💥 Accident & Collision Alerts**: Employs an accident classifier model (`accident-yolov8s.pt`) to scan frame segments for visual collision indicators, generating instant dashboard alerts with screenshots and synthesizer siren sounds.
5. **📊 Cyber-Style Web Dashboard**: Glassmorphic, dark-mode monitoring center built in React showing:
   - Live annotated camera feed stream.
   - Real-time stats cards with vehicle counts.
   - Live chronologically scrolling violations log with zoomable screenshot attachments.
   - Statistical charts (vehicle breakdown and violation frequency).

---

## 📦 Requirements & Storage Footprint

This project runs **GPU-Accelerated (CUDA)** on the local **NVIDIA RTX 3050** to handle multiple model inferences at 30+ FPS.

### Storage Breakdown
| Component | Library/Model | Size (Approx) |
| :--- | :--- | :--- |
| **Deep Learning Framework** | PyTorch + CUDA 12.1 Wheels | **~2.5 GB** |
| **Computer Vision Core** | Ultralytics (YOLOv8) + OpenCV | **~105 MB** |
| **Object Detection Weights** | YOLOv8s COCO Weights (`yolov8s.pt`) | **~22.5 MB** |
| **Violation Weights** | Helmet Detector (`helmet_yolov8n.pt`) | **~6 MB** |
| **Collision Weights** | Accident Detector (`accident-yolov8s.pt`) | **~22.5 MB** |
| **Web Server Stack** | FastAPI + Uvicorn + WebSockets | **~30 MB** |
| **Frontend Node Packages** | React + Recharts + Lucide Icons | **~250 MB** |
| **Total Disk Space Needed** | — | **~2.9 GB - 3.2 GB** |

---

## 🛠️ Step-by-Step Setup Guide

### 1. Backend Setup
Activate the Python virtual environment and launch the FastAPI server:

```bash
# Clone the repository and navigate inside
cd Smart_Traffic_ML

# Create the virtual environment using Python 3.12
python3.12 -m venv venv
source venv/bin/activate

# Install all packages (PyTorch with CUDA, YOLO, FastAPI, OpenCV, python-multipart, etc.)
pip install -r requirements.txt
```

### 2. Generate the Simulated Traffic Demo Video
A built-in script generates a simulated high-fidelity traffic video to verify the tracking, speed calculation, helmet violations, and accident alerts:

```bash
python backend/generate_demo_video.py
```
This generates `backend/videos/demo_traffic.mp4` with a speeding car, a motorcycle, and a simulated rear-end collision.

### 3. Start the FastAPI Web Server
```bash
uvicorn backend.main:app --reload --port 8000
```
The backend server runs at `http://localhost:8000`.

### 4. Frontend Setup & Run
Open a second terminal window:

```bash
cd frontend
npm install
npm run dev
```
Open your browser and navigate to the dashboard at `http://localhost:5173`.

---

## 🚀 How to Run Analysis
1. Upload a video file through the dashboard or use the generated `demo_traffic.mp4` pre-selected in the dropdown.
2. Click **Analyze Video**.
3. Watch the counts increment, speed limit triggers fire, and helmet violation alerts populate the log.
4. When a collision occurs, a flashing critical banner will appear and a siren audio alert will chime!
5. Click on any violation card's thumbnail to zoom the captured screenshot evidence.
