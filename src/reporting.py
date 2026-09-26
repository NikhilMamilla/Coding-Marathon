"""Output-file generation and console summary display."""

import csv
from typing import Dict, List

from models import MachineStats, AnomalyRecord, RejectedRecord, ProcessingSummary

MACHINE_SUMMARY_HEADER = [
    "machine_id", "machine_type", "location", "accepted_event_count",
    "running_event_count", "idle_event_count", "maintenance_event_count",
    "stopped_event_count", "average_temperature", "maximum_vibration",
    "latest_units_produced", "latest_defect_count",
    "temperature_anomaly_count", "vibration_anomaly_count",
]

ANOMALIES_HEADER = [
    "event_id", "machine_id", "timestamp", "anomaly_code", "observed_value", "reference_value",
]

REJECTED_RECORDS_HEADER = [
    "source_file", "line_number", "record_id", "reason_code",
]


def write_machine_summary(path: str, machine_order: List[int], stats: Dict[int, MachineStats]) -> None:
    with open(path, "w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(MACHINE_SUMMARY_HEADER)
        for machine_id in machine_order:
            s = stats[machine_id]
            writer.writerow([
                s.machine.machine_id,
                s.machine.machine_type,
                s.machine.location,
                s.accepted_event_count,
                s.running_event_count,
                s.idle_event_count,
                s.maintenance_event_count,
                s.stopped_event_count,
                f"{s.average_temperature:.2f}",
                f"{s.maximum_vibration:.2f}",
                s.latest_units_produced,
                s.latest_defect_count,
                s.temperature_anomaly_count,
                s.vibration_anomaly_count,
            ])


def write_anomalies(path: str, anomalies: List[AnomalyRecord]) -> None:
    with open(path, "w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(ANOMALIES_HEADER)
        for a in anomalies:
            writer.writerow([
                a.event_id, a.machine_id, a.timestamp, a.anomaly_code,
                a.observed_value, a.reference_value,
            ])


def write_rejected_records(path: str, rejected: List[RejectedRecord]) -> None:
    with open(path, "w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(REJECTED_RECORDS_HEADER)
        for r in rejected:
            writer.writerow([r.source_file, r.line_number, r.record_id, r.reason_code])


def format_console_summary(summary: ProcessingSummary) -> str:
    lines = [
        f"Total machine records: {summary.total_machine_records}",
        f"Valid unique machines: {summary.valid_unique_machines}",
        f"Rejected machine records: {summary.rejected_machine_records}",
        f"Total event records: {summary.total_event_records}",
        f"Accepted event records: {summary.accepted_event_records}",
        f"Rejected event records: {summary.rejected_event_records}",
        f"Temperature anomaly events: {summary.temperature_anomaly_events}",
        f"Vibration anomaly events: {summary.vibration_anomaly_events}",
        f"Total anomaly records: {summary.total_anomaly_records}",
    ]
    return "\n".join(lines)


def print_console_summary(summary: ProcessingSummary) -> None:
    print(format_console_summary(summary))
