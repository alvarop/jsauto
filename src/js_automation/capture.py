"""JLS recording via pyjoulescope_driver.entry_points.record."""

import os
import sys
import types

from pyjoulescope_driver import Driver, time64
from pyjoulescope_driver.entry_points import record

from js_automation.device import resolve_device


def _default_output(serial: str) -> str:
    timestamp = time64.filename(".jls")  # e.g. 20260502_154645.jls
    base = timestamp.replace(".jls", f"_{serial}.jls")
    captures_dir = os.path.join(os.getcwd(), "captures")
    os.makedirs(captures_dir, exist_ok=True)
    return os.path.join(captures_dir, base)


def run_capture(
    duration: float,
    output: str | None = None,
    frequency: int | None = None,
    signals: list[str] | None = None,
    serial: str | None = None,
) -> dict:
    """Record a JLS file and return metadata dict."""
    if signals is None:
        signals = ["current", "voltage"]
    signals_str = ",".join(signals)

    # Resolve device first (needs a live Driver to enumerate)
    with Driver() as jsdrv:
        jsdrv.log_level = "WARNING"
        device_path = resolve_device(jsdrv, serial)

    dev_serial = device_path.split("/")[-1]
    if output is None:
        output = _default_output(dev_serial)

    # Build a fake args namespace that record.on_cmd expects
    args = types.SimpleNamespace(
        filename=output,
        duration=duration,
        frequency=frequency,
        open="defaults",
        serial_number=serial,
        signals=signals_str,
        note=None,
        set=[],
        verbose=False,
        jsdrv_log_level="warning",
    )

    ret = record.on_cmd(args)
    if ret and ret != 0:
        print(f"Capture failed with code {ret}", file=sys.stderr)
        sys.exit(ret)

    size = os.path.getsize(output) if os.path.exists(output) else 0
    return {
        "file": os.path.abspath(output),
        "duration_s": duration,
        "size_bytes": size,
    }
