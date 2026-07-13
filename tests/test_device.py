import pytest

from src.device import (
    DeviceProfile,
    build_packet,
    build_payload_for,
    build_pulses_payload,
    build_transmit_payload,
    pt2260_pulses,
    resolve_code,
)

PROFILE_PATH = "devices/sofa_king_fan.yaml"


@pytest.fixture
def profile():
    return DeviceProfile.load(PROFILE_PATH)


# --- packet structure ---


def test_packet_is_32_bits(profile):
    bits = build_packet(profile, unit="main", command="speed1")
    assert len(bits) == 32


def test_all_packets_are_32_bits(profile):
    for unit in profile.units:
        for command in profile.commands:
            bits = build_packet(profile, unit=unit, command=command)
            assert len(bits) == 32, f"{unit}/{command} produced {len(bits)} bits"


def test_packet_contains_only_01(profile):
    bits = build_packet(profile, unit="main", command="off")
    assert set(bits).issubset({"0", "1"})


# --- address + command concatenation ---


def test_main_speed1_address_prefix(profile):
    bits = build_packet(profile, unit="main", command="speed1")
    assert bits.startswith("1000110011110110"), "first 16 bits should be main address"
    assert bits[16:] == "0001000011101111", "last 16 bits should be speed1 command"


def test_stairs_off(profile):
    bits = build_packet(profile, unit="stairs", command="off")
    assert bits == "1111000100111011" + "0100000010111111"


# --- known full codes from captures ---


def test_main_light_full_code(profile):
    bits = build_packet(profile, unit="main", command="light")
    assert bits == "10001100111101101100000000111111"


def test_main_off_full_code(profile):
    bits = build_packet(profile, unit="main", command="off")
    assert bits == "10001100111101100100000010111111"


def test_main_speed2_full_code(profile):
    bits = build_packet(profile, unit="main", command="speed2")
    assert bits == "10001100111101101001000001101111"


def test_main_speed3_full_code(profile):
    bits = build_packet(profile, unit="main", command="speed3")
    assert bits == "10001100111101100100100010110111"


def test_stairs_speed1_full_code(profile):
    bits = build_packet(profile, unit="stairs", command="speed1")
    assert bits == "11110001001110110001000011101111"


# --- error handling ---


def test_unknown_command_raises(profile):
    with pytest.raises(KeyError):
        build_packet(profile, unit="main", command="turbo")


def test_unknown_unit_raises(profile):
    with pytest.raises(KeyError):
        build_packet(profile, unit="garage", command="speed1")


# --- profile metadata ---


def test_frequency(profile):
    assert profile.frequency_mhz == 433.935


def test_timing_keys_present(profile):
    required = {"sync_us", "pulse_us", "zero_gap_us", "one_gap_us", "repeat_count"}
    assert required.issubset(profile.timing.keys())


def test_units_have_fan_number(profile):
    for name, unit in profile.units.items():
        assert "fan_number" in unit, f"unit '{name}' missing fan_number"
        assert isinstance(unit["fan_number"], int)


# --- build_transmit_payload ---


def test_build_transmit_payload_shape(profile):
    payload = build_transmit_payload(profile, bits="01" * 16)
    assert payload["bits"] == "01" * 16
    assert set(payload["timing"].keys()) == {
        "sync_us",
        "sync_gap_us",
        "pulse_us",
        "zero_gap_us",
        "one_gap_us",
        "repeat_count",
    }
    assert payload["timing"]["pulse_us"] == 560
    assert payload["timing"]["repeat_count"] == 20


def test_build_transmit_payload_rejects_bad_bits(profile):
    with pytest.raises(ValueError):
        build_transmit_payload(profile, bits="")
    with pytest.raises(ValueError):
        build_transmit_payload(profile, bits="0102")


# --- PT2260 pulse-train encoding ---

PT2260_TIMING = {
    "short_us": 180,
    "long_us": 540,
    "sync_gap_us": 5580,
    "repeat_count": 6,
}


def _pt2260_profile():
    return DeviceProfile(
        frequency_mhz=433.92,
        encoding="PT2260",
        timing=PT2260_TIMING,
        commands={},
        units={
            "window": {
                "position": 2,
                "codes": {"on": "0F1F0F0F1010", "off": "0F1F0F0F1001"},
            },
        },
    )


