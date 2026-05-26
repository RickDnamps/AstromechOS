"""Unit tests for the pure Drive-layout validation logic (Custom Drive Layout)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from master.api.drive_layout_bp import _valid_device_key, _sanitize_layout, _clamp_pt


def test_valid_device_key():
    assert _valid_device_key("touch_834x1194")
    assert _valid_device_key("mouse_1920x1080")
    assert not _valid_device_key("../etc")          # path chars
    assert not _valid_device_key("a" * 80)           # too long
    assert not _valid_device_key("<script>")
    assert not _valid_device_key("")
    assert not _valid_device_key(None)


def test_clamp_pt():
    assert _clamp_pt({"x": -5, "y": 150}) == {"x": 0.0, "y": 100.0}
    assert _clamp_pt({"x": 12.5, "y": 70}) == {"x": 12.5, "y": 70.0}
    assert _clamp_pt({"x": "NaN", "y": 1}) is None
    assert _clamp_pt({"x": float("inf"), "y": 1}) is None
    assert _clamp_pt("nope") is None
    assert _clamp_pt({"x": 1}) is None               # missing y


def test_sanitize_layout_clamps_and_rejects():
    raw = {"propulsion": {"x": -5, "y": 150},
           "dome": {"x": 50, "y": 50},
           "shortcuts": {"sc_1": {"x": 10, "y": 10}, "bad": {"x": "NaN", "y": 1}}}
    out = _sanitize_layout(raw)
    assert out["propulsion"] == {"x": 0.0, "y": 100.0}    # clamped 0..100
    assert out["dome"] == {"x": 50.0, "y": 50.0}
    assert out["shortcuts"]["sc_1"] == {"x": 10.0, "y": 10.0}
    assert "bad" not in out["shortcuts"]                  # non-finite point dropped


def test_sanitize_layout_rejects_non_dict():
    assert _sanitize_layout([1, 2, 3]) is None
    assert _sanitize_layout("nope") is None
    assert _sanitize_layout(None) is None


def test_sanitize_layout_drops_bad_sid():
    out = _sanitize_layout({"shortcuts": {"x" * 40: {"x": 1, "y": 1},
                                          "../x": {"x": 1, "y": 1}}})
    assert out["shortcuts"] == {}                         # both sids rejected


def test_sanitize_layout_empty_ok():
    out = _sanitize_layout({})
    assert out == {"shortcuts": {}}                       # valid, just nothing set


def test_sanitize_layout_cam_clamped():
    assert _sanitize_layout({"cam": {"x": 10, "y": 20, "w": 60, "h": 80}})["cam"] == {"x": 10.0, "y": 20.0, "w": 60.0, "h": 80.0}
    # x/y default to 0 when absent; w/h clamp 25..100
    assert _sanitize_layout({"cam": {"w": 150, "h": 10}})["cam"] == {"x": 0.0, "y": 0.0, "w": 100.0, "h": 25.0}
    # x/y clamp 0..100
    c = _sanitize_layout({"cam": {"x": -5, "y": 200, "w": 50, "h": 50}})["cam"]
    assert c["x"] == 0.0 and c["y"] == 100.0
    assert "cam" not in _sanitize_layout({"cam": {"w": "x", "h": 1}})   # non-finite dropped
    assert "cam" not in _sanitize_layout({"cam": "full"})              # non-dict dropped
    assert "cam" not in _sanitize_layout({})                          # absent → not added


def test_sanitize_layout_editor_params():
    out = _sanitize_layout({"mode": "custom", "snap": False, "snapStep": 3})
    assert out["mode"] == "custom" and out["snap"] is False and out["snapStep"] == 3
    assert "mode" not in _sanitize_layout({"mode": "bogus"})        # invalid mode dropped
    assert "snap" not in _sanitize_layout({"snap": "yes"})          # non-bool dropped
    assert "snapStep" not in _sanitize_layout({"snapStep": 99})     # out-of-range dropped
    assert "snapStep" not in _sanitize_layout({"snapStep": "x"})    # non-int dropped


if __name__ == "__main__":
    funcs = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in funcs:
        try:
            fn()
            print(f"  PASS {fn.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"  FAIL {fn.__name__}: {e!r}")
    print(f"\n{len(funcs) - failed}/{len(funcs)} passed")
    sys.exit(1 if failed else 0)
