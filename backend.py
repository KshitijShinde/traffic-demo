from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import StreamingResponse, JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from ultralytics import YOLO
import cv2
import threading
import time
import random
import uvicorn
import os
import sqlite3
import hashlib
import jwt
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, List
from pydantic import BaseModel
import numpy as np
import math

# Initialize FastAPI app
app = FastAPI(title="Smart Traffic Management API with EcoCoin & GPS", version="3.2.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security
security = HTTPBearer()
JWT_SECRET = "your-secret-key-change-in-production"
JWT_ALGORITHM = "HS256"

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

# Video paths
video_paths = [
    r"C:\Users\HP\Downloads\videoplayback (1).mp4",
    r"C:\Users\HP\OneDrive\Desktop\sih\backend\videoplayback (1).mp4"
]

# Configuration
vehicle_names = ["car", "motorbike", "bus", "truck"]
vehicle_emission = {"car": 0.34, "motorbike": 0.15, "bus": 1.0, "truck": 1.5}

TRAFFIC_THRESHOLDS = {
    "low": 8,
    "medium": 20,
    "high": 999
}

BOTTLENECK_THRESHOLD = 25

SIGNAL_CONFIG = {
    "min_green": 20,
    "max_green": 60,
    "base_green": 30,
    "red_time": 25,
    "vehicle_increment": 1.5,
    "max_waiting_penalty": 15
}

# EcoCoin Configuration - FIXED: Removed automatic generation based on metrics
ECOCOIN_RATES = {
    "co2_reduction_per_kg": 10,
    "metro_discount_rate": 0.1,
    "bus_discount_rate": 0.15,
    "parking_discount_rate": 0.05,
    "fuel_subsidy_rate": 0.02,
    "green_transport_bonus": 50,
    "traffic_efficiency_bonus": 20,
    # NEW: Formula for user trip rewards
    "base_ecocoin_per_km": 2,  # Base 2 EcoCoins per km
    "time_efficiency_multiplier": 1.5,  # Bonus for time efficiency
    "eco_transport_multiplier": {
        "walk": 5.0,
        "bike": 4.0,  
        "metro": 3.0,
        "bus": 2.5,
        "motorbike": 1.2,
        "car": 1.0
    }
}

GOVERNMENT_SERVICES = {
    "metro": {"base_price": 20, "max_discount": 50},
    "bus": {"base_price": 15, "max_discount": 40},
    "parking": {"base_price": 100, "max_discount": 30},
    "fuel_subsidy": {"base_price": 80, "max_discount": 20},
    "toll_tax": {"base_price": 50, "max_discount": 25},
    "vehicle_registration": {"base_price": 1000, "max_discount": 10},
    "pollution_certificate": {"base_price": 200, "max_discount": 30}
}

# Camera locations with actual coordinates (you can update these to real locations)
CAMERA_LOCATIONS = {
    1: {"lat": 28.6139, "lng": 77.2090, "name": "Delhi Junction", "address": "Connaught Place, New Delhi"},
    2: {"lat": 28.6304, "lng": 77.2177, "name": "CP Metro Station", "address": "Rajiv Chowk, New Delhi"}
}

# Pydantic Models
class UserRegistration(BaseModel):
    username: str
    email: str
    phone: str
    password: str
    vehicle_type: str = "car"

class UserLogin(BaseModel):
    username: str
    password: str

class TripData(BaseModel):
    user_id: int
    start_location: str
    end_location: str
    distance_km: float
    duration_minutes: int
    transport_mode: str
    route_efficiency: float = 1.0

class RouteRequest(BaseModel):
    start_lat: float
    start_lng: float
    end_lat: float
    end_lng: float
    start_address: str = ""
    end_address: str = ""

class EcoCoinTransaction(BaseModel):
    user_id: int
    transaction_type: str
    amount: int
    description: str
    service_type: Optional[str] = None

# Enhanced Global variables
class LocationMetrics:
    def __init__(self):
        self.vehicles = 0
        self.status = "Low"
        self.signal_time = SIGNAL_CONFIG["base_green"]
        self.waiting_time = 0
        self.co2 = 0.0
        self.bottleneck = "No"
        # REMOVED: ecocoins_generated - no longer auto-generated
        self.vehicle_history = []
        self.last_update = time.time()
        self.detection_confidence = 0.0
        self.signal_cycle_start = time.time()
        self.is_green_phase = True

# Initialize location metrics
location_metrics = [LocationMetrics() for _ in video_paths]
yield_frame = [None for _ in video_paths]
processing_threads = []

# Database functions
def init_database():
    conn = sqlite3.connect('ecocoin_system.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            phone TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            vehicle_type TEXT DEFAULT 'car',
            ecocoin_balance INTEGER DEFAULT 0,
            total_co2_saved REAL DEFAULT 0.0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            transaction_type TEXT NOT NULL,
            amount INTEGER NOT NULL,
            description TEXT,
            service_type TEXT,
            co2_saved REAL DEFAULT 0.0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS trips (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            start_location TEXT,
            end_location TEXT,
            distance_km REAL,
            duration_minutes INTEGER,
            transport_mode TEXT,
            route_efficiency REAL,
            co2_saved REAL,
            ecocoins_earned INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS service_redemptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            service_type TEXT,
            original_price REAL,
            discount_amount REAL,
            final_price REAL,
            ecocoins_used INTEGER,
            redemption_code TEXT,
            status TEXT DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    conn.commit()
    conn.close()
    print("✅ EcoCoin database initialized successfully")

init_database()

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def create_jwt_token(user_id: int, username: str) -> str:
    payload = {
        "user_id": user_id,
        "username": username,
        "exp": datetime.utcnow() + timedelta(hours=24)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def verify_jwt_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

def calculate_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Calculate distance between two points using Haversine formula"""
    R = 6371  # Earth's radius in kilometers
    
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lng = math.radians(lng2 - lng1)
    
    a = (math.sin(delta_lat / 2) ** 2 + 
         math.cos(lat1_rad) * math.cos(lat2_rad) * 
         math.sin(delta_lng / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    return R * c

def estimate_travel_time(distance_km: float, transport_mode: str, traffic_condition: str = "Medium") -> int:
    """Estimate travel time based on distance, transport mode, and traffic"""
    # Average speeds in km/h for different transport modes
    base_speeds = {
        "walk": 5,
        "bike": 15,
        "motorbike": 25,
        "car": 30,
        "bus": 20,
        "metro": 35
    }
    
    # Traffic impact multipliers
    traffic_multipliers = {
        "Low": 1.0,
        "Medium": 1.3,
        "High": 1.8
    }
    
    base_speed = base_speeds.get(transport_mode, 30)
    traffic_multiplier = traffic_multipliers.get(traffic_condition, 1.3)
    
    # Calculate time considering traffic
    effective_speed = base_speed / traffic_multiplier
    time_hours = distance_km / effective_speed
    time_minutes = int(time_hours * 60)
    
    return max(time_minutes, 5)  # Minimum 5 minutes

def calculate_user_ecocoins(distance_km: float, actual_time_minutes: int, estimated_time_minutes: int, transport_mode: str) -> Dict:
    """NEW: Calculate EcoCoins for user based on actual trip data"""
    
    # Base EcoCoins per km
    base_coins = distance_km * ECOCOIN_RATES["base_ecocoin_per_km"]
    
    # Transport mode multiplier
    transport_multiplier = ECOCOIN_RATES["eco_transport_multiplier"].get(transport_mode, 1.0)
    
    # Time efficiency bonus/penalty
    if estimated_time_minutes > 0:
        time_efficiency = estimated_time_minutes / max(actual_time_minutes, 1)
        if time_efficiency > 1.2:  # Completed trip 20% faster than estimated
            time_bonus = base_coins * 0.5  # 50% bonus
        elif time_efficiency > 1.0:  # Completed faster
            time_bonus = base_coins * 0.2  # 20% bonus
        elif time_efficiency > 0.8:  # Normal time
            time_bonus = 0
        else:  # Took longer than expected
            time_bonus = -base_coins * 0.1  # 10% penalty
    else:
        time_bonus = 0
    
    # Calculate total EcoCoins
    total_coins = int((base_coins * transport_multiplier) + time_bonus)
    
    # Minimum 1 EcoCoin per trip
    total_coins = max(total_coins, 1)
    
    # Calculate CO2 saved
    co2_saved = calculate_co2_savings(distance_km, transport_mode)
    
    return {
        "ecocoins_earned": total_coins,
        "base_coins": int(base_coins),
        "transport_multiplier": transport_multiplier,
        "time_bonus": int(time_bonus),
        "co2_saved": co2_saved,
        "formula_explanation": f"Base ({int(base_coins)}) × Transport ({transport_multiplier}) + Time Bonus ({int(time_bonus)}) = {total_coins}"
    }

def calculate_co2_savings(distance_km: float, transport_mode: str) -> float:
    """Calculate CO2 savings compared to car"""
    emission_factors = {
        "car": 0.21, "motorbike": 0.11, "bus": 0.08, "metro": 0.04,
        "bike": 0.0, "walk": 0.0
    }
    
    car_emission = distance_km * emission_factors["car"]
    actual_emission = distance_km * emission_factors.get(transport_mode, emission_factors["car"])
    co2_saved = max(0, car_emission - actual_emission)
    
    return co2_saved

def get_cameras_on_route(start_lat: float, start_lng: float, end_lat: float, end_lng: float, radius: float = 10.0) -> List[Dict]:
    """Get cameras within radius of the route"""
    cameras_on_route = []
    
    for camera_id, camera_info in CAMERA_LOCATIONS.items():
        start_distance = calculate_distance(start_lat, start_lng, camera_info["lat"], camera_info["lng"])
        end_distance = calculate_distance(end_lat, end_lng, camera_info["lat"], camera_info["lng"])
        
        # Check if camera is on route (within radius of start, end, or route path)
        if start_distance <= radius or end_distance <= radius:
            if camera_id - 1 < len(location_metrics):
                current_metrics = location_metrics[camera_id - 1]
                camera_data = {
                    "id": camera_id,
                    "lat": camera_info["lat"],
                    "lng": camera_info["lng"],
                    "name": camera_info["name"],
                    "address": camera_info["address"],
                    "traffic_status": current_metrics.status,
                    "vehicle_count": current_metrics.vehicles,
                    "signal_time": current_metrics.signal_time,
                    "bottleneck": current_metrics.bottleneck == "Yes",
                    "distance_from_start": round(start_distance, 2),
                    "distance_from_end": round(end_distance, 2)
                }
                cameras_on_route.append(camera_data)
    
    return cameras_on_route

def calculate_co2_emissions(distance_km: float, transport_mode: str, duration_minutes: int) -> Dict:
    emission_factors = {
        "car": 0.21, "motorbike": 0.11, "bus": 0.08, "metro": 0.04,
        "bike": 0.0, "walk": 0.0
    }
    
    base_car_emission = distance_km * emission_factors["car"]
    actual_emission = distance_km * emission_factors.get(transport_mode, emission_factors["car"])
    co2_saved = max(0, base_car_emission - actual_emission)
    
    if duration_minutes > 0:
        efficiency_factor = max(0.5, min(1.5, 60 / duration_minutes))
        co2_saved *= efficiency_factor
    
    return {
        "actual_emission": actual_emission,
        "baseline_emission": base_car_emission,
        "co2_saved": co2_saved,
        "efficiency_factor": efficiency_factor if 'efficiency_factor' in locals() else 1.0
    }

def calculate_ecocoins(co2_saved: float, transport_mode: str, route_efficiency: float) -> int:
    base_coins = int(co2_saved * ECOCOIN_RATES["co2_reduction_per_kg"])
    
    mode_multipliers = {
        "walk": 2.0, "bike": 1.8, "metro": 1.5, "bus": 1.3,
        "motorbike": 1.1, "car": 1.0
    }
    
    multiplier = mode_multipliers.get(transport_mode, 1.0)
    efficiency_bonus = max(0, (2.0 - route_efficiency) * 0.5)
    
    total_coins = int(base_coins * multiplier * (1 + efficiency_bonus))
    
    if transport_mode in ["walk", "bike", "metro", "bus"]:
        total_coins += ECOCOIN_RATES["green_transport_bonus"]
    
    if route_efficiency < 0.8:
        total_coins += ECOCOIN_RATES["traffic_efficiency_bonus"]
    
    return total_coins

def get_density_label(count):
    if count <= TRAFFIC_THRESHOLDS["low"]:
        return "Low"
    elif count <= TRAFFIC_THRESHOLDS["medium"]:
        return "Medium"
    else:
        return "High"

def calculate_smart_signal_timing(vehicle_count: int, current_waiting_time: int, traffic_history: list) -> Dict:
    base_green = SIGNAL_CONFIG["base_green"]
    min_green = SIGNAL_CONFIG["min_green"]
    max_green = SIGNAL_CONFIG["max_green"]
    vehicle_increment = SIGNAL_CONFIG["vehicle_increment"]
    
    if vehicle_count == 0:
        green_time = min_green
        waiting_time = max(0, current_waiting_time - 2)
    elif vehicle_count <= 5:
        green_time = base_green
        waiting_time = max(0, current_waiting_time - 1)
    elif vehicle_count <= 15:
        extra_time = (vehicle_count - 5) * vehicle_increment
        green_time = base_green + extra_time
        waiting_time = current_waiting_time + random.randint(0, 2)
    else:
        extra_time = 10 * vehicle_increment
        waiting_penalty = min((vehicle_count - 15) * 0.5, SIGNAL_CONFIG["max_waiting_penalty"])
        green_time = base_green + extra_time + waiting_penalty
        waiting_time = current_waiting_time + random.randint(2, 4)
    
    if len(traffic_history) > 3:
        recent_avg = sum(traffic_history[-3:]) / 3
        if recent_avg > 0:
            trend_factor = min(max(vehicle_count / recent_avg, 0.8), 1.2)
            green_time = green_time * trend_factor
    
    green_time = max(min_green, min(green_time, max_green))
    green_time = int(green_time)
    waiting_time = max(0, min(waiting_time, 45))
    
    total_cycle_time = green_time + SIGNAL_CONFIG["red_time"]
    efficiency_ratio = green_time / total_cycle_time
    
    base_emission_per_vehicle = 0.08
    efficiency_factor = min(efficiency_ratio * 1.2, 1.0)
    co2_reduction = vehicle_count * base_emission_per_vehicle * efficiency_factor
    
    if vehicle_count > 10 and green_time < max_green:
        co2_reduction *= 1.1
    
    return {
        "signal_time": green_time,
        "waiting_time": int(waiting_time),
        "co2_reduction": round(co2_reduction, 2),
        "efficiency_ratio": round(efficiency_ratio, 2),
        "cycle_time": total_cycle_time
    }

def process_video(idx, path):
    """Video processing - no changes to detection, just removed ecocoin generation"""
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
    
    fps = int(cap.get(cv2.CAP_PROP_FPS))
    frame_count = 0
    metrics_update_interval = max(1, fps // 3)

    while True:
        ret, frame = cap.read()
        if not ret:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            frame_count = 0
            continue

        frame_count += 1
        current_time = time.time()

        try:
            original_height, original_width = frame.shape[:2]
            target_size = 640
            scale = target_size / max(original_width, original_height)
            new_width = int(original_width * scale)
            new_height = int(original_height * scale)
            
            frame_resized = cv2.resize(frame, (new_width, new_height))
            
            results = model(frame_resized, verbose=False, conf=0.25)
            vehicle_count = 0
            total_confidence = 0

            if results and results[0].boxes is not None and len(results[0].boxes) > 0:
                h_ratio = original_height / new_height
                w_ratio = original_width / new_width

                for box in results[0].boxes:
                    cls_id = int(box.cls.cpu().numpy()[0])
                    cls_name = model.names[cls_id].lower()
                    confidence = float(box.conf.cpu().numpy()[0])

                    if cls_name in vehicle_names and confidence > 0.25:
                        vehicle_count += 1
                        total_confidence += confidence
                        
                        x1, y1, x2, y2 = map(int, box.xyxy[0].cpu().numpy())
                        x1, x2 = int(x1 * w_ratio), int(x2 * w_ratio)
                        y1, y2 = int(y1 * h_ratio), int(y2 * h_ratio)

                        # Green bounding box, no confidence score
                        color = (0, 255, 0)
                        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                        
                        # Only show vehicle type
                        label = f"{cls_name}"
                        label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)[0]
                        cv2.rectangle(frame, (x1, y1 - label_size[1] - 8), 
                                    (x1 + label_size[0], y1), color, -1)
                        cv2.putText(frame, label, (x1, y1 - 4),
                                  cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

            if frame_count % metrics_update_interval == 0:
                location_metrics[idx].vehicle_history.append(vehicle_count)
                if len(location_metrics[idx].vehicle_history) > 10:
                    location_metrics[idx].vehicle_history.pop(0)
                
                signal_data = calculate_smart_signal_timing(
                    vehicle_count,
                    location_metrics[idx].waiting_time,
                    location_metrics[idx].vehicle_history
                )
                
                location_metrics[idx].vehicles = vehicle_count
                location_metrics[idx].status = get_density_label(vehicle_count)
                location_metrics[idx].signal_time = signal_data["signal_time"]
                location_metrics[idx].waiting_time = signal_data["waiting_time"]
                location_metrics[idx].co2 = signal_data["co2_reduction"]
                location_metrics[idx].bottleneck = "Yes" if vehicle_count >= BOTTLENECK_THRESHOLD else "No"
                location_metrics[idx].last_update = current_time
                location_metrics[idx].detection_confidence = round(total_confidence / max(vehicle_count, 1), 2) if vehicle_count > 0 else 0.0

            yield_frame[idx] = frame

        except Exception as e:
            print(f"❌ Error processing frame for video {idx}: {e}")
            continue

        time.sleep(0.033)

def generate_frames(video_idx):
    while True:
        try:
            frame = yield_frame[video_idx]
            if frame is not None:
                encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 85]
                ret, buffer = cv2.imencode('.jpg', frame, encode_param)
                if ret:
                    frame_bytes = buffer.tobytes()
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
            time.sleep(0.033)
        except Exception as e:
            print(f"❌ Error in frame generation for video {video_idx}: {e}")
            time.sleep(0.1)

# API Endpoints
@app.post("/api/register")
def register_user(user: UserRegistration):
    conn = sqlite3.connect('ecocoin_system.db')
    cursor = conn.cursor()
    
    try:
        password_hash = hash_password(user.password)
        cursor.execute("""
            INSERT INTO users (username, email, phone, password_hash, vehicle_type)
            VALUES (?, ?, ?, ?, ?)
        """, (user.username, user.email, user.phone, password_hash, user.vehicle_type))
        
        user_id = cursor.lastrowid
        conn.commit()
        
        cursor.execute("""
            INSERT INTO transactions (user_id, transaction_type, amount, description)
            VALUES (?, 'earn', 100, 'Welcome bonus')
        """, (user_id,))
        
        cursor.execute("UPDATE users SET ecocoin_balance = 100 WHERE id = ?", (user_id,))
        conn.commit()
        
        token = create_jwt_token(user_id, user.username)
        
        return {
            "message": "User registered successfully",
            "user_id": user_id,
            "token": token,
            "welcome_bonus": 100
        }
    
    except sqlite3.IntegrityError as e:
        raise HTTPException(status_code=400, detail="Username, email, or phone already exists")
    finally:
        conn.close()

@app.post("/api/login")
def login_user(user: UserLogin):
    conn = sqlite3.connect('ecocoin_system.db')
    cursor = conn.cursor()
    
    password_hash = hash_password(user.password)
    cursor.execute("""
        SELECT id, username, ecocoin_balance FROM users 
        WHERE username = ? AND password_hash = ?
    """, (user.username, password_hash))
    
    user_data = cursor.fetchone()
    conn.close()
    
    if not user_data:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    user_id, username, balance = user_data
    token = create_jwt_token(user_id, username)
    
    return {
        "message": "Login successful",
        "token": token,
        "user_id": user_id,
        "username": username,
        "ecocoin_balance": balance
    }

@app.get("/api/user-profile")
def get_user_profile(user_data: dict = Depends(verify_jwt_token)):
    conn = sqlite3.connect('ecocoin_system.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT username, email, phone, vehicle_type, ecocoin_balance, total_co2_saved, created_at
            FROM users WHERE id = ?
        """, (user_data["user_id"],))
        
        user_info = cursor.fetchone()
        
        if not user_info:
            raise HTTPException(status_code=404, detail="User not found")
        
        cursor.execute("""
            SELECT COUNT(*) as trip_count, 
                   COALESCE(SUM(distance_km), 0) as total_distance, 
                   COALESCE(AVG(route_efficiency), 0) as avg_efficiency
            FROM trips WHERE user_id = ?
        """, (user_data["user_id"],))
        
        trip_stats = cursor.fetchone()
        
        cursor.execute("""
            SELECT transaction_type, amount, description, co2_saved, created_at
            FROM transactions WHERE user_id = ? 
            ORDER BY created_at DESC LIMIT 10
        """, (user_data["user_id"],))
        
        recent_transactions = cursor.fetchall()
        
        return {
            "user_info": {
                "username": user_info[0],
                "email": user_info[1],
                "phone": user_info[2],
                "vehicle_type": user_info[3],
                "ecocoin_balance": user_info[4],
                "total_co2_saved": user_info[5] or 0,
                "member_since": user_info[6]
            },
            "statistics": {
                "total_trips": trip_stats[0] or 0,
                "total_distance_km": trip_stats[1] or 0,
                "average_efficiency": trip_stats[2] or 0
            },
            "recent_transactions": [
                {
                    "type": tx[0],
                    "amount": tx[1],
                    "description": tx[2],
                    "co2_saved": tx[3] or 0,
                    "date": tx[4]
                } for tx in recent_transactions
            ]
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        conn.close()

@app.post("/api/record-trip")
def record_trip(trip: TripData, user_data: dict = Depends(verify_jwt_token)):
    """NEW: Enhanced trip recording with improved EcoCoin calculation"""
    conn = sqlite3.connect('ecocoin_system.db')
    cursor = conn.cursor()
    
    # Get estimated time for the trip based on distance and transport mode
    estimated_time = estimate_travel_time(trip.distance_km, trip.transport_mode, "Medium")
    
    # Calculate EcoCoins using new formula
    ecocoin_result = calculate_user_ecocoins(
        trip.distance_km, 
        trip.duration_minutes, 
        estimated_time, 
        trip.transport_mode
    )
    
    ecocoins_earned = ecocoin_result["ecocoins_earned"]
    co2_saved = ecocoin_result["co2_saved"]
    
    try:
        cursor.execute("""
            INSERT INTO trips (user_id, start_location, end_location, distance_km, 
                             duration_minutes, transport_mode, route_efficiency, 
                             co2_saved, ecocoins_earned)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (user_data["user_id"], trip.start_location, trip.end_location, 
              trip.distance_km, trip.duration_minutes, trip.transport_mode, 
              trip.route_efficiency, co2_saved, ecocoins_earned))
        
        cursor.execute("""
            INSERT INTO transactions (user_id, transaction_type, amount, description, co2_saved)
            VALUES (?, 'earn', ?, ?, ?)
        """, (user_data["user_id"], ecocoins_earned, 
              f"Trip: {trip.start_location} → {trip.end_location} via {trip.transport_mode}", 
              co2_saved))
        
        cursor.execute("""
            UPDATE users 
            SET ecocoin_balance = ecocoin_balance + ?, 
                total_co2_saved = total_co2_saved + ?
            WHERE id = ?
        """, (ecocoins_earned, co2_saved, user_data["user_id"]))
        
        conn.commit()
        
        cursor.execute("SELECT ecocoin_balance FROM users WHERE id = ?", (user_data["user_id"],))
        new_balance = cursor.fetchone()[0]
        
        return {
            "message": "Trip recorded successfully",
            "ecocoins_earned": ecocoins_earned,
            "co2_saved": round(co2_saved, 4),
            "new_balance": new_balance,
            "calculation_details": {
                "base_coins": ecocoin_result["base_coins"],
                "transport_multiplier": ecocoin_result["transport_multiplier"],
                "time_bonus": ecocoin_result["time_bonus"],
                "estimated_time_minutes": estimated_time,
                "actual_time_minutes": trip.duration_minutes,
                "formula": ecocoin_result["formula_explanation"]
            }
        }
    
    finally:
        conn.close()

@app.post("/api/get-route-traffic")
def get_route_traffic(route_request: RouteRequest):
    """Enhanced route traffic analysis"""
    try:
        distance = calculate_distance(
            route_request.start_lat, route_request.start_lng,
            route_request.end_lat, route_request.end_lng
        )
        
        cameras_on_route = get_cameras_on_route(
            route_request.start_lat, route_request.start_lng,
            route_request.end_lat, route_request.end_lng
        )
        
        # Calculate overall traffic condition
        total_traffic_score = 0
        high_traffic_segments = 0
        
        for camera in cameras_on_route:
            if camera["traffic_status"] == "High":
                total_traffic_score += 3
                high_traffic_segments += 1
            elif camera["traffic_status"] == "Medium":
                total_traffic_score += 2
            else:
                total_traffic_score += 1
        
        if cameras_on_route:
            avg_traffic_score = total_traffic_score / len(cameras_on_route)
        else:
            avg_traffic_score = 1.5  # Default medium traffic
        
        if avg_traffic_score >= 2.5:
            route_status = "High Traffic"
            route_color = "#dc3545"
            traffic_condition = "High"
        elif avg_traffic_score >= 1.5:
            route_status = "Medium Traffic" 
            route_color = "#ffc107"
            traffic_condition = "Medium"
        else:
            route_status = "Light Traffic"
            route_color = "#28a745"
            traffic_condition = "Low"
        
        # Estimate travel times for different transport modes
        transport_estimates = {}
        for mode in ["car", "motorbike", "bus", "metro", "bike", "walk"]:
            time_estimate = estimate_travel_time(distance, mode, traffic_condition)
            ecocoin_estimate = calculate_user_ecocoins(distance, time_estimate, time_estimate, mode)
            transport_estimates[mode] = {
                "estimated_time_minutes": time_estimate,
                "potential_ecocoins": ecocoin_estimate["ecocoins_earned"],
                "co2_saved": round(ecocoin_estimate["co2_saved"], 4)
            }
        
        alternative_route = None
        if high_traffic_segments > 0:
            alternative_route = {
                "suggestion": "Alternative route available",
                "description": f"Avoid {high_traffic_segments} high-traffic area(s)",
                "estimated_time_saved": f"{high_traffic_segments * 5}-{high_traffic_segments * 10} minutes",
                "potential_ecocoin_bonus": high_traffic_segments * 5
            }
        
        return {
            "route_info": {
                "distance_km": round(distance, 2),
                "status": route_status,
                "status_color": route_color,
                "traffic_score": round(avg_traffic_score, 2),
                "cameras_monitoring": len(cameras_on_route),
                "traffic_condition": traffic_condition
            },
            "cameras_on_route": cameras_on_route,
            "transport_estimates": transport_estimates,
            "alternative_route": alternative_route,
            "route_coordinates": [
                {"lat": route_request.start_lat, "lng": route_request.start_lng},
                {"lat": route_request.end_lat, "lng": route_request.end_lng}
            ]
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Route calculation error: {str(e)}")

@app.get("/api/government-services")
def get_government_services():
    """Get available government services with pricing"""
    return {
        "services": GOVERNMENT_SERVICES,
        "ecocoin_rates": ECOCOIN_RATES
    }

@app.post("/api/redeem-service")
def redeem_service(service_type: str, ecocoins_to_use: int, user_data: dict = Depends(verify_jwt_token)):
    """Redeem EcoCoins for government service discounts"""
    conn = sqlite3.connect('ecocoin_system.db')
    cursor = conn.cursor()
    
    # Check user balance
    cursor.execute("SELECT ecocoin_balance FROM users WHERE id = ?", (user_data["user_id"],))
    balance_result = cursor.fetchone()
    
    if not balance_result:
        raise HTTPException(status_code=404, detail="User not found")
    
    current_balance = balance_result[0]
    
    if current_balance < ecocoins_to_use:
        raise HTTPException(status_code=400, detail="Insufficient EcoCoin balance")
    
    if service_type not in GOVERNMENT_SERVICES:
        raise HTTPException(status_code=400, detail="Invalid service type")
    
    service_info = GOVERNMENT_SERVICES[service_type]
    base_price = service_info["base_price"]
    max_discount_percent = service_info["max_discount"]
    
    # Calculate discount
    if service_type in ["metro", "bus"]:
        discount_rate = ECOCOIN_RATES["metro_discount_rate"] if service_type == "metro" else ECOCOIN_RATES["bus_discount_rate"]
    elif service_type == "parking":
        discount_rate = ECOCOIN_RATES["parking_discount_rate"]
    else:
        discount_rate = 0.05  # Default 5%
    
    discount_amount = min(ecocoins_to_use * discount_rate, base_price * max_discount_percent / 100)
    final_price = max(0, base_price - discount_amount)
    
    # Generate redemption code
    redemption_code = f"ECO{service_type.upper()}{user_data['user_id']}{int(time.time())}"[-12:]
    expires_at = datetime.now() + timedelta(days=30)
    
    try:
        # Record redemption
        cursor.execute("""
            INSERT INTO service_redemptions 
            (user_id, service_type, original_price, discount_amount, final_price, 
             ecocoins_used, redemption_code, expires_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (user_data["user_id"], service_type, base_price, discount_amount, 
              final_price, ecocoins_to_use, redemption_code, expires_at))
        
        # Record transaction
        cursor.execute("""
            INSERT INTO transactions (user_id, transaction_type, amount, description, service_type)
            VALUES (?, 'redeem', ?, ?, ?)
        """, (user_data["user_id"], -ecocoins_to_use, 
              f"Redeemed for {service_type} discount", service_type))
        
        # Update user balance
        cursor.execute("""
            UPDATE users SET ecocoin_balance = ecocoin_balance - ? WHERE id = ?
        """, (ecocoins_to_use, user_data["user_id"]))
        
        conn.commit()
        
        # Get new balance
        cursor.execute("SELECT ecocoin_balance FROM users WHERE id = ?", (user_data["user_id"],))
        new_balance = cursor.fetchone()[0]
        
        return {
            "message": "Service discount redeemed successfully",
            "redemption_code": redemption_code,
            "service_type": service_type,
            "original_price": base_price,
            "discount_amount": discount_amount,
            "final_price": final_price,
            "ecocoins_used": ecocoins_to_use,
            "new_balance": new_balance,
            "expires_at": expires_at.isoformat()
        }
    
    finally:
        conn.close()

@app.get("/api/camera-locations")
def get_camera_locations():
    """Get all camera locations with current traffic data"""
    cameras_with_traffic = []
    
    for camera_id, camera_info in CAMERA_LOCATIONS.items():
        if camera_id - 1 < len(location_metrics):
            current_metrics = location_metrics[camera_id - 1]
            camera_data = {
                "id": camera_id,
                "lat": camera_info["lat"],
                "lng": camera_info["lng"],
                "name": camera_info["name"],
                "address": camera_info["address"],
                "traffic_status": current_metrics.status,
                "vehicle_count": current_metrics.vehicles,
                "signal_time": current_metrics.signal_time,
                "bottleneck": current_metrics.bottleneck == "Yes",
                "last_update": current_metrics.last_update
            }
            cameras_with_traffic.append(camera_data)
    
    return {"cameras": cameras_with_traffic}

@app.get("/", response_class=HTMLResponse)
async def root():
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Smart Traffic Management - Fixed & Enhanced</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; background: #f0f2f6; }
            .container { max-width: 1000px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; }
            h1 { color: #0066cc; text-align: center; }
            .status-card { background: #e8f5e8; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 5px solid #28a745; }
            .feature-card { background: #fff3cd; padding: 15px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #ffc107; }
            .endpoint { background: #f8f9fa; padding: 15px; margin: 10px 0; border-radius: 5px; border-left: 4px solid #0066cc; }
            a { color: #0066cc; text-decoration: none; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🚦 Smart Traffic Management - All Issues Fixed</h1>
            <p><strong>Version:</strong> 3.2.0 Fixed | <strong>Status:</strong> <span style="color: #28a745; font-weight: bold;">All Issues Resolved</span></p>
            
            <div class="status-card">
                <h3>✅ Fixed Issues</h3>
                <p>🔧 Button ID conflicts resolved</p>
                <p>🗺️ Map shows actual user-entered locations</p>
                <p>🪙 EcoCoins now calculated per user trip (not from system metrics)</p>
                <p>🏛️ Government services fully functional</p>
                <p>📊 Enhanced EcoCoin formula with time efficiency</p>
            </div>
            
            <div class="feature-card">
                <h3>🪙 New EcoCoin Formula</h3>
                <p><strong>Base Formula:</strong> (Distance × 2 EcoCoins/km) × Transport Multiplier + Time Bonus</p>
                <ul>
                    <li><strong>Walk:</strong> 5x multiplier</li>
                    <li><strong>Bike:</strong> 4x multiplier</li>
                    <li><strong>Metro:</strong> 3x multiplier</li>
                    <li><strong>Bus:</strong> 2.5x multilier</li>
                    <li><strong>Car:</strong> 1x multiplier</li>
                </ul>
                <p><strong>Time Bonus:</strong> Complete trip faster than estimated = bonus EcoCoins</p>
            </div>
            
            <div class="endpoint">
                <h4><a href="/viewer">🖥️ /viewer</a></h4>
                <p>Clean video viewer (no confidence scores)</p>
            </div>
            
            <div class="endpoint">
                <h4><a href="/metrics">📊 /metrics</a></h4>
                <p>Traffic metrics (EcoCoin generation removed from here)</p>
            </div>
            
            <p><strong>Frontend:</strong> <code>streamlit run frontend/main_app.py</code></p>
            <p><strong>All Issues:</strong> Resolved ✅</p>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.get("/health")
def health_check():
    conn = sqlite3.connect('ecocoin_system.db')
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]
    
    cursor.execute("SELECT SUM(ecocoin_balance) FROM users")
    total_ecocoins = cursor.fetchone()[0] or 0
    
    cursor.execute("SELECT SUM(total_co2_saved) FROM users")
    total_co2_saved = cursor.fetchone()[0] or 0
    
    conn.close()
    
    processing_stats = []
    for i in range(len(video_paths)):
        if i < len(location_metrics):
            stats = {
                "video_id": i + 1,
                "path": os.path.basename(video_paths[i]) if i < len(video_paths) else "Unknown",
                "exists": os.path.exists(video_paths[i]) if i < len(video_paths) else False,
                "processing": yield_frame[i] is not None,
                "current_vehicles": location_metrics[i].vehicles,
                "current_signal_time": location_metrics[i].signal_time,
                "traffic_status": location_metrics[i].status,
                "last_update": location_metrics[i].last_update
            }
        else:
            stats = {"video_id": i + 1, "error": "Metrics not initialized"}
        processing_stats.append(stats)
    
    return {
        "status": "healthy" if model is not None else "degraded",
        "model_loaded": model is not None,
        "videos": processing_stats,
        "active_threads": len([t for t in processing_threads if t.is_alive()]),
        "streaming_fps": "~30",
        "detection_enabled": True,
        "confidence_scores_removed": True,
        "gps_navigation_enabled": True,
        "camera_network": len(CAMERA_LOCATIONS),
        "all_issues_fixed": True,
        "ecocoin_system": {
            "total_users": total_users,
            "total_ecocoins_in_circulation": total_ecocoins,
            "total_co2_saved_kg": round(total_co2_saved, 2),
            "system_status": "active",
            "ecocoin_generation": "user_trip_based"
        }
    }

@app.get("/video/{video_id}")
async def video_feed(video_id: int):
    if not 1 <= video_id <= len(video_paths):
        raise HTTPException(status_code=404, detail=f"Video {video_id} not found")
    
    if not os.path.exists(video_paths[video_id - 1]):
        raise HTTPException(status_code=404, detail=f"Video file not found")
    
    return StreamingResponse(
        generate_frames(video_id - 1),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )

@app.get("/metrics")
def get_metrics():
    """FIXED: Removed ecocoins_generated from metrics"""
    current_time = time.time()
    
    metrics_data = []
    for i, location in enumerate(location_metrics):
        metrics_data.append({
            "vehicles": location.vehicles,
            "status": location.status,
            "signal_time": location.signal_time,
            "waiting_time": location.waiting_time,
            "co2": location.co2,
            "bottleneck": location.bottleneck,
            "last_update": location.last_update,
            "detection_confidence": location.detection_confidence,
            "data_freshness": "live" if (current_time - location.last_update) < 5 else "delayed"
        })
    
    return {
        "timestamp": current_time,
        "locations": metrics_data,
        "summary": {
            "total_vehicles": sum(m["vehicles"] for m in metrics_data),
            "active_bottlenecks": sum(1 for m in metrics_data if m["bottleneck"] == "Yes"),
            "average_waiting_time": round(sum(m["waiting_time"] for m in metrics_data) / len(metrics_data), 1) if metrics_data else 0,
            "total_co2_reduction": round(sum(m["co2"] for m in metrics_data), 2)
        }
    }

@app.get("/api/leaderboard")
def get_leaderboard():
    conn = sqlite3.connect('ecocoin_system.db')
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT username, ecocoin_balance, total_co2_saved
        FROM users 
        ORDER BY ecocoin_balance DESC, total_co2_saved DESC
        LIMIT 50
    """)
    
    leaderboard = cursor.fetchall()
    conn.close()
    
    return {
        "leaderboard": [
            {
                "rank": idx + 1,
                "username": user[0],
                "ecocoin_balance": user[1],
                "total_co2_saved": user[2] or 0
            } for idx, user in enumerate(leaderboard)
        ]
    }

@app.on_event("startup")
def startup_event():
    global processing_threads
    
    print("🚀 Starting Fixed Smart Traffic Management System...")
    print("✅ All issues resolved:")
    print("  - Button ID conflicts fixed")
    print("  - Map location accuracy improved") 
    print("  - EcoCoin calculation moved to user trips")
    print("  - Government services enabled")
    print("  - Enhanced EcoCoin formula implemented")
    
    for i, video_path in enumerate(video_paths):
        if os.path.exists(video_path):
            print(f"✅ Video {i+1} found: {os.path.basename(video_path)}")
            
            thread = threading.Thread(
                target=process_video,
                args=(i, video_path),
                daemon=True,
                name=f"FixedVideoProcessor-{i}"
            )
            thread.start()
            processing_threads.append(thread)
            print(f"✅ Fixed processing thread started for video {i+1}")

if __name__ == "__main__":
    uvicorn.run(
        "backend:app",
        host="127.0.0.1", 
        port=8000,
        reload=True,
        log_level="info"
    )
