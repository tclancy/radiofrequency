"""
Sofucor OOK Signal Explorer — Streamlit app for understanding RF waveforms.

Run with:  streamlit run signal_explorer.py
"""

import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import yaml
from pathlib import Path

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(page_title="OOK Signal Explorer", layout="wide")

# ---------------------------------------------------------------------------
# Load device profile
# ---------------------------------------------------------------------------
DEVICE_FILE = Path(__file__).parent / "sofucor_fan.yaml"


@st.cache_data
def load_device():
    with open(DEVICE_FILE) as f:
        return yaml.safe_load(f)


dev = load_device()
timing = dev["timing"]

# ---------------------------------------------------------------------------
# Styling helpers
# ---------------------------------------------------------------------------
DARK_BG = "#0e1117"
PANEL_BG = "#161b22"
CYAN = "#00d4aa"
ORANGE = "#ff6b35"
RED = "#ff4b4b"
YELLOW = "#ffd166"
MUTED = "#8b949e"
WHITE = "#e6edf3"


def style_ax(ax, title="", xlabel="Time (µs)", ylabel_left="HIGH", ylabel_right="LOW"):
    """Apply consistent dark styling to an axis."""
    ax.set_facecolor(PANEL_BG)
    ax.set_title(title, color=WHITE, fontsize=13, fontweight="bold", pad=12)
    ax.set_xlabel(xlabel, color=MUTED, fontsize=10)
    ax.set_yticks([0, 1])
    ax.set_yticklabels([ylabel_right, ylabel_left], color=MUTED, fontsize=10)
    ax.tick_params(axis="x", colors=MUTED, labelsize=9)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["bottom"].set_color(MUTED)
    ax.spines["left"].set_color(MUTED)
    ax.set_ylim(-0.15, 1.45)


def build_ook_waveform(bits, pulse_us, zero_gap_us, one_gap_us, sync_us=0, sync_gap_us=0):
    """
    Build time and level arrays for an OOK pulse-distance waveform.
    Returns (times, levels, bit_centers, bit_boundaries) in microseconds.
    """
    t = 0.0
    times = []
    levels = []
    bit_centers = []
    bit_boundaries = [0.0]

    # Optional sync pulse
    if sync_us > 0:
        # Sync HIGH
        times += [t, t + sync_us]
        levels += [1, 1]
        t += sync_us
        # Sync gap LOW
        times += [t, t + sync_gap_us]
        levels += [0, 0]
        t += sync_gap_us
        bit_boundaries = [t]

    for b in bits:
        start = t
        # HIGH pulse
        times += [t, t + pulse_us]
        levels += [1, 1]
        t += pulse_us
        # LOW gap
        gap = one_gap_us if b == "1" else zero_gap_us
        times += [t, t + gap]
        levels += [0, 0]
        t += gap
        bit_centers.append((start + t) / 2)
        bit_boundaries.append(t)

    return np.array(times), np.array(levels), bit_centers, bit_boundaries


# ===========================================================================
# SIDEBAR
# ===========================================================================
st.sidebar.title("⚡ Signal Parameters")

st.sidebar.markdown("### Timing (µs)")
pulse_us = st.sidebar.slider("Pulse width (HIGH)", 100, 1000, timing["pulse_us"], step=50)
zero_gap_us = st.sidebar.slider("Zero gap (LOW)", 100, 2000, timing["zero_gap_us"], step=50)
one_gap_us = st.sidebar.slider("One gap (LOW)", 500, 4000, timing["one_gap_us"], step=50)
sync_us = st.sidebar.slider("Sync pulse", 0, 15000, timing["sync_us"], step=500)
sync_gap_us = st.sidebar.slider("Sync gap", 0, 2000, timing["sync_gap_us"], step=50)

st.sidebar.markdown("---")
st.sidebar.markdown("### Select a signal")

unit_name = st.sidebar.selectbox("Fan", list(dev["units"].keys()))
cmd_name = st.sidebar.selectbox("Command", list(dev["commands"].keys()))

