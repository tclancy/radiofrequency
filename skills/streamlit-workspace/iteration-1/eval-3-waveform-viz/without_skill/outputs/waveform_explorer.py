"""
Streamlit Dashboard for RF Waveform Visualization
Reads sofucor_fan.yaml and visualizes OOK waveforms with live timing adjustment
"""

import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
import yaml
from pathlib import Path


@st.cache_data
def load_device_profile(yaml_path):
    """Load and parse the YAML device profile"""
    with open(yaml_path, "r") as f:
        config = yaml.safe_load(f)
    return config


def generate_waveform(
    command_bits,
    address_bits,
    pulse_us,
    zero_gap_us,
    one_gap_us,
    sync_us,
    sync_gap_us,
    repeat_count=1,
    sample_rate_hz=100000,
):
    """
    Generate OOK_PDM waveform samples.

    Protocol:
    - Start each repetition with SYNC: HIGH for sync_us, then LOW for sync_gap_us
    - For each bit in packet (address + command):
      - HIGH pulse for pulse_us
      - LOW gap: zero_gap_us for bit=0, one_gap_us for bit=1

    Returns:
        time_array (µs), samples (0=LOW, 1=HIGH)
    """
    samples = []
    time_points = []
    current_time = 0

    # Combine address and command
    full_packet = address_bits + command_bits

    for rep in range(repeat_count):
        # Sync HIGH pulse
        num_samples = int(sync_us * sample_rate_hz / 1e6)
        samples.extend([1] * num_samples)
        time_points.extend(
            [current_time + i / sample_rate_hz * 1e6 for i in range(num_samples)]
        )
        current_time += sync_us

        # Sync gap LOW
        num_samples = int(sync_gap_us * sample_rate_hz / 1e6)
        samples.extend([0] * num_samples)
        time_points.extend(
            [current_time + i / sample_rate_hz * 1e6 for i in range(num_samples)]
        )
        current_time += sync_gap_us

        # Data bits
        for bit_char in full_packet:
            bit = int(bit_char)

            # Pulse HIGH
            num_samples = int(pulse_us * sample_rate_hz / 1e6)
            samples.extend([1] * num_samples)
            time_points.extend(
                [current_time + i / sample_rate_hz * 1e6 for i in range(num_samples)]
            )
            current_time += pulse_us

            # Gap LOW (duration depends on bit value)
            gap = one_gap_us if bit == 1 else zero_gap_us
            num_samples = int(gap * sample_rate_hz / 1e6)
            samples.extend([0] * num_samples)
            time_points.extend(
                [current_time + i / sample_rate_hz * 1e6 for i in range(num_samples)]
            )
            current_time += gap

    return np.array(time_points), np.array(samples)


def plot_waveform(time_array, samples, title="OOK Waveform"):
    """Create matplotlib figure for waveform visualization"""
    fig, ax = plt.subplots(figsize=(14, 4))

    ax.plot(time_array, samples, linewidth=1.5, color="#1f77b4", drawstyle="steps-post")
    ax.fill_between(time_array, 0, samples, alpha=0.3, color="#1f77b4", step="post")

    ax.set_xlabel("Time (µs)", fontsize=11)
    ax.set_ylabel("Signal Level", fontsize=11)
    ax.set_title(title, fontsize=13, fontweight="bold")
    ax.set_ylim(-0.1, 1.2)
    ax.grid(True, alpha=0.3, linestyle="--")
    ax.set_yticks([0, 1])
    ax.set_yticklabels(["LOW", "HIGH"])

    return fig


