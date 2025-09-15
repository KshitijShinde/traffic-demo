import cv2
import torch
from ultralytics import YOLO
import time
import math


VIDEO_PATH = r"C:\Users\HP\OneDrive\Desktop\sih\WhatsApp Video 2025-09-13 at 09.51.56_470528c0.mp4"  
OUTPUT_PATH = "dataset/output/vid2_output.mp4"

IMG_SIZE = 416      
FRAME_SKIP = 1   
ROI_FRACTION = 0.7

PPM = 10  # pixels per meter (adjust based real life width of the roads)


vehicle_classes = ["car", "bus", "truck", "motorbike", "bicycle"]

model = YOLO("yolov8s.pt")       
device = "cuda" if torch.cuda.is_available() else "cpu"
model.to(device)


cap = cv2.VideoCapture(VIDEO_PATH)
fps = int(cap.get(cv2.CAP_PROP_FPS))
width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

fourcc = cv2.VideoWriter_fourcc(*"mp4v")
out = cv2.VideoWriter(OUTPUT_PATH, fourcc, fps, (width, height))


vehicle_tracks = {}  
next_vehicle_id = 0
frame_count = 0


while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break

    frame_count += 1
    if frame_count % FRAME_SKIP != 0:
        out.write(frame)
        continue

    roi_start = int(height * (1 - ROI_FRACTION))
    roi = frame[roi_start:, :]

    start_time = time.time()
    results = model(roi, imgsz=IMG_SIZE, conf = 0.3,verbose=False)
    end_time = time.time()
    print(f"Inference time: {(end_time - start_time) * 1000:.2f} ms")

    detections = []
    for r in results:
        for box in r.boxes:
            cls_id = int(box.cls[0])
            label = model.names[cls_id]
            if label in vehicle_classes:
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                y1 += roi_start
                y2 += roi_start
                cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
                detections.append((cx, cy, (x1, y1, x2, y2), label))


    updated_tracks = {}
    for cx, cy, bbox, label in detections:
        matched_id = None
        min_dist = 50  # threshold to match vehicle
        for vid, history in vehicle_tracks.items():
            prev_cx, prev_cy, prev_frame = history[-1]
            dist = math.hypot(cx - prev_cx, cy - prev_cy)
            if dist < min_dist:
                min_dist = dist
                matched_id = vid

        if matched_id is None:
            matched_id = next_vehicle_id
            next_vehicle_id += 1
            vehicle_tracks[matched_id] = []

        vehicle_tracks[matched_id].append((cx, cy, frame_count))
        updated_tracks[matched_id] = vehicle_tracks[matched_id]


        speed_text = ""
        if len(vehicle_tracks[matched_id]) >= 2:
            (x1_c, y1_c, f1), (x2_c, y2_c, f2) = vehicle_tracks[matched_id][-2], vehicle_tracks[matched_id][-1]
            dist_pixels = math.hypot(x2_c - x1_c, y2_c - y1_c)
            time_elapsed = (f2 - f1) / fps
            if time_elapsed > 0:
                speed_mps = (dist_pixels / PPM) / time_elapsed
                speed_kmph = speed_mps * 3.6
                speed_text = f"{speed_kmph:.1f} km/h"


        x1, y1, x2, y2 = bbox
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.putText(frame, f"ID:{matched_id}", (x1, y1 - 25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
        if speed_text:
            cv2.putText(frame, speed_text, (x1, y2 + 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

    vehicle_tracks = updated_tracks


    cv2.imshow("YOLOv8 Low-Latency Detection + Speed", frame)
    out.write(frame)

    if cv2.waitKey(1) & 0xFF == 27: 
        break

cap.release()
out.release()
cv2.destroyAllWindows()