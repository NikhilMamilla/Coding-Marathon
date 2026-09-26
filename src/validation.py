"""Business-rule validation and duplicate-detection helpers.

Duplicate-ID detection needs information from every record in the
file (an identifier repeated far apart is still a duplicate), so it
is implemented as a frequency-counting pre-pass shared by both the
machine and event pipelines, per the assignment's guidance that
duplicate detection "may be handled separately" from per-record
validation (sections 14.3 / 14.4 / 16). The counted frequency is then
supplied to validateMachine / validateEvent as a simple boolean flag
so the priority-ordered rule chain stays in one place.

Similarly, the out-of-order timestamp check needs the previously
accepted timestamp for the same machine -- state that only the
sequential event processor maintains -- so it is supplied to
validateEvent as an extra argument rather than being computed inside
the function.
"""

from collections import Counter
from typing import Dict, Iterable, Optional, Tuple

from models import RawMachineRecord, RawEventRecord, ValidationResult, MachineRecord, PERMITTED_STATUSES


def build_duplicate_id_set(ids: Iterable[Optional[int]]) -> set:
    """Return the set of positive-integer ids that occur more than once."""
    counts = Counter(i for i in ids if i is not None and i > 0)
    return {i for i, n in counts.items() if n > 1}


def validateMachine(machineRecord: RawMachineRecord, is_duplicate: bool = False) -> ValidationResult:
    """Apply the machine-master validation priority chain (section 18.1).

    Position 1 (INCOMPLETE_MACHINE_RECORD) is enforced upstream by
    parseMachineRecord, which is the only stage that knows whether the
    row was structurally malformed (wrong column count).
    """
    if machineRecord.machine_id is None or machineRecord.machine_id <= 0:
        return ValidationResult(False, "INVALID_MACHINE_ID")

    if is_duplicate:
        return ValidationResult(False, "DUPLICATE_MACHINE_ID")

    if not machineRecord.machine_type:
        return ValidationResult(False, "MISSING_MACHINE_TYPE")

    if (
        machineRecord.minimum_temperature is None
        or machineRecord.maximum_temperature is None
        or not (machineRecord.minimum_temperature < machineRecord.maximum_temperature)
    ):
        return ValidationResult(False, "INVALID_TEMPERATURE_LIMITS")

    if machineRecord.maximum_vibration is None or machineRecord.maximum_vibration <= 0:
        return ValidationResult(False, "INVALID_VIBRATION_LIMIT")

    if not machineRecord.location:
        return ValidationResult(False, "MISSING_LOCATION")

    return ValidationResult(True)


def validateEvent(
    eventRecord: RawEventRecord,
    validMachines: Dict[int, MachineRecord],
    is_duplicate: bool = False,
    previous_timestamp: Optional[int] = None,
) -> ValidationResult:
    """Apply the machine-event validation priority chain (section 18.2).

    Position 1 (INCOMPLETE_EVENT_RECORD) is enforced upstream by
    parseEventRecord. ``previous_timestamp`` is the timestamp of the
    last *accepted* event for this event's machine, supplied by the
    sequential processor so the OUT_OF_ORDER_TIMESTAMP check can sit at
    its required position (7) between INVALID_TIMESTAMP (6) and
    INVALID_STATUS (8).
    """
    if eventRecord.event_id is None or eventRecord.event_id <= 0:
        return ValidationResult(False, "INVALID_EVENT_ID")

    if is_duplicate:
        return ValidationResult(False, "DUPLICATE_EVENT_ID")

    if eventRecord.machine_id is None or eventRecord.machine_id <= 0:
        return ValidationResult(False, "INVALID_MACHINE_ID")

    if eventRecord.machine_id not in validMachines:
        return ValidationResult(False, "UNKNOWN_MACHINE_ID")

    if eventRecord.timestamp is None or eventRecord.timestamp < 0:
        return ValidationResult(False, "INVALID_TIMESTAMP")

    if previous_timestamp is not None and eventRecord.timestamp < previous_timestamp:
        return ValidationResult(False, "OUT_OF_ORDER_TIMESTAMP")

    if eventRecord.status not in PERMITTED_STATUSES:
        return ValidationResult(False, "INVALID_STATUS")

    if eventRecord.temperature is None:
        return ValidationResult(False, "INVALID_TEMPERATURE")

    if eventRecord.vibration is None or eventRecord.vibration < 0:
        return ValidationResult(False, "INVALID_VIBRATION")

    if eventRecord.units_produced is None or eventRecord.units_produced < 0:
        return ValidationResult(False, "INVALID_PRODUCTION_COUNT")

    if (
        eventRecord.defect_count is None
        or eventRecord.defect_count < 0
        or eventRecord.defect_count > eventRecord.units_produced
    ):
        return ValidationResult(False, "INVALID_DEFECT_COUNT")

    return ValidationResult(True)
