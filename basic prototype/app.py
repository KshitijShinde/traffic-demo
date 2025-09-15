import cv2
import csv
import datetime
import os
from ultralytics import YOLO
#import requests  # Uncomment if you want SMS via Textlocal

# -----------------------------
# ⚡ SMS/WhatsApp Alert Setup (Optional)
# -----------------------------
# API_KEY = "YOUR_TEXTLOCAL_API_KEY"
# SENDER = "TXTLCL"
# TO_NUMBER = "91XXXXXXXXXX"

# def notify_user_sms(message):
#     try:
#         url = "https://api.textlocal.in/send/"
#         payload = {
#             'apikey': API_KEY,
#             'numbers': TO_NUMBER,
#             'sender': SENDER,
#             'message': message
#         }
#         response = requests.post(url, data=payload)
#         print("[SMS sent]", response.json())
#     except Exception as e:
#         print("[SMS error]", e)

# -----------------------------
# ⚡ Load YOLOv5 model
# -----------------------------
model = YOLO("yolov5s.pt")

# -----------------------------
# ⚡ Load traffic video
# -----------------------------
cap = cv2.VideoCapture(r"C:\Users\HP\OneDrive\Desktop\sih\Untitled video - Made with Clipchamp.mp4")

# -----------------------------
# ⚡ CSV logging setup
# -----------------------------
csv_file = "traffic_log.csv"
if not os.path.exists(csv_file):
    with open(csv_file, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Timestamp", "Vehicle_Count", "Traffic_Status", "Signal_Green_Time"])

# -----------------------------
# ⚡ Functions for traffic density & signal timing
# -----------------------------
def get_density_label(vehicle_count):
    if vehicle_count < 10:
        return "Low Traffic"
    elif 10 <= vehicle_count < 25:
        return "Medium Traffic"
    else:
        return "High Traffic - Congestion Alert!"

def get_signal_time(density_status):
    if "High" in density_status:
        return 60
    elif "Medium" in density_status:
        return 40
    else:
        return 20

notify_interval = 150  # Optional: send SMS every 150 frames
frame_count = 0

# -----------------------------
# ⚡ Main loop
# -----------------------------
while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break

    frame_count += 1

    # YOLO inference
    results = model(frame, verbose=False)
    detections = results[0].boxes.data.cpu().numpy()  # [x1, y1, x2, y2, conf, cls]

    vehicle_classes = [2, 3, 5, 7]  # car, motorcycle, bus, truck
    vehicle_count = 0

    for det in detections:
        x1, y1, x2, y2, conf, cls_id = det
        cls_id = int(cls_id)
        if cls_id in vehicle_classes:
            vehicle_count += 1
            cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2)
            cv2.putText(frame, f"Vehicle {conf:.2f}", (int(x1), int(y1) - 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

    density_status = get_density_label(vehicle_count)
    green_time = get_signal_time(density_status)

    # Annotate frame
    cv2.putText(frame, f"Vehicles: {vehicle_count}", (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
    cv2.putText(frame, f"Traffic: {density_status}", (20, 80),
                cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 0), 2)
    cv2.putText(frame, f"Green Signal: {green_time}s", (20, 120),
                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

    cv2.imshow("Traffic Density Detection", frame)

    # Save to CSV
    with open(csv_file, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([datetime.datetime.now(), vehicle_count, density_status, green_time])

    # Console log
    print(f"[{datetime.datetime.now()}] Vehicles={vehicle_count}, Status={density_status}, Green={green_time}s")

    # Optional SMS
    # if "High" in density_status and frame_count % notify_interval == 0:
    #     msg = f"🚨 High Traffic Alert! Vehicles: {vehicle_count}, Green Signal: {green_time}s."
    #     notify_user_sms(msg)

    if cv2.waitKey(30) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
