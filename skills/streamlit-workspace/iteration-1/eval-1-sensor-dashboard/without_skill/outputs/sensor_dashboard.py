import streamlit as st
import pandas as pd
import plotly.express as px
import os

# Page configuration
st.set_page_config(
    page_title="Temperature Sensor Dashboard", page_icon="thermometer", layout="wide"
)

st.title("Temperature Sensor Dashboard")
st.markdown(
    "Explore temperature and humidity readings from multiple sensors over time."
)


# Load data
@st.cache_data
def load_data(filepath):
    """Load CSV data and parse timestamps."""
    df = pd.read_csv(filepath)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df


# Determine data path - check multiple locations
possible_paths = [
    "data/readings.csv",
    "../../../test-data/readings.csv",
    "/sessions/friendly-relaxed-goodall/mnt/radiofrequency/.claude/skills/streamlit-workspace/iteration-1/eval-1-sensor-dashboard/test-data/readings.csv",
]

data_path = None
for path in possible_paths:
    if os.path.exists(path):
        data_path = path
        break

if data_path is None:
    st.error("Could not find readings.csv in expected locations.")
    st.stop()

df = load_data(data_path)

# Display data summary
with st.sidebar:
    st.header("Data Summary")
    st.metric("Total Records", len(df))
    st.metric("Sensors", df["sensor_id"].nunique())
    st.metric(
        "Date Range",
        f"{df['timestamp'].min().date()} to {df['timestamp'].max().date()}",
    )

# Filters
st.sidebar.header("Filters")

# Sensor filter
all_sensors = sorted(df["sensor_id"].unique().tolist())
selected_sensors = st.sidebar.multiselect(
    "Select Sensors", all_sensors, default=all_sensors
)

# Date range filter
min_date = df["timestamp"].min().date()
max_date = df["timestamp"].max().date()

date_range = st.sidebar.date_input(
    "Date Range", value=(min_date, max_date), min_value=min_date, max_value=max_date
)

# Handle date range
if isinstance(date_range, tuple) and len(date_range) == 2:
    start_date, end_date = date_range
else:
    start_date = min_date
    end_date = max_date

# Filter data
filtered_df = df[
    (df["sensor_id"].isin(selected_sensors))
    & (df["timestamp"].dt.date >= start_date)
    & (df["timestamp"].dt.date <= end_date)
]

# Display filtered data summary
st.sidebar.markdown("---")
st.sidebar.subheader("Filtered Data")
st.sidebar.metric("Records", len(filtered_df))
if len(filtered_df) > 0:
    st.sidebar.metric(
        "Temp Range (°C)",
        f"{filtered_df['temp_celsius'].min():.1f} to {filtered_df['temp_celsius'].max():.1f}",
    )
    st.sidebar.metric(
        "Humidity Range (%)",
        f"{filtered_df['humidity'].min():.1f} to {filtered_df['humidity'].max():.1f}",
    )

# Main content
if len(filtered_df) == 0:
    st.warning("No data matches the selected filters.")
    st.stop()

# Create tabs for different views
tab1, tab2, tab3, tab4 = st.tabs(
    ["Temperature Over Time", "Humidity Over Time", "Statistics", "Raw Data"]
)

with tab1:
    st.subheader("Temperature Readings")

    fig_temp = px.line(
        filtered_df,
        x="timestamp",
        y="temp_celsius",
        color="sensor_id",
        title="Temperature Over Time",
        labels={
            "temp_celsius": "Temperature (°C)",
            "timestamp": "Date/Time",
            "sensor_id": "Sensor",
        },
        markers=True,
    )
    fig_temp.update_layout(
        hovermode="x unified",
        height=500,
        xaxis_title="Date/Time",
        yaxis_title="Temperature (°C)",
    )
    st.plotly_chart(fig_temp, use_container_width=True)

with tab2:
    st.subheader("Humidity Readings")

    fig_humidity = px.line(
        filtered_df,
        x="timestamp",
        y="humidity",
        color="sensor_id",
        title="Humidity Over Time",
        labels={
            "humidity": "Humidity (%)",
            "timestamp": "Date/Time",
            "sensor_id": "Sensor",
        },
        markers=True,
    )
    fig_humidity.update_layout(
        hovermode="x unified",
        height=500,
        xaxis_title="Date/Time",
        yaxis_title="Humidity (%)",
    )
    st.plotly_chart(fig_humidity, use_container_width=True)

with tab3:
    st.subheader("Statistics by Sensor")

    # Calculate statistics
    stats = (
        filtered_df.groupby("sensor_id")
        .agg(
            {"temp_celsius": ["min", "max", "mean"], "humidity": ["min", "max", "mean"]}
        )
        .round(2)
    )

    stats.columns = [
        "Temp Min (°C)",
        "Temp Max (°C)",
        "Temp Mean (°C)",
        "Humidity Min (%)",
        "Humidity Max (%)",
        "Humidity Mean (%)",
    ]

    st.dataframe(stats, use_container_width=True)

    # Comparative box plots
    col1, col2 = st.columns(2)

    with col1:
        fig_temp_box = px.box(
            filtered_df,
            x="sensor_id",
            y="temp_celsius",
            title="Temperature Distribution by Sensor",
            labels={"temp_celsius": "Temperature (°C)", "sensor_id": "Sensor"},
        )
        fig_temp_box.update_layout(height=400)
        st.plotly_chart(fig_temp_box, use_container_width=True)

    with col2:
        fig_humidity_box = px.box(
            filtered_df,
            x="sensor_id",
            y="humidity",
            title="Humidity Distribution by Sensor",
            labels={"humidity": "Humidity (%)", "sensor_id": "Sensor"},
        )
        fig_humidity_box.update_layout(height=400)
        st.plotly_chart(fig_humidity_box, use_container_width=True)

with tab4:
    st.subheader("Raw Data")
    st.dataframe(
        filtered_df.sort_values("timestamp", ascending=False),
        use_container_width=True,
        height=600,
    )

    # Download button
    csv = filtered_df.to_csv(index=False)
    st.download_button(
        label="Download filtered data as CSV",
        data=csv,
        file_name=f"sensor_readings_{start_date}_{end_date}.csv",
        mime="text/csv",
    )