def main():
    st.set_page_config(
        page_title="RF Waveform Explorer",
        page_icon="📡",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    st.title("📡 RF Waveform Explorer")
    st.markdown(
        "Visualize OOK-PDM waveforms from your RF device profile with live parameter tuning"
    )

    # Locate the YAML file
    yaml_path = Path(
        "/sessions/friendly-relaxed-goodall/mnt/radiofrequency/devices/sofucor_fan.yaml"
    )

    if not yaml_path.exists():
        st.error(f"Device profile not found at {yaml_path}")
        return

    # Load device profile
    config = load_device_profile(str(yaml_path))

    st.sidebar.markdown("## Device Info")
    st.sidebar.write(f"**Frequency:** {config['frequency_mhz']} MHz")
    st.sidebar.write(f"**Encoding:** {config['encoding']}")

    # Timing controls in sidebar
    st.sidebar.markdown("## Timing Parameters (µs)")

    timing = config["timing"]

    pulse_us = st.sidebar.slider(
        "Pulse Duration (pulse_us)",
        min_value=100,
        max_value=1000,
        value=timing["pulse_us"],
        step=10,
        help="Duration of HIGH signal for each bit carrier",
    )

    zero_gap_us = st.sidebar.slider(
        "Zero Gap Duration (zero_gap_us)",
        min_value=100,
        max_value=2000,
        value=timing["zero_gap_us"],
        step=10,
        help="Duration of LOW gap after pulse when bit=0",
    )

    one_gap_us = st.sidebar.slider(
        "One Gap Duration (one_gap_us)",
        min_value=500,
        max_value=3000,
        value=timing["one_gap_us"],
        step=10,
        help="Duration of LOW gap after pulse when bit=1",
    )

    sync_us = st.sidebar.slider(
        "Sync Pulse Duration (sync_us)",
        min_value=2000,
        max_value=15000,
        value=timing["sync_us"],
        step=100,
        help="Duration of initial SYNC HIGH pulse",
    )

    sync_gap_us = st.sidebar.slider(
        "Sync Gap Duration (sync_gap_us)",
        min_value=100,
        max_value=2000,
        value=timing["sync_gap_us"],
        step=10,
        help="Duration of LOW gap between sync and first data bit",
    )

    repeat_count = st.sidebar.slider(
        "Repetition Count",
        min_value=1,
        max_value=50,
        value=min(5, timing["repeat_count"]),
        step=1,
        help="Number of times to repeat the full packet",
    )

    # Command and unit selection
    col1, col2 = st.columns(2)

    with col1:
        selected_command = st.selectbox(
            "Select Command",
            list(config["commands"].keys()),
            help="Choose a command to visualize",
        )

    with col2:
        selected_unit = st.selectbox(
            "Select Unit",
            list(config["units"].keys()),
            help="Choose which remote/unit to use (determines address bits)",
        )

    # Get bits for selected command and unit
    command_bits = config["commands"][selected_command]
    address_bits = config["units"][selected_unit]["address"]

    st.markdown("---")
    st.markdown("## Waveform Visualization")

    # Generate and display waveform
    time_array, samples = generate_waveform(
        command_bits=command_bits,
        address_bits=address_bits,
        pulse_us=pulse_us,
        zero_gap_us=zero_gap_us,
        one_gap_us=one_gap_us,
        sync_us=sync_us,
        sync_gap_us=sync_gap_us,
        repeat_count=repeat_count,
        sample_rate_hz=100000,
    )

    fig = plot_waveform(
        time_array,
        samples,
        title=f"Command: {selected_command} | Unit: {selected_unit} | Repetitions: {repeat_count}",
    )
    st.pyplot(fig, use_container_width=True)

    # Display packet information
    st.markdown("## Packet Details")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Address Bits", address_bits)

    with col2:
        st.metric("Command Bits", command_bits)

    with col3:
        total_duration_ms = (time_array[-1] - time_array[0]) / 1000
        st.metric("Total Duration", f"{total_duration_ms:.2f} ms")

    # Show timing summary table
    st.markdown("### Timing Summary")
    timing_data = {
        "Parameter": ["Sync Pulse", "Sync Gap", "Data Pulse", "Zero Gap", "One Gap"],
        "Current Value (µs)": [sync_us, sync_gap_us, pulse_us, zero_gap_us, one_gap_us],
        "Device Profile (µs)": [
            timing["sync_us"],
            timing["sync_gap_us"],
            timing["pulse_us"],
            timing["zero_gap_us"],
            timing["one_gap_us"],
        ],
    }
    st.table(timing_data)

    # Protocol explanation
    with st.expander("📚 Protocol Explanation"):
        st.markdown("""
        ### OOK Pulse Distance Modulation (OOK_PDM)

        This Sofucor fan uses **On-Off Keying with Pulse Distance Modulation**:

        - **Pulse:** HIGH signal is always the same duration (`pulse_us`)
        - **Distance:** Information is encoded in the LOW gap duration:
          - **Bit 0:** short LOW gap (`zero_gap_us`)
          - **Bit 1:** long LOW gap (`one_gap_us`)

        #### Packet Structure
        1. **Sync Burst:** Long HIGH pulse (`sync_us`) followed by LOW gap (`sync_gap_us`)
        2. **Address Bits:** 16 bits identifying the remote/unit (unique per physical remote)
        3. **Command Bits:** 16 bits specifying the action (speed, light, off, etc.)

        #### Example Timeline
        - 0–8000 µs: SYNC HIGH
        - 8000–8670 µs: SYNC LOW gap
        - 8670–9070 µs: Bit 0 HIGH pulse
        - 9070–9740 µs: Bit 0 LOW gap (short, for bit=0)
        - 9740–10140 µs: Bit 1 HIGH pulse
        - 10140–11940 µs: Bit 1 LOW gap (long, for bit=1)
        - ... and so on for remaining 30 bits

        #### Why This Works
        The receiver measures the gap duration and thresholds it:
        - Gap < threshold → decoded as 0
        - Gap ≥ threshold → decoded as 1
        """)


if __name__ == "__main__":
    main()