address = dev["units"][unit_name]["address"]
command = dev["commands"][cmd_name]
full_code = address + command

st.sidebar.markdown("---")
st.sidebar.code(f"Address:  {address}\nCommand:  {command}\nFull:     {full_code}", language="text")

# ===========================================================================
# MAIN CONTENT
# ===========================================================================
st.title("🔊 OOK Signal Explorer")
st.markdown(
    f"Visualizing the RF protocol for your **Sofucor ceiling fans** — "
    f"currently showing `{unit_name}` / `{cmd_name}`."
)

# ---------------------------------------------------------------------------
# TAB 1: What the remote actually transmits
# ---------------------------------------------------------------------------
tab1, tab2, tab3, tab4 = st.tabs([
    "1️⃣ What the Remote Sends",
    "2️⃣ What You See in Audacity",
    "3️⃣ How to Read Bits",
    "4️⃣ Full Packet Explorer",
])

with tab1:
    st.markdown("""
    ### The ideal OOK signal — what the remote's TX chip actually outputs

    **On-Off Keying** is the simplest possible digital radio modulation. The transmitter
    has exactly two states: carrier ON (HIGH) and carrier OFF (LOW). It's the RF equivalent
    of flashing a flashlight in Morse code.

    **Pulse Distance** means every bit starts with the same short HIGH pulse, and the
    information is encoded in *how long the gap after it lasts*:

    - **Short gap → bit 0** (currently {zero_gap} µs)
    - **Long gap → bit 1** (currently {one_gap} µs)

    Play with the sliders in the sidebar to see how changing the timing affects the waveform.
    """.format(zero_gap=zero_gap_us, one_gap=one_gap_us))

    # Show first 8 bits with sync
    first_8 = full_code[:8]
    t, lvl, centers, bounds = build_ook_waveform(
        first_8, pulse_us, zero_gap_us, one_gap_us, sync_us, sync_gap_us
    )

    fig1, ax1 = plt.subplots(figsize=(14, 3), facecolor=DARK_BG)
    ax1.fill_between(t, lvl, step="post", alpha=0.35, color=CYAN)
    ax1.step(t, lvl, where="post", color=CYAN, linewidth=2)
    style_ax(ax1, title=f"Sync + first 8 data bits  [{first_8}]",
             ylabel_left="Carrier ON", ylabel_right="Carrier OFF")

    # Annotate sync
    if sync_us > 0:
        ax1.annotate("← 8 ms sync pulse (carrier on, no data) →",
                      xy=(sync_us / 2, 1.15), color=ORANGE, fontsize=9,
                      ha="center", va="bottom")

    # Annotate each bit
    for i, (c, b) in enumerate(zip(centers, first_8)):
        ax1.text(c, 1.25, b, ha="center", va="bottom", color=YELLOW,
                 fontsize=11, fontweight="bold")

    ax1.set_xlabel("Time (µs)", color=MUTED)
    st.pyplot(fig1, width="stretch")
    plt.close(fig1)

