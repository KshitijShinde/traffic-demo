import streamlit as st
import requests
import cv2
import numpy as np
import threading
import time
import json
from datetime import datetime
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import folium
from streamlit_folium import st_folium
from auth import login, require_permission, get_current_user

# Configuration
BACKEND_URL = "http://127.0.0.1:8000"
VIDEO_COUNT = 2

st.set_page_config(
    page_title="Smart Traffic Management - Fixed",
    page_icon="🚦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS (same as before)
st.markdown("""
<style>
.metric-card {
    background-color: #f0f2f6;
    padding: 10px;
    border-radius: 10px;
    border-left: 5px solid #ff6b6b;
}
.status-low { border-left-color: #51cf66 !important; }
.status-medium { border-left-color: #ffd43b !important; }
.status-high { border-left-color: #ff6b6b !important; }
.video-container {
    border: 2px solid #0066cc;
    border-radius: 10px;
    padding: 15px;
    margin: 10px 0;
    background-color: #f8f9fa;
}
.ecocoin-card {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    padding: 20px;
    border-radius: 15px;
    margin: 10px 0;
    text-align: center;
}
.gps-card {
    background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
    color: white;
    padding: 20px;
    border-radius: 15px;
    margin: 10px 0;
    text-align: center;
}
.route-card {
    background-color: #e3f2fd;
    padding: 15px;
    border-radius: 10px;
    margin: 10px 0;
    border-left: 4px solid #2196f3;
}
.traffic-high { background-color: #ffebee; border-left-color: #f44336; }
.traffic-medium { background-color: #fff8e1; border-left-color: #ff9800; }
.traffic-low { background-color: #e8f5e8; border-left-color: #4caf50; }
.service-card {
    background-color: #e8f5e8;
    padding: 15px;
    border-radius: 10px;
    margin: 10px 0;
    border-left: 4px solid #28a745;
}
.updating-indicator {
    animation: pulse 2s infinite;
    color: #28a745;
    font-weight: bold;
}
@keyframes pulse {
    0% { opacity: 1; }
    50% { opacity: 0.5; }
    100% { opacity: 1; }
}
</style>
""", unsafe_allow_html=True)

# Session state initialization
if 'auto_refresh_enabled' not in st.session_state:
    st.session_state.auto_refresh_enabled = True
if 'refresh_counter' not in st.session_state:
    st.session_state.refresh_counter = 0
if 'last_metrics' not in st.session_state:
    st.session_state.last_metrics = None

def check_backend_connection():
    try:
        response = requests.get(f"{BACKEND_URL}/health", timeout=5)
        return response.status_code == 200, response.json() if response.status_code == 200 else None
    except Exception as e:
        return False, str(e)

@st.cache_data(ttl=1)
def fetch_metrics():
    try:
        response = requests.get(f"{BACKEND_URL}/metrics", timeout=10)
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        st.error(f"❌ Error fetching metrics: {str(e)}")
        return None

def display_video_stream(video_id: int, container):
    video_url = f"{BACKEND_URL}/video/{video_id}"
    timestamp = int(time.time())
    html_code = f"""
    <div class="video-container">
        <h4 style="color: #0066cc; margin-bottom: 10px;">📍 Location {video_id} - Live Stream</h4>
        <img src="{video_url}?t={timestamp}" style="width: 100%; height: 300px; border-radius: 8px; object-fit: cover;">
        <p style="color: #28a745; font-size: 12px; margin-top: 5px;">
            <span class="updating-indicator">🟢 Live • Clean Detection • No Confidence Scores</span>
        </p>
    </div>
    """
    container.markdown(html_code, unsafe_allow_html=True)

def get_user_location():
    """Enhanced location detection"""
    location_html = """
    <script>
    function getLocation() {
        if (navigator.geolocation) {
            navigator.geolocation.getCurrentPosition(
                function(position) {
                    const lat = position.coords.latitude;
                    const lng = position.coords.longitude;
                    const accuracy = position.coords.accuracy;
                    
                    sessionStorage.setItem('userLat', lat);
                    sessionStorage.setItem('userLng', lng);
                    sessionStorage.setItem('locationAccuracy', accuracy);
                    
                    document.getElementById('location-status').innerHTML = 
                        '✅ Location: ' + lat.toFixed(6) + ', ' + lng.toFixed(6) + 
                        ' (±' + Math.round(accuracy) + 'm)';
                        
                    document.getElementById('location-success').value = 'true';
                    
                    // Store in parent window if in iframe
                    if (window.parent !== window) {
                        window.parent.postMessage({
                            type: 'location_update',
                            lat: lat,
                            lng: lng,
                            accuracy: accuracy
                        }, '*');
                    }
                },
                function(error) {
                    let errorMsg = 'Location access denied';
                    switch(error.code) {
                        case error.PERMISSION_DENIED:
                            errorMsg = "Location access denied by user";
                            break;
                        case error.POSITION_UNAVAILABLE:
                            errorMsg = "Location information unavailable";
                            break;
                        case error.TIMEOUT:
                            errorMsg = "Location request timeout";
                            break;
                    }
                    document.getElementById('location-status').innerHTML = '❌ ' + errorMsg;
                }
            );
        } else {
            document.getElementById('location-status').innerHTML = 
                '❌ Geolocation not supported by browser';
        }
    }
    
    // Auto-get location on page load
    window.onload = function() {
        getLocation();
    }
    </script>
    
    <div>
        <button onclick="getLocation()" style="
            background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
            color: white; border: none; padding: 10px 20px; 
            border-radius: 25px; cursor: pointer; font-weight: bold;
        ">📍 Get My Location</button>
        <p id="location-status" style="margin-top: 10px; font-size: 14px;">🔍 Click to get your location...</p>
        <input type="hidden" id="location-success" value="false">
    </div>
    """
    
    return location_html

def ecocoin_login_register():
    """FIXED: EcoCoin authentication with unique button keys"""
    st.sidebar.header("🪙 EcoCoin Account")
    
    if "ecocoin_token" not in st.session_state:
        st.session_state.ecocoin_token = None
    if "ecocoin_user" not in st.session_state:
        st.session_state.ecocoin_user = None
    
    if st.session_state.ecocoin_token is None:
        tab1, tab2 = st.sidebar.tabs(["Login", "Register"])
        
        with tab1:
            with st.form("ecocoin_login_form"):
                username = st.text_input("Username", key="login_username")
                password = st.text_input("Password", type="password", key="login_password")
                login_clicked = st.form_submit_button("🔑 Login", key="login_submit")
                
                if login_clicked and username and password:
                    try:
                        response = requests.post(f"{BACKEND_URL}/api/login", 
                                               json={"username": username, "password": password})
                        if response.status_code == 200:
                            data = response.json()
                            st.session_state.ecocoin_token = data["token"]
                            st.session_state.ecocoin_user = data
                            st.success("✅ Login successful!")
                            st.rerun()
                        else:
                            st.error("❌ Invalid credentials")
                    except Exception as e:
                        st.error(f"❌ Login error: {str(e)}")
        
        with tab2:
            with st.form("ecocoin_register_form"):
                reg_username = st.text_input("Choose Username", key="reg_username")
                reg_email = st.text_input("Email", key="reg_email")
                reg_phone = st.text_input("Phone Number", key="reg_phone")
                reg_password = st.text_input("Choose Password", type="password", key="reg_password")
                vehicle_type = st.selectbox("Primary Vehicle", ["car", "motorbike", "bus", "bike"], key="reg_vehicle")
                register_clicked = st.form_submit_button("📝 Register", key="register_submit")
                
                if register_clicked and all([reg_username, reg_email, reg_phone, reg_password]):
                    try:
                        response = requests.post(f"{BACKEND_URL}/api/register", 
                                               json={
                                                   "username": reg_username,
                                                   "email": reg_email,
                                                   "phone": reg_phone,
                                                   "password": reg_password,
                                                   "vehicle_type": vehicle_type
                                               })
                        if response.status_code == 200:
                            data = response.json()
                            st.session_state.ecocoin_token = data["token"]
                            st.session_state.ecocoin_user = data
                            st.success(f"✅ Registration successful! Welcome bonus: {data['welcome_bonus']} EcoCoins")
                            st.rerun()
                        else:
                            error_detail = response.json().get("detail", "Registration failed")
                            st.error(f"❌ {error_detail}")
                    except Exception as e:
                        st.error(f"❌ Registration error: {str(e)}")
        
        return None
    
    else:
        try:
            headers = {"Authorization": f"Bearer {st.session_state.ecocoin_token}"}
            response = requests.get(f"{BACKEND_URL}/api/user-profile", headers=headers)
            
            if response.status_code == 200:
                profile = response.json()
                
                st.sidebar.markdown(f"""
                <div class="ecocoin-card">
                    <h3>🪙 {profile['user_info']['ecocoin_balance']}</h3>
                    <p>EcoCoins Balance</p>
                    <small>💚 {profile['user_info']['total_co2_saved']:.2f} kg CO₂ saved</small>
                </div>
                """, unsafe_allow_html=True)
                
                st.sidebar.write(f"👤 **{profile['user_info']['username']}**")
                st.sidebar.write(f"🚗 Vehicle: {profile['user_info']['vehicle_type']}")
                st.sidebar.write(f"🛣️ Total trips: {profile['statistics']['total_trips']}")
                
                if st.sidebar.button("🚪 Logout", key="ecocoin_logout"):
                    st.session_state.ecocoin_token = None
                    st.session_state.ecocoin_user = None
                    st.rerun()
                
                return profile
            else:
                st.sidebar.error(f"❌ Profile Error: {response.status_code}")
                if st.sidebar.button("🔄 Retry Login", key="retry_login"):
                    st.session_state.ecocoin_token = None
                return None
        except Exception as e:
            st.sidebar.error(f"❌ Connection error: {str(e)}")
            if st.sidebar.button("🔄 Retry", key="retry_connection"):
                st.session_state.ecocoin_token = None
            return None

def gps_navigation_dashboard():
    """FIXED: GPS navigation with accurate geocoding for both locations and proper road routing"""
    import os
    import requests as req_lib
    import json
    
    st.subheader("🗺️ GPS Navigation & Route Planning")
    
    col1, col2 = st.columns([1, 1])
    api_key = "AIzaSyDHEwdS0kwcW_X1LVvsiQym9VsV3owtsHU"
    with col1:
        st.markdown("### 📍 Your Current Location")
        
        # Initialize session state for start location
        if 'start_lat' not in st.session_state:
            st.session_state.start_lat = 28.6139
        if 'start_lng' not in st.session_state:
            st.session_state.start_lng = 77.2090
        if 'start_address' not in st.session_state:
            st.session_state.start_address = ""
        
        # API Key input (shared for both locations)
        
        
        # Start address input
        start_address = st.text_input(
            "Enter your current address", 
            placeholder="e.g., Hinjewadi, Pune or Connaught Place, Delhi",
            key="start_address_input",
            value=st.session_state.start_address
        )
        
        # Geocode start address
        if st.button("🔍 Find My Location", key="geocode_start_btn", type="primary"):
            if not api_key.strip():
                st.error("❌ Please enter your Google Maps API key first!")
            elif not start_address.strip():
                st.error("❌ Please enter your current address!")
            else:
                try:
                    # Enhanced address formatting
                    formatted_address = start_address.strip()
                    if not any(country in formatted_address.lower() for country in ['india', 'pune', 'mumbai', 'delhi', 'bangalore']):
                        formatted_address += ", India"
                    
                    st.info(f"🔍 Searching for: {formatted_address}")
                    
                    GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"
                    params = {"address": formatted_address, "key": api_key.strip()}
                    
                    resp = req_lib.get(GEOCODE_URL, params=params, timeout=15)
                    
                    if resp.status_code == 200:
                        data = resp.json()
                        status = data.get("status")
                        
                        if status == "OK" and data["results"]:
                            loc = data["results"][0]["geometry"]["location"]
                            st.session_state.start_lat = loc["lat"]
                            st.session_state.start_lng = loc["lng"]
                            st.session_state.start_address = start_address
                            
                            formatted_result = data["results"][0]["formatted_address"]
                            st.success(f"✅ Your location found: {formatted_result}")
                            st.success(f"📍 Coordinates: {loc['lat']:.6f}, {loc['lng']:.6f}")
                            st.rerun()
                        else:
                            st.error(f"❌ Could not find your location: {formatted_address}")
                    else:
                        st.error("❌ Geocoding service error")
                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")
        
        # Show current start coordinates
        st.info(f"📍 **Your Location:** {st.session_state.start_lat:.6f}, {st.session_state.start_lng:.6f}")
        
    with col2:
        st.markdown("### 🎯 Destination")
        
        # Initialize session state for destination
        if 'dest_lat' not in st.session_state:
            st.session_state.dest_lat = 28.6304
        if 'dest_lng' not in st.session_state:
            st.session_state.dest_lng = 77.2177
        if 'dest_address' not in st.session_state:
            st.session_state.dest_address = ""
        
        # Destination address input
        dest_address = st.text_input(
            "Enter destination address", 
            placeholder="e.g., Spine City, Pune or India Gate, Delhi",
            key="destination_address_input",
            value=st.session_state.dest_address
        )
        
        # Geocode destination address
        if st.button("🔍 Find Destination", key="geocode_dest_btn", type="primary"):
            if not api_key.strip():
                st.error("❌ Please enter your Google Maps API key first!")
            elif not dest_address.strip():
                st.error("❌ Please enter a destination address!")
            else:
                try:
                    # Enhanced address formatting
                    formatted_address = dest_address.strip()
                    if not any(country in formatted_address.lower() for country in ['india', 'pune', 'mumbai', 'delhi', 'bangalore']):
                        formatted_address += ", India"
                    
                    st.info(f"🔍 Searching for: {formatted_address}")
                    
                    GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"
                    params = {"address": formatted_address, "key": api_key.strip()}
                    
                    resp = req_lib.get(GEOCODE_URL, params=params, timeout=15)
                    
                    if resp.status_code == 200:
                        data = resp.json()
                        status = data.get("status")
                        
                        if status == "OK" and data["results"]:
                            loc = data["results"][0]["geometry"]["location"]
                            st.session_state.dest_lat = loc["lat"]
                            st.session_state.dest_lng = loc["lng"]
                            st.session_state.dest_address = dest_address
                            
                            formatted_result = data["results"][0]["formatted_address"]
                            st.success(f"✅ Destination found: {formatted_result}")
                            st.success(f"📍 Coordinates: {loc['lat']:.6f}, {loc['lng']:.6f}")
                            st.rerun()
                        else:
                            st.error(f"❌ Could not find destination: {formatted_address}")
                    else:
                        st.error("❌ Geocoding service error")
                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")
        
        # Show current destination coordinates
        st.info(f"🎯 **Destination:** {st.session_state.dest_lat:.6f}, {st.session_state.dest_lng:.6f}")
        
        # Quick destination presets
        quick_destinations = st.selectbox("Quick Destinations", [
            "Select...",
            "Spine City Mall, Pune",
            "Delhi Airport", 
            "India Gate, Delhi",
            "Hinjewadi IT Park, Pune",
            "Mumbai Central",
            "Bangalore Airport"
        ], key="quick_dest_select")
        
        if quick_destinations != "Select..." and st.button(f"🎯 Use {quick_destinations}", key="use_quick_dest"):
            if api_key.strip():
                # Geocode the quick destination
                try:
                    GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"
                    params = {"address": quick_destinations + ", India", "key": api_key.strip()}
                    resp = req_lib.get(GEOCODE_URL, params=params, timeout=15)
                    
                    if resp.status_code == 200:
                        data = resp.json()
                        if data.get("status") == "OK" and data["results"]:
                            loc = data["results"][0]["geometry"]["location"]
                            st.session_state.dest_lat = loc["lat"]
                            st.session_state.dest_lng = loc["lng"]
                            st.session_state.dest_address = quick_destinations
                            st.success(f"✅ Destination set to: {quick_destinations}")
                            st.rerun()
                except Exception as e:
                    st.error(f"❌ Error setting destination: {str(e)}")
            else:
                st.error("❌ Please enter API key first")
    
    # Route Planning with Proper Road Routing
    # Route Planning with Real-time Traffic Analysis
    if st.button("🗺️ Plan Route & Check Traffic", type="primary", key="plan_route_btn"):
        if not st.session_state.start_address or not st.session_state.dest_address:
            st.warning("⚠️ Please find both your location and destination first!")
            return
            
        try:
            # Use the geocoded coordinates from session state
            start_lat = st.session_state.start_lat
            start_lng = st.session_state.start_lng
            dest_lat = st.session_state.dest_lat
            dest_lng = st.session_state.dest_lng
            
            st.info(f"""
            🗺️ **Analyzing Route with Live Traffic:**
            📍 **From:** {st.session_state.start_address} ({start_lat:.6f}, {start_lng:.6f})
            🎯 **To:** {st.session_state.dest_address} ({dest_lat:.6f}, {dest_lng:.6f})
            📹 **Checking cameras for traffic conditions...**
            """)
            
            # Enhanced route data with traffic analysis request
            route_data = {
                "start_lat": start_lat,
                "start_lng": start_lng,
                "end_lat": dest_lat,
                "end_lng": dest_lng,
                "start_address": st.session_state.start_address,
                "end_address": st.session_state.dest_address,
                "analyze_traffic": True,  # Request traffic analysis
                "route_buffer_km": 2.0    # Check cameras within 2km of route
            }
            
            response = requests.post(f"{BACKEND_URL}/api/get-route-traffic", json=route_data)
            
            if response.status_code == 200:
                route_result = response.json()
                
                # Analyze overall route traffic
                cameras_on_route = route_result.get('cameras_on_route', [])
                traffic_analysis = analyze_route_traffic(cameras_on_route)
                
                st.success("✅ Route analyzed with real-time camera data!")
                
                # Enhanced traffic display
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("🛣️ Distance", f"{route_result['route_info']['distance_km']} km")
                
                with col2:
                    overall_status = traffic_analysis['overall_status']
                    status_colors = {'Low': '#4CAF50', 'Medium': '#FF9800', 'High': '#F44336'}
                    color = status_colors.get(overall_status, '#2196F3')
                    st.markdown(f"<p style='color: {color}; font-weight: bold; font-size: 18px;'>🚦 {overall_status} Traffic</p>", 
                              unsafe_allow_html=True)
                
                with col3:
                    st.metric("📹 Cameras Active", len(cameras_on_route))
                
                with col4:
                    avg_vehicles = traffic_analysis['average_vehicles']
                    st.metric("🚗 Avg Vehicles", f"{avg_vehicles:.0f}")
                
                # Traffic condition summary
                st.subheader("🚦 Live Traffic Analysis")
                
                traffic_summary_cols = st.columns(3)
                
                with traffic_summary_cols[0]:
                    high_traffic_cameras = [c for c in cameras_on_route if c['traffic_status'] == 'High']
                    st.markdown(f"""
                    <div style="background: #ffebee; padding: 15px; border-radius: 10px; border-left: 4px solid #f44336;">
                        <h4 style="color: #d32f2f; margin: 0;">🔴 High Traffic Zones</h4>
                        <p style="margin: 5px 0;"><strong>{len(high_traffic_cameras)} locations</strong></p>
                        <small>Heavy congestion detected</small>
                    </div>
                    """, unsafe_allow_html=True)
                
                with traffic_summary_cols[1]:
                    medium_traffic_cameras = [c for c in cameras_on_route if c['traffic_status'] == 'Medium']
                    st.markdown(f"""
                    <div style="background: #fff3e0; padding: 15px; border-radius: 10px; border-left: 4px solid #ff9800;">
                        <h4 style="color: #f57c00; margin: 0;">🟡 Medium Traffic Zones</h4>
                        <p style="margin: 5px 0;"><strong>{len(medium_traffic_cameras)} locations</strong></p>
                        <small>Moderate congestion</small>
                    </div>
                    """, unsafe_allow_html=True)
                
                with traffic_summary_cols[2]:
                    low_traffic_cameras = [c for c in cameras_on_route if c['traffic_status'] == 'Low']
                    st.markdown(f"""
                    <div style="background: #e8f5e8; padding: 15px; border-radius: 10px; border-left: 4px solid #4caf50;">
                        <h4 style="color: #388e3c; margin: 0;">🟢 Clear Traffic Zones</h4>
                        <p style="margin: 5px 0;"><strong>{len(low_traffic_cameras)} locations</strong></p>
                        <small>Light traffic flow</small>
                    </div>
                    """, unsafe_allow_html=True)
                
                st.subheader("🗺️ Route Map with Live Traffic")
                
                # Get proper road routing using OSRM
                def get_osrm_route(start_lat, start_lng, end_lat, end_lng):
                    """Get proper road route using OSRM"""
                    try:
                        osrm_url = f"http://router.project-osrm.org/route/v1/driving/{start_lng},{start_lat};{end_lng},{end_lat}"
                        params = {
                            "overview": "full",
                            "geometries": "geojson",
                            "steps": "true"
                        }
                        
                        resp = requests.get(osrm_url, params=params, timeout=10)
                        
                        if resp.status_code == 200:
                            data = resp.json()
                            if data["routes"]:
                                coordinates = data["routes"][0]["geometry"]["coordinates"]
                                route_coords = [[coord[1], coord[0]] for coord in coordinates]
                                
                                route_info = {
                                    "coordinates": route_coords,
                                    "distance": data["routes"][0]["distance"] / 1000,
                                    "duration": data["routes"][0]["duration"] / 60,
                                    "steps": len(data["routes"][0]["legs"][0]["steps"]) if data["routes"][0]["legs"] else 0
                                }
                                return route_info
                        return None
                    except Exception as e:
                        st.warning(f"⚠️ OSRM routing failed: {str(e)}, using direct line")
                        return None
                
                # Get proper road route
                road_route = get_osrm_route(start_lat, start_lng, dest_lat, dest_lng)
                
                # Calculate map center and zoom
                center_lat = (start_lat + dest_lat) / 2
                center_lng = (start_lng + dest_lng) / 2
                
                distance_km = route_result['route_info']['distance_km']
                if distance_km < 5:
                    zoom_level = 12
                elif distance_km < 20:
                    zoom_level = 10
                elif distance_km < 50:
                    zoom_level = 8
                else:
                    zoom_level = 6
                
                # Create enhanced map with traffic visualization
                m = folium.Map(
                    location=[center_lat, center_lng],
                    zoom_start=zoom_level,
                    tiles='OpenStreetMap'
                )
                
                # Add start marker
                folium.Marker(
                    [start_lat, start_lng],
                    popup=f"""
                    <b>📍 Your Location</b><br>
                    {st.session_state.start_address}<br>
                    Lat: {start_lat:.6f}<br>
                    Lng: {start_lng:.6f}
                    """,
                    tooltip=st.session_state.start_address,
                    icon=folium.Icon(color='blue', icon='home')
                ).add_to(m)
                
                # Add destination marker
                folium.Marker(
                    [dest_lat, dest_lng],
                    popup=f"""
                    <b>🎯 Destination</b><br>
                    {st.session_state.dest_address}<br>
                    Lat: {dest_lat:.6f}<br>
                    Lng: {dest_lng:.6f}
                    """,
                    tooltip=st.session_state.dest_address,
                    icon=folium.Icon(color='red', icon='star')
                ).add_to(m)
                
                # Add route with traffic-based color coding
                if road_route and road_route["coordinates"]:
                    # Color route based on overall traffic
                    route_color = {
                        'Low': '#4CAF50',     # Green for light traffic
                        'Medium': '#FF9800',  # Orange for medium traffic  
                        'High': '#F44336'     # Red for heavy traffic
                    }.get(overall_status, '#2196F3')
                    
                    folium.PolyLine(
                        road_route["coordinates"],
                        weight=6,
                        color=route_color,
                        opacity=0.8,
                        popup=f"🛣️ Route: {road_route['distance']:.1f} km | 🚦 {overall_status} Traffic"
                    ).add_to(m)
                    
                    st.success(f"""
                    🛣️ **Road Route with Live Traffic Analysis!**
                    📏 **Distance:** {road_route['distance']:.1f} km
                    ⏱️ **Estimated Time:** {road_route['duration']:.0f} minutes
                    🚦 **Traffic Level:** {overall_status}
                    📹 **Monitoring Points:** {len(cameras_on_route)} cameras
                    """)
                else:
                    # Fallback to straight line
                    route_color = {
                        'Low': '#4CAF50', 'Medium': '#FF9800', 'High': '#F44336'
                    }.get(overall_status, '#2196F3')
                    
                    folium.PolyLine(
                        [[start_lat, start_lng], [dest_lat, dest_lng]],
                        weight=4,
                        color=route_color,
                        opacity=0.7,
                        popup=f"Direct Route: {distance_km} km | Traffic: {overall_status}"
                    ).add_to(m)
                
                # Add traffic cameras with enhanced info
                for i, camera in enumerate(cameras_on_route):
                    # Camera icon and color based on traffic status
                    camera_colors = {
                        'High': 'red',
                        'Medium': 'orange',
                        'Low': 'green'
                    }
                    camera_color = camera_colors.get(camera['traffic_status'], 'blue')
                    
                    # Camera icon based on traffic level
                    camera_icons = {
                        'High': 'exclamation-triangle',
                        'Medium': 'warning',
                        'Low': 'check-circle'
                    }
                    camera_icon = camera_icons.get(camera['traffic_status'], 'video-camera')
                    
                    # Enhanced popup with more traffic details
                    popup_html = f"""
                    <div style="width: 200px;">
                        <h4 style="margin: 0; color: {camera_colors.get(camera['traffic_status'], 'blue')};">
                            📹 {camera['name']}
                        </h4>
                        <hr style="margin: 5px 0;">
                        <p style="margin: 2px 0;"><strong>🚦 Status:</strong> {camera['traffic_status']} Traffic</p>
                        <p style="margin: 2px 0;"><strong>🚗 Vehicles:</strong> {camera['vehicle_count']}</p>
                        <p style="margin: 2px 0;"><strong>⏱️ Signal:</strong> {camera['signal_time']}s</p>
                        <p style="margin: 2px 0;"><strong>📍 Location:</strong> {camera['address']}</p>
                        <p style="margin: 2px 0;"><strong>📏 Distance:</strong> {camera.get('distance_from_start', 0):.1f} km from start</p>
                        <small style="color: gray;">Camera #{i+1} • Live feed</small>
                    </div>
                    """
                    
                    folium.Marker(
                        [camera['lat'], camera['lng']],
                        popup=folium.Popup(popup_html, max_width=250),
                        tooltip=f"📹 {camera['name']} - {camera['traffic_status']} Traffic",
                        icon=folium.Icon(
                            color=camera_color, 
                            icon=camera_icon,
                            prefix='fa'
                        )
                    ).add_to(m)
                    
                    # Add traffic level circle around camera
                    circle_colors = {
                        'High': '#F44336',
                        'Medium': '#FF9800', 
                        'Low': '#4CAF50'
                    }
                    
                    folium.Circle(
                        [camera['lat'], camera['lng']],
                        radius=200,  # 200 meter radius
                        color=circle_colors.get(camera['traffic_status'], '#2196F3'),
                        fillColor=circle_colors.get(camera['traffic_status'], '#2196F3'),
                        fillOpacity=0.2,
                        opacity=0.6,
                        popup=f"Traffic Zone: {camera['traffic_status']}"
                    ).add_to(m)
                
                # Display the enhanced map
                st_folium(m, width=700, height=500, key=f"traffic_route_{start_lat}_{dest_lat}_{overall_status}")
                
                # Detailed traffic breakdown
                # Detailed traffic breakdown
                st.subheader("📊 Detailed Traffic Analysis")
                
                # Traffic cameras details
                if cameras_on_route:
                    for i, camera in enumerate(cameras_on_route):
                        status_color = {
                            'High': '#ffebee',
                            'Medium': '#fff3e0',
                            'Low': '#e8f5e8'
                        }.get(camera['traffic_status'], '#f5f5f5')
                        
                        # Fixed: Use separate variables instead of dict inside f-string
                        border_colors = {
                            'High': '#f44336', 
                            'Medium': '#ff9800', 
                            'Low': '#4caf50'
                        }
                        border_color = border_colors.get(camera['traffic_status'], '#2196f3')
                        
                        st.markdown(f"""
                        <div style="background: {status_color}; padding: 12px; border-radius: 8px; margin: 8px 0; border-left: 4px solid {border_color};">
                            <h5 style="margin: 0; color: #333;">📹 Camera {i+1}: {camera['name']}</h5>
                            <p style="margin: 5px 0; font-size: 14px;">
                                <strong>🚦 Traffic:</strong> {camera['traffic_status']} | 
                                <strong>🚗 Vehicles:</strong> {camera['vehicle_count']} | 
                                <strong>⏱️ Signal:</strong> {camera['signal_time']}s
                            </p>
                            <p style="margin: 5px 0; font-size: 12px; color: #666;">
                                📍 {camera['address']} • {camera.get('distance_from_start', 0):.1f} km from start
                            </p>
                        </div>
                        """, unsafe_allow_html=True)

                
                # Route recommendations based on traffic
                st.subheader("💡 Route Recommendations")
                
                if overall_status == 'High':
                    st.error("""
                    🚨 **Heavy Traffic Alert!**
                    
                    • Consider delaying your trip by 30-60 minutes
                    • Use alternative transport (metro/bus) if available
                    • Allow extra 20-30 minutes for your journey
                    • Check for alternative routes
                    """)
                elif overall_status == 'Medium':
                    st.warning("""
                    ⚠️ **Moderate Traffic Detected**
                    
                    • Allow extra 10-15 minutes for your journey
                    • Monitor traffic updates during trip
                    • Consider leaving slightly earlier
                    """)
                else:
                    st.success("""
                    ✅ **Clear Route Ahead!**
                    
                    • Good time to travel
                    • Normal travel time expected
                    • Traffic flowing smoothly
                    """)
                
                # Transport estimates with traffic adjustment
                transport_estimates = route_result.get('transport_estimates', {})
                if transport_estimates:
                    st.subheader("🚌 Transport Options (Traffic Adjusted)")
                    
                    # Adjust times based on traffic
                    traffic_multiplier = {
                        'Low': 1.0,
                        'Medium': 1.3,
                        'High': 1.6
                    }.get(overall_status, 1.0)
                    
                    cols = st.columns(3)
                    for i, (mode, estimate) in enumerate(transport_estimates.items()):
                        with cols[i % 3]:
                            adjusted_time = int(estimate['estimated_time_minutes'] * traffic_multiplier)
                            mode_emoji = {
                                "walk": "🚶", "bike": "🚴", "car": "🚗", 
                                "motorbike": "🏍️", "bus": "🚌", "metro": "🚇"
                            }
                            
                            st.markdown(f"""
                            <div class="route-card" style="background: {'#ffebee' if overall_status == 'High' else '#fff3e0' if overall_status == 'Medium' else '#e8f5e8'};">
                                <h4>{mode_emoji.get(mode, '🚗')} {mode.title()}</h4>
                                <p><strong>Time:</strong> {adjusted_time} min {f'(+{adjusted_time - estimate["estimated_time_minutes"]} due to traffic)' if traffic_multiplier > 1.0 else ''}</p>
                                <p><strong>EcoCoins:</strong> {estimate['potential_ecocoins']}</p>
                                <p><strong>CO₂ Saved:</strong> {estimate['co2_saved']} kg</p>
                            </div>
                            """, unsafe_allow_html=True)
            
            else:
                st.error("❌ Failed to get route data from backend")
                
        except Exception as e:
            st.error(f"❌ Route planning error: {str(e)}")

# Add traffic analysis helper function
def analyze_route_traffic(cameras_on_route):
    """Analyze overall traffic conditions from camera data"""
    if not cameras_on_route:
        return {
            'overall_status': 'Unknown',
            'average_vehicles': 0,
            'high_traffic_count': 0,
            'medium_traffic_count': 0,
            'low_traffic_count': 0
        }
    
    # Count traffic levels
    high_count = len([c for c in cameras_on_route if c['traffic_status'] == 'High'])
    medium_count = len([c for c in cameras_on_route if c['traffic_status'] == 'Medium'])
    low_count = len([c for c in cameras_on_route if c['traffic_status'] == 'Low'])
    
    # Calculate average vehicles
    total_vehicles = sum(c['vehicle_count'] for c in cameras_on_route)
    avg_vehicles = total_vehicles / len(cameras_on_route) if cameras_on_route else 0
    
    # Determine overall status
    if high_count > len(cameras_on_route) * 0.3:  # More than 30% high traffic
        overall_status = 'High'
    elif medium_count + high_count > len(cameras_on_route) * 0.5:  # More than 50% medium+ traffic
        overall_status = 'Medium'
    else:
        overall_status = 'Low'
    
    return {
        'overall_status': overall_status,
        'average_vehicles': avg_vehicles,
        'high_traffic_count': high_count,
        'medium_traffic_count': medium_count,
        'low_traffic_count': low_count
    }








def record_trip_interface():
    """ENHANCED: GPS-integrated trip recording with automatic time tracking"""
    st.subheader("🚗 Record Trip & Earn EcoCoins")
    
    # Initialize session state for trip tracking
    if 'trip_active' not in st.session_state:
        st.session_state.trip_active = False
    if 'trip_start_time' not in st.session_state:
        st.session_state.trip_start_time = None
    if 'trip_start_location' not in st.session_state:
        st.session_state.trip_start_location = None
    if 'trip_destination' not in st.session_state:
        st.session_state.trip_destination = None
    if 'auto_distance_calculated' not in st.session_state:
        st.session_state.auto_distance_calculated = 0.0
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 🗺️ GPS-Integrated Trip Recording")
        
        # Step 1: Set Start Location (from Navigation)
        if st.session_state.get('start_address') and st.session_state.get('start_lat'):
            start_location = st.session_state.start_address
            start_coords = f"({st.session_state.start_lat:.6f}, {st.session_state.start_lng:.6f})"
            
            st.success(f"📍 **Start Location Set:**\n{start_location}\n📍 {start_coords}")
            st.session_state.trip_start_location = {
                'address': start_location,
                'lat': st.session_state.start_lat,
                'lng': st.session_state.start_lng
            }
        else:
            st.warning("⚠️ Please set your location in the GPS Navigation tab first")
            st.info("👆 Go to 'GPS Navigation' tab and click 'Find My Location'")
            
            # Manual fallback
            with st.expander("📝 Manual Start Location (if GPS unavailable)"):
                manual_start = st.text_input(
                    "Enter Start Location", 
                    placeholder="e.g., My Home, Office Address",
                    key="manual_start_location"
                )
                if st.button("📍 Set Manual Start", key="set_manual_start"):
                    if manual_start:
                        st.session_state.trip_start_location = {
                            'address': manual_start,
                            'lat': 0.0,
                            'lng': 0.0
                        }
                        st.success(f"✅ Manual start location set: {manual_start}")
                        st.rerun()
        
        # Step 2: Set Destination (from Navigation)
        if st.session_state.get('dest_address') and st.session_state.get('dest_lat'):
            dest_location = st.session_state.dest_address
            dest_coords = f"({st.session_state.dest_lat:.6f}, {st.session_state.dest_lng:.6f})"
            
            st.success(f"🎯 **Destination Set:**\n{dest_location}\n📍 {dest_coords}")
            st.session_state.trip_destination = {
                'address': dest_location,
                'lat': st.session_state.dest_lat,
                'lng': st.session_state.dest_lng
            }
            
            # Auto-calculate distance
            if (st.session_state.get('start_lat') and st.session_state.get('dest_lat')):
                import math
                lat1, lng1 = st.session_state.start_lat, st.session_state.start_lng
                lat2, lng2 = st.session_state.dest_lat, st.session_state.dest_lng
                
                # Haversine formula for distance
                R = 6371  # Earth's radius in km
                lat1_rad, lng1_rad = math.radians(lat1), math.radians(lng1)
                lat2_rad, lng2_rad = math.radians(lat2), math.radians(lng2)
                
                dlat = lat2_rad - lat1_rad
                dlng = lng2_rad - lng1_rad
                
                a = math.sin(dlat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlng/2)**2
                c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
                distance_km = R * c
                
                st.session_state.auto_distance_calculated = distance_km
                st.info(f"📏 **Auto-calculated Distance:** {distance_km:.2f} km")
                
        else:
            st.warning("⚠️ Please set your destination in the GPS Navigation tab")
            st.info("👆 Go to 'GPS Navigation' tab and click 'Find Destination'")
        
        # Transport Mode Selection
        st.markdown("#### 🚌 Transport Mode")
        transport_mode = st.selectbox(
            "How are you traveling?", 
            ["car", "motorbike", "bus", "metro", "bike", "walk"],
            format_func=lambda x: {
                "car": "🚗 Car", "motorbike": "🏍️ Motorbike", "bus": "🚌 Bus",
                "metro": "🚇 Metro", "bike": "🚴 Bicycle", "walk": "🚶 Walking"
            }[x],
            key="eco_transport_mode"
        )
    
    with col2:
        st.markdown("#### ⏱️ Automatic Trip Timer")
        
        # Trip Status Display
        if st.session_state.trip_active:
            current_duration = int((time.time() - st.session_state.trip_start_time) / 60)
            
            st.markdown(f"""
            <div style="background: linear-gradient(135deg, #4CAF50, #45a049); color: white; padding: 20px; border-radius: 15px; text-align: center; animation: pulse 2s infinite;">
                <h2>🟢 TRIP IN PROGRESS</h2>
                <h1>⏱️ {current_duration} minutes</h1>
                <p><strong>Started:</strong> {time.strftime('%H:%M:%S', time.localtime(st.session_state.trip_start_time))}</p>
                <p><strong>From:</strong> {st.session_state.trip_start_location['address'] if st.session_state.trip_start_location else 'Not set'}</p>
                <p><strong>To:</strong> {st.session_state.trip_destination['address'] if st.session_state.trip_destination else 'Not set'}</p>
            </div>
            """, unsafe_allow_html=True)
            
            # Distance verification during trip
            if st.session_state.auto_distance_calculated > 0:
                estimated_speed = st.session_state.auto_distance_calculated / (current_duration / 60) if current_duration > 0 else 0
                st.info(f"📊 **Trip Stats:**\n📏 Distance: {st.session_state.auto_distance_calculated:.2f} km\n🏃 Avg Speed: {estimated_speed:.1f} km/h")
            
            # Arrival confirmation section
            st.markdown("#### 🏁 Arrived at Destination?")
            st.warning("⚠️ Only click 'Arrived' when you actually reach your destination!")
            
            col_arrive1, col_arrive2 = st.columns(2)
            
            with col_arrive1:
                if st.button("✅ I've Arrived!", key="trip_complete_btn", type="primary"):
                    # Complete the trip
                    actual_duration = int((time.time() - st.session_state.trip_start_time) / 60)
                    complete_trip_and_earn_ecocoins(
                        st.session_state.trip_start_location,
                        st.session_state.trip_destination,
                        st.session_state.auto_distance_calculated,
                        actual_duration,
                        transport_mode
                    )
            
            with col_arrive2:
                if st.button("❌ Cancel Trip", key="cancel_trip_btn"):
                    st.session_state.trip_active = False
                    st.session_state.trip_start_time = None
                    st.warning("🚫 Trip cancelled. No EcoCoins earned.")
                    st.rerun()
        
        else:
            # Trip not started
            st.markdown("""
            <div style="background: #f0f2f6; padding: 20px; border-radius: 15px; text-align: center; border: 2px dashed #ccc;">
                <h3>⏱️ Ready to Start Trip</h3>
                <p>Set your start location and destination in GPS Navigation tab, then start your trip timer here.</p>
            </div>
            """, unsafe_allow_html=True)
            
            # Start Trip Button
            can_start_trip = (
                st.session_state.trip_start_location and 
                st.session_state.trip_destination and 
                st.session_state.auto_distance_calculated > 0
            )
            
            if can_start_trip:
                st.markdown("#### 🚀 Start Your Trip")
                
                # Trip preview
                preview_calc = calculate_ecocoin_preview(
                    st.session_state.auto_distance_calculated, 
                    30,  # Estimated duration
                    transport_mode
                )
                
                st.markdown(f"""
                <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 15px; border-radius: 10px; text-align: center; margin: 10px 0;">
                    <h4>🪙 Potential Earnings</h4>
                    <h2>{preview_calc['estimated_ecocoins']} EcoCoins</h2>
                    <p>💚 {preview_calc['co2_saved']:.3f} kg CO₂ saved</p>
                    <small>📏 {st.session_state.auto_distance_calculated:.2f} km • 🚗 {transport_mode}</small>
                </div>
                """, unsafe_allow_html=True)
                
                if st.button("🚀 Start Trip Timer", key="start_trip_timer_btn", type="primary"):
                    st.session_state.trip_active = True
                    st.session_state.trip_start_time = time.time()
                    st.success("✅ Trip timer started! Safe travels! 🚗💨")
                    st.balloons()
                    st.rerun()
            
            else:
                st.error("❌ **Cannot Start Trip:**")
                if not st.session_state.trip_start_location:
                    st.error("• Set start location in GPS Navigation tab")
                if not st.session_state.trip_destination:
                    st.error("• Set destination in GPS Navigation tab")
                if st.session_state.auto_distance_calculated <= 0:
                    st.error("• Distance calculation failed")
        
        # Anti-fraud measures info
        with st.expander("🛡️ Anti-Fraud Protection"):
            st.markdown("""
            **🔒 Security Measures:**
            
            • **GPS Verification**: Start/end locations are GPS-verified
            • **Time Lock**: Timer cannot be stopped manually during trip
            • **Distance Validation**: Auto-calculated based on actual coordinates
            • **Speed Analysis**: Unrealistic speeds are flagged
            • **Location Confirmation**: Must confirm arrival at destination
            
            **⚠️ Fair Play Rules:**
            • Only start timer when actually beginning your trip
            • Only click 'Arrived' when you reach your destination  
            • Fake trips will be detected and penalized
            • Multiple violations may result in account suspension
            """)

# Enhanced trip completion function
def complete_trip_and_earn_ecocoins(start_location, destination, distance_km, duration_minutes, transport_mode):
    """Complete trip and award EcoCoins with enhanced validation"""
    
    if not st.session_state.ecocoin_token:
        st.error("❌ Please login to your EcoCoin account first")
        return
    
    # Validation checks
    if duration_minutes < 1:
        st.error("❌ Trip too short (minimum 1 minute required)")
        return
    
    if distance_km < 0.1:
        st.error("❌ Trip too short (minimum 0.1 km required)")
        return
    
    # Speed validation (prevent unrealistic trips)
    speed_kmh = distance_km / (duration_minutes / 60) if duration_minutes > 0 else 0
    max_speeds = {"walk": 8, "bike": 40, "car": 120, "motorbike": 140, "bus": 80, "metro": 100}
    max_speed = max_speeds.get(transport_mode, 120)
    
    if speed_kmh > max_speed:
        st.error(f"❌ Speed too high ({speed_kmh:.1f} km/h) for {transport_mode}. Maximum: {max_speed} km/h")
        st.warning("🕵️ Possible fraud detected. Please ensure accurate trip data.")
        return
    
    try:
        headers = {"Authorization": f"Bearer {st.session_state.ecocoin_token}"}
        
        # Enhanced trip data with GPS validation
        trip_data = {
            "user_id": st.session_state.ecocoin_user["user_id"],
            "start_location": start_location['address'],
            "end_location": destination['address'],
            "start_coordinates": {"lat": start_location['lat'], "lng": start_location['lng']},
            "end_coordinates": {"lat": destination['lat'], "lng": destination['lng']},
            "distance_km": distance_km,
            "duration_minutes": duration_minutes,
            "transport_mode": transport_mode,
            "route_efficiency": 1.0,  # Auto-calculated routes are considered efficient
            "gps_verified": True,
            "auto_calculated": True,
            "average_speed_kmh": speed_kmh,
            "trip_validation": {
                "gps_start_verified": start_location['lat'] != 0.0,
                "gps_end_verified": destination['lat'] != 0.0,
                "distance_auto_calculated": True,
                "time_locked": True
            }
        }
        
        response = requests.post(f"{BACKEND_URL}/api/record-trip", 
                               json=trip_data, headers=headers)
        
        if response.status_code == 200:
            result = response.json()
            
            # Reset trip state
            st.session_state.trip_active = False
            st.session_state.trip_start_time = None
            
            # Enhanced success display
            st.success(f"""
            🎉 **Trip Completed Successfully!**
            
            🏁 **Route:** {start_location['address']} → {destination['address']}
            📏 **Distance:** {distance_km:.2f} km
            ⏱️ **Duration:** {duration_minutes} minutes  
            🏃 **Average Speed:** {speed_kmh:.1f} km/h
            🚗 **Transport:** {transport_mode.title()}
            
            💰 **Rewards Earned:**
            🪙 **EcoCoins:** +{result['ecocoins_earned']}
            💚 **CO₂ Saved:** {result['co2_saved']:.4f} kg
            💰 **New Balance:** {result['new_balance']} EcoCoins
            """)
            
            # Show efficiency bonus
            if speed_kmh > 0:
                transport_avg_speeds = {"walk": 5, "bike": 15, "car": 25, "motorbike": 30, "bus": 20, "metro": 35}
                avg_speed = transport_avg_speeds.get(transport_mode, 25)
                efficiency = (avg_speed / speed_kmh) * 100 if speed_kmh > 0 else 100
                
                if efficiency > 120:
                    st.info(f"🏆 **Efficiency Bonus!** You traveled {efficiency:.0f}% more efficiently than average!")
                elif efficiency > 90:
                    st.info(f"👍 **Good Efficiency:** {efficiency:.0f}% of expected travel time")
            
            # Celebration effects
            st.balloons()
            
            # Auto-refresh to update balance
            time.sleep(2)
            st.rerun()
            
        else:
            error_detail = response.json().get("detail", "Unknown error")
            st.error(f"❌ Failed to record trip: {error_detail}")
            
    except Exception as e:
        st.error(f"❌ Trip recording error: {str(e)}")
        st.session_state.trip_active = False
        st.session_state.trip_start_time = None


def calculate_ecocoin_preview(distance_km: float, duration_minutes: int, transport_mode: str) -> dict:
    """Calculate EcoCoin preview for user interface"""
    # Use the same calculation as the backend
    base_coins = distance_km * 2  # Base 2 EcoCoins per km
    
    transport_multipliers = {
        "walk": 5.0,
        "bike": 4.0,  
        "metro": 3.0,
        "bus": 2.5,
        "motorbike": 1.2,
        "car": 1.0
    }
    
    multiplier = transport_multipliers.get(transport_mode, 1.0)
    estimated_ecocoins = int(base_coins * multiplier)
    
    # Calculate CO2 savings
    emission_factors = {
        "car": 0.21, "motorbike": 0.11, "bus": 0.08, "metro": 0.04,
        "bike": 0.0, "walk": 0.0
    }
    
    car_emission = distance_km * emission_factors["car"]
    actual_emission = distance_km * emission_factors.get(transport_mode, emission_factors["car"])
    co2_saved = max(0, car_emission - actual_emission)
    
    return {
        "estimated_ecocoins": estimated_ecocoins,
        "co2_saved": co2_saved,
        "transport_multiplier": multiplier
    }


def government_services_interface():
    """FIXED: Government services interface with proper styling"""
    st.subheader("🏛️ Government Services & Discounts")
    
    # Add custom CSS for service cards
    st.markdown("""
    <style>
    .service-card {
        background: linear-gradient(135deg, #e8f5e8 0%, #d4edda 100%) !important;
        color: #155724 !important;
        padding: 20px;
        border-radius: 10px;
        margin: 10px 0;
        border-left: 4px solid #28a745;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .service-card h4 {
        color: #155724 !important;
        font-weight: bold;
        margin-bottom: 10px;
    }
    .service-card p {
        color: #155724 !important;
        margin: 5px 0;
    }
    .service-card strong {
        color: #0d4e14 !important;
    }
    .redeem-card {
        background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%) !important;
        color: #212529 !important;
        padding: 20px;
        border-radius: 10px;
        margin: 10px 0;
        border: 2px solid #007bff;
        box-shadow: 0 2px 8px rgba(0,123,255,0.2);
    }
    .discount-preview {
        background: linear-gradient(135deg, #fff3cd 0%, #ffeaa7 100%) !important;
        color: #856404 !important;
        padding: 15px;
        border-radius: 8px;
        border-left: 4px solid #ffc107;
        margin: 10px 0;
    }
    </style>
    """, unsafe_allow_html=True)
    
    try:
        response = requests.get(f"{BACKEND_URL}/api/government-services")
        if response.status_code == 200:
            services_data = response.json()
            services = services_data["services"]
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("### 🎫 Available Services")
                
                for service_type, service_info in services.items():
                    # Service icons
                    service_icons = {
                        "metro": "🚇",
                        "bus": "🚌", 
                        "parking": "🅿️",
                        "fuel_subsidy": "⛽",
                        "toll_tax": "🛣️",
                        "vehicle_registration": "📝",
                        "pollution_certificate": "🌱"
                    }
                    
                    icon = service_icons.get(service_type, "🎯")
                    
                    st.markdown(f"""
                    <div class="service-card">
                        <h4>{icon} {service_type.replace('_', ' ').title()}</h4>
                        <p><strong>Base Price:</strong> ₹{service_info['base_price']}</p>
                        <p><strong>Max Discount:</strong> {service_info['max_discount']}%</p>
                        <p><strong>Service Category:</strong> Transportation & Utilities</p>
                    </div>
                    """, unsafe_allow_html=True)
            
            with col2:
                st.markdown("### 💳 Redeem Service Discount")
                
                if st.session_state.ecocoin_token:
                    st.markdown("""
                    <div class="redeem-card">
                        <h4>🪙 EcoCoin Service Redemption</h4>
                        <p>Use your earned EcoCoins to get discounts on government services!</p>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    with st.form("service_redemption_form"):
                        selected_service = st.selectbox(
                            "Select Service", 
                            list(services.keys()), 
                            key="service_select_dropdown"
                        )
                        
                        ecocoins_to_use = st.number_input(
                            "EcoCoins to Use", 
                            min_value=1, 
                            max_value=1000, 
                            value=50, 
                            step=10,
                            key="ecocoins_redemption_amount"
                        )
                        
                        if selected_service in services:
                            base_price = services[selected_service]["base_price"]
                            max_discount_percent = services[selected_service]["max_discount"]
                            
                            # Calculate discount preview
                            discount_rates = {
                                "metro": 0.1, "bus": 0.15, "parking": 0.05,
                                "fuel_subsidy": 0.02, "toll_tax": 0.04,
                                "vehicle_registration": 0.03, "pollution_certificate": 0.08
                            }
                            
                            discount_rate = discount_rates.get(selected_service, 0.05)
                            estimated_discount = min(
                                ecocoins_to_use * discount_rate, 
                                base_price * max_discount_percent / 100
                            )
                            estimated_final_price = max(0, base_price - estimated_discount)
                            
                            st.markdown(f"""
                            <div class="discount-preview">
                                <h4>📊 Discount Preview</h4>
                                <p><strong>Original Price:</strong> ₹{base_price}</p>
                                <p><strong>Your Discount:</strong> ₹{estimated_discount:.2f}</p>
                                <p><strong>Final Price:</strong> ₹{estimated_final_price:.2f}</p>
                                <p><strong>Savings:</strong> {((estimated_discount/base_price)*100):.1f}%</p>
                            </div>
                            """, unsafe_allow_html=True)
                        
                        redeem_clicked = st.form_submit_button(
                            "🎯 Redeem Service Discount", 
                            type="primary",
                            key="redeem_service_button"
                        )
                        
                        if redeem_clicked:
                            try:
                                headers = {"Authorization": f"Bearer {st.session_state.ecocoin_token}"}
                                response = requests.post(
                                    f"{BACKEND_URL}/api/redeem-service",
                                    params={
                                        "service_type": selected_service, 
                                        "ecocoins_to_use": ecocoins_to_use
                                    },
                                    headers=headers
                                )
                                
                                if response.status_code == 200:
                                    result = response.json()
                                    
                                    st.success(f"""
                                    ✅ **Service Redeemed Successfully!**
                                    
                                    🎫 **Redemption Code:** `{result['redemption_code']}`
                                    
                                    💰 **Original Price:** ₹{result['original_price']}
                                    💸 **Your Discount:** ₹{result['discount_amount']:.2f}
                                    💳 **Final Price:** ₹{result['final_price']:.2f}
                                    
                                    🪙 **EcoCoins Used:** {result['ecocoins_used']}
                                    💰 **Remaining Balance:** {result['new_balance']} EcoCoins
                                    
                                    ⏰ **Valid Until:** {result['expires_at'][:10]}
                                    
                                    📱 **Instructions:** Present this code at the service center
                                    """)
                                    
                                    # Show QR code placeholder
                                    st.info("🔗 QR Code for service redemption will be generated here")
                                    
                                else:
                                    error_detail = response.json().get("detail", "Unknown error")
                                    st.error(f"❌ Redemption failed: {error_detail}")
                                    
                            except Exception as e:
                                st.error(f"❌ Redemption error: {str(e)}")
                else:
                    st.markdown("""
                    <div class="redeem-card">
                        <h4>🔒 Login Required</h4>
                        <p>Please login to your EcoCoin account to redeem services</p>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Show benefits for non-logged users
                    st.markdown("""
                    <div class="service-card">
                        <h4>🌟 EcoCoin Benefits</h4>
                        <p><strong>✅ Metro & Bus:</strong> Up to 50% discount</p>
                        <p><strong>✅ Parking:</strong> Up to 30% discount</p>
                        <p><strong>✅ Fuel Subsidy:</strong> Direct cost reduction</p>
                        <p><strong>✅ Vehicle Services:</strong> Registration & certificates</p>
                    </div>
                    """, unsafe_allow_html=True)
    
    except Exception as e:
        st.error(f"❌ Failed to load services: {str(e)}")
        st.info("🔧 Please check if the backend service is running properly")

    
    except Exception as e:
        st.error(f"❌ Failed to load services: {str(e)}")
  
        st.error(f"❌ Failed to load services: {str(e)}")

def display_leaderboard():
    """Display EcoCoin leaderboard with unique keys"""
    st.subheader("🏆 EcoCoin Leaderboard")
    
    try:
        response = requests.get(f"{BACKEND_URL}/api/leaderboard")
        if response.status_code == 200:
            leaderboard_data = response.json()
            leaderboard = leaderboard_data["leaderboard"]
            
            if leaderboard:
                # Top 3 podium display
                if len(leaderboard) >= 3:
                    col1, col2, col3 = st.columns(3)
                    
                    with col2:  # 1st place center
                        st.markdown(f"""
                        <div style="text-align: center; background: linear-gradient(135deg, #ffd700, #ffed4e); 
                                   padding: 20px; border-radius: 15px; margin: 10px;">
                            <h2>🥇</h2>
                            <h3>{leaderboard[0]['username']}</h3>
                            <p><strong>🪙 {leaderboard[0]['ecocoin_balance']} EcoCoins</strong></p>
                            <p>💚 {leaderboard[0]['total_co2_saved']:.2f} kg CO₂ saved</p>
                        </div>
                        """, unsafe_allow_html=True)
                    
                    with col1:  # 2nd place left
                        st.markdown(f"""
                        <div style="text-align: center; background: linear-gradient(135deg, #c0c0c0, #e8e8e8); 
                                   padding: 15px; border-radius: 15px; margin: 10px;">
                            <h3>🥈</h3>
                            <h4>{leaderboard[1]['username']}</h4>
                            <p><strong>🪙 {leaderboard[1]['ecocoin_balance']}</strong></p>
                            <p>💚 {leaderboard[1]['total_co2_saved']:.2f} kg</p>
                        </div>
                        """, unsafe_allow_html=True)
                    
                    with col3:  # 3rd place right
                        st.markdown(f"""
                        <div style="text-align: center; background: linear-gradient(135deg, #cd7f32, #deb887); 
                                   padding: 15px; border-radius: 15px; margin: 10px;">
                            <h3>🥉</h3>
                            <h4>{leaderboard[2]['username']}</h4>
                            <p><strong>🪙 {leaderboard[2]['ecocoin_balance']}</strong></p>
                            <p>💚 {leaderboard[2]['total_co2_saved']:.2f} kg</p>
                        </div>
                        """, unsafe_allow_html=True)
                
                # Full leaderboard table
                st.markdown("### 📊 Full Rankings")
                leaderboard_df = pd.DataFrame(leaderboard)
                leaderboard_df.index = leaderboard_df.index + 1  # Start ranking from 1
                
                st.dataframe(
                    leaderboard_df[['username', 'ecocoin_balance', 'total_co2_saved']].rename(columns={
                        'username': '👤 Username',
                        'ecocoin_balance': '🪙 EcoCoins',
                        'total_co2_saved': '💚 CO₂ Saved (kg)'
                    }),
                    use_container_width=True
                )
            else:
                st.info("🏆 No users on leaderboard yet. Be the first EcoCoin champion!")
                
    except Exception as e:
        st.error(f"❌ Failed to load leaderboard: {str(e)}")

def create_summary_charts(metrics_data):
    """Create analytics charts from metrics data"""
    if not metrics_data or "locations" not in metrics_data:
        return None, None
    
    locations = metrics_data["locations"]
    
    # Vehicle count chart
    vehicle_data = pd.DataFrame({
        'Location': [f'Location {i+1}' for i in range(len(locations))],
        'Vehicles': [loc['vehicles'] for loc in locations],
        'Status': [loc['status'] for loc in locations],
        'CO2_Reduction': [loc['co2'] for loc in locations]  # REMOVED: ecocoins_generated
    })
    
    fig_vehicles = px.bar(
        vehicle_data, 
        x='Location', 
        y='Vehicles',
        color='Status',
        color_discrete_map={'Low': '#51cf66', 'Medium': '#ffd43b', 'High': '#ff6b6b'},
        title="🚗 Real-time Vehicle Count by Location",
        hover_data=['CO2_Reduction']
    )
    fig_vehicles.update_layout(height=400)
    
    # CO2 reduction chart (REPLACED: ecocoins chart)
    fig_co2 = px.bar(
        vehicle_data,
        x='Location',
        y='CO2_Reduction',
        title="🌱 CO₂ Reduction by Location (kg)",
        color='CO2_Reduction',
        color_continuous_scale='Greens'
    )
    fig_co2.update_layout(height=400)
    
    return fig_vehicles, fig_co2

def main():
    """Main application function - FIXED: All button ID conflicts resolved"""
    
    # Authentication
    user_role = login()
    if user_role is None:
        st.info("📝 Please log in using the sidebar to access the complete system")
        return
    
    # EcoCoin authentication
    ecocoin_profile = ecocoin_login_register()
    
    # Auto-refresh controls in sidebar (FIXED: Unique keys)
    st.sidebar.markdown("---")
    st.sidebar.header("🔄 System Settings")
    
    auto_refresh = st.sidebar.checkbox("Auto-refresh enabled", value=True, key="auto_refresh_toggle")
    refresh_interval = st.sidebar.selectbox("Refresh interval (seconds)", [1, 2, 3, 5], index=1, key="refresh_interval_select")
    
    if st.sidebar.button("🔄 Manual Refresh", key="manual_refresh_btn"):
        st.session_state.refresh_counter += 1
        st.cache_data.clear()
        st.rerun()
    
    if auto_refresh:
        countdown_placeholder = st.sidebar.empty()
    
    # Header
    st.title("🚦 Smart Traffic Management - All Issues Fixed 🗺️")
    st.markdown("### Complete Solution: All Features + GPS Navigation (User Dashboard Only)")
    
    # Show current user role
    if user_role == "authority":
        st.markdown("**👑 Authority Dashboard** - All original features available")
    else:
        st.markdown("**👤 User Dashboard** - All features + GPS Navigation + Enhanced EcoCoin System")
    
    current_time = datetime.now().strftime("%H:%M:%S")
    st.markdown(f"<div class='updating-indicator'>⏰ Last updated: {current_time}</div>", 
                unsafe_allow_html=True)
    st.markdown("---")
    
    # Check backend connection
    backend_connected, health_data = check_backend_connection()
    
    if not backend_connected:
        st.error("🔴 **Backend Connection Failed**")
        st.error("Please ensure the fixed backend server is running on port 8000")
        if st.button("🔄 Retry Connection", key="retry_backend_connection"):
            st.rerun()
        return
    
    # System Status Dashboard
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.success("🟢 Backend Connected")
    with col2:
        if health_data:
            confidence_status = "🎯 No Confidence" if health_data.get('confidence_scores_removed') else "📊 With Confidence"
            st.info(confidence_status)
    with col3:
        if health_data:
            gps_status = "🗺️ GPS: Users Only" if health_data.get('gps_navigation_enabled') else "📍 GPS: Disabled"
            st.info(gps_status)
    with col4:
        if health_data:
            issues_status = "✅ All Fixed" if health_data.get('all_issues_fixed') else "⚠️ Issues Present"
            st.info(issues_status)
    with col5:
        if st.button("🔄 Refresh Status", key="refresh_status_btn"):
            st.rerun()
    
    # EcoCoin System Status (if available)
    if health_data and 'ecocoin_system' in health_data:
        ecocoin_data = health_data['ecocoin_system']
        
        st.subheader("🪙 EcoCoin System Overview")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("👥 Total Users", ecocoin_data['total_users'])
        with col2:
            st.metric("🪙 EcoCoins in Circulation", ecocoin_data['total_ecocoins_in_circulation'])
        with col3:
            st.metric("💚 Total CO₂ Saved", f"{ecocoin_data['total_co2_saved_kg']} kg")
        with col4:
            generation_type = ecocoin_data.get('ecocoin_generation', 'system_based')
            generation_display = "👤 User Trip Based" if generation_type == "user_trip_based" else "🏢 System Based"
            st.info(generation_display)
        
        st.markdown("---")
    
    # Fetch current metrics
    try:
        metrics_data = fetch_metrics()
        st.session_state.last_metrics = metrics_data
    except Exception as e:
        st.error(f"❌ Failed to fetch metrics: {str(e)}")
        metrics_data = st.session_state.last_metrics
    
    if metrics_data:
        # Global Summary (FIXED: Removed ecocoins from summary)
        summary = metrics_data.get("summary", {})
        
        st.subheader("🌐 Live Traffic Overview")
        col1, col2, col3, col4 = st.columns(4)  # REDUCED: from 5 to 4 columns
        
        with col1:
            st.metric("🚗 Total Vehicles", summary.get("total_vehicles", 0))
        with col2:
            st.metric("⚠️ Active Bottlenecks", summary.get("active_bottlenecks", 0))
        with col3:
            avg_wait = summary.get('average_waiting_time', 0)
            st.metric("⏱️ Avg Wait Time", f"{avg_wait:.1f}s")
        with col4:
            total_co2 = summary.get('total_co2_reduction', 0)
            st.metric("🌱 CO₂ Reduction", f"{total_co2:.2f} kg")
        # REMOVED: EcoCoins Generated metric
        
        st.markdown("---")
        
        # Main Content Tabs (FIXED: Different tabs for Authority vs User)
        if user_role == "authority":
            # Authority Dashboard - Original tabs (no GPS)
            tab1, tab2, tab3, tab4, tab5 = st.tabs([
                "🎥 Live Video Feeds", 
                "🪙 EcoCoin Dashboard", 
                "📊 Traffic Analytics", 
                "🏛️ Government Services",
                "🏆 Leaderboard"
            ])
            
            # Set tab variables for authority
            video_tab = tab1
            ecocoin_tab = tab2
            analytics_tab = tab3
            services_tab = tab4
            leaderboard_tab = tab5
            
        else:
            # User Dashboard - Includes GPS navigation
            tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
                "🎥 Live Video Feeds",
                "🗺️ GPS Navigation",  # NEW: Only for users
                "🪙 EcoCoin Dashboard", 
                "📊 Traffic Analytics", 
                "🏛️ Government Services",
                "🏆 Leaderboard"
            ])
            
            # Set tab variables for users  
            video_tab = tab1
            gps_tab = tab2
            ecocoin_tab = tab3
            analytics_tab = tab4
            services_tab = tab5
            leaderboard_tab = tab6
        
        # Live Video Feeds Tab
        with video_tab:
            st.subheader("📺 Real-time Traffic Cameras")
            st.info("🎯 **Fixed:** Clean display with no confidence scores, all detection features preserved")
            
            locations = metrics_data.get("locations", [])
            col1, col2 = st.columns(2)
            
            for i in range(min(VIDEO_COUNT, len(locations))):
                with col1 if i % 2 == 0 else col2:
                    # Video stream container
                    video_container = st.empty()
                    display_video_stream(i + 1, video_container)
                    
                    # Real-time metrics for this location
                    metrics = locations[i]
                    
                    st.markdown(f"**📊 Location {i+1} Live Metrics:**")
                    
                    # Metrics display
                    metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)
                    
                    with metric_col1:
                        status_color = {"Low": "🟢", "Medium": "🟡", "High": "🔴"}
                        status_emoji = status_color.get(metrics['status'], '⚪')
                        st.metric("Traffic Status", f"{status_emoji} {metrics['status']}")
                    
                    with metric_col2:
                        st.metric("🚗 Vehicles", metrics["vehicles"])
                    
                    with metric_col3:
                        st.metric("⏱️ Signal Time", f"{metrics['signal_time']}s")
                    
                    with metric_col4:
                        st.metric("⌛ Wait Time", f"{metrics['waiting_time']}s")
                    
                    # Additional metrics row
                    metric_col1, metric_col2, metric_col3 = st.columns(3)
                    
                    with metric_col1:
                        st.metric("🌱 CO₂ Reduction", f"{metrics['co2']:.2f} kg")
                    
                    with metric_col2:
                        bottleneck_emoji = "🔴" if metrics["bottleneck"] == "Yes" else "🟢"
                        st.metric("⚠️ Bottleneck", f"{bottleneck_emoji} {metrics['bottleneck']}")
                    
                    with metric_col3:
                        # Data freshness indicator
                        current_time = time.time()
                        data_age = current_time - metrics.get('last_update', current_time)
                        if data_age < 5:
                            st.success("🔴 LIVE DATA")
                        else:
                            st.warning(f"⚠️ {data_age:.1f}s ago")
                    
                    st.markdown("---")
        
        # GPS Navigation Tab (ONLY for users)
        if user_role != "authority":
            with gps_tab:
                gps_navigation_dashboard()
        
        # EcoCoin Dashboard Tab
        with ecocoin_tab:
            if ecocoin_profile:
                col1, col2 = st.columns(2)
                
                with col1:
                    record_trip_interface()
                
                with col2:
                    st.subheader("📊 Your EcoCoin Statistics")
                    
                    user_info = ecocoin_profile['user_info']
                    stats = ecocoin_profile['statistics']
                    
                    # User stats card
                    st.markdown(f"""
                    <div class="ecocoin-card">
                        <h2>🪙 {user_info['ecocoin_balance']}</h2>
                        <p><strong>Current Balance</strong></p>
                        <hr style="border-color: rgba(255,255,255,0.3);">
                        <p>💚 <strong>{user_info['total_co2_saved']:.2f} kg</strong> CO₂ saved</p>
                        <p>🛣️ <strong>{stats['total_trips']}</strong> trips recorded</p>
                        <p>📏 <strong>{stats['total_distance_km']:.1f} km</strong> total distance</p>
                        <p>🏆 <strong>Rank:</strong> Check leaderboard!</p>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Recent transactions
                    st.subheader("💰 Recent EcoCoin Activity")
                    
                    recent_transactions = ecocoin_profile['recent_transactions'][:5]
                    
                    if recent_transactions:
                        for tx in recent_transactions:
                            tx_type = tx['type']
                            amount = tx['amount']
                            desc = tx['description']
                            date = tx['date'][:10]
                            
                            emoji = "📈" if tx_type == "earn" else "📉"
                            color = "#e8f5e8" if tx_type == "earn" else "#ffe6e6"
                            
                            st.markdown(f"""
                            <div style="background-color: {color}; padding: 10px; border-radius: 8px; margin: 5px 0;">
                                <p><strong>{emoji} {amount} EcoCoins</strong> - {desc}</p>
                                <small>📅 {date} | CO₂: {tx.get('co2_saved', 0):.3f} kg</small>
                            </div>
                            """, unsafe_allow_html=True)
                    else:
                        st.info("💡 Start recording trips to earn EcoCoins!")
                        
                    # EcoCoin earning tips
                    with st.expander("💡 EcoCoin Earning Tips"):
                        st.markdown("""
                        **🪙 How to Maximize EcoCoins:**
                        
                        1. **🚶 Walk or 🚴 Bike:** 4-5x multiplier
                        2. **🚇 Use Metro/🚌 Bus:** 2.5-3x multiplier  
                        3. **⏱️ Complete trips faster:** Time bonus
                        4. **🗺️ Use GPS navigation:** Find efficient routes
                        5. **🎯 Choose eco-friendly options:** Higher rewards
                        
                        **💡 Formula:** (Distance × 2) × Transport Multiplier + Time Bonus
                        """)
            else:
                st.info("🔒 Please login to your EcoCoin account to view your dashboard")
                
                # Show system benefits for non-logged users
                st.markdown("""
                <div class="gps-card">
                    <h3>🪙 Join the EcoCoin System!</h3>
                    <p>Earn rewards for sustainable transportation choices</p>
                    <ul style="text-align: left; list-style: none; padding-left: 0;">
                        <li>🎯 Earn EcoCoins for every trip</li>
                        <li>🏛️ Redeem for government service discounts</li>  
                        <li>🗺️ Get GPS navigation with traffic data</li>
                        <li>📊 Track your environmental impact</li>
                        <li>🏆 Compete on the leaderboard</li>
                    </ul>
                </div>
                """, unsafe_allow_html=True)
        
        # Traffic Analytics Tab  
        with analytics_tab:
            if require_permission("view_all"):
                st.subheader("📊 Traffic & System Analytics")
                st.info("🔧 **Fixed:** EcoCoin metrics moved to user trip tracking, system focuses on traffic analysis")
                
                # Create charts
                fig_vehicles, fig_co2 = create_summary_charts(metrics_data)
                
                if fig_vehicles and fig_co2:
                    col1, col2 = st.columns(2)
                    with col1:
                        st.plotly_chart(fig_vehicles, use_container_width=True)
                    with col2:
                        st.plotly_chart(fig_co2, use_container_width=True)
                
                # Real-time metrics comparison table
                st.subheader("📈 Real-time Traffic Metrics Comparison")
                
                comparison_data = []
                for i, location in enumerate(locations):
                    status_mapping = {'Low': '🟢', 'Medium': '🟡', 'High': '🔴'}
                    status_emoji = status_mapping.get(location['status'], '⚪')
                    status_display = f"{status_emoji} {location['status']}"
                    
                    bottleneck_display = "🔴 Yes" if location["bottleneck"] == "Yes" else "🟢 No"
                    
                    comparison_data.append({
                        "📍 Location": f"Location {i+1}",
                        "🚗 Vehicles": location["vehicles"],
                        "📊 Status": status_display,
                        "⏱️ Signal (s)": location["signal_time"],
                        "⌛ Wait (s)": location["waiting_time"],
                        "⚠️ Bottleneck": bottleneck_display,
                        "🌱 CO₂ (kg)": f"{location['co2']:.2f}",
                        "🕐 Last Update": f"{(time.time() - location['last_update']):.0f}s ago"
                    })
                
                if comparison_data:
                    df_comparison = pd.DataFrame(comparison_data)
                    st.dataframe(df_comparison, use_container_width=True, hide_index=True)
                
                # System performance metrics
                st.subheader("⚡ System Performance")
                
                perf_col1, perf_col2, perf_col3, perf_col4 = st.columns(4)
                
                with perf_col1:
                    st.metric("🎥 Active Cameras", len([l for l in locations if (time.time() - l['last_update']) < 10]))
                
                with perf_col2:
                    st.metric("📊 Data Freshness", "Live" if all((time.time() - l['last_update']) < 5 for l in locations) else "Delayed")
                
                with perf_col3:
                    avg_vehicles = sum(l['vehicles'] for l in locations) / len(locations) if locations else 0
                    st.metric("📈 Avg Vehicles", f"{avg_vehicles:.1f}")
                
                with perf_col4:
                    efficient_signals = len([l for l in locations if 20 <= l['signal_time'] <= 60])
                    st.metric("🚦 Optimal Signals", f"{efficient_signals}/{len(locations)}")
                
                st.info("📈 **Coming Soon:** Historical analytics, trend analysis, and predictive modeling")
                
            else:
                st.warning("🔒 You don't have permission to view detailed analytics")
                st.info("💡 Authority or admin access required for traffic analytics")
        
        # Government Services Tab
        with services_tab:
            government_services_interface()
        
        # Leaderboard Tab
        with leaderboard_tab:
            display_leaderboard()
    
    else:
        st.error("❌ Unable to fetch traffic metrics from backend")
        st.info("🔧 **Troubleshooting:**")
        st.info("1. Check if backend server is running on port 8000")
        st.info("2. Verify video files are present in backend directory")
        st.info("3. Ensure YOLO model is loaded correctly")
        
        if st.button("🔄 Retry Data Fetch", key="retry_data_fetch"):
            st.rerun()
    
    # Auto-refresh logic (FIXED: Works without conflicts)
    if auto_refresh:
        # Show countdown
        for i in range(refresh_interval, 0, -1):
            if 'countdown_placeholder' in locals():
                countdown_placeholder.info(f"🔄 Next refresh in: {i}s")
            time.sleep(1)
        
        # Clear cache and refresh
        st.cache_data.clear()
        st.rerun()

if __name__ == "__main__":
    main()
        
