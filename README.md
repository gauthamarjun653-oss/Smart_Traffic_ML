# Smart Traffic Management System

An AI-powered traffic monitoring dashboard that processes video feeds to count unique vehicles, detect traffic violations (overspeeding, no-helmet riding), and alert on traffic accidents/anomalies in real-time.

## System Architecture & Features

1. **Unique Vehicle Counting**: Detects and tracks vehicles (cars, motorbikes, buses, trucks) across video frames using YOLOv8 & a tracking algorithm (e.g., ByteTrack), preventing double-counting.
2. **Helmet Detection**: Identifies motorcycle riders and checks if they are wearing helmets. Saves screenshot of violations.
3. **Speed Estimation**: Uses Region of Interest (ROI) / virtual lines to track vehicle travel times and compute speeds, triggering alerts and screenshots for overspeeding.
4. **Accident Detection**: Heuristic detection of collisions or sudden halts in active traffic zones, firing real-time alerts.
5. **Real-time Monitoring Dashboard**: Web-based interface displaying live counts, violation feeds, and screenshots.

---

## Technical Requirements & Storage Size

Below are the approximate download/installation storage requirements for the project:

### 1. Computer Vision & ML Core
* **PyTorch (Deep Learning Framework)**
  * *CPU-only version:* **~250 MB**
  * *CUDA/GPU version:* **~2.5 GB**
* **Ultralytics (YOLOv8)**: **~15 MB**
* **OpenCV (`opencv-python`)**: **~90 MB**
* **Model Weights**
  * YOLOv8 Object Detection Weights (`yolov8s.pt` or `yolov8n.pt`): **~6 MB to ~23 MB**
  * Helmet Detection Model Weights: **~10 MB to ~30 MB**
* **EasyOCR (Optional)**: **~120 MB** (Library + Model weights)

### 2. Backend Server & Database
* **FastAPI, Uvicorn, & WebSockets**: **~30 MB**
* **SQLite Database**: **Built-in** (No extra storage)

### 3. Frontend Dashboard
* **Node.js, React, & Node Modules**: **~200 MB to ~300 MB**

### Summary of Total Storage Required
* **Without GPU acceleration (CPU-only execution):** **~700 MB - 900 MB**
* **With GPU acceleration (NVIDIA CUDA):** **~3.0 GB - 3.5 GB**

---

## Queries & Doubts (Clarifications Needed)

To kick off the implementation, please let us know:
1. **CPU or GPU Execution**: Should we build the system to run on **CPU** or do you have a CUDA-enabled **NVIDIA GPU** we can configure PyTorch to use?
2. **Helmet Detection**: Should we download a pre-trained YOLOv8 helmet detection model weight, or implement a heuristic (person + motorcycle overlap)?
3. **Speed Estimation ROI**: Do you want speed tracking to use default coordinates configured in code, or should we make it adjustable?
4. **Accident Detection Logic**: Are you comfortable with our heuristic approach (bounding box collision, sudden decelerations to 0, stationary vehicle alerts), or did you have a specific machine learning model in mind?
