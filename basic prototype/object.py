import cv2
from ultralytics import YOLO
import os

# ---------------------------
# Load YOLOv8 model (pretrained on COCO dataset)
# ---------------------------
# COCO has vehicle classes: car, bus, truck, motorcycle, bicycle
model = YOLO("yolov8n.pt")  # you can also use yolov8s.pt for better accuracy

# ---------------------------
# Video input/output
# ---------------------------
video_path = r"C:\Users\HP\OneDrive\Desktop\sih\WhatsApp Video 2025-09-13 at 09.51.56_470528c0.mp4"  # <-- replace with your video

# Check if file exists
if not os.path.exists(video_path):
    raise FileNotFoundError(f"⚠️ Video file not found: {video_path}")

cap = cv2.VideoCapture(video_path)

if not cap.isOpened():
    raise RuntimeError("❌ Could not open video. Check path or codec.")

# Save output video
fourcc = cv2.VideoWriter_fourcc(*"mp4v")
out = cv2.VideoWriter(
    "vehicle_detection_output.mp4",
    fourcc,
    int(cap.get(cv2.CAP_PROP_FPS)),
    (int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)))
)

# ---------------------------
# Vehicle classes in COCO
# ---------------------------
vehicle_classes = ["car", "bus", "truck", "motorbike", "bicycle"]

# ---------------------------
# Processing loop
# ---------------------------
while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break

    # Run YOLO inference
    results = model(frame, verbose=False)

    for r in results:
        boxes = r.boxes
        for box in boxes:
            cls_id = int(box.cls[0])
            label = model.names[cls_id]

            if label in vehicle_classes:
                # Get coordinates
                x1, y1, x2, y2 = map(int, box.xyxy[0])

                # Draw bounding box
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)

                # Label
                cv2.putText(
                    frame, label, (x1, y1 - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2
                )

    # Show live preview
    cv2.imshow("Vehicle Detection", frame)

    # Write output video
    out.write(frame)

    # Press Q to quit
    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

# ---------------------------
# Cleanup
# ---------------------------
cap.release()
out.release()
cv2.destroyAllWindows()