# ---------------------------------------------------------------------------
# TAB 2: The rtl_fm inversion
# ---------------------------------------------------------------------------
with tab2:
    st.markdown("""
    ### The inversion problem — why Audacity looks "backwards"

    When you record with `rtl_fm`, you're capturing the **FM-demodulated amplitude envelope**.
    Here's the catch: `rtl_fm` outputs *deviation from the center frequency*, not the
    raw carrier. The result is that:
    """)

    col1, col2 = st.columns(2)
    with col1:
        st.info("**Carrier ON** (remote transmitting) → quiet/flat line in Audacity")
    with col2:
        st.error("**Carrier OFF** (gap between pulses) → noisy burst in Audacity")

    st.markdown("""
    This is the single most confusing thing about reading OOK signals in Audacity.
    Your brain says "the loud part must be the signal" — but it's actually the *absence*
    of signal. The loud bursts are your SDR's noise floor rushing in when the carrier
    drops out.
    """)

    # Build a short example: 3 bits [0, 1, 1]
    demo_bits = "011"
    t_real, lvl_real, _, _ = build_ook_waveform(demo_bits, pulse_us, zero_gap_us, one_gap_us)

    # Simulated FM demod: invert + add noise during "gaps"
    np.random.seed(42)
    sample_rate = 5  # samples per µs
    t_cont = np.arange(0, t_real[-1], 1.0 / sample_rate)
    # Interpolate the ideal signal
    ideal = np.interp(t_cont, t_real, lvl_real)
    # FM demod: quiet when carrier is ON, noisy when carrier is OFF
    noise = np.random.normal(0, 0.35, len(t_cont))
    fm_demod = np.where(ideal > 0.5, 0.0, noise)

    fig2, (ax_real, ax_fm) = plt.subplots(2, 1, figsize=(14, 5), facecolor=DARK_BG,
                                           gridspec_kw={"hspace": 0.5})

    # Top: real signal
    ax_real.fill_between(t_real, lvl_real, step="post", alpha=0.35, color=CYAN)
    ax_real.step(t_real, lvl_real, where="post", color=CYAN, linewidth=2)
    style_ax(ax_real, title='What the remote transmits  (bits "0, 1, 1")',
             ylabel_left="Carrier ON", ylabel_right="Carrier OFF")
    # Annotate bits
    bit_labels_x = []
    pos = 0
    for b in demo_bits:
        gap = one_gap_us if b == "1" else zero_gap_us
        center = pos + (pulse_us + gap) / 2
        bit_labels_x.append((center, b))
        pos += pulse_us + gap
    for cx, bl in bit_labels_x:
        ax_real.text(cx, 1.25, f"bit {bl}", ha="center", color=YELLOW, fontsize=10, fontweight="bold")

    # Bottom: FM demod
    ax_fm.plot(t_cont, fm_demod, color=ORANGE, linewidth=0.6, alpha=0.9)
    ax_fm.set_facecolor(PANEL_BG)
    ax_fm.set_title('What you see in Audacity  (rtl_fm output)', color=WHITE,
                     fontsize=13, fontweight="bold", pad=12)
    ax_fm.set_xlabel("Time (µs)", color=MUTED, fontsize=10)
    ax_fm.set_ylabel("Amplitude", color=MUTED, fontsize=10)
    ax_fm.tick_params(colors=MUTED, labelsize=9)
    ax_fm.spines["top"].set_visible(False)
    ax_fm.spines["right"].set_visible(False)
    ax_fm.spines["bottom"].set_color(MUTED)
    ax_fm.spines["left"].set_color(MUTED)
    ax_fm.set_ylim(-1.2, 1.2)

    # Shade the "quiet" regions (carrier ON → pulse regions)
    pos = 0
    for b in demo_bits:
        ax_fm.axvspan(pos, pos + pulse_us, alpha=0.15, color=CYAN)
        ax_fm.text(pos + pulse_us / 2, 1.0, "quiet\n(carrier ON)", ha="center",
                   va="bottom", color=CYAN, fontsize=7)
        pos += pulse_us
        gap = one_gap_us if b == "1" else zero_gap_us
        ax_fm.annotate("", xy=(pos, -0.9), xytext=(pos + gap, -0.9),
                        arrowprops=dict(arrowstyle="<->", color=YELLOW, lw=1.5))
        ax_fm.text(pos + gap / 2, -1.05, f"{'long' if b == '1' else 'short'} noise burst = bit {b}",
                   ha="center", color=YELLOW, fontsize=8)
        pos += gap

    st.pyplot(fig2, width="stretch")
    plt.close(fig2)

    st.markdown("""
    > **The rule:** In Audacity, you're measuring the **noisy bursts** (the gaps), not the
    > quiet parts. Short burst → 0. Long burst → 1. The quiet flat sections *between*
    > the bursts are the actual carrier pulses — that's the remote yelling "I'M HERE" at
    > 315.4 MHz.

    Here's the text version from last session:
    ```
    Real signal:    ████░░░████████░░░████░░░░░░░░░░████████░░░
    FM demod out:   ░░░░███░░░░░░░░███░░░░████████████░░░░░░░███
                         ^ noisy bursts are the GAPS between pulses
    ```
    """)

