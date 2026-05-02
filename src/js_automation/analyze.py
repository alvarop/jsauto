"""JLS file analysis: overall stats, bucketed waveform, event detection, drill-down."""

import csv
import sys
from typing import Optional

import numpy as np
from pyjls import Reader, SummaryFSR


def _find_signal(r: Reader, name: str):
    for s in r.signals.values():
        if s.name == name and s.signal_id != 0:
            return s
    return None


def _sample_range_for_window(signal, window: tuple[float, float]) -> tuple[int, int]:
    """Convert a (start_s, end_s) window to (start_sample, end_sample) clamped to signal length."""
    t0 = max(0.0, window[0])
    t1 = min(signal.length / signal.sample_rate, window[1])
    s0 = int(t0 * signal.sample_rate)
    s1 = int(t1 * signal.sample_rate)
    s0 = max(0, min(s0, signal.length - 1))
    s1 = max(s0 + 1, min(s1, signal.length))
    return s0, s1


def _compute_overall(r: Reader, signal, s0: int, s1: int) -> dict:
    """Compute overall statistics for current signal over [s0, s1)."""
    length = s1 - s0
    stats = r.fsr_statistics(signal.signal_id, s0, length, 1)[0]
    duration_s = length / signal.sample_rate
    mean_a = float(stats[SummaryFSR.MEAN])
    return {
        "duration_s": round(duration_s, 6),
        "current_mean_A": mean_a,
        "current_min_A": float(stats[SummaryFSR.MIN]),
        "current_max_A": float(stats[SummaryFSR.MAX]),
        "current_std_A": float(stats[SummaryFSR.STD]),
        "energy_J": round(mean_a * duration_s, 9),
    }


def _compute_voltage_overall(r: Reader, signal, s0: int, s1: int) -> dict:
    length = s1 - s0
    stats = r.fsr_statistics(signal.signal_id, s0, length, 1)[0]
    return {
        "voltage_mean_V": float(stats[SummaryFSR.MEAN]),
        "voltage_min_V": float(stats[SummaryFSR.MIN]),
        "voltage_max_V": float(stats[SummaryFSR.MAX]),
        "voltage_std_V": float(stats[SummaryFSR.STD]),
    }


def _compute_buckets(r: Reader, signal, s0: int, s1: int, bucket_count: int) -> list[dict]:
    length = s1 - s0
    actual = min(bucket_count, length)
    incr = max(1, length // actual)
    actual = length // incr
    if actual == 0:
        return []
    data = r.fsr_statistics(signal.signal_id, s0, incr, actual)
    dt = incr / signal.sample_rate
    buckets = []
    for idx in range(actual):
        row = data[idx]
        buckets.append({
            "t_s": round(s0 / signal.sample_rate + idx * dt, 6),
            "i_mean_A": float(row[SummaryFSR.MEAN]),
            "i_min_A": float(row[SummaryFSR.MIN]),
            "i_max_A": float(row[SummaryFSR.MAX]),
            "i_std_A": float(row[SummaryFSR.STD]),
        })
    return buckets


def _detect_events(r: Reader, signal, s0: int, s1: int, threshold: float, buckets: list[dict]) -> list[dict]:
    """Find contiguous runs of buckets where i_mean_A > threshold."""
    if not buckets:
        return []
    above = np.array([b["i_mean_A"] > threshold for b in buckets])
    events = []
    in_event = False
    ev_start = 0
    for idx, val in enumerate(above):
        if val and not in_event:
            in_event = True
            ev_start = idx
        elif not val and in_event:
            in_event = False
            events.append((ev_start, idx - 1))
    if in_event:
        events.append((ev_start, len(buckets) - 1))

    result = []
    for (bi0, bi1) in events:
        t_start = buckets[bi0]["t_s"]
        t_end = buckets[bi1]["t_s"] + (buckets[1]["t_s"] - buckets[0]["t_s"] if len(buckets) > 1 else 0)
        # For peak and energy, read the raw sample range within this event
        si0 = int(t_start * signal.sample_rate)
        si1 = int(t_end * signal.sample_rate)
        si0 = max(s0, min(si0, s1 - 1))
        si1 = max(si0 + 1, min(si1, s1))
        ev_len = si1 - si0
        if ev_len > 0:
            raw = r.fsr(signal.signal_id, si0, ev_len).astype(np.float64)
            finite = raw[np.isfinite(raw)]
            peak = float(np.max(finite)) if len(finite) else float("nan")
            mean = float(np.mean(finite)) if len(finite) else float("nan")
        else:
            peak = float(buckets[bi0]["i_max_A"])
            mean = float(np.mean([b["i_mean_A"] for b in buckets[bi0:bi1 + 1]]))
        duration = t_end - t_start
        result.append({
            "t_start_s": round(t_start, 6),
            "t_end_s": round(t_end, 6),
            "duration_s": round(duration, 6),
            "i_peak_A": round(peak, 9),
            "i_mean_A": round(mean, 9),
            "charge_C": round(mean * duration, 9),
            "energy_J": round(mean * duration * 3.3, 9),  # approximate; exact needs voltage signal
        })
    return result


def _export_samples_csv(r: Reader, i_signal, v_signal, s0: int, s1: int, path: str):
    """Write current, voltage, power CSV for sample range [s0, s1)."""
    length = s1 - s0
    i_data = r.fsr(i_signal.signal_id, s0, length).astype(np.float64)
    v_data = r.fsr(v_signal.signal_id, s0, length).astype(np.float64) if v_signal else np.full(length, float("nan"))
    p_data = i_data * v_data
    dt = 1.0 / i_signal.sample_rate
    t0 = s0 / i_signal.sample_rate
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["time_s", "current_A", "voltage_V", "power_W"])
        for idx in range(length):
            w.writerow([
                round(t0 + idx * dt, 9),
                float(i_data[idx]),
                float(v_data[idx]),
                float(p_data[idx]),
            ])


