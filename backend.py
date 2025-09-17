from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from ultralytics import YOLO
import cv2
import threading
import time
import random
import uvicorn
import os
from pathlib import Path

# Initialize FastAPI app
app = FastAPI(title="Smart Traffic Management API", version="1.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Get the directory of the current script
BASE_DIR = Path(__file__).parent

# Initialize YOLO model
MODEL_PATH = BASE_DIR / "yolov8n.pt"
try:
    model = YOLO(str(MODEL_PATH))
    print("✅ YOLO model loaded successfully")
except Exception as e:
    print(f"❌ Error loading YOLO model: {e}")
    model = None

# Video paths - Updated with your actual video files
video_paths = [
    r"C:\Users\HP\OneDrive\Desktop\sih\backend\Untitled video - Made with Clipchamp.mp4",
    r"C:\Users\HP\OneDrive\Desktop\sih\backend\WhatsApp Video 2025-09-16 at 12.27.13_520b86cf.mp4"
]

# Configuration
vehicle_names = ["car", "motorbike", "bus", "truck"]
vehicle_emission = {"car": 0.34, "motorbike": 0.15, "bus": 1.0, "truck": 1.5}
BOTTLENECK_THRESHOLD = 25

# Global variables
metrics = [
    {
        "vehicles": 0,
        "status": "Low",
        "signal_time": 20,
        "waiting_time": 0,
        "co2": 0,
        "bottleneck": "No"
    } for _ in video_paths
]

yield_frame = [None for _ in video_paths]
processing_threads = []

def get_density_label(count):
    """Classify traffic density based on vehicle count"""
    if count < 10:
        return "Low"
    elif 10 <= count < 25:
        return "Medium"
    else:
        return "High"

def process_video(idx, path):
    """Process video for vehicle detection and metrics calculation"""
    if not os.path.exists(path):
        print(f"❌ Video file not found: {path}")
        return
    
    if model is None:
        print(f"❌ YOLO model not available for processing video {idx}")
        return

    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        print(f"❌ Error: Could not open video {path}")
        return

    print(f"✅ Started processing video {idx}: {os.path.basename(path)}")
    waiting_time, current_green = 0, 20

    while True:
        ret, frame = cap.read()
        if not ret:
            # Loop the video
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            continue

        try:
            # Resize frame for processing
            frame_resized = cv2.resize(frame, (640, 360))
            results = model(frame_resized, verbose=False)
            vehicle_count, co2_reduction = 0, 0

            if results and results[0].boxes is not None:
                h_ratio = frame.shape[0] / 360
                w_ratio = frame.shape[1] / 640

                for box in results[0].boxes:
                    cls_id = int(box.cls.cpu().numpy()[0])
                    cls_name = model.names[cls_id].lower()

                    if cls_name in vehicle_names:
                        vehicle_count += 1
                        
                        # Draw bounding box
                        x1, y1, x2, y2 = map(int, box.xyxy[0].cpu().numpy())
                        x1, x2 = int(x1 * w_ratio), int(x2 * w_ratio)
                        y1, y2 = int(y1 * h_ratio), int(y2 * h_ratio)
                        conf = float(box.conf.cpu().numpy()[0])

                        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                        cv2.putText(
                            frame,
                            f"{cls_name} {conf:.2f}",
                            (x1, y1 - 5),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.6,
                            (0, 255, 0),
                            2
                        )

                        # Calculate dynamic signal timing
                        waiting_time = min(waiting_time + random.randint(2, 5), 50)
                        base_time, alpha, beta = 20, 1, 0.5
                        target_green = max(20, min(int(base_time + alpha * vehicle_count + beta * waiting_time), 90))
                        current_green = current_green + 0.2 * (target_green - current_green)

                        # Calculate CO2 reduction
                        time_saved_ratio = max(0, (int(current_green) - 20) / int(current_green))
                        co2_reduction += vehicle_emission[cls_name] * time_saved_ratio

            # Update metrics
            density_status = get_density_label(vehicle_count)
            bottleneck = "Yes" if vehicle_count >= BOTTLENECK_THRESHOLD else "No"

            metrics[idx] = {
                "vehicles": vehicle_count,
                "status": density_status,
                "signal_time": int(current_green),
                "waiting_time": waiting_time,
                "co2": round(co2_reduction, 2),
                "bottleneck": bottleneck
            }

            yield_frame[idx] = frame

        except Exception as e:
            print(f"❌ Error processing frame for video {idx}: {e}")

        time.sleep(0.05)  # Control processing speed

def mjpeg_generator(idx):
    """Generate MJPEG stream for video feed"""
    while True:
        frame = yield_frame[idx]
        if frame is not None:
            try:
                _, buffer = cv2.imencode(".jpg", frame)
                frame_bytes = buffer.tobytes()
                yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n")
            except Exception as e:
                print(f"❌ Error encoding frame for video {idx}: {e}")
        time.sleep(0.05)

@app.get("/")
def root():
    """Root endpoint"""
    return {
        "message": "Smart Traffic Management System API",
        "version": "1.0.0",
        "status": "active",
        "endpoints": {
            "video_feed": "/video/{video_id}",
            "metrics": "/metrics",
            "health": "/health"
        }
    }

@app.get("/health")
def health_check():
    """Health check endpoint"""
    video_status = []
    for i, path in enumerate(video_paths):
        video_status.append({
            "video_id": i + 1,
            "path": os.path.basename(path),
            "exists": os.path.exists(path),
            "processing": yield_frame[i] is not None
        })
    
    return {
        "status": "healthy" if model is not None else "degraded",
        "model_loaded": model is not None,
        "videos": video_status,
        "active_threads": len([t for t in processing_threads if t.is_alive()])
    }

@app.get("/video/{video_id}")
def video_feed(video_id: int):
    """Stream video feed with vehicle detection"""
    if not 1 <= video_id <= len(video_paths):
        raise HTTPException(status_code=404, detail=f"Video {video_id} not found")
    
    if not os.path.exists(video_paths[video_id - 1]):
        raise HTTPException(status_code=404, detail=f"Video file not found: {video_paths[video_id - 1]}")
    
    return StreamingResponse(
        mjpeg_generator(video_id - 1),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )

@app.get("/metrics")
def get_metrics():
    """Get current traffic metrics for all locations"""
    return {
        "timestamp": time.time(),
        "locations": metrics,
        "summary": {
            "total_vehicles": sum(m["vehicles"] for m in metrics),
            "active_bottlenecks": sum(1 for m in metrics if m["bottleneck"] == "Yes"),
            "average_waiting_time": sum(m["waiting_time"] for m in metrics) / len(metrics) if metrics else 0,
            "total_co2_reduction": sum(m["co2"] for m in metrics)
        }
    }

@app.on_event("startup")
def startup_event():
    """Initialize video processing threads on startup"""
    global processing_threads
    
    print("🚀 Starting Smart Traffic Management System...")
    
    # Verify video files exist
    for i, video_path in enumerate(video_paths):
        if os.path.exists(video_path):
            print(f"✅ Video {i+1} found: {os.path.basename(video_path)}")
        else:
            print(f"❌ Video {i+1} not found: {video_path}")
    
    # Start processing threads
    for i, video_path in enumerate(video_paths):
        if os.path.exists(video_path):
            thread = threading.Thread(
                target=process_video,
                args=(i, video_path),
                daemon=True,
                name=f"VideoProcessor-{i}"
            )
            thread.start()
            processing_threads.append(thread)
            print(f"✅ Started processing thread for video {i+1}")

@app.on_event("shutdown")
def shutdown_event():
    """Cleanup on shutdown"""
    print("🛑 Shutting down Smart Traffic Management System...")

if __name__ == "__main__":
    uvicorn.run(
        "backend:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        log_level="info"
    )
