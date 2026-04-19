import pytest

from src.device import DeviceProfile, build_packet, build_transmit_payload

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
        "sync_us", "sync_gap_us", "pulse_us",
        "zero_gap_us", "one_gap_us", "repeat_count",
    }
    assert payload["timing"]["pulse_us"] == 400
    assert payload["timing"]["repeat_count"] == 20


def test_build_transmit_payload_rejects_bad_bits(profile):
    with pytest.raises(ValueError):
        build_transmit_payload(profile, bits="")
    with pytest.raises(ValueError):
        build_transmit_payload(profile, bits="0102")