def run_analyze(
    jls_path: str,
    window: Optional[tuple[float, float]] = None,
    bucket_count: int = 500,
    threshold: Optional[float] = None,
    samples_csv: Optional[str] = None,
    plot_path: Optional[str] = None,
) -> dict:
    r = Reader(jls_path)

    i_signal = _find_signal(r, "current")
    v_signal = _find_signal(r, "voltage")

    if i_signal is None:
        print(f"No 'current' signal found in {jls_path}", file=sys.stderr)
        sys.exit(1)

    if window is not None:
        s0, s1 = _sample_range_for_window(i_signal, window)
    else:
        s0, s1 = 0, i_signal.length

    result: dict = {"file": jls_path, "sample_rate_hz": i_signal.sample_rate}

    overall = _compute_overall(r, i_signal, s0, s1)
    if v_signal:
        overall.update(_compute_voltage_overall(r, v_signal, s0, s1))
        # Improve energy estimate using voltage if available
        p_mean = overall.get("current_mean_A", 0) * overall.get("voltage_mean_V", 0)
        overall["power_mean_W"] = round(p_mean, 9)
        overall["energy_J"] = round(p_mean * overall["duration_s"], 9)
    result["overall"] = overall

    buckets = _compute_buckets(r, i_signal, s0, s1, bucket_count)
    result["buckets"] = buckets

    if threshold is not None:
        result["events"] = {
            "threshold_A": threshold,
            "list": _detect_events(r, i_signal, s0, s1, threshold, buckets),
        }

    if samples_csv:
        _export_samples_csv(r, i_signal, v_signal, s0, s1, samples_csv)
        result["samples_csv"] = samples_csv

    if plot_path:
        _save_plot(buckets, plot_path, overall)
        result["plot"] = plot_path

    return result


def _save_plot(buckets: list[dict], path: str, overall: dict):
    import matplotlib.pyplot as plt
    if not buckets:
        return
    x = [b["t_s"] for b in buckets]
    y = [b["i_mean_A"] for b in buckets]
    fig, ax = plt.subplots()
    ax.plot(x, y)
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Current (A)")
    ax.set_title("Current vs Time")
    ax.grid(True)
    fig.savefig(path)
    plt.close(fig)
