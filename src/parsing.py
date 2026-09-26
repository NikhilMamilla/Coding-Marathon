"""CSV record parsing.

Responsible only for structural parsing: splitting a CSV row into
fields, trimming whitespace, and converting individual fields to their
expected type where possible. Business-rule validation (ranges,
required-value checks, uniqueness) is intentionally left to the
validation module -- parsing never rejects a record for being
semantically invalid, only for being structurally malformed (wrong
number of columns).
"""

from typing import Optional

from models import MachineParseResult, RawMachineRecord, EventParseResult, RawEventRecord

MACHINE_FIELD_COUNT = 6
EVENT_FIELD_COUNT = 8


def _safe_int(text: str) -> Optional[int]:
    try:
        return int(text)
    except (ValueError, TypeError):
        return None


def _safe_float(text: str) -> Optional[float]:
    try:
        return float(text)
    except (ValueError, TypeError):
        return None


def parseMachineRecord(csvRow: str, lineNumber: int) -> MachineParseResult:
    """Parse one physical row of machine_master.csv."""
    fields = [f.strip() for f in csvRow.split(",")]

    if len(fields) != MACHINE_FIELD_COUNT:
        return MachineParseResult(
            success=False,
            machine=None,
            machine_id=None,
            line_number=lineNumber,
            reason_code="INCOMPLETE_MACHINE_RECORD",
        )

    machine_id = _safe_int(fields[0])
    machine_type = fields[1]
    minimum_temperature = _safe_float(fields[2])
    maximum_temperature = _safe_float(fields[3])
    maximum_vibration = _safe_float(fields[4])
    location = fields[5]

    raw = RawMachineRecord(
        machine_id=machine_id,
        machine_type=machine_type,
        minimum_temperature=minimum_temperature,
        maximum_temperature=maximum_temperature,
        maximum_vibration=maximum_vibration,
        location=location,
    )

    return MachineParseResult(
        success=True,
        machine=raw,
        machine_id=machine_id,
        line_number=lineNumber,
        reason_code=None,
    )


def parseEventRecord(csvRow: str, lineNumber: int) -> EventParseResult:
    """Parse one physical row of machine_events.csv."""
    fields = [f.strip() for f in csvRow.split(",")]

    if len(fields) != EVENT_FIELD_COUNT:
        return EventParseResult(
            success=False,
            event=None,
            event_id=None,
            line_number=lineNumber,
            reason_code="INCOMPLETE_EVENT_RECORD",
        )

    event_id = _safe_int(fields[0])
    machine_id = _safe_int(fields[1])
    timestamp = _safe_int(fields[2])
    status = fields[3]
    temperature = _safe_float(fields[4])
    vibration = _safe_float(fields[5])
    units_produced = _safe_int(fields[6])
    defect_count = _safe_int(fields[7])

    raw = RawEventRecord(
        event_id=event_id,
        machine_id=machine_id,
        timestamp=timestamp,
        status=status,
        temperature=temperature,
        vibration=vibration,
        units_produced=units_produced,
        defect_count=defect_count,
    )

    return EventParseResult(
        success=True,
        event=raw,
        event_id=event_id,
        line_number=lineNumber,
        reason_code=None,
    )
