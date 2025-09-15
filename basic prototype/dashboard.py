import streamlit as st
import pandas as pd
import os
import plotly.express as px
import plotly.graph_objects as go
import random
import time

# ---------------------------
# Page Config
# ---------------------------
st.set_page_config(page_title="Smart Traffic Dashboard", layout="wide")
st.title("🚦 Smart Traffic Management Dashboard")

csv_file = "traffic_log.csv"

# ---------------------------
# Sidebar Settings
# ---------------------------
st.sidebar.header("⚙️ Settings")
refresh_interval = st.sidebar.slider("Dashboard Refresh Interval (seconds)", 1, 10, 5)
traffic_threshold = st.sidebar.number_input("High Traffic Threshold", min_value=10, value=50, step=5)

# Customizable green light times
st.sidebar.markdown("### ⏱️ Green Light Duration")
green_low = st.sidebar.number_input("Low Traffic (s)", min_value=10, value=30, step=5)
green_medium = st.sidebar.number_input("Medium Traffic (s)", min_value=10, value=40, step=5)
green_high = st.sidebar.number_input("High Traffic (s)", min_value=10, value=60, step=5)

# Dropdown for selecting metric
metric = st.sidebar.selectbox(
    "Select Metric for Trend",
    ["Vehicle_Count", "Signal_Green_Time", "Both"]
)

# ---------------------------
# Load CSV
# ---------------------------
if not os.path.exists(csv_file):
    st.warning("⚠️ Run `app.py` first to generate traffic logs.")
else:
    df = pd.read_csv(csv_file)

    # ---------------------------
    # KPI Cards
    # ---------------------------
    st.subheader("📌 Key Performance Indicators")
    kpi_col1, kpi_col2, kpi_col3 = st.columns(3)

    peak_vehicles = df["Vehicle_Count"].max() if not df.empty else 0
    avg_green_time = df["Signal_Green_Time"].mean() if not df.empty else 0
    latest_traffic = df["Vehicle_Count"].iloc[-1] if not df.empty else 0

    with kpi_col1:
        st.metric("🚗 Peak Vehicle Count Today", peak_vehicles, delta=random.randint(-5, 5))
    with kpi_col2:
        st.metric("🟢 Avg Green Light Time (s)", round(avg_green_time, 2), delta=random.uniform(-1, 1))
    with kpi_col3:
        st.metric("🚦 Vehicles at Last Entry", latest_traffic, delta=random.randint(-5, 5))

    st.markdown("---")

    # ---------------------------
    # Last Entry Metrics (Dynamic)
    # ---------------------------
    last = df.tail(1).iloc[0]
    last_vehicle_count = int(last["Vehicle_Count"])

    # Dynamic status and green light time
    if last_vehicle_count >= traffic_threshold:
        dynamic_status = "High"
        dynamic_green_time = green_high
    elif last_vehicle_count >= traffic_threshold / 2:
        dynamic_status = "Medium"
        dynamic_green_time = green_medium
    else:
        dynamic_status = "Low"
        dynamic_green_time = green_low

    kpi1, kpi2, kpi3 = st.columns(3)
    with kpi1:
        st.metric("🚗 Vehicles Detected", last_vehicle_count)
    with kpi2:
        st.metric("🔴 Traffic Status", dynamic_status)
    with kpi3:
        st.metric("🟢 Green Light Time (s)", dynamic_green_time)

    st.markdown("---")

    # ---------------------------
    # Recent Traffic Logs
    # ---------------------------
    st.subheader("📊 Recent Traffic Logs")
    st.dataframe(df.tail(10), use_container_width=True)

    # CSV Download
    csv_bytes = df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Download Traffic Logs CSV",
        data=csv_bytes,
        file_name="traffic_logs.csv",
        mime="text/csv"
    )

    st.markdown("---")

    # ---------------------------
    # Traffic Gauge (Congestion Level)
    # ---------------------------
    st.subheader("🚦 Traffic Congestion Gauge")
    max_value = max(traffic_threshold*2, last_vehicle_count*1.5)
    fig_gauge = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=last_vehicle_count,
        delta={'reference': traffic_threshold},
        gauge={'axis': {'range': [0, max_value]},
               'bar': {'color': "red" if dynamic_status=="High" else "orange" if dynamic_status=="Medium" else "green"}},
        title={'text': "Vehicle Count"}
    ))
    st.plotly_chart(fig_gauge, use_container_width=True)

    st.markdown("---")

    # ---------------------------
    # Interactive Traffic Trends
    # ---------------------------
    st.subheader("📈 Traffic Trends (Interactive)")
    if metric == "Both":
        fig = px.line(
            df,
            x="Timestamp",
            y=["Vehicle_Count", "Signal_Green_Time"],
            markers=True,
            title="Traffic vs Signal Time"
        )
    else:
        fig = px.line(
            df,
            x="Timestamp",
            y=metric,
            markers=True,
            title=f"{metric} Over Time"
        )
    fig.update_layout(xaxis_title="Time", yaxis_title="Value", hovermode="x unified")
    st.plotly_chart(fig, use_container_width=True)

    # ---------------------------
    # High Traffic Alert
    # ---------------------------
    if last_vehicle_count >= traffic_threshold:
        st.error(f"🚨 HIGH TRAFFIC ALERT! Vehicles: {last_vehicle_count}")

    # ---------------------------
    # Auto-refresh
    # ---------------------------
    time.sleep(refresh_interval)
    st.rerun()
