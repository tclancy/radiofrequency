"""
RF Waveform Explorer — Visualize OOK pulse sequences with adjustable timing parameters.

Load a device YAML profile, select a command, adjust timing sliders, and see the
RF waveform update in real time.

Run with:  streamlit run waveform_explorer.py
"""

import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
import yaml
from pathlib import Path


# ============================================================================
# Page config (must be first st call)
# ============================================================================
st.set_page_config(page_title="RF Waveform Explorer", layout="wide")


# ============================================================================
# Data loading and caching
# ============================================================================
@st.cache_data
def load_device_yaml(yaml_path):
    """Load and parse the device YAML profile."""
    with open(yaml_path, "r") as f:
        return yaml.safe_load(f)


def get_yaml_path():
    """Locate the sofucor_fan.yaml relative to this script's directory."""
    script_dir = Path(__file__).parent
    # Go up to the RF root: .../outputs -> .../with_skill -> .../eval-3-waveform-viz -> ... -> radiofrequency
    # For this test, we'll construct the path based on the working directory
    # Try multiple possible paths
    candidates = [
        Path(
            "/sessions/friendly-relaxed-goodall/mnt/radiofrequency/devices/sofucor_fan.yaml"
        ),
        script_dir.parent.parent.parent.parent.parent / "devices" / "sofucor_fan.yaml",
    ]
    for path in candidates:
        if path.exists():
            return path
    # If not found, raise error with helpful message
    raise FileNotFoundError(f"Could not find sofucor_fan.yaml. Tried: {candidates}")


# ============================================================================
# Waveform generation
# ============================================================================
def generate_waveform(address_bits, command_bits, timing, repeat_count=1):
    """
    Generate OOK waveform as a series of (duration_us, level) tuples.

    Packet structure:
      [sync HIGH] [sync_gap LOW] [32 bits of data] (repeat)

    Each bit is encoded as:
      [pulse HIGH] [zero_gap or one_gap LOW]

    Returns:
      List of (duration_us, level) tuples where level is 1 (HIGH) or 0 (LOW)
    """
    waveform = []

    # Concatenate address + command (32 bits total)
    bit_string = address_bits + command_bits

    # Repeat the packet N times
    for rep in range(repeat_count):
        # Sync pulse at the start of each repetition
        waveform.append((timing["sync_us"], 1))
        waveform.append((timing["sync_gap_us"], 0))

        # Data bits
        for bit in bit_string:
            # Carrier HIGH
            waveform.append((timing["pulse_us"], 1))
            # LOW gap depends on bit value
            gap = timing["one_gap_us"] if bit == "1" else timing["zero_gap_us"]
            waveform.append((gap, 0))

    return waveform


def waveform_to_time_series(waveform, sample_rate=1e6):
    """
    Convert a waveform (list of duration/level tuples) to a time series.

    Args:
        waveform: List of (duration_us, level) tuples
        sample_rate: Samples per second (default 1 MHz = 1 sample/microsecond)

    Returns:
        (time_array, signal_array) suitable for plotting
    """
    time_us = []
    signal = []
    current_time = 0.0

    for duration_us, level in waveform:
        # Calculate number of samples for this segment
        num_samples = max(1, int(duration_us))
        segment_times = np.linspace(
            current_time, current_time + duration_us, num_samples
        )
        time_us.extend(segment_times)
        signal.extend([level] * num_samples)
        current_time += duration_us

    return np.array(time_us), np.array(signal)


# ============================================================================
# Styling constants for dark theme
# ============================================================================
DARK_BG = "#0e1117"
PANEL_BG = "#161b22"
WHITE = "#e6edf3"
MUTED = "#8b949e"
ACCENT = "#58a6ff"


# ============================================================================
# Main app
# ============================================================================
st.title("RF Waveform Explorer")
st.write(
    "Load a device YAML profile, pick a command, adjust timing parameters, "
    "and visualize the resulting OOK waveform in real time."
)

# Sidebar: Load YAML and get user selections
st.sidebar.title("Controls")

try:
    yaml_path = get_yaml_path()
    device = load_device_yaml(yaml_path)
except FileNotFoundError as e:
    st.error(f"Error loading YAML: {e}")
    st.stop()

# Display basic device info
st.sidebar.markdown("### Device Info")
st.sidebar.write(f"**Frequency:** {device.get('frequency_mhz')} MHz")
st.sidebar.write(f"**Encoding:** {device.get('encoding')}")

# Select command
st.sidebar.markdown("### Select Command")
command_names = list(device.get("commands", {}).keys())
if not command_names:
    st.error("No commands found in YAML")
    st.stop()

