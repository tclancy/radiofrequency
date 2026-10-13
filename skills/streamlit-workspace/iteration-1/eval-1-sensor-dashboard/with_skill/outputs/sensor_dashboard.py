"""
Interactive sensor data explorer dashboard.

Load temperature and humidity readings from a CSV file and explore them
with filters by sensor and date range. Includes time series charts,
statistics, and raw data table.

Run with:  streamlit run sensor_dashboard.py
"""

import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from pathlib import Path

# ============================================================================
# Page configuration (must be first Streamlit call)
# ============================================================================
st.set_page_config(
    page_title="Sensor Dashboard", layout="wide", initial_sidebar_state="expanded"
)


# ============================================================================
# Data loading (cached)
# ============================================================================
@st.cache_data
def load_data(csv_path):
    """Load CSV data and parse timestamp column."""
    df = pd.read_csv(csv_path)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df.sort_values("timestamp").reset_index(drop=True)


# Locate the data file relative to this script
script_dir = Path(__file__).parent
# Navigate up to find the test-data directory
# Structure: with_skill/outputs/sensor_dashboard.py
# Need: test-data/readings.csv (4 levels up)
data_dir = script_dir.parent.parent.parent / "test-data"
csv_path = data_dir / "readings.csv"

if not csv_path.exists():
    st.error(f"Data file not found at {csv_path}")
    st.stop()

df = load_data(str(csv_path))

# ============================================================================
# Sidebar controls
# ============================================================================
st.sidebar.title("Controls")

# Get min/max dates from data
min_date = df["timestamp"].min().date()
max_date = df["timestamp"].max().date()

# Date range selector
date_range = st.sidebar.date_input(
    "Select date range",
    value=(min_date, max_date),
    min_value=min_date,
    max_value=max_date,
)

if len(date_range) == 2:
    start_date, end_date = date_range
    start_datetime = pd.Timestamp(start_date)
    end_datetime = pd.Timestamp(end_date) + timedelta(days=1)
else:
    start_datetime = pd.Timestamp(min_date)
    end_datetime = pd.Timestamp(max_date) + timedelta(days=1)

# Sensor selector
all_sensors = sorted(df["sensor_id"].unique().tolist())
selected_sensors = st.sidebar.multiselect(
    "Select sensors",
    options=all_sensors,
    default=all_sensors,
    help="Pick one or more sensors to display",
)

if not selected_sensors:
    st.warning("Please select at least one sensor.")
    st.stop()

# ============================================================================
# Filter data based on sidebar selections
# ============================================================================
filtered_df = df[
    (df["timestamp"] >= start_datetime)
    & (df["timestamp"] < end_datetime)
    & (df["sensor_id"].isin(selected_sensors))
].copy()

if filtered_df.empty:
    st.warning("No data matches the selected filters.")
    st.stop()

# ============================================================================
# Main content
# ============================================================================
st.title("Sensor Data Explorer")
st.markdown(
    f"**Showing {len(filtered_df)} readings across {len(selected_sensors)} sensor(s)**"
)

# Tabs for different views
tab1, tab2, tab3 = st.tabs(["Time Series", "Statistics", "Raw Data"])

# ============================================================================
# Tab 1: Time Series Charts
# ============================================================================
with tab1:
    col1, col2 = st.columns(2)

    # Temperature chart
    with col1:
        st.subheader("Temperature Over Time")

        # Prepare data for plotting
        fig, ax = plt.subplots(figsize=(10, 5), facecolor="#0e1117")
        ax.set_facecolor("#161b22")

        for sensor in selected_sensors:
            sensor_data = filtered_df[filtered_df["sensor_id"] == sensor]
            ax.plot(
                sensor_data["timestamp"],
                sensor_data["temp_celsius"],
                marker="o",
                markersize=3,
                label=sensor,
                linewidth=1.5,
                alpha=0.8,
            )

        ax.set_xlabel("Time", color="#e6edf3")
        ax.set_ylabel("Temperature (°C)", color="#e6edf3")
        ax.set_title(
            "Temperature Over Time", color="#e6edf3", fontsize=12, fontweight="bold"
        )
        ax.legend(loc="best")
        ax.grid(True, alpha=0.2)
        ax.tick_params(colors="#8b949e")
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["bottom"].set_color("#8b949e")
        ax.spines["left"].set_color("#8b949e")

        plt.xticks(rotation=45, ha="right")
        plt.tight_layout()
        st.pyplot(fig, width="stretch")
        plt.close(fig)

    # Humidity chart
    with col2:
        st.subheader("Humidity Over Time")

        fig, ax = plt.subplots(figsize=(10, 5), facecolor="#0e1117")
        ax.set_facecolor("#161b22")

        for sensor in selected_sensors:
            sensor_data = filtered_df[filtered_df["sensor_id"] == sensor]
            ax.plot(
                sensor_data["timestamp"],
                sensor_data["humidity"],
                marker="s",
                markersize=3,
                label=sensor,
                linewidth=1.5,
                alpha=0.8,
            )

        ax.set_xlabel("Time", color="#e6edf3")
        ax.set_ylabel("Humidity (%)", color="#e6edf3")
        ax.set_title(
            "Humidity Over Time", color="#e6edf3", fontsize=12, fontweight="bold"
        )
        ax.legend(loc="best")
        ax.grid(True, alpha=0.2)
        ax.tick_params(colors="#8b949e")
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["bottom"].set_color("#8b949e")
        ax.spines["left"].set_color("#8b949e")

        plt.xticks(rotation=45, ha="right")
        plt.tight_layout()
        st.pyplot(fig, width="stretch")
        plt.close(fig)

