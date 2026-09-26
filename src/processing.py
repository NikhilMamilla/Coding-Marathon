"""Pipeline orchestration: reading input files, running validation and
duplicate detection, sequential event processing, anomaly detection,
and machine-wise statistics accumulation.

Each input file is read from disk exactly once into a list of parse
results; duplicate-ID detection and the main validation pass then both
operate on that in-memory list, so large files (hundreds of thousands
of event rows) are streamed off disk a single time rather than being
re-opened per pass.
"""

from typing import Dict, List, Tuple

from models import (
    MachineRecord,
    EventRecord,
    MachineStats,
    AnomalyRecord,
    RejectedRecord,
    ProcessingSummary,
)
from parsing import parseMachineRecord, parseEventRecord
from validation import validateMachine, validateEvent, build_duplicate_id_set
from anomaly import detectAnomalies

MACHINE_MASTER_FILE = "machine_master.csv"
MACHINE_EVENTS_FILE = "machine_events.csv"


def iter_data_rows(path: str):
    """Yield (physical_line_number, line_text) for every non-header,
    non-blank line of a CSV file. Header rows and blank lines are
    skipped and not counted, per the file-handling requirements.
    """
    with open(path, "r", newline="") as handle:
        line_number = 0
        for raw_line in handle:
            line_number += 1
            if line_number == 1:
                continue  # header
            line = raw_line.rstrip("\r\n")
            if line.strip() == "":
                continue  # blank line
            yield line_number, line


def load_machines(path: str) -> Tuple[Dict[int, MachineRecord], List[int], List[RejectedRecord], int]:
    """Read and validate machine_master.csv.

    Returns the valid-unique-machine lookup (keyed by machine_id), the
    machine IDs in file order (for machine_summary.csv row ordering),
    the rejected machine-master records (in file order), and the total
    number of data rows read.
    """
    parse_results = [parseMachineRecord(line, ln) for ln, line in iter_data_rows(path)]
    total_count = len(parse_results)

    duplicate_ids = build_duplicate_id_set(pr.machine_id for pr in parse_results)

    valid_machines: Dict[int, MachineRecord] = {}
    machine_order: List[int] = []
    rejected: List[RejectedRecord] = []

    for pr in parse_results:
        if not pr.success:
            rejected.append(RejectedRecord(MACHINE_MASTER_FILE, pr.line_number, "UNKNOWN", pr.reason_code))
            continue

        record_id = str(pr.machine_id) if pr.machine_id is not None else "UNKNOWN"
        is_duplicate = pr.machine_id in duplicate_ids if pr.machine_id is not None else False
        result = validateMachine(pr.machine, is_duplicate)

        if not result.valid:
            rejected.append(RejectedRecord(MACHINE_MASTER_FILE, pr.line_number, record_id, result.reason_code))
            continue

        raw = pr.machine
        machine = MachineRecord(
            machine_id=raw.machine_id,
            machine_type=raw.machine_type,
            minimum_temperature=raw.minimum_temperature,
            maximum_temperature=raw.maximum_temperature,
            maximum_vibration=raw.maximum_vibration,
            location=raw.location,
        )
        valid_machines[machine.machine_id] = machine
        machine_order.append(machine.machine_id)

    return valid_machines, machine_order, rejected, total_count


def process_events(
    path: str, valid_machines: Dict[int, MachineRecord]
) -> Tuple[Dict[int, MachineStats], List[RejectedRecord], List[AnomalyRecord], int, int, int]:
    """Read, validate, and sequentially process machine_events.csv.

    Returns per-machine statistics, rejected event records (file
    order), accepted anomaly records (acceptance order), the total
    number of data rows read, and the count of accepted events that
    contained at least one temperature / vibration anomaly.
    """
    parse_results = [parseEventRecord(line, ln) for ln, line in iter_data_rows(path)]
    total_count = len(parse_results)

    duplicate_ids = build_duplicate_id_set(pr.event_id for pr in parse_results)

    stats: Dict[int, MachineStats] = {mid: MachineStats(machine=m) for mid, m in valid_machines.items()}
    last_accepted_timestamp: Dict[int, int] = {}
    rejected: List[RejectedRecord] = []
    anomalies: List[AnomalyRecord] = []
    temperature_anomaly_events = 0
    vibration_anomaly_events = 0

    for pr in parse_results:
        if not pr.success:
            rejected.append(RejectedRecord(MACHINE_EVENTS_FILE, pr.line_number, "UNKNOWN", pr.reason_code))
            continue

        raw = pr.event
        record_id = str(pr.event_id) if pr.event_id is not None else "UNKNOWN"
        is_duplicate = pr.event_id in duplicate_ids if pr.event_id is not None else False
        previous_timestamp = (
            last_accepted_timestamp.get(raw.machine_id) if raw.machine_id in valid_machines else None
        )

        result = validateEvent(raw, valid_machines, is_duplicate, previous_timestamp)
        if not result.valid:
            rejected.append(RejectedRecord(MACHINE_EVENTS_FILE, pr.line_number, record_id, result.reason_code))
            continue

        machine = valid_machines[raw.machine_id]
        event = EventRecord(
            event_id=raw.event_id,
            machine_id=raw.machine_id,
            timestamp=raw.timestamp,
            status=raw.status,
            temperature=raw.temperature,
            vibration=raw.vibration,
            units_produced=raw.units_produced,
            defect_count=raw.defect_count,
        )

        machine_stats = stats[machine.machine_id]
        machine_stats.record_accepted_event(event)
        last_accepted_timestamp[machine.machine_id] = event.timestamp

        anomaly_result = detectAnomalies(event, machine)
        machine_stats.record_anomalies(anomaly_result)
        if anomaly_result.has_temperature_anomaly:
            temperature_anomaly_events += 1
        if anomaly_result.has_vibration_anomaly:
            vibration_anomaly_events += 1
        anomalies.extend(anomaly_result.anomalies)

    return stats, rejected, anomalies, total_count, temperature_anomaly_events, vibration_anomaly_events


def run_pipeline(machine_master_path: str, machine_events_path: str):
    """Run the full pipeline and return everything needed for reporting."""
    valid_machines, machine_order, rejected_machines, total_machine_records = load_machines(machine_master_path)

    (
        stats,
        rejected_events,
        anomalies,
        total_event_records,
        temperature_anomaly_events,
        vibration_anomaly_events,
    ) = process_events(machine_events_path, valid_machines)

    accepted_event_records = sum(s.accepted_event_count for s in stats.values())

    summary = ProcessingSummary(
        total_machine_records=total_machine_records,
        valid_unique_machines=len(valid_machines),
        rejected_machine_records=len(rejected_machines),
        total_event_records=total_event_records,
        accepted_event_records=accepted_event_records,
        rejected_event_records=len(rejected_events),
        temperature_anomaly_events=temperature_anomaly_events,
        vibration_anomaly_events=vibration_anomaly_events,
        total_anomaly_records=len(anomalies),
    )

    rejected_records = rejected_machines + rejected_events

    return machine_order, stats, anomalies, rejected_records, summary