selected_command = st.sidebar.selectbox("Command", command_names)
command_bits = device["commands"][selected_command]

# Get the first unit's address for this demo (or allow selection)
st.sidebar.markdown("### Select Unit")
unit_names = list(device.get("units", {}).keys())
if not unit_names:
    st.error("No units found in YAML")
    st.stop()

selected_unit = st.sidebar.selectbox("Unit", unit_names)
address_bits = device["units"][selected_unit]["address"]

# Timing parameter sliders
st.sidebar.markdown("### Timing (microseconds)")
timing_controls = {}
timing_defaults = device.get("timing", {})

timing_controls["sync_us"] = st.sidebar.slider(
    "Sync HIGH",
    min_value=1000,
    max_value=20000,
    value=int(timing_defaults.get("sync_us", 8000)),
    step=100,
)

timing_controls["sync_gap_us"] = st.sidebar.slider(
    "Sync Gap LOW",
    min_value=100,
    max_value=2000,
    value=int(timing_defaults.get("sync_gap_us", 670)),
    step=10,
)

timing_controls["pulse_us"] = st.sidebar.slider(
    "Pulse HIGH",
    min_value=100,
    max_value=1000,
    value=int(timing_defaults.get("pulse_us", 400)),
    step=10,
)

timing_controls["zero_gap_us"] = st.sidebar.slider(
    "Zero Gap LOW",
    min_value=100,
    max_value=2000,
    value=int(timing_defaults.get("zero_gap_us", 670)),
    step=10,
)

timing_controls["one_gap_us"] = st.sidebar.slider(
    "One Gap LOW",
    min_value=500,
    max_value=3000,
    value=int(timing_defaults.get("one_gap_us", 1800)),
    step=10,
)

repeat_count = st.sidebar.slider(
    "Repeats",
    min_value=1,
    max_value=50,
    value=int(timing_defaults.get("repeat_count", 20)),
    step=1,
)

# ============================================================================
# Generate and display waveform
# ============================================================================
st.markdown("### Waveform Visualization")

# Generate the waveform
waveform = generate_waveform(address_bits, command_bits, timing_controls, repeat_count)

# Convert to time series
time_us, signal = waveform_to_time_series(waveform, sample_rate=1e6)

# Plot with matplotlib, styled for dark theme
fig, ax = plt.subplots(figsize=(14, 6), facecolor=DARK_BG)
ax.set_facecolor(PANEL_BG)
ax.plot(time_us, signal, color=ACCENT, linewidth=2, label="RF Carrier")
ax.fill_between(time_us, 0, signal, alpha=0.2, color=ACCENT)

ax.set_xlabel("Time (µs)", color=WHITE, fontsize=11)
ax.set_ylabel("Level", color=WHITE, fontsize=11)
ax.set_title(
    f"OOK Waveform: {selected_unit.title()} — {selected_command} ({repeat_count}x repeat)",
    color=WHITE,
    fontsize=13,
    pad=15,
)
ax.set_ylim(-0.1, 1.1)
ax.set_yticks([0, 1])
ax.set_yticklabels(["LOW", "HIGH"], color=MUTED)
ax.tick_params(colors=MUTED, labelsize=10)
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
ax.spines["bottom"].set_color(MUTED)
ax.spines["left"].set_color(MUTED)
ax.legend(loc="upper right", frameon=False, labelcolor=WHITE)
ax.grid(True, alpha=0.1, color=MUTED, linestyle="--")

st.pyplot(fig, width="stretch")
plt.close(fig)

# ============================================================================
# Info panels
# ============================================================================
col1, col2 = st.columns(2)

with col1:
    st.markdown("#### Command Details")
    st.code(
        f"""
Address: {address_bits} (16 bits)
Command: {command_bits} (16 bits)
Packet:  {address_bits}{command_bits} (32 bits)
        """,
        language="text",
    )

with col2:
    st.markdown("#### Timing Summary")
    total_us = sum(d for d, _ in waveform)
    st.metric("Total Duration (µs)", f"{total_us:,.0f}")
    st.metric(
        "Bit Time (µs)", timing_controls["pulse_us"] + timing_controls["zero_gap_us"]
    )
    st.metric("Total Samples", len(time_us))

# Expander for raw waveform data
with st.expander("Show raw waveform data"):
    st.write("(duration_us, level) tuples — first 20 segments:")
    for i, (duration, level) in enumerate(waveform[:20]):
        level_name = "HIGH" if level == 1 else "LOW"
        st.write(f"{i}: {duration:.0f} µs {level_name}")
    if len(waveform) > 20:
        st.write(f"... and {len(waveform) - 20} more segments")
