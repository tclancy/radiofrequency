"""Generate realistic temperature sensor data for testing."""

import csv
from datetime import datetime, timedelta
import random

# Configuration
sensors = ["sensor_001", "sensor_002", "sensor_003"]
start_date = datetime(2026, 3, 29, 0, 0, 0)
hours = 7 * 24  # 7 days of hourly readings

# Base temperatures for each sensor (Celsius)
base_temps = {
    "sensor_001": 22.0,  # Indoor sensor 1
    "sensor_002": 18.5,  # Indoor sensor 2
    "sensor_003": 15.0,  # Cooler location
}

# Output file
output_file = "/sessions/friendly-relaxed-goodall/mnt/radiofrequency/.claude/skills/streamlit-workspace/iteration-1/eval-1-sensor-dashboard/test-data/readings.csv"

with open(output_file, "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["timestamp", "sensor_id", "temp_celsius", "humidity"])

    for hour in range(hours):
        current_time = start_date + timedelta(hours=hour)
        timestamp = current_time.isoformat()

        for sensor in sensors:
            # Add realistic variation: higher temps during day, lower at night
            hour_of_day = current_time.hour
            time_variation = 3.0 * (1 + (hour_of_day - 12) / 12) ** 2

            # Random noise
            noise = random.uniform(-0.5, 0.5)

            # Calculate temperature
            temp = base_temps[sensor] + time_variation + noise

            # Humidity: typically inverse to temperature
            humidity = 45 + (temp - base_temps[sensor]) * (-2) + random.uniform(-3, 3)
            humidity = max(20, min(95, humidity))  # Clamp to reasonable range

            writer.writerow([timestamp, sensor, f"{temp:.2f}", f"{humidity:.1f}"])

print(f"Generated {hours * len(sensors)} readings in {output_file}")
