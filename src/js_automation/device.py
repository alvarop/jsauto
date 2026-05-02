"""Device discovery, configuration, and selection helpers."""

import sys
from pyjoulescope_driver import Driver


_UDEV_HINT = (
    "Hint: Joulescopes require udev rules for non-root USB access on Linux. "
    "See https://github.com/jetperch/joulescope_driver#linux-udev-rules"
)


def list_devices() -> list[dict]:
    """Return a list of connected Joulescopes as dicts with device_path, model, serial."""
    with Driver() as jsdrv:
        jsdrv.log_level = "WARNING"
        paths = sorted(jsdrv.device_paths())
    result = []
    for p in paths:
        parts = p.split("/")  # e.g. ['u', 'js220', '000123']
        model = parts[1] if len(parts) >= 2 else "unknown"
        serial = parts[2] if len(parts) >= 3 else "unknown"
        result.append({"device_path": p, "model": model, "serial": serial})
    return result


def resolve_device(jsdrv: Driver, serial: str | None) -> str:
    """Return the single device_path to use, or exit with a clear error.

    Exits with code 3 if no devices found, 2 if multiple and serial not specified.
    """
    paths = sorted(jsdrv.device_paths())
    if not paths:
        print(f"No Joulescope found. {_UDEV_HINT}", file=sys.stderr)
        sys.exit(3)
    if serial:
        serial_lower = serial.lower()
        matched = [p for p in paths if p.lower().endswith("/" + serial_lower)]
        if not matched:
            available = ", ".join(paths)
            print(f"Serial {serial!r} not found. Available: {available}", file=sys.stderr)
            sys.exit(2)
        return matched[0]
    if len(paths) == 1:
        return paths[0]
    import json
    print(
        f"Multiple Joulescopes found. Use --serial to select one:\n"
        + json.dumps([p.split("/")[-1] for p in paths], indent=2),
        file=sys.stderr,
    )
    sys.exit(2)


def configure_device(jsdrv: Driver, device_path: str, frequency: int | None = None):
    """Open device with defaults and configure current/voltage ranging."""
    jsdrv.open(device_path, mode="defaults")
    if "js220" in device_path:
        jsdrv.publish(f"{device_path}/s/i/range/mode", "auto")
        jsdrv.publish(f"{device_path}/s/v/range/mode", "auto")
    elif "js110" in device_path:
        jsdrv.publish(f"{device_path}/s/i/range/select", "auto")
        jsdrv.publish(f"{device_path}/s/v/range/select", "15 V")
    if frequency is not None:
        jsdrv.publish(f"{device_path}/h/fs", int(frequency))