# ============================================================================
# Tab 2: Statistics
# ============================================================================
with tab2:
    st.subheader("Summary Statistics by Sensor")

    for sensor in selected_sensors:
        sensor_data = filtered_df[filtered_df["sensor_id"] == sensor]

        with st.expander(f"📊 {sensor}", expanded=(len(selected_sensors) == 1)):
            col1, col2, col3, col4 = st.columns(4)

            temp_data = sensor_data["temp_celsius"]
            humidity_data = sensor_data["humidity"]

            with col1:
                st.metric(
                    "Avg Temperature",
                    f"{temp_data.mean():.2f}°C",
                    delta=f"{temp_data.std():.2f}°C (std)",
                )

            with col2:
                st.metric(
                    "Temp Range", f"{temp_data.min():.2f} to {temp_data.max():.2f}°C"
                )

            with col3:
                st.metric(
                    "Avg Humidity",
                    f"{humidity_data.mean():.1f}%",
                    delta=f"{humidity_data.std():.1f}% (std)",
                )

            with col4:
                st.metric(
                    "Humidity Range",
                    f"{humidity_data.min():.1f} to {humidity_data.max():.1f}%",
                )

            # Distribution plots
            fig, axes = plt.subplots(1, 2, figsize=(12, 4), facecolor="#0e1117")

            for ax, data, title, ylabel in [
                (axes[0], temp_data, "Temperature Distribution", "Temperature (°C)"),
                (axes[1], humidity_data, "Humidity Distribution", "Humidity (%)"),
            ]:
                ax.set_facecolor("#161b22")
                ax.hist(data, bins=20, color="#58a6ff", edgecolor="#e6edf3", alpha=0.7)
                ax.set_title(title, color="#e6edf3", fontweight="bold")
                ax.set_xlabel(ylabel, color="#e6edf3")
                ax.set_ylabel("Frequency", color="#e6edf3")
                ax.tick_params(colors="#8b949e")
                ax.spines["top"].set_visible(False)
                ax.spines["right"].set_visible(False)
                ax.spines["bottom"].set_color("#8b949e")
                ax.spines["left"].set_color("#8b949e")

            plt.tight_layout()
            st.pyplot(fig, width="stretch")
            plt.close(fig)

# ============================================================================
# Tab 3: Raw Data
# ============================================================================
with tab3:
    st.subheader("Raw Data Table")

    # Display options
    col1, col2 = st.columns(2)
    with col1:
        show_all = st.checkbox("Show all rows", value=False)
    with col2:
        sort_by = st.selectbox("Sort by", ["timestamp", "sensor_id", "temp_celsius"])

    display_df = filtered_df.sort_values(sort_by).reset_index(drop=True)

    if not show_all:
        display_df = display_df.head(100)
        st.info(
            f"Showing first 100 of {len(filtered_df)} rows. Check 'Show all rows' to see everything."
        )

    st.dataframe(display_df, use_container_width=True)

    # Download button
    csv_data = filtered_df.to_csv(index=False)
    st.download_button(
        label="Download filtered data as CSV",
        data=csv_data,
        file_name=f"sensor_readings_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv",
    )

# ============================================================================
# Footer
# ============================================================================
st.divider()
st.caption(
    f"Data spans {min_date} to {max_date} • "
    f"Total readings: {len(df)} • "
    f"Active sensors: {len(selected_sensors)}"
)
