# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Setup

```
pip install -e ".[dev]"    # installs jsauto CLI + pytest
python -m pytest tests/    # hardware-free smoke tests
```

After cloning/installing for the first time, install the Claude Code skill:
```
jsauto install-skill
```

## Architecture

`pyjoulescope_driver` is the sole driver library (the older `joulescope` high-level package is installed in the dev venv but not used). JLS files are read back with `pyjls`.

- `src/js_automation/device.py` — device enumeration, `resolve_device()`, `configure_device()`. All hardware access starts here.
- `src/js_automation/measure.py` — short in-RAM blocking read using Driver pub/sub. The `_read()` function mirrors the pattern in `third_party/pyjoulescope_examples/bin/read_by_pyjoulescope_driver.py:102`.
- `src/js_automation/capture.py` — JLS recording via `pyjoulescope_driver.entry_points.record.on_cmd()`. Builds a `types.SimpleNamespace` to call the entry point directly. Default output goes to `./captures/` relative to CWD (not the package install dir).
- `src/js_automation/analyze.py` — JLS readback using `pyjls.Reader.fsr_statistics()`. The JLS summary tree makes bucketed reads fast even on multi-hour files. `pyjls.SummaryFSR` enum indexes columns: MEAN=0, STD=1, MIN=2, MAX=3, COUNT=4.
- `src/js_automation/skill.py` — `install_skill()` copies the bundled `data/SKILL.md` to `~/.claude/skills/joulescope/`.
- `src/js_automation/cli.py` — argparse dispatcher; all subcommands emit JSON to stdout.
- `src/js_automation/data/SKILL.md` — bundled Claude Code skill (package data, included in the wheel).

## Important constraints

- JS220 and JS110 use different topic names for current/voltage range mode. `configure_device()` already branches on them; keep that branch when touching device config.
- `fsr_statistics()` returns shape `(N, 5)` where columns are `SummaryFSR.MEAN/STD/MIN/MAX/COUNT` (0–4).
- `_read()` in `measure.py` pre-allocates a numpy buffer sized `(duration + 1) * sample_rate + 1_000_000`. Don't shrink this — the device may deliver samples slightly past the target duration before the stop condition fires.
- Captures default to `./captures/<timestamp>_<serial>.jls` relative to CWD, not relative to the package installation directory.
- The bundled `data/SKILL.md` uses plain `jsauto` (not an absolute path). Keep it portable.

## Common pitfalls

- **No device found (exit 3)**: Joulescopes need udev rules on Linux. Check `jsauto list`; if empty but `lsusb` shows the device, udev rules are missing.
- **Multiple devices (exit 2)**: pass `--serial <SN>` to disambiguate. SN is the last path component of `device_path` (e.g. `000123`).
- **Power signal**: power = I×V is computed automatically whenever both current and voltage are captured. Prefer capturing `current,voltage` and letting the code multiply rather than requesting the `power` signal explicitly.
- **Skill not available after install-skill**: Claude Code must be restarted (or skills reloaded) to pick up a newly installed skill.