# ---------------------------------------------------------------------------
# TAB 3: How to read bits
# ---------------------------------------------------------------------------
with tab3:
    st.markdown("""
    ### A step-by-step guide to reading bits from an Audacity waveform

    Once you've internalized the inversion, here's the practical workflow:
    """)

    st.markdown(f"""
    **Your timing reference values** (from the decoded protocol):

    | What | Duration | What it looks like in Audacity |
    |------|----------|-------------------------------|
    | Carrier pulse | **{pulse_us} µs** | Short quiet/flat section |
    | Bit 0 gap | **{zero_gap_us} µs** | Short noisy burst |
    | Bit 1 gap | **{one_gap_us} µs** | Long noisy burst (~{one_gap_us / zero_gap_us:.1f}× longer) |
    | Sync pulse | **{sync_us} µs** | Very long quiet section ({sync_us / 1000:.0f} ms) |

    The key ratio is **{one_gap_us / zero_gap_us:.1f}:1** — a "one" burst is about
    {one_gap_us / zero_gap_us:.1f}× wider than a "zero" burst. That's very visible
    once you know what to look for.
    """)

    # Build 8 bits with alternating pattern for clarity
    demo_pattern = "01010110"
    t_demo, lvl_demo, centers_demo, bounds_demo = build_ook_waveform(
        demo_pattern, pulse_us, zero_gap_us, one_gap_us
    )

    fig3, ax3 = plt.subplots(figsize=(14, 4), facecolor=DARK_BG)
    ax3.fill_between(t_demo, lvl_demo, step="post", alpha=0.3, color=CYAN)
    ax3.step(t_demo, lvl_demo, where="post", color=CYAN, linewidth=2)
    style_ax(ax3, title=f"Reading bits from the waveform: [{demo_pattern}]",
             ylabel_left="Carrier ON", ylabel_right="Carrier OFF")

    # Color-code the gaps
    pos = 0
    for i, b in enumerate(demo_pattern):
        # Pulse region (light cyan)
        ax3.axvspan(pos, pos + pulse_us, alpha=0.08, color=CYAN)
        pos += pulse_us
        gap = one_gap_us if b == "1" else zero_gap_us
        # Gap region — colored by bit value
        color = RED if b == "1" else YELLOW
        ax3.axvspan(pos, pos + gap, alpha=0.15, color=color)
        ax3.text(pos + gap / 2, -0.08, f"{'LONG' if b == '1' else 'short'}",
                 ha="center", va="top", color=color, fontsize=8, fontweight="bold")
        ax3.text(pos + gap / 2, 1.30, b, ha="center", va="bottom",
                 color=color, fontsize=14, fontweight="bold")
        pos += gap

    # Legend
    short_patch = mpatches.Patch(color=YELLOW, alpha=0.4, label=f"Short gap ({zero_gap_us} µs) = 0")
    long_patch = mpatches.Patch(color=RED, alpha=0.4, label=f"Long gap ({one_gap_us} µs) = 1")
    ax3.legend(handles=[short_patch, long_patch], loc="upper right",
               facecolor=PANEL_BG, edgecolor=MUTED, labelcolor=WHITE, fontsize=9)

    st.pyplot(fig3, width="stretch")
    plt.close(fig3)

    st.markdown("""
    **Practical tips for Audacity:**

    1. **Zoom in** until you can see individual pulses — at the full file view they'll
       look like a solid block.
    2. **Use the selection tool** to measure the width of a noisy burst. Audacity shows
       the selection duration in the bottom toolbar.
    3. **Start from the sync pulse** — it's the huge quiet gap (~8 ms) that resets the pattern.
       The first noisy burst after that quiet stretch is the gap after bit 0 of the address.
    4. **Don't try to be exact** — you just need to tell "short" from "long." The ratio is
       nearly 3:1, so it's pretty obvious once you're zoomed in.
    5. **Compare two captures** of the same button press — the bit pattern should be identical.
       If it's not, you're reading noise, not signal.
    """)

