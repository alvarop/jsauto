"""jsauto command-line interface."""

import argparse
import json
import sys


def _print_json(data, pretty: bool):
    indent = 2 if pretty else None
    print(json.dumps(data, indent=indent))


def _add_common(p: argparse.ArgumentParser):
    p.add_argument("--serial", help="Serial number of the Joulescope to use.")
    p.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")


def main():
    parser = argparse.ArgumentParser(
        prog="jsauto",
        description="Joulescope automation toolkit.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # list
    p_list = sub.add_parser("list", help="List connected Joulescopes.")
    p_list.add_argument("--pretty", action="store_true")

    # measure
    p_meas = sub.add_parser("measure", help="Short blocking read; returns statistics.")
    _add_common(p_meas)
    p_meas.add_argument("--duration", "-d", type=float, default=1.0,
                        help="Capture duration in seconds (default: 1.0).")
    p_meas.add_argument("--frequency", "-f", type=int,
                        help="Sampling frequency in Hz.")
    p_meas.add_argument("--signals", default="current,voltage",
                        help="Comma-separated signals: current,voltage,power (default: current,voltage).")

    # capture
    p_cap = sub.add_parser("capture", help="Record a JLS file.")
    _add_common(p_cap)
    p_cap.add_argument("--duration", "-d", type=float, required=True,
                       help="Capture duration in seconds.")
    p_cap.add_argument("--output", "-o",
                       help="Output JLS file path (default: captures/<timestamp>_<serial>.jls).")
    p_cap.add_argument("--frequency", "-f", type=int,
                       help="Sampling frequency in Hz.")
    p_cap.add_argument("--signals", default="current,voltage",
                       help="Comma-separated signals (default: current,voltage).")

    # install-skill
    p_skill = sub.add_parser(
        "install-skill",
        help="Install the Claude Code skill to ~/.claude/skills/joulescope/.",
    )
    p_skill.add_argument(
        "--target-dir",
        default=None,
        help="Override skill install directory (default: ~/.claude/skills/joulescope).",
    )
    p_skill.add_argument(
        "--link",
        action="store_true",
        help="Symlink instead of copy (stays in sync with the package source; useful for developers).",
    )

    # analyze
    p_ana = sub.add_parser("analyze", help="Analyze a JLS file.")
    p_ana.add_argument("jls", help="Path to the JLS file.")
    p_ana.add_argument("--window", help="Time window as start:end in seconds, e.g. 12.35:12.45.")
    p_ana.add_argument("--buckets", type=int, default=500,
                       help="Number of summary buckets (default: 500).")
    p_ana.add_argument("--threshold", type=float,
                       help="Current threshold in amps for event detection.")
    p_ana.add_argument("--samples-csv", dest="samples_csv",
                       help="Export raw samples as CSV to this path.")
    p_ana.add_argument("--plot", help="Save a current-vs-time PNG to this path.")
    p_ana.add_argument("--pretty", action="store_true")

    args = parser.parse_args()

    if args.command == "install-skill":
        from js_automation.skill import install_skill
        install_skill(args.target_dir, link=args.link)
        return

    elif args.command == "list":
        from js_automation.device import list_devices
        result = list_devices()
        _print_json(result, args.pretty)

    elif args.command == "measure":
        from js_automation.measure import run_measure
        result = run_measure(
            duration=args.duration,
            frequency=args.frequency,
            signals=args.signals.split(","),
            serial=args.serial,
        )
        _print_json(result, args.pretty)

    elif args.command == "capture":
        from js_automation.capture import run_capture
        result = run_capture(
            duration=args.duration,
            output=args.output,
            frequency=args.frequency,
            signals=args.signals.split(","),
            serial=args.serial,
        )
        _print_json(result, args.pretty)

    elif args.command == "analyze":
        from js_automation.analyze import run_analyze
        window = None
        if args.window:
            parts = args.window.split(":")
            if len(parts) != 2:
                print("--window must be start:end in seconds", file=sys.stderr)
                sys.exit(1)
            window = (float(parts[0]), float(parts[1]))
        result = run_analyze(
            jls_path=args.jls,
            window=window,
            bucket_count=args.buckets,
            threshold=args.threshold,
            samples_csv=args.samples_csv,
            plot_path=args.plot,
        )
        _print_json(result, args.pretty)
