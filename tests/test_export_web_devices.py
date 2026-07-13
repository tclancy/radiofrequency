import json
from pathlib import Path

from scripts.export_web_devices import build_bundle

ZAP_YAML = """\
frequency_mhz: 433.92
encoding: PT2260
timing: {short_us: 180, long_us: 540, sync_gap_us: 5580, repeat_count: 6}
units:
  couch:  {position: 3, codes: {'on': '0F1F0F0F1100', 'off': '0F1F0F0F0011'}}
  window: {position: 2, codes: {'on': '0F1F0F0F1010', 'off': '0F1F0F0F1001'}}
"""

FAN_YAML_PATH = Path("devices/sofa_king_fan.yaml")


def test_bundle_exports_pt2260_units_sorted_by_position(tmp_path):
    (tmp_path / "zap_lights.yaml").write_text(ZAP_YAML)
    # Non-PT2260 profiles are skipped (fans stay on their GET endpoints).
    (tmp_path / "fan.yaml").write_text(FAN_YAML_PATH.read_text())

    bundle = build_bundle(tmp_path)

    assert [u["unit"] for u in bundle["lights"]] == ["window", "couch"]
    window = bundle["lights"][0]
    assert window["label"] == "Window"
    assert window["position"] == 2
    assert window["commands"]["on"]["repeat_count"] == 6
    assert len(window["commands"]["on"]["pulses"]) == 25
    json.dumps(bundle)  # must be JSON-serializable as-is
