import pytest

from src.device import DeviceProfile, build_packet

PROFILE_PATH = "devices/sofucor_fan.yaml"


@pytest.fixture
def profile():
    return DeviceProfile.load(PROFILE_PATH)


# --- packet structure ---

def test_packet_is_32_bits(profile):
    bits = build_packet(profile, unit="bedroom", command="speed1")
    assert len(bits) == 32


def test_all_packets_are_32_bits(profile):
    for unit in profile.units:
        for command in profile.commands:
            bits = build_packet(profile, unit=unit, command=command)
            assert len(bits) == 32, f"{unit}/{command} produced {len(bits)} bits"


def test_packet_contains_only_01(profile):
    bits = build_packet(profile, unit="bedroom", command="off")
    assert set(bits).issubset({"0", "1"})


# --- address + command concatenation ---

def test_bedroom_speed1_address_prefix(profile):
    bits = build_packet(profile, unit="bedroom", command="speed1")
    assert bits.startswith("1000110011110110"), "first 16 bits should be bedroom address"
    assert bits[16:] == "0001000011101111", "last 16 bits should be speed1 command"


def test_living_room_off(profile):
    bits = build_packet(profile, unit="living_room", command="off")
    assert bits == "1111000100111011" + "0100000010111111"


# --- known full codes from captures ---

def test_bedroom_light_full_code(profile):
    bits = build_packet(profile, unit="bedroom", command="light")
    assert bits == "10001100111101101100000000111111"


def test_bedroom_off_full_code(profile):
    bits = build_packet(profile, unit="bedroom", command="off")
    assert bits == "10001100111101100100000010111111"


def test_bedroom_speed2_full_code(profile):
    bits = build_packet(profile, unit="bedroom", command="speed2")
    assert bits == "10001100111101101001000001101111"


def test_bedroom_speed3_full_code(profile):
    bits = build_packet(profile, unit="bedroom", command="speed3")
    assert bits == "10001100111101100100100010110111"


def test_living_room_speed1_full_code(profile):
    bits = build_packet(profile, unit="living_room", command="speed1")
    assert bits == "11110001001110110001000011101111"


# --- error handling ---

def test_unknown_command_raises(profile):
    with pytest.raises(KeyError):
        build_packet(profile, unit="bedroom", command="turbo")


def test_unknown_unit_raises(profile):
    with pytest.raises(KeyError):
        build_packet(profile, unit="garage", command="speed1")


# --- profile metadata ---

def test_frequency(profile):
    assert profile.frequency_mhz == 315.4


def test_timing_keys_present(profile):
    required = {"sync_us", "pulse_us", "zero_gap_us", "one_gap_us", "repeat_count"}
    assert required.issubset(profile.timing.keys())


def test_units_have_fan_number(profile):
    for name, unit in profile.units.items():
        assert "fan_number" in unit, f"unit '{name}' missing fan_number"
        assert isinstance(unit["fan_number"], int)
