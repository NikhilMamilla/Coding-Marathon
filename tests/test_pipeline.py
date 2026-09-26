"""Unit tests covering every reason code (sections 17.1/17.2), every
anomaly rule (section 10), and the duplicate/out-of-order edge cases.

Run with: python -m pytest tests/ -v   (from the project root, after
adding src/ to PYTHONPATH -- see conftest.py)
"""
import pytest
from models import RawMachineRecord, RawEventRecord, MachineRecord
from parsing import parseMachineRecord, parseEventRecord
from validation import validateMachine, validateEvent, build_duplicate_id_set
from anomaly import detectAnomalies
from models import EventRecord


def machine(**overrides):
    base = dict(machine_id=1, machine_type="Cutting", minimum_temperature=10.0,
                maximum_temperature=50.0, maximum_vibration=5.0, location="LineA")
    base.update(overrides)
    return RawMachineRecord(**base)


def event(**overrides):
    base = dict(event_id=1, machine_id=1, timestamp=0, status="RUNNING",
                temperature=20.0, vibration=1.0, units_produced=10, defect_count=0)
    base.update(overrides)
    return RawEventRecord(**base)


VALID_MACHINES = {1: MachineRecord(1, "Cutting", 10.0, 50.0, 5.0, "LineA")}


# --- parseMachineRecord / parseEventRecord -------------------------------

def test_parse_machine_wrong_field_count_is_incomplete():
    r = parseMachineRecord("1,Cutting,10.0,50.0,5.0", 2)
    assert not r.success and r.reason_code == "INCOMPLETE_MACHINE_RECORD"


def test_parse_event_wrong_field_count_is_incomplete():
    r = parseEventRecord("1,1,0,RUNNING,20.0,1.0,10", 2)
    assert not r.success and r.reason_code == "INCOMPLETE_EVENT_RECORD"


def test_parse_strips_whitespace():
    r = parseMachineRecord(" 1 , Cutting , 10.0 , 50.0 , 5.0 , LineA ", 2)
    assert r.success and r.machine.machine_type == "Cutting" and r.machine.location == "LineA"


def test_parse_non_numeric_becomes_none_not_error():
    r = parseMachineRecord("abc,Cutting,10.0,50.0,5.0,LineA", 2)
    assert r.success and r.machine.machine_id is None


# --- validateMachine: section 18.1 priority order -------------------------

@pytest.mark.parametrize("mid", [0, -5, None])
def test_invalid_machine_id(mid):
    assert validateMachine(machine(machine_id=mid)).reason_code == "INVALID_MACHINE_ID"


def test_duplicate_machine_id_beats_later_checks():
    m = machine(machine_type="")  # would also fail MISSING_MACHINE_TYPE
    assert validateMachine(m, is_duplicate=True).reason_code == "DUPLICATE_MACHINE_ID"


def test_missing_machine_type():
    assert validateMachine(machine(machine_type="")).reason_code == "MISSING_MACHINE_TYPE"


@pytest.mark.parametrize("lo,hi", [(None, 50.0), (10.0, None), (50.0, 10.0), (30.0, 30.0)])
def test_invalid_temperature_limits(lo, hi):
    r = validateMachine(machine(minimum_temperature=lo, maximum_temperature=hi))
    assert r.reason_code == "INVALID_TEMPERATURE_LIMITS"


@pytest.mark.parametrize("vib", [None, 0, -1])
def test_invalid_vibration_limit(vib):
    assert validateMachine(machine(maximum_vibration=vib)).reason_code == "INVALID_VIBRATION_LIMIT"


def test_missing_location():
    assert validateMachine(machine(location="")).reason_code == "MISSING_LOCATION"


def test_valid_machine_passes():
    assert validateMachine(machine()).valid


# --- validateEvent: section 18.2 priority order ---------------------------

@pytest.mark.parametrize("eid", [0, -1, None])
def test_invalid_event_id(eid):
    assert validateEvent(event(event_id=eid), VALID_MACHINES).reason_code == "INVALID_EVENT_ID"


def test_duplicate_event_id_beats_later_checks():
    e = event(status="ACTIVE")  # would also fail INVALID_STATUS
    assert validateEvent(e, VALID_MACHINES, is_duplicate=True).reason_code == "DUPLICATE_EVENT_ID"


