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
from auth import login, require_permission, get_current_user

# Configuration
BACKEND_URL = "http://127.0.0.1:8000"
VIDEO_COUNT = 2
REFRESH_INTERVAL = 1  # seconds

# Page configuration
st.set_page_config(
    page_title="Smart Traffic Management System",
    page_icon="🚦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
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
</style>
""", unsafe_allow_html=True)

def check_backend_connection():
    """Check if backend is accessible"""
    try:
        response = requests.get(f"{BACKEND_URL}/health", timeout=5)
        return response.status_code == 200, response.json() if response.status_code == 200 else None
    except Exception as e:
        return False, str(e)

def fetch_metrics():
    """Fetch current metrics from backend"""
    try:
        response = requests.get(f"{BACKEND_URL}/metrics", timeout=10)
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        st.error(f"❌ Error fetching metrics: {str(e)}")
        return None

def display_video_feed(video_id: int, container):
    """Display video feed in the given container"""
    try:
        response = requests.get(f"{BACKEND_URL}/video/{video_id}", stream=True, timeout=10)
        if response.status_code == 200:
            bytes_data = b''
            for chunk in response.iter_content(chunk_size=1024):
                bytes_data += chunk
                a = bytes_data.find(b'\xff\xd8')
                b = bytes_data.find(b'\xff\xd9')
                if a != -1 and b != -1:
                    jpg = bytes_data[a:b+2]
                    bytes_data = bytes_data[b+2:]
                    try:
                        img = cv2.imdecode(np.frombuffer(jpg, np.uint8), cv2.IMREAD_COLOR)
                        if img is not None:
                            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                            container.image(img, use_column_width=True)
                            break  # Show one frame and exit
                    except Exception:
                        pass
        else:
            container.error(f"❌ Video feed {video_id} unavailable")
    except Exception as e:
        container.error(f"❌ Connection error: {str(e)}")

def create_summary_charts(metrics_data):
    """Create summary charts from metrics data"""
    if not metrics_data or "locations" not in metrics_data:
        return None, None
    
    locations = metrics_data["locations"]
    
    # Vehicle count chart
    vehicle_data = pd.DataFrame({
        'Location': [f'Location {i+1}' for i in range(len(locations))],
        'Vehicles': [loc['vehicles'] for loc in locations],
        'Status': [loc['status'] for loc in locations]
    })
    
    fig_vehicles = px.bar(
        vehicle_data, 
        x='Location', 
        y='Vehicles',
        color='Status',
        color_discrete_map={'Low': '#51cf66', 'Medium': '#ffd43b', 'High': '#ff6b6b'},
        title="Vehicle Count by Location"
    )
    
    # CO2 reduction chart
    co2_data = pd.DataFrame({
        'Location': [f'Location {i+1}' for i in range(len(locations))],
        'CO2_Reduction': [loc['co2'] for loc in locations]
    })
    
    fig_co2 = px.line(
        co2_data,
        x='Location',
        y='CO2_Reduction',
        title="CO₂ Reduction by Location",
        markers=True
    )
    
    return fig_vehicles, fig_co2

def main():
    """Main application function"""
    
    # Authentication
    user_role = login()
    if user_role is None:
        st.info("📝 Please log in using the sidebar to access the system")
        return
    
    # Header
    st.title("🚦 Smart Traffic Management System")
    st.markdown("---")
    
    # Check backend connection
    backend_connected, health_data = check_backend_connection()
    
    if not backend_connected:
        st.error("🔴 **Backend Connection Failed**")
        st.error("Please ensure the backend server is running on http://127.0.0.1:8000")
        st.info("Run the backend with: `python smart_traffic/backend/backend.py`")
        return
    
    # Backend status
    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        st.success("🟢 Backend Connected")
    with col2:
        if health_data:
            model_status = "✅ Loaded" if health_data.get('model_loaded') else "❌ Not Loaded"
            st.info(f"📊 Model Status: {model_status}")
    with col3:
        if st.button("🔄 Refresh"):
            st.rerun()
    
    # Authority controls
    if user_role == "authority" and require_permission("modify_settings"):
        with st.sidebar:
            st.header("⚙️ Authority Controls")
            bottleneck_threshold = st.slider("Bottleneck Threshold", 5, 50, 25)
            auto_refresh = st.checkbox("Auto Refresh", value=True)
            refresh_rate = st.slider("Refresh Rate (seconds)", 1, 10, 2)
            
            if st.button("🔧 Apply Settings"):
                st.success("✅ Settings applied!")
    
    # Fetch current metrics
    metrics_data = fetch_metrics()
    
    if metrics_data:
        # Summary metrics at top
        summary = metrics_data.get("summary", {})
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("🚗 Total Vehicles", summary.get("total_vehicles", 0))
        with col2:
            st.metric("⚠️ Active Bottlenecks", summary.get("active_bottlenecks", 0))
        with col3:
            avg_wait_time = summary.get('average_waiting_time', 0)
            st.metric("⏱️ Avg Wait Time", f"{avg_wait_time:.1f}s")
        with col4:
            total_co2 = summary.get('total_co2_reduction', 0)
            st.metric("🌱 CO₂ Reduction", f"{total_co2:.2f}")
        
        st.markdown("---")
        
        # Main content area
        tab1, tab2, tab3 = st.tabs(["📹 Live Feeds", "📊 Analytics", "📋 Detailed Metrics"])
        
        with tab1:
            # Video feeds and basic metrics
            col1, col2 = st.columns(2)
            locations = metrics_data.get("locations", [])
            
            for i in range(min(VIDEO_COUNT, len(locations))):
                with col1 if i % 2 == 0 else col2:
                    st.subheader(f"📍 Location {i+1}")
                    
                    # Video feed placeholder
                    video_container = st.empty()
                    display_video_feed(i+1, video_container)
                    
                    # Basic metrics
                    metrics = locations[i]
                    metric_col1, metric_col2, metric_col3 = st.columns(3)
                    
                    with metric_col1:
                        status_color = {"Low": "🟢", "Medium": "🟡", "High": "🔴"}
                        status_emoji = status_color.get(metrics['status'], '⚪')
                        st.metric("Traffic Status", f"{status_emoji} {metrics['status']}")
                        st.metric("🚗 Vehicles", metrics["vehicles"])
                    
                    with metric_col2:
                        st.metric("⏱️ Signal Time", f"{metrics['signal_time']}s")
                        st.metric("⌛ Wait Time", f"{metrics['waiting_time']}s")
                    
                    with metric_col3:
                        bottleneck_emoji = "🔴" if metrics["bottleneck"] == "Yes" else "🟢"
                        st.metric("Bottleneck", f"{bottleneck_emoji} {metrics['bottleneck']}")
                        st.metric("🌱 CO₂ Reduction", f"{metrics['co2']:.2f}")
                    
                    st.markdown("---")
        
        with tab2:
            if require_permission("view_all"):
                # Analytics charts
                fig_vehicles, fig_co2 = create_summary_charts(metrics_data)
                
                if fig_vehicles and fig_co2:
                    col1, col2 = st.columns(2)
                    with col1:
                        st.plotly_chart(fig_vehicles, use_container_width=True)
                    with col2:
                        st.plotly_chart(fig_co2, use_container_width=True)
                
                # Time series would go here (requires historical data)
                st.info("📈 Historical analytics require data logging implementation")
            else:
                st.warning("🔒 You don't have permission to view analytics")
        
        with tab3:
            if require_permission("view_all"):
                # Detailed metrics table
                st.subheader("📋 Detailed Location Metrics")
                
                # Convert to DataFrame for better display
                df_data = []
                for i, location in enumerate(locations):
                    df_data.append({
                        "Location": f"Location {i+1}",
                        "Vehicles": location["vehicles"],
                        "Status": location["status"], 
                        "Signal Time (s)": location["signal_time"],
                        "Wait Time (s)": location["waiting_time"],
                        "CO₂ Reduction": location["co2"],
                        "Bottleneck": location["bottleneck"]
                    })
                
                if df_data:
                    df = pd.DataFrame(df_data)
                    st.dataframe(df, use_container_width=True)
                    
                    # Export functionality for authority users
                    if user_role == "authority" and require_permission("export_data"):
                        if st.button("📊 Export Data"):
                            csv = df.to_csv(index=False)
                            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                            filename = f"traffic_metrics_{timestamp}.csv"
                            st.download_button(
                                label="📥 Download CSV",
                                data=csv,
                                file_name=filename,
                                mime="text/csv"
                            )
            else:
                st.warning("🔒 You don't have permission to view detailed metrics")
    
    else:
        st.error("❌ Unable to fetch metrics from backend")
    
    # Auto-refresh for certain users
    if user_role == "authority" and 'auto_refresh' in locals() and auto_refresh:
        time.sleep(refresh_rate)
        st.rerun()

if __name__ == "__main__":
    main()
