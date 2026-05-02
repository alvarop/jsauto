# Joulescope Power Measurement

Use this skill whenever the user wants to measure power consumption, current draw, voltage, or energy from a device under test connected to a Joulescope JS220 or JS110.

The `jsauto` command is provided by the `jsauto` package. Invoke it as `jsauto` if it is on PATH (user pip install or activated venv), or with the full path to the environment's bin dir (e.g., `~/.local/bin/jsauto` or `/path/to/venv/bin/jsauto`). Run `which jsauto` or `python -m js_automation.cli --help` to locate it.

## When to use which subcommand

| Goal | Subcommand |
|------|-----------|
| Quick average current/power/energy | `measure --duration <s>` |
| Record a long session to a file | `capture --duration <s>` |
| Analyze a file for stats or transient peaks | `analyze <file.jls>` |
| Check what Joulescope is connected | `list` |

## Quick reference

```bash
# Average power over 5 seconds
jsauto measure --duration 5 --pretty

# 60-second capture (output auto-named in ./captures/)
jsauto capture --duration 60 --pretty

# Analyze: overview with 1000 buckets
jsauto analyze <file.jls> --buckets 1000 --pretty

# Analyze: detect events above 50 mA
jsauto analyze <file.jls> --threshold 50e-3 --pretty

# Drill into t=12.35–12.45s and export raw samples
jsauto analyze <file.jls> --window 12.35:12.45 --buckets 500 --samples-csv /tmp/peak.csv --pretty
```

## JSON output fields

`measure` returns: `current_A_mean/min/max/std`, `voltage_V_mean`, `power_mean_W`, `energy_J`.

`analyze` returns:
- `overall` — mean/min/max/std for current and voltage; `energy_J`, `power_mean_W`.
- `buckets` — array of `{t_s, i_mean_A, i_min_A, i_max_A, i_std_A}`. Scan `i_max_A` for transient peaks.
- `events` (when `--threshold` given) — `{t_start_s, t_end_s, duration_s, i_peak_A, i_mean_A, charge_C, energy_J}`.

## Troubleshooting

- **Exit 3 / no device found**: Joulescope udev rules missing. Direct user to https://github.com/jetperch/joulescope_driver#linux-udev-rules
- **Exit 2 / multiple devices**: add `--serial <SN>` (run `list` to find serial numbers).
- **Transient events not detected**: first run without `--threshold` and inspect `buckets[].i_max_A` to pick a sensible threshold, then re-run.