def test_pt2260_symbol_waveforms():
    # '0' = 2x (short-high, long-low); '1' = 2x (long-high, short-low);
    # 'F' = (short-high, long-low) then (long-high, short-low); sync pair last.
    assert pt2260_pulses("01F", PT2260_TIMING) == [
        (180, 540),
        (180, 540),  # 0
        (540, 180),
        (540, 180),  # 1
        (180, 540),
        (540, 180),  # F
        (180, 5580),  # sync
    ]


def test_pt2260_full_frame_is_25_pairs():
    # 12 symbols x 2 pulses + 1 sync pair
    assert len(pt2260_pulses("0F1F0F0F1010", PT2260_TIMING)) == 25


def test_pt2260_rejects_invalid_symbol():
    with pytest.raises(ValueError, match="symbol"):
        pt2260_pulses("01X", PT2260_TIMING)


def test_resolve_code_looks_up_unit_command():
    profile = _pt2260_profile()
    assert resolve_code(profile, "window", "on") == "0F1F0F0F1010"


def test_resolve_code_unknown_unit_raises_keyerror():
    with pytest.raises(KeyError):
        resolve_code(_pt2260_profile(), "basement", "on")


def test_profile_load_tolerates_missing_commands(tmp_path):
    yaml_text = (
        "frequency_mhz: 433.92\n"
        "encoding: PT2260\n"
        "timing: {short_us: 180, long_us: 540, sync_gap_us: 5580, repeat_count: 6}\n"
        "units:\n"
        "  window: {position: 2, codes: {'on': '0F1F0F0F1010', 'off': '0F1F0F0F1001'}}\n"
    )
    p = tmp_path / "zap.yaml"
    p.write_text(yaml_text)
    profile = DeviceProfile.load(str(p))
    assert profile.commands == {}
    assert profile.units["window"]["codes"]["off"] == "0F1F0F0F1001"


# --- pulses payload validation (mirrors firmware limits exactly) ---


def test_pulses_payload_shape():
    payload = build_pulses_payload([(180, 540), (180, 5580)], repeat_count=6)
    assert payload == {"pulses": [[180, 540], [180, 5580]], "repeat_count": 6}


def test_pulses_payload_rejects_empty():
    with pytest.raises(ValueError, match="at least one"):
        build_pulses_payload([], repeat_count=6)


def test_pulses_payload_rejects_too_many_pairs():
    with pytest.raises(ValueError, match="256"):
        build_pulses_payload([(10, 10)] * 257, repeat_count=1)


def test_pulses_payload_rejects_out_of_range_us():
    with pytest.raises(ValueError, match="1..100000"):
        build_pulses_payload([(0, 540)], repeat_count=6)
    with pytest.raises(ValueError, match="1..100000"):
        build_pulses_payload([(180, 100_001)], repeat_count=6)


def test_pulses_payload_rejects_bad_repeat_count():
    for bad in (0, 101):
        with pytest.raises(ValueError, match="repeat_count"):
            build_pulses_payload([(180, 540)], repeat_count=bad)


def test_pulses_payload_rejects_over_duration_budget():
    # 256 pairs x 200ms x 100 reps = 5120s >> 5s budget. The firmware
    # hard-resets on payloads like this (soft WDT ~3.2s); fail locally.
    with pytest.raises(ValueError, match="budget"):
        build_pulses_payload([(100_000, 100_000)] * 256, repeat_count=100)


def test_zap_frame_fits_budget_comfortably():
    pulses = pt2260_pulses("0F1F0F0F1010", PT2260_TIMING)
    payload = build_pulses_payload(pulses, repeat_count=6)
    total_us = sum(high + low for high, low in pulses) * payload["repeat_count"]
    assert total_us < 5_000_000


# --- payload routing by encoding ---


def test_payload_for_pt2260_profile_is_pulse_shaped():
    payload = build_payload_for(_pt2260_profile(), "window", "on")
    assert set(payload) == {"pulses", "repeat_count"}
    assert payload["repeat_count"] == 6
    assert len(payload["pulses"]) == 25
    assert payload["pulses"][-1] == [180, 5580]  # sync pair last


def test_payload_for_fan_profile_unchanged(profile):
    payload = build_payload_for(profile, "main", "light")
    assert set(payload) == {"bits", "timing"}
    assert payload == build_transmit_payload(
        profile, bits=build_packet(profile, unit="main", command="light")
    )