# ---------------------------------------------------------------------------
# TAB 4: Full packet explorer
# ---------------------------------------------------------------------------
with tab4:
    st.markdown(f"""
    ### Full 32-bit packet:  `{unit_name}` / `{cmd_name}`
    """)

    st.markdown(f"""
    ```
    Address (bits 0-15):  {address}
    Command (bits 16-31): {command}
    Full 32-bit code:     {full_code}
    ```
    """)

    show_sync = st.checkbox("Show sync pulse", value=False)

    t_full, lvl_full, centers_full, bounds_full = build_ook_waveform(
        full_code, pulse_us, zero_gap_us, one_gap_us,
        sync_us=sync_us if show_sync else 0,
        sync_gap_us=sync_gap_us if show_sync else 0,
    )

    fig4, ax4 = plt.subplots(figsize=(16, 4), facecolor=DARK_BG)
    ax4.fill_between(t_full, lvl_full, step="post", alpha=0.3, color=CYAN)
    ax4.step(t_full, lvl_full, where="post", color=CYAN, linewidth=1.5)
    style_ax(ax4, title=f"Complete packet: {unit_name} / {cmd_name}")

    # Color address vs command regions
    offset = (sync_us + sync_gap_us) if show_sync else 0
    addr_end = bounds_full[16]  # boundary after 16th bit
    ax4.axvspan(offset, addr_end, alpha=0.08, color=ORANGE)
    ax4.axvspan(addr_end, bounds_full[-1], alpha=0.08, color=CYAN)

    # Labels
    addr_mid = (offset + addr_end) / 2
    cmd_mid = (addr_end + bounds_full[-1]) / 2
    ax4.text(addr_mid, 1.35, "ADDRESS (bits 0–15)", ha="center", color=ORANGE,
             fontsize=10, fontweight="bold")
    ax4.text(cmd_mid, 1.35, "COMMAND (bits 16–31)", ha="center", color=CYAN,
             fontsize=10, fontweight="bold")

    # Bit labels
    for i, (c, b) in enumerate(zip(centers_full, full_code)):
        color = ORANGE if i < 16 else CYAN
        ax4.text(c, 1.18, b, ha="center", va="bottom", color=color, fontsize=7)

    st.pyplot(fig4, width="stretch")
    plt.close(fig4)

    # Show all commands as a comparison
    st.markdown("---")
    st.markdown("### All commands compared")
    st.markdown("Notice how the left half (address) stays the same and only the right half (command) changes:")

    fig5, axes = plt.subplots(len(dev["commands"]), 1,
                               figsize=(16, 2.2 * len(dev["commands"])),
                               facecolor=DARK_BG,
                               gridspec_kw={"hspace": 0.6})

    for idx, (cname, cbits) in enumerate(dev["commands"].items()):
        ax = axes[idx]
        code = address + cbits
        t_c, lvl_c, centers_c, bounds_c = build_ook_waveform(
            code, pulse_us, zero_gap_us, one_gap_us
        )
        ax.fill_between(t_c, lvl_c, step="post", alpha=0.3, color=CYAN)
        ax.step(t_c, lvl_c, where="post", color=CYAN, linewidth=1.2)
        style_ax(ax, title=f"{cname}:  {address} | {cbits}")

        # Color regions
        addr_end_c = bounds_c[16]
        ax.axvspan(0, addr_end_c, alpha=0.08, color=ORANGE)
        ax.axvspan(addr_end_c, bounds_c[-1], alpha=0.08, color=CYAN)

    st.pyplot(fig5, width="stretch")
    plt.close(fig5)