@pytest.mark.parametrize("mid", [0, -1, None])
def test_invalid_machine_id_on_event(mid):
    assert validateEvent(event(machine_id=mid), VALID_MACHINES).reason_code == "INVALID_MACHINE_ID"


def test_unknown_machine_id():
    assert validateEvent(event(machine_id=999), VALID_MACHINES).reason_code == "UNKNOWN_MACHINE_ID"


@pytest.mark.parametrize("ts", [None, -1])
def test_invalid_timestamp(ts):
    assert validateEvent(event(timestamp=ts), VALID_MACHINES).reason_code == "INVALID_TIMESTAMP"


def test_out_of_order_timestamp_sits_before_status_check():
    e = event(timestamp=5, status="ACTIVE")  # would also fail INVALID_STATUS
    r = validateEvent(e, VALID_MACHINES, previous_timestamp=10)
    assert r.reason_code == "OUT_OF_ORDER_TIMESTAMP"


def test_equal_timestamp_is_not_out_of_order():
    r = validateEvent(event(timestamp=10), VALID_MACHINES, previous_timestamp=10)
    assert r.valid


def test_invalid_status():
    assert validateEvent(event(status="ACTIVE"), VALID_MACHINES).reason_code == "INVALID_STATUS"


def test_invalid_temperature():
    assert validateEvent(event(temperature=None), VALID_MACHINES).reason_code == "INVALID_TEMPERATURE"


@pytest.mark.parametrize("vib", [None, -1])
def test_invalid_vibration(vib):
    assert validateEvent(event(vibration=vib), VALID_MACHINES).reason_code == "INVALID_VIBRATION"


@pytest.mark.parametrize("units", [None, -1])
def test_invalid_production_count(units):
    assert validateEvent(event(units_produced=units), VALID_MACHINES).reason_code == "INVALID_PRODUCTION_COUNT"


@pytest.mark.parametrize("defects", [None, -1, 999])
def test_invalid_defect_count(defects):
    assert validateEvent(event(defect_count=defects, units_produced=10), VALID_MACHINES).reason_code == "INVALID_DEFECT_COUNT"


def test_defect_count_equal_to_units_is_valid():
    assert validateEvent(event(units_produced=10, defect_count=10), VALID_MACHINES).valid


def test_valid_event_passes():
    assert validateEvent(event(), VALID_MACHINES).valid


# --- duplicate detection: far apart, all occurrences flagged --------------

def test_duplicate_ids_far_apart_all_flagged():
    ids = [1, 2, 3, None, -1, 1, 4, 1]
    dup = build_duplicate_id_set(ids)
    assert dup == {1}


def test_no_false_duplicate_for_invalid_ids():
    dup = build_duplicate_id_set([0, -1, None, 0, -1])
    assert dup == set()


# --- detectAnomalies: section 10, boundaries are not anomalies -----------

M = MachineRecord(1, "Cutting", 20.0, 80.0, 6.0, "LineA")


@pytest.mark.parametrize("temp,vib,expected_codes", [
    (20.0, 6.0, []),                                    # both at boundary -> no anomaly
    (19.9, 3.0, ["LOW_TEMPERATURE"]),
    (80.1, 3.0, ["HIGH_TEMPERATURE"]),
    (50.0, 6.1, ["HIGH_VIBRATION"]),
    (85.0, 7.0, ["HIGH_TEMPERATURE", "HIGH_VIBRATION"]),  # order: temperature before vibration
    (10.0, 7.0, ["LOW_TEMPERATURE", "HIGH_VIBRATION"]),
])
def test_anomaly_boundaries_and_ordering(temp, vib, expected_codes):
    e = EventRecord(1, 1, 0, "RUNNING", temp, vib, 10, 0)
    result = detectAnomalies(e, M)
    assert [a.anomaly_code for a in result.anomalies] == expected_codes


def test_anomaly_never_both_low_and_high_temperature():
    # min < max always (enforced by validateMachine), so this is structurally impossible;
    # documents the invariant detectAnomalies relies on.
    assert M.minimum_temperature < M.maximum_temperature
