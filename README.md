# jsauto

CLI and Python library for automating [Joulescope](https://www.joulescope.com/) JS220/JS110 power measurements. Designed for use by Claude agents and other automation scripts.

## Install

```
pip install jsauto
```

Or from source (editable, for development):

```
git clone <repo>
cd joulescope-automation
pip install -e ".[dev]"
```

## Prerequisites

Joulescopes require udev rules for non-root USB access on Linux:
https://github.com/jetperch/joulescope_driver#linux-udev-rules

## Commands

### list

```
jsauto list [--pretty]
```

Returns connected Joulescopes. Exit code 3 if none found.

```json
[{"device_path": "u/js220/000123", "model": "js220", "serial": "000123"}]
```

### measure

```
jsauto measure --duration <s> [--frequency <Hz>] [--signals current,voltage] [--serial <SN>] [--pretty]
```

Short blocking read (duration must fit in RAM; a few minutes at 1 MHz is fine).

```json
{
  "device_path": "u/js220/000123",
  "duration_s": 5.0,
  "sample_rate_hz": 1000000,
  "samples": 5000000,
  "current_A_mean": 0.0123,
  "current_A_min": 0.0001,
  "current_A_max": 0.498,
  "current_A_std": 0.034,
  "voltage_V_mean": 3.302,
  "power_mean_W": 0.0406,
  "energy_J": 0.203
}
```

### capture

```
jsauto capture --duration <s> [--output <path.jls>] [--frequency <Hz>] [--signals current,voltage] [--serial <SN>] [--pretty]
```

Records a JLS v2 file. Default output: `./captures/<timestamp>_<serial>.jls` relative to the current working directory.

```json
{"file": "/abs/path/to/captures/20260502_154645_000123.jls", "duration_s": 60.0, "size_bytes": 480123456}
```

### analyze

```
jsauto analyze <jls> [--window start:end] [--buckets N] [--threshold <A>] [--samples-csv <path>] [--plot <path>] [--pretty]
```

Analyzes a JLS file. All statistics are for the specified `--window` (seconds) or the whole file.

**Typical two-pass transient workflow (e.g. wifi TX peaks):**

```bash
# 1. Record
jsauto capture --duration 60

# 2. Overview: scan bucket i_max_A values for peaks
jsauto analyze captures/<file>.jls --buckets 1000

# 3. Event list once threshold is known
jsauto analyze captures/<file>.jls --threshold 50e-3

# 4. Drill into a specific event
jsauto analyze captures/<file>.jls --window 12.35:12.45 --buckets 500 --samples-csv /tmp/peak.csv
```

Output always includes `overall` and `buckets`. `events` is added when `--threshold` is given.

### install-skill

```
jsauto install-skill [--target-dir <path>]
```

Installs the bundled Claude Code skill to `~/.claude/skills/joulescope/SKILL.md` (default). After running this, any Claude Code session on the machine can use the `joulescope` skill to drive measurements automatically. Restart Claude Code to pick it up.

## Exit codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | General error |
| 2 | Multiple devices found; use `--serial` |
| 3 | No device found (check udev rules or USB connection) |

## Python API

All subcommand logic is also importable:

```python
from js_automation.measure import run_measure
from js_automation.capture import run_capture
from js_automation.analyze import run_analyze

stats = run_measure(duration=5.0)
result = run_capture(duration=60.0)
analysis = run_analyze("captures/run.jls", bucket_count=1000, threshold=0.05)
```

## Running tests (hardware-free)

```
python -m pytest tests/
```
