"""Entry point for the Industrial Equipment Event Log Analysis and
Reporting System.

Usage:
    python main.py [machine_master.csv] [machine_events.csv] [output_dir]

All three arguments are optional; they default to machine_master.csv
and machine_events.csv in the current directory, and the current
directory for output.
"""

import os
import sys

from processing import run_pipeline
from reporting import (
    write_machine_summary,
    write_anomalies,
    write_rejected_records,
    print_console_summary,
)


def _check_readable(path: str) -> bool:
    try:
        with open(path, "r"):
            return True
    except OSError as exc:
        print(f"Error: unable to open input file '{path}': {exc.strerror}", file=sys.stderr)
        return False


def main(argv) -> int:
    machine_master_path = argv[1] if len(argv) > 1 else "machine_master.csv"
    machine_events_path = argv[2] if len(argv) > 2 else "machine_events.csv"
    output_dir = argv[3] if len(argv) > 3 else "."

    if not _check_readable(machine_master_path):
        return 1
    if not _check_readable(machine_events_path):
        return 1

    os.makedirs(output_dir, exist_ok=True)

    machine_order, stats, anomalies, rejected_records, summary = run_pipeline(
        machine_master_path, machine_events_path
    )

    write_machine_summary(os.path.join(output_dir, "machine_summary.csv"), machine_order, stats)
    write_anomalies(os.path.join(output_dir, "anomalies.csv"), anomalies)
    write_rejected_records(os.path.join(output_dir, "rejected_records.csv"), rejected_records)

    print_console_summary(summary)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
