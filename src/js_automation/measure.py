"""Short blocking read that returns current/voltage/power statistics."""

import numpy as np
from queue import Queue, Empty

from pyjoulescope_driver import Driver, time64
from pyjoulescope_driver.record import _SIGNALS, _signal_name_map

from js_automation.device import resolve_device, configure_device

_SIGNAL_MAP = _signal_name_map()


def _read(jsdrv: Driver, device_path: str, signals: list[str], duration: float) -> dict:
    """Blocking read for `duration` seconds. Returns {signal_name: np.ndarray}."""
    queue = Queue()
    state = {}

    for sig_name in signals:
        info = _SIGNALS[sig_name]
        data_topic = f"{device_path}/{info['data_topic']}"
        ctrl_topic = f"{device_path}/{info['ctrl_topic']}"
        sig_state = {
            "info": info,
            "data_topic": data_topic,
            "ctrl_topic": ctrl_topic,
        }
        state[sig_name] = sig_state

        def _make_data_fn(ss):
            def data_fn(topic, value):
                decimate = value["decimate_factor"]
                sample_id = value["sample_id"] // decimate
                samples = value["data"]
                if "samples" not in ss:
                    ss["sample_rate"] = value["sample_rate"] // decimate
                    ss["sample_id_start"] = sample_id
                    ss["sample_id_next"] = sample_id
                    count = int((duration + 1.0) * ss["sample_rate"] + 1_000_000)
                    ss["samples"] = np.empty(count, dtype=samples.dtype)
                offset = sample_id - ss["sample_id_start"]
                if offset >= 0 and offset < len(ss["samples"]):
                    end = offset + len(samples)
                    if end > len(ss["samples"]):
                        end = len(ss["samples"])
                    ss["samples"][offset:end] = samples[: end - offset]
                ss["sample_id_next"] = sample_id + len(samples)
                queue.put(sig_name)
            return data_fn

        sig_state["data_fn"] = _make_data_fn(sig_state)
        jsdrv.subscribe(data_topic, ["pub"], sig_state["data_fn"])
        jsdrv.publish(ctrl_topic, 1, timeout=0)

    # Wait until all signals have accumulated `duration` worth of samples
    while True:
        try:
            queue.get(timeout=0.1)
        except Empty:
            continue
        done = True
        for ss in state.values():
            if "sample_rate" not in ss:
                done = False
                break
            collected = (ss["sample_id_next"] - ss["sample_id_start"]) / ss["sample_rate"]
            if collected < duration:
                done = False
                break
        if done:
            break

    # Unsubscribe and trim
    result = {}
    for sig_name, ss in state.items():
        jsdrv.unsubscribe(ss["data_topic"], ss["data_fn"], timeout=0)
        jsdrv.publish(ss["ctrl_topic"], 0)
        if "samples" not in ss:
            result[sig_name] = np.array([], dtype=np.float32)
            continue
        n = int(duration * ss["sample_rate"])
        result[sig_name] = ss["samples"][:n]

    return result


def run_measure(
    duration: float = 1.0,
    frequency: int | None = None,
    signals: list[str] | None = None,
    serial: str | None = None,
) -> dict:
    """Run a blocking measurement and return statistics as a dict."""
    if signals is None:
        signals = ["current", "voltage"]
    resolved = [_SIGNAL_MAP[s.strip().lower()] for s in signals]

    # Always capture current and voltage for power calculation
    need = set(resolved)
    if "current" in resolved or "voltage" in resolved:
        need.update(["current", "voltage"])
    fetch = list(need)

    with Driver() as jsdrv:
        jsdrv.log_level = "WARNING"
        device_path = resolve_device(jsdrv, serial)
        configure_device(jsdrv, device_path, frequency)
        data = _read(jsdrv, device_path, fetch, duration)
        jsdrv.close(device_path)

    i = data.get("current", np.array([]))
    v = data.get("voltage", np.array([]))
    p = i * v if len(i) and len(v) else np.array([])

    def _stats(arr, key_prefix):
        finite = arr[np.isfinite(arr)] if len(arr) else arr
        if not len(finite):
            return {f"{key_prefix}_mean": None, f"{key_prefix}_min": None,
                    f"{key_prefix}_max": None, f"{key_prefix}_std": None}
        return {
            f"{key_prefix}_mean": float(np.mean(finite, dtype=np.float64)),
            f"{key_prefix}_min": float(np.min(finite)),
            f"{key_prefix}_max": float(np.max(finite)),
            f"{key_prefix}_std": float(np.std(finite, dtype=np.float64)),
        }

    sample_rate = 0
    for s in fetch:
        if s in ("current", "voltage") and "sample_rate" in (data.get(s) or {}):
            break
    # retrieve sample_rate from the state; easier to just compute from array length
    sample_count = len(i) if len(i) else len(v)
    sample_rate = int(round(sample_count / duration)) if duration > 0 else 0

    result: dict = {
        "device_path": device_path,
        "duration_s": duration,
        "sample_rate_hz": sample_rate,
        "samples": sample_count,
    }
    result.update(_stats(i, "current_A"))
    result.update(_stats(v, "voltage_V"))

    p_mean = result.get("current_A_mean")
    v_mean = result.get("voltage_V_mean")
    if p_mean is not None and v_mean is not None:
        p_mean_w = float(np.mean(p[np.isfinite(p)], dtype=np.float64)) if len(p) else p_mean * v_mean
        result["power_mean_W"] = p_mean_w
        result["energy_J"] = p_mean_w * duration

    return result
