"""Hardware-free smoke tests: argparse wiring + analyze against a synthetic JLS fixture."""

import json
import os
import sys
import tempfile

import numpy as np
import pytest
from pyjls import DataType, Reader, Writer


@pytest.fixture(scope="session")
def fixture_jls(tmp_path_factory):
    """Create a synthetic 5-second JLS v2 file at 1 kHz with two current pulses."""
    tmp = tmp_path_factory.mktemp("jls")
    path = str(tmp / "fixture.jls")
    n = 5000  # 5 s at 1 kHz
    wr = Writer(path)
    wr.source_def(
        source_id=1,
        name="JS220-000001",
        vendor="Jetperch",
        model="JS220",
        version="",
        serial_number="000001",
    )
    wr.signal_def(signal_id=1, source_id=1, sample_rate=1000,
                  data_type=DataType.F32, name="current", units="A")
    wr.signal_def(signal_id=2, source_id=1, sample_rate=1000,
                  data_type=DataType.F32, name="voltage", units="V")
    rng = np.random.default_rng(42)
    i_data = rng.uniform(0.001, 0.002, n).astype(np.float32)
    # Pulse 1: t=1.0–1.05 s, ~100 mA
    i_data[1000:1050] = 0.10
    # Pulse 2: t=3.0–3.06 s, ~150 mA
    i_data[3000:3060] = 0.15
    v_data = np.full(n, 3.3, dtype=np.float32)
    wr.fsr(1, 0, i_data)
    wr.fsr(2, 0, v_data)
    wr.close()
    return path


# ---------------------------------------------------------------------------
# CLI wiring smoke tests (no hardware)
# ---------------------------------------------------------------------------

def _run_jsauto(*args):
    """Call the jsauto main() with given args and capture stdout/stderr."""
    from io import StringIO
    from unittest.mock import patch
    import js_automation.cli as cli_mod
    out, err = StringIO(), StringIO()
    with patch("sys.argv", ["jsauto", *args]), \
         patch("sys.stdout", out), \
         patch("sys.stderr", err):
        try:
            cli_mod.main()
        except SystemExit as e:
            return e.code, out.getvalue(), err.getvalue()
    return 0, out.getvalue(), err.getvalue()


def test_help_exits_zero():
    code, out, _ = _run_jsauto("--help")
    assert code == 0


def test_analyze_overall(fixture_jls):
    code, out, err = _run_jsauto("analyze", fixture_jls, "--buckets", "100")
    assert code == 0, f"stderr: {err}"
    data = json.loads(out)
    assert "overall" in data
    assert "buckets" in data
    assert len(data["buckets"]) == 100
    overall = data["overall"]
    assert overall["current_mean_A"] > 0
    assert overall["duration_s"] == pytest.approx(5.0, abs=0.1)


def test_analyze_window(fixture_jls):
    code, out, err = _run_jsauto("analyze", fixture_jls, "--window", "0.5:2.0", "--buckets", "50")
    assert code == 0, f"stderr: {err}"
    data = json.loads(out)
    assert data["overall"]["duration_s"] == pytest.approx(1.5, abs=0.05)


def test_analyze_threshold_finds_pulses(fixture_jls):
    code, out, err = _run_jsauto("analyze", fixture_jls, "--threshold", "0.05")
    assert code == 0, f"stderr: {err}"
    data = json.loads(out)
    assert "events" in data
    events = data["events"]["list"]
    assert len(events) == 2, f"Expected 2 pulses, got {len(events)}: {events}"
    assert events[0]["i_peak_A"] == pytest.approx(0.10, abs=0.01)
    assert events[1]["i_peak_A"] == pytest.approx(0.15, abs=0.01)


def test_analyze_samples_csv(fixture_jls, tmp_path):
    csv_path = str(tmp_path / "out.csv")
    code, out, err = _run_jsauto(
        "analyze", fixture_jls, "--window", "1.0:1.1", "--samples-csv", csv_path
    )
    assert code == 0, f"stderr: {err}"
    assert os.path.exists(csv_path)
    import csv
    with open(csv_path) as f:
        rows = list(csv.reader(f))
    assert rows[0] == ["time_s", "current_A", "voltage_V", "power_W"]
    assert len(rows) > 1


def test_analyze_plot(fixture_jls, tmp_path):
    png_path = str(tmp_path / "plot.png")
    code, out, err = _run_jsauto("analyze", fixture_jls, "--plot", png_path)
    assert code == 0, f"stderr: {err}"
    assert os.path.exists(png_path)
    assert os.path.getsize(png_path) > 0


def test_analyze_pretty_json(fixture_jls):
    code, out, _ = _run_jsauto("analyze", fixture_jls, "--pretty")
    assert code == 0
    assert "\n" in out  # indented = has newlines
    json.loads(out)  # must still be valid JSON
